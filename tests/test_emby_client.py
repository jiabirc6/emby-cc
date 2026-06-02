"""Emby 客户端测试"""

import pytest
from emby_cc.core.emby_client import EmbyClient


def test_client_init():
    client = EmbyClient(
        base_url="https://emby.example.com",
        api_key="test-key",
        username="admin",
    )
    assert client.base_url == "https://emby.example.com"
    assert client.api_key == "test-key"


def test_client_url_normalize():
    client = EmbyClient(base_url="https://emby.example.com/")
    assert client.base_url == "https://emby.example.com"
