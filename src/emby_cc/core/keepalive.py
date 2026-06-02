"""保活模块 - Emby 播放模拟"""

from __future__ import annotations

import asyncio
import random
from datetime import datetime, timedelta

from emby_cc.config import AccountConfig
from emby_cc.core.emby_client import EmbyClient
from emby_cc.utils.logger import get_logger

logger = get_logger("keepalive")


class KeepAliveRunner:
    """Emby 账号保活执行器"""

    def __init__(self, account: AccountConfig):
        self.account = account
        self.client = EmbyClient(
            base_url=account.emby_url,
            api_key=account.api_key,
            username=account.username,
            password=account.password,
        )

    async def run_once(self) -> bool:
        """执行一次保活循环"""
        try:
            items = await self.client.get_random_items(limit=20)
            if not items:
                logger.warning(f"[{self.account.name}] 没有可用的媒体项")
                return False

            item = random.choice(items)
            duration = random.randint(
                self.account.keepalive.min_minutes,
                self.account.keepalive.max_minutes,
            )

            item_name = item.get("Name", "Unknown")
            item_type = item.get("Type", "Unknown")
            logger.info(
                f"[{self.account.name}] 开始保活: {item_name} ({item_type}) "
                f"- {duration} 分钟"
            )

            success = await self.client.simulate_playback(
                item_id=item["Id"],
                duration_minutes=duration,
            )

            if success:
                user_id = await self.client.get_user_id()
                await self.client.mark_played(item["Id"], user_id)
                logger.success(
                    f"[{self.account.name}] 保活完成: {item_name} ({duration}min)"
                )
            return success

        except Exception as e:
            logger.error(f"[{self.account.name}] 保活失败: {e}")
            return False

    async def run_loop(self):
        """持续保活循环"""
        interval = self.account.keepalive.interval_hours * 3600
        logger.info(
            f"[{self.account.name}] 保活循环启动，间隔 {self.account.keepalive.interval_hours}h"
        )

        while True:
            try:
                await self.run_once()
            except Exception as e:
                logger.error(f"[{self.account.name}] 保活异常: {e}")

            next_run = datetime.now() + timedelta(seconds=interval)
            logger.info(
                f"[{self.account.name}] 下次保活: {next_run.strftime('%H:%M:%S')}"
            )
            await asyncio.sleep(interval)
