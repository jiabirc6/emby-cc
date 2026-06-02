"""认证模块"""

from __future__ import annotations

import httpx

from emby_cc.config import AuthConfig
from emby_cc.utils.logger import get_logger
from emby_cc.utils.retry import retry

logger = get_logger("auth")


class AuthManager:
    """认证管理器 - 支持多认证源"""

    def __init__(self, config: AuthConfig):
        self.config = config
        self._token_cache: dict[str, str] = {}

    @retry(max_retries=2, base_delay=1.0)
    async def get_token(self, username: str, password: str) -> str:
        """获取认证 Token，支持备用认证源"""
        # 主认证源
        if self.config.server:
            token = await self._authenticate(
                self.config.server, username, password
            )
            if token:
                return token

        # 备用认证源
        if self.config.fallback_server:
            logger.warning("主认证源失败，尝试备用认证源")
            token = await self._authenticate(
                self.config.fallback_server, username, password
            )
            if token:
                return token

        raise ConnectionError("所有认证源均不可用")

    async def _authenticate(
        self, server: str, username: str, password: str
    ) -> str | None:
        """向指定认证源发送认证请求"""
        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                resp = await client.post(
                    f"{server}/auth",
                    json={"username": username, "password": password},
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("token", "")
        except Exception as e:
            logger.debug(f"认证失败 ({server}): {e}")
            return None
