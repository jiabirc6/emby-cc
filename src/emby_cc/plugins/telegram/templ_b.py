"""Template B: /checkin -> wait reply -> captcha"""

from __future__ import annotations
import asyncio
from emby_cc.plugins.telegram.base import TelegramBotCheckin
from emby_cc.utils.logger import get_logger
logger = get_logger("templ_b")

class TemplateBCheckin(TelegramBotCheckin):
    bot_checkin_cmd = ["/checkin"]
    bot_checkin_button = []
    bot_timeout: int = 120

    async def _wait_and_handle(self, entity, app):
        from emby_cc.plugins.base import CheckinResult
        deadline = asyncio.get_event_loop().time() + self.bot_timeout
        while asyncio.get_event_loop().time() < deadline:
            try:
                messages = await app.get_chat_history(entity.id, limit=5)
                for msg in messages:
                    if msg.photo and self.bot_use_captcha:
                        handled = await self._handle_captcha(msg, app, entity)
                        if handled:
                            return handled
                    if msg.text:
                        result = self._check_text_result(msg.text)
                        if result == "success":
                            return CheckinResult(success=True, message=msg.text[:100], bot_name=self.name)
                        if result == "account_fail":
                            return CheckinResult(success=False, message=msg.text[:100], bot_name=self.name)
                        if result == "checked":
                            return CheckinResult(success=True, message=msg.text[:100], bot_name=self.name)
                await asyncio.sleep(3)
            except Exception as e:
                logger.debug(f"wait error: {e}")
                await asyncio.sleep(3)
        return CheckinResult(success=False, message="timeout", bot_name=self.name)
