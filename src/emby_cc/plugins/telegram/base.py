"""Telegram Bot 签到插件基类 - 基于 Pyrogram"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Optional, Union

from emby_cc.config import AccountConfig
from emby_cc.plugins.base import CheckinPlugin, CheckinResult
from emby_cc.utils.logger import get_logger

logger = get_logger("tg_checkin")

DEFAULT_SUCCESS_KEYWORDS = ("成功", "通过", "完成", "获得", "签到成功", "已签到")
DEFAULT_CHECKED_KEYWORDS = ("只能", "已经", "过了", "签过", "明日再来", "重复签到")
DEFAULT_FAIL_KEYWORDS = ("失败", "错误", "超时")
DEFAULT_ACCOUNT_FAIL_KEYWORDS = (
    "拉黑", "黑名单", "冻结", "未找到用户", "无资格",
    "退出群", "退群", "加群", "加入群聊", "请先关注",
    "请先加入", "未注册", "不存在", "不在群组中",
)


class TelegramBotCheckin(CheckinPlugin, ABC):
    """Telegram Bot 签到插件基类

    通过 Pyrogram 连接 Telegram，向目标 bot 发送签到命令，
    等待回复并处理验证码，最终判断签到结果。

    子类可覆盖以下属性自定义行为：
    - bot_username: 目标 bot 用户名
    - bot_checkin_cmd: 签到命令列表
    - bot_checkin_button: 签到按钮文本
    - bot_success_keywords: 成功关键词
    - bot_fail_keywords: 失败关键词
    """

    bot_username: str = ""
    bot_checkin_cmd: Union[str, list[str]] = ["/start"]
    bot_checkin_button: Union[str, list[str]] = ["签到", "簽到"]
    bot_use_captcha: bool = True
    bot_success_keywords: tuple[str, ...] = DEFAULT_SUCCESS_KEYWORDS
    bot_checked_keywords: tuple[str, ...] = DEFAULT_CHECKED_KEYWORDS
    bot_fail_keywords: tuple[str, ...] = DEFAULT_FAIL_KEYWORDS
    bot_account_fail_keywords: tuple[str, ...] = DEFAULT_ACCOUNT_FAIL_KEYWORDS
    bot_send_interval: int = 3
    bot_timeout: int = 120
    bot_max_retries: int = 3

    async def checkin(self, account: AccountConfig) -> CheckinResult:
        if not account.telegram_bot_token:
            return CheckinResult(success=False, message="未配置 Telegram Bot Token", bot_name=self.name)
        if not self.bot_username:
            return CheckinResult(success=False, message="未配置 bot_username", bot_name=self.name)

        try:
            from pyrogram import Client
            app = Client(
                name=f"emby_cc_{account.name}",
                api_id=20460004,
                api_hash="8da9c24e66a94bb19ad73f3297539f77",
                bot_token=account.telegram_bot_token,
            )
            async with app:
                return await self._do_checkin(app)
        except ImportError:
            return CheckinResult(success=False, message="未安装 pyrogram: pip install pyrogram tgcrypto", bot_name=self.name)
        except Exception as e:
            return CheckinResult(success=False, message=f"签到异常: {e}", bot_name=self.name)

    async def _do_checkin(self, app) -> CheckinResult:
        try:
            entity = await app.get_user(self.bot_username)
        except Exception:
            return CheckinResult(success=False, message=f"无法找到 bot: {self.bot_username}", bot_name=self.name)

        for cmd in self.bot_checkin_cmd:
            await app.send_message(entity, cmd)
            await asyncio.sleep(self.bot_send_interval)

        return await self._wait_and_handle(entity, app)

    async def _wait_and_handle(self, entity, app) -> CheckinResult:
        deadline = asyncio.get_event_loop().time() + self.bot_timeout
        while asyncio.get_event_loop().time() < deadline:
            try:
                messages = await app.get_chat_history(entity.id, limit=5)
                for msg in messages:
                    if msg.text:
                        result = self._check_text_result(msg.text)
                        if result == "success":
                            return CheckinResult(success=True, message=msg.text[:100], bot_name=self.name)
                        if result == "account_fail":
                            return CheckinResult(success=False, message=f"账号异常: {msg.text[:100]}", bot_name=self.name)
                        if result == "checked":
                            return CheckinResult(success=True, message=f"已签到: {msg.text[:100]}", bot_name=self.name)

                    if msg.reply_markup and hasattr(msg.reply_markup, "inline_keyboard"):
                        for row in msg.reply_markup.inline_keyboard:
                            for button in row:
                                if self._matches_button(button.text):
                                    await app.answer_callback_query(button.callback_data)
                                    await asyncio.sleep(self.bot_send_interval)

                    if msg.photo and self.bot_use_captcha:
                        handled = await self._handle_captcha(msg, app, entity)
                        if handled:
                            return handled

                await asyncio.sleep(3)
            except Exception as e:
                logger.debug(f"等待回复异常: {e}")
                await asyncio.sleep(3)

        return CheckinResult(success=False, message="签到超时", bot_name=self.name)

    def _check_text_result(self, text: str) -> Optional[str]:
        for kw in self.bot_account_fail_keywords:
            if kw in text:
                return "account_fail"
        for kw in self.bot_checked_keywords:
            if kw in text:
                return "checked"
        for kw in self.bot_success_keywords:
            if kw in text:
                return "success"
        for kw in self.bot_fail_keywords:
            if kw in text:
                return "fail"
        return None

    def _matches_button(self, text: str) -> bool:
        if not text:
            return False
        if isinstance(self.bot_checkin_button, str):
            return self.bot_checkin_button in text
        return any(btn in text for btn in self.bot_checkin_button)

    async def _handle_captcha(self, msg, app, entity) -> Optional[CheckinResult]:
        try:
            import ddddocr
        except ImportError:
            logger.warning("未安装 ddddocr，跳过验证码")
            return None
        try:
            file_bytes = await app.download_media(msg.photo, in_memory=True)
            ocr = ddddocr.DdddOcr(show_ad=False)
            result = ocr.classification(file_bytes)
            logger.info(f"验证码识别: {result}")
            await app.send_message(entity, result)
            await asyncio.sleep(self.bot_send_interval)
            messages = await app.get_chat_history(entity.id, limit=3)
            for reply in messages:
                if reply.text and self._check_text_result(reply.text) == "success":
                    return CheckinResult(success=True, message=f"验证码签到成功: {reply.text[:100]}", bot_name=self.name)
        except Exception as e:
            logger.error(f"验证码处理失败: {e}")
        return None
