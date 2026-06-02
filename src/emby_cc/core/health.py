"""健康检查模块"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from emby_cc.utils.logger import get_logger

logger = get_logger("health")


@dataclass
class HealthStatus:
    """健康状态"""
    accounts: dict[str, dict[str, Any]] = field(default_factory=dict)
    last_check: float = 0.0
    uptime_start: float = field(default_factory=time.time)

    def record_checkin(self, account: str, bot: str, success: bool):
        if account not in self.accounts:
            self.accounts[account] = {"checkins": {}, "keepalives": []}
        self.accounts[account]["checkins"][bot] = {
            "success": success,
            "time": time.time(),
        }

    def record_keepalive(self, account: str, success: bool):
        if account not in self.accounts:
            self.accounts[account] = {"checkins": {}, "keepalives": []}
        self.accounts[account]["keepalives"].append({
            "success": success,
            "time": time.time(),
        })

    def to_dict(self) -> dict:
        return {
            "uptime_seconds": int(time.time() - self.uptime_start),
            "accounts": self.accounts,
            "last_check": self.last_check,
        }


# 全局健康状态实例
health_status = HealthStatus()
