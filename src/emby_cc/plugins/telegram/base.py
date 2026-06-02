"""Telegram Bot 签到插件基类"""

from __future__ import annotations

import asyncio
import random
from typing import Optional

from emby_cc.config import AccountConfig
from emby_cc.plugins.base import CheckinPlugin, CheckinResult
from emby_cc.utils.logger import get_logger

logger = get_logger("tg_checkin")


class TelegramCheckinPlugin(CheckinPlugin):
    """Telegram Bot 签到插件基类

    子类只需实现 send_checkin_message 方法。
    通过 Telethon 连接 Telegram 并发送签到消息。
    """

    bot_username: str = ""
    bot_name: str = ""

    async def checkin(self, account: AccountConfig) -> CheckinResult:
        if not account.telegram_bot_token:
            return CheckinResult(
                success=False,
                message="未配置 Telegram Bot Token",
                bot_name=self.name,
            )

        if not self.bot_username:
            return CheckinResult(
                success=False,
                message="未配置 bot_username",
                bot_name=self.name,
            )

        try:
            from telethon import TelegramClient

            client = TelegramClient(
                f"emby_cc_{account.name}",
                api_id=0,
                api_hash="",
            )

            # 使用 Bot Token 连接
            await client.start(bot_token=account.telegram_bot_token)

            try:
                success = await self.send_checkin_message(client)
                if success:
                    return CheckinResult(
                        success=True,
                        message=f"{self.bot_name} 签到成功",
                        bot_name=self.name,
                    )
                else:
                    return CheckinResult(
                        success=False,
                        message=f"{self.bot_name} 签到失败",
                        bot_name=self.name,
                    )
            finally:
                await client.disconnect()

        except ImportError:
            return CheckinResult(
                success=False,
                message="未安装 telethon: pip install telethon",
                bot_name=self.name,
            )
        except Exception as e:
            return CheckinResult(
                success=False,
                message=f"{self.bot_name} 签到异常: {e}",
                bot_name=self.name,
            )

    async def send_checkin_message(self, client) -> bool:
        """发送签到消息 - 子类必须实现

        默认实现：向 bot 发送 /checkin 命令
        """
        try:
            entity = await client.get_entity(self.bot_username)
            await client.send_message(entity, "/checkin")
            await asyncio.sleep(random.uniform(2, 5))
            messages = await client.get_messages(entity, limit=1)
            if messages:
                return "成功" in messages[0].text or "已签到" in messages[0].text
            return False
        except Exception as e:
            logger.error(f"发送签到消息失败: {e}")
            return False
