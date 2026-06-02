"""Template A: /start -> click checkin button"""

from __future__ import annotations
import asyncio
from typing import Union
from emby_cc.plugins.telegram.base import TelegramBotCheckin
from emby_cc.utils.logger import get_logger
logger = get_logger("templ_a")

class TemplateACheckin(TelegramBotCheckin):
    bot_checkin_cmd = ["/start"]
    bot_checkin_button: Union[str, list[str]] = ["签到", "簽到"]
    use_button_answer: bool = True

    async def _wait_and_handle(self, entity, app):
        from emby_cc.plugins.base import CheckinResult
        deadline = asyncio.get_event_loop().time() + self.bot_timeout
        while asyncio.get_event_loop().time() < deadline:
            try:
                messages = await app.get_chat_history(entity.id, limit=5)
                for msg in messages:
                    if msg.reply_markup and hasattr(msg.reply_markup, "inline_keyboard"):
                        for row in msg.reply_markup.inline_keyboard:
                            for button in row:
                                if self._matches_button(button.text):
                                    try:
                                        if self.use_button_answer and button.callback_data:
                                            await app.answer_callback_query(button.callback_data)
                                        else:
                                            await app.click(msg.id, button.text)
                                    except Exception:
                                        pass
                                    await asyncio.sleep(self.bot_send_interval)
                    if msg.text:
                        result = self._check_text_result(msg.text)
                        if result == "success":
                            return CheckinResult(success=True, message=msg.text[:100], bot_name=self.name)
                        if result == "account_fail":
                            return CheckinResult(success=False, message=msg.text[:100], bot_name=self.name)
                        if result == "checked":
                            return CheckinResult(success=True, message=msg.text[:100], bot_name=self.name)
                    if msg.photo and self.bot_use_captcha:
                        handled = await self._handle_captcha(msg, app, entity)
                        if handled:
                            return handled
                    if msg.photo and msg.caption:
                        cr = self._check_text_result(msg.caption)
                        if cr == "success":
                            return CheckinResult(success=True, message=msg.caption[:100], bot_name=self.name)
                await asyncio.sleep(3)
            except Exception as e:
                logger.debug(f"wait error: {e}")
                await asyncio.sleep(3)
        return CheckinResult(success=False, message="timeout", bot_name=self.name)
