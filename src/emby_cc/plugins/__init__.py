"""签到插件注册机制"""

from emby_cc.plugins.base import CheckinPlugin, CheckinResult
from emby_cc.plugins.telegram.base import TelegramBotCheckin

__all__ = ["CheckinPlugin", "CheckinResult", "TelegramBotCheckin"]
