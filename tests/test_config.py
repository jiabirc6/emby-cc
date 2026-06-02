"""配置模块测试"""

import pytest
from emby_cc.config import (
    AppConfig,
    AccountConfig,
    KeepAliveConfig,
    CheckinConfig,
    load_config,
)


def test_default_config():
    config = AppConfig()
    assert len(config.accounts) == 0
    assert config.general.log_level == "info"


def test_account_config():
    account = AccountConfig(
        name="test",
        emby_url="https://emby.example.com/",
        username="admin",
        password="pass",
    )
    assert account.emby_url == "https://emby.example.com"
    assert account.keepalive.enabled is True


def test_keepalive_validation():
    with pytest.raises(Exception):
        KeepAliveConfig(min_minutes=100, max_minutes=50)
