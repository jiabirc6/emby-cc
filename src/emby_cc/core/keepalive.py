"""保活模块 - Emby 慢速流式播放模拟"""

from __future__ import annotations

import asyncio
import random
from datetime import datetime, timedelta

import httpx

from emby_cc.config import AccountConfig
from emby_cc.core.emby_client import EmbyClient
from emby_cc.utils.logger import get_logger
from emby_cc.utils.retry import retry

logger = get_logger("keepalive")

USER_AGENTS = [
    "Yamby/2.1.0 (iOS; 17.4; iPad14,5)",
    "Yamby/2.0.8 (iOS; 17.3.1; iPhone15,2)",
    "Yamby/2.0.5 (Android; 14; Pixel 8 Pro)",
    "Yamby/1.9.2 (macOS; 14.3; Mac14,5)",
    "Yamby/2.1.0 (Android; 13; SM-S918B)",
]


class KeepAliveRunner:
    """Emby 账号保活执行器 - 慢速流式播放"""

    def __init__(self, account: AccountConfig):
        self.account = account
        self.client = EmbyClient(
            base_url=account.emby_url,
            api_key=account.api_key,
            username=account.username,
            password=account.password,
        )

    @retry(max_retries=3, base_delay=5.0)
    async def run_once(self) -> bool:
        """执行一次保活"""
        try:
            await self.client.detect_version()
            user_id = await self.client.get_user_id()

            items = await self.client.get_random_items(limit=20)
            if not items:
                logger.warning(f"[{self.account.name}] 没有可用媒体项")
                return False

            item = random.choice(items)
            item_name = item.get("Name", "Unknown")
            item_type = item.get("Type", "Unknown")
            item_id = item["Id"]

            duration = random.randint(
                self.account.keepalive.min_minutes * 60,
                self.account.keepalive.max_minutes * 60,
            )

            logger.info(
                f"[{self.account.name}] 保活: {item_name} ({item_type}) - {duration // 60}min"
            )

            success = await self._slow_stream(item_id, duration)

            if success:
                logger.success(f"[{self.account.name}] 保活完成: {item_name}")
            return success

        except Exception as e:
            logger.error(f"[{self.account.name}] 保活失败: {e}")
            return False

    async def _slow_stream(self, item_id: str, duration_seconds: int) -> bool:
        """慢速流式播放 - 不会产生大量入站流量"""
        ua = random.choice(USER_AGENTS)
        headers = {"User-Agent": ua, "Accept": "*/*", "Connection": "keep-alive"}
        if self.client.api_key:
            headers["X-Emby-Token"] = self.client.api_key

        stream_url = f"{self.client.base_url}/Videos/{item_id}/stream"

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as http:
                async with http.stream("GET", stream_url, headers=headers) as resp:
                    resp.raise_for_status()
                    elapsed = 0
                    while elapsed < duration_seconds:
                        try:
                            chunk = await asyncio.wait_for(resp.aiter.read(1024), timeout=10)
                            if not chunk:
                                break
                        except asyncio.TimeoutError:
                            pass
                        elapsed += 5
                        await asyncio.sleep(random.uniform(4, 6))
            return True
        except Exception as e:
            logger.error(f"流式播放异常: {e}")
            return False

    async def run_loop(self):
        """持续保活循环"""
        interval = self.account.keepalive.interval_hours * 3600
        logger.info(f"[{self.account.name}] 保活循环启动，间隔 {self.account.keepalive.interval_hours}h")
        while True:
            try:
                await self.run_once()
            except Exception as e:
                logger.error(f"[{self.account.name}] 保活异常: {e}")
            next_run = datetime.now() + timedelta(seconds=interval)
            logger.info(f"[{self.account.name}] 下次保活: {next_run.strftime('%H:%M:%S')}")
            await asyncio.sleep(interval)
