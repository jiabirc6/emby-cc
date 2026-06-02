"""Checkin plugin registry"""

from emby_cc.plugins.base import CheckinPlugin, CheckinResult
from emby_cc.plugins.telegram.base import TelegramBotCheckin
from emby_cc.plugins.telegram import PLUGIN_REGISTRY

__all__ = ["CheckinPlugin", "CheckinResult", "TelegramBotCheckin", "PLUGIN_REGISTRY"]
