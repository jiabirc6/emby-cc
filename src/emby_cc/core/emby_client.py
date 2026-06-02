import asyncio

"""Emby API 客户端 - 版本兼容层"""

from __future__ import annotations

import random
from typing import Any, Optional

import httpx

from emby_cc.utils.logger import get_logger
from emby_cc.utils.retry import retry

logger = get_logger("emby_client")


class EmbyClient:
    """支持 Emby 4.6 ~ 4.9+ 的兼容客户端"""

    def __init__(
        self,
        base_url: str,
        api_key: str = "",
        username: str = "",
        password: str = "",
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.username = username
        self.password = password
        self._server_version: Optional[str] = None
        self._user_id: Optional[str] = None
        self._auth_token: Optional[str] = None
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
        )

    async def close(self):
        await self._client.aclose()

    @property
    def headers(self) -> dict[str, str]:
        h = {"Accept": "application/json"}
        token = self._auth_token or self.api_key
        if token:
            h["X-Emby-Token"] = token
        return h

    @retry(max_retries=3, base_delay=2.0)
    async def detect_version(self) -> str:
        """自动检测 Emby 服务器版本"""
        resp = await self._client.get(
            "/System/Info/Public",
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        info = resp.json()
        self._server_version = info.get("Version", "4.7.0.0")
        server_name = info.get("ServerName", "Unknown")
        logger.info(f"Emby 服务器: {server_name} (v{self._server_version})")
        return self._server_version

    @retry(max_retries=2, base_delay=1.0)
    async def authenticate(self) -> str:
        """用户名密码认证，获取 Token"""
        if self.api_key:
            self._auth_token = self.api_key
            return self.api_key

        resp = await self._client.post(
            "/Users/AuthenticateByName",
            headers={
                "X-Emby-Authorization": (
                    'MediaBrowser Client="Emby-CC", Device="Python", '
                    'DeviceId="emby-cc-001", Version="0.1.0"'
                ),
            },
            json={"Username": self.username, "Pw": self.password},
        )
        resp.raise_for_status()
        data = resp.json()
        self._auth_token = data["AccessToken"]
        self._user_id = data["User"]["Id"]
        logger.info(f"认证成功: {self.username}")
        return self._auth_token

    async def _ensure_auth(self):
        if not self._auth_token:
            await self.authenticate()

    @retry(max_retries=2, base_delay=1.0)
    async def get_additional_parts(self, user_id: str) -> dict:
        """带降级的 AdditionalParts 获取"""
        await self._ensure_auth()
        try:
            resp = await self._client.get(
                f"/Users/{user_id}/AdditionalParts",
                headers=self.headers,
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.debug("AdditionalParts 不支持，使用降级方案")
                return await self._fallback_user_info(user_id)
            raise

    async def _fallback_user_info(self, user_id: str) -> dict:
        """降级获取用户信息"""
        resp = await self._client.get(
            f"/Users/{user_id}",
            headers=self.headers,
        )
        resp.raise_for_status()
        return resp.json()

    @retry(max_retries=2, base_delay=1.0)
    async def get_user_id(self) -> str:
        """获取当前用户 ID"""
        if self._user_id:
            return self._user_id
        await self._ensure_auth()
        resp = await self._client.get("/Users", headers=self.headers)
        resp.raise_for_status()
        users = resp.json()
        for user in users:
            if user.get("Name") == self.username:
                self._user_id = user["Id"]
                return self._user_id
        raise ValueError(f"未找到用户: {self.username}")

    @retry(max_retries=2, base_delay=1.0)
    async def get_random_items(self, limit: int = 20) -> list[dict]:
        """随机获取媒体项（用于保活）"""
        await self._ensure_auth()
        user_id = await self.get_user_id()
        resp = await self._client.get(
            f"/Users/{user_id}/Items",
            headers=self.headers,
            params={
                "Recursive": "true",
                "IncludeItemTypes": "Movie,Episode",
                "Limit": limit,
                "SortBy": "Random",
                "Filters": "IsPlayed",
            },
        )
        resp.raise_for_status()
        return resp.json().get("Items", [])

    @retry(max_retries=2, base_delay=1.0)
    async def mark_played(self, item_id: str, user_id: str) -> bool:
        """标记为已播放"""
        await self._ensure_auth()
        resp = await self._client.post(
            f"/Users/{user_id}/Items/{item_id}/Played",
            headers=self.headers,
        )
        resp.raise_for_status()
        return True

    async def simulate_playback(
        self,
        item_id: str,
        duration_minutes: int = 30,
    ) -> bool:
        """模拟播放行为 - 保活核心

        模拟流程:
        1. 开始播放（Sessions/Playing）
        2. 定期汇报进度（Sessions/Playing/Progress）
        3. 结束播放（Sessions/Playing/Stopped）
        """
        await self._ensure_auth()
        session = await self._create_playback_session(item_id)

        total_seconds = duration_minutes * 60
        progress_interval = 10  # 每 10 秒汇报一次进度
        elapsed = 0

        try:
            while elapsed < total_seconds:
                progress = elapsed / total_seconds
                await self._report_progress(session, progress, elapsed, total_seconds)
                sleep_time = progress_interval + random.uniform(-1, 2)
                elapsed += progress_interval
                await asyncio.sleep(sleep_time)

            await self._report_stopped(session)
            logger.debug(f"播放模拟完成: {item_id} ({duration_minutes}min)")
            return True
        except Exception as e:
            logger.error(f"播放模拟失败: {e}")
            await self._report_stopped(session)
            raise

    async def _create_playback_session(self, item_id: str) -> str:
        """创建播放会话"""
        resp = await self._client.post(
            "/Sessions/Playing",
            headers=self.headers,
            json={
                "ItemId": item_id,
                "MediaSourceId": item_id,
                "CanSeek": True,
                "IsPaused": False,
                "IsMuted": False,
            },
        )
        resp.raise_for_status()
        return item_id

    async def _report_progress(
        self, session: str, progress: float, position: int, runtime: int
    ):
        """汇报播放进度"""
        resp = await self._client.post(
            "/Sessions/Playing/Progress",
            headers=self.headers,
            json={
                "ItemId": session,
                "MediaSourceId": session,
                "PositionTicks": position * 10_000_000,
                "IsPaused": False,
                "IsMuted": False,
            },
        )
        resp.raise_for_status()

    async def _report_stopped(self, session: str):
        """汇报播放结束"""
        try:
            await self._client.post(
                "/Sessions/Playing/Stopped",
                headers=self.headers,
                json={
                    "ItemId": session,
                    "MediaSourceId": session,
                    "PositionTicks": 0,
                },
            )
        except Exception:
            pass
