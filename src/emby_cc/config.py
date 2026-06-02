"""配置加载模块 - TOML 解析 + Pydantic 校验"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class KeepAliveConfig(BaseModel):
    """保活配置"""
    enabled: bool = True
    interval_hours: int = Field(default=6, ge=1, le=48)
    min_minutes: int = Field(default=30, ge=5, le=60)
    max_minutes: int = Field(default=120, ge=30, le=480)

    @field_validator("max_minutes")
    @classmethod
    def max_gt_min(cls, v: int, info) -> int:
        min_val = info.data.get("min_minutes", 5)
        if v < min_val:
            raise ValueError(f"max_minutes ({v}) must be >= min_minutes ({min_val})")
        return v


class CheckinConfig(BaseModel):
    """签到配置"""
    telegram_bots: list[str] = Field(default_factory=list)


class AccountConfig(BaseModel):
    """单个 Emby 账号配置"""
    name: str
    emby_url: str
    username: str
    password: str = ""
    api_key: str = ""
    telegram_bot_token: str = ""
    keepalive: KeepAliveConfig = Field(default_factory=KeepAliveConfig)
    checkin: CheckinConfig = Field(default_factory=CheckinConfig)

    @field_validator("emby_url")
    @classmethod
    def normalize_url(cls, v: str) -> str:
        return v.rstrip("/")


class NotificationConfig(BaseModel):
    """通知配置"""
    enabled: bool = False
    type: str = "telegram"
    bot_token: str = ""
    chat_id: str = ""
    notify_on: list[str] = Field(default_factory=lambda: ["error", "warning"])


class GeneralConfig(BaseModel):
    """通用配置"""
    version: str = "1.0.0"
    log_level: str = "info"
    health_port: int = 8080
    hot_reload: bool = False
    hot_reload_interval_seconds: int = 60


class AuthConfig(BaseModel):
    """认证配置"""
    server: str = ""
    fallback_server: str = ""
    timeout: int = 30


class DashboardConfig(BaseModel):
    """Web 仪表盘配置"""
    enabled: bool = False
    port: int = 8081


class DistributedConfig(BaseModel):
    """分布式配置"""
    enabled: bool = False
    backend: str = "sqlite"


class AppConfig(BaseModel):
    """应用根配置"""
    general: GeneralConfig = Field(default_factory=GeneralConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    notifications: NotificationConfig = Field(default_factory=NotificationConfig)
    accounts: list[AccountConfig] = Field(default_factory=list)
    dashboard: DashboardConfig = Field(default_factory=DashboardConfig)
    distributed: DistributedConfig = Field(default_factory=DistributedConfig)

    def get_account(self, name: str) -> Optional[AccountConfig]:
        for acc in self.accounts:
            if acc.name == name:
                return acc
        return None


def _try_tomllib():
    try:
        import tomllib
        return tomllib
    except ModuleNotFoundError:
        import tomli as tomli
        return tomli


def load_config(config_path: str | Path) -> AppConfig:
    """加载并校验 TOML 配置文件"""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {path}")

    tomllib = _try_tomllib()
    try:
        with open(path, "rb") as f:
            raw = tomllib.load(f)
    except Exception as e:
        raise ValueError(f"TOML 解析失败: {e}") from e

    try:
        return AppConfig(**raw)
    except Exception as e:
        raise ValueError(f"配置校验失败: {e}") from e


def find_config() -> Path:
    """自动查找配置文件"""
    candidates = [
        Path("config.toml"),
        Path.home() / ".emby-cc" / "config.toml",
        Path("/etc/emby-cc/config.toml"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "未找到配置文件。请在当前目录创建 config.toml，"
        "或指定路径: emby-cc --config /path/to/config.toml"
    )
