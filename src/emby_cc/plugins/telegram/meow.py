"""meow - Template A + special verify button"""

from __future__ import annotations
import asyncio
import random
from emby_cc.plugins.telegram.templ_a import TemplateACheckin
from emby_cc.utils.logger import get_logger
logger = get_logger("meow")

class MeowCheckin(TemplateACheckin):
    name = "meow"
    bot_username = "gymeowfly_bot"

    async def _wait_and_handle(self, entity, app):
        from emby_cc.plugins.base import CheckinResult
        deadline = asyncio.get_event_loop().time() + self.bot_timeout
        while asyncio.get_event_loop().time() < deadline:
            try:
                messages = await app.get_chat_history(entity.id, limit=5)
                for msg in messages:
                    if msg.photo and msg.caption and "请先验证你不是机器人" in (msg.caption or ""):
                        if msg.reply_markup and hasattr(msg.reply_markup, "inline_keyboard"):
                            for row in msg.reply_markup.inline_keyboard:
                                for button in row:
                                    if button.text and "我不是机器人" in button.text:
                                        await asyncio.sleep(random.uniform(0.5, 1.5))
                                        try:
                                            if button.callback_data:
                                                await app.answer_callback_query(button.callback_data)
                                        except Exception:
                                            pass
                                        await asyncio.sleep(self.bot_send_interval)
                        continue
                    return await super()._wait_and_handle(entity, app)
                await asyncio.sleep(3)
            except Exception as e:
                logger.debug(f"wait error: {e}")
                await asyncio.sleep(3)
        return CheckinResult(success=False, message="timeout", bot_name=self.name)
