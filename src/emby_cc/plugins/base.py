"""签到插件基类"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from emby_cc.config import AccountConfig


@dataclass
class CheckinResult:
    """签到结果"""
    success: bool
    message: str = ""
    bot_name: str = ""


class CheckinPlugin(ABC):
    """签到插件基类 - 所有签到插件必须继承此类"""

    name: str = "base"
    description: str = ""
    enabled: bool = True

    @abstractmethod
    async def checkin(self, account: AccountConfig) -> CheckinResult:
        """执行签到

        Args:
            account: 账号配置

        Returns:
            CheckinResult 签到结果
        """
        ...

    def should_run(self, hour: int = -1) -> bool:
        """判断是否应该执行"""
        if not self.enabled:
            return False
        if hour < 0:
            from datetime import datetime
            hour = datetime.now().hour
        return 8 <= hour <= 23
