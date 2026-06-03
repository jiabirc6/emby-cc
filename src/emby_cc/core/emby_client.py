"""Emby API client with curl_cffi TLS fingerprint"""
from __future__ import annotations
import asyncio, random
from typing import Optional
import httpx
from emby_cc.utils.logger import get_logger
from emby_cc.utils.retry import retry
logger = get_logger("emby_client")

class EmbyClient:
    def __init__(self, base_url: str, api_key: str = "", username: str = "", password: str = ""):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.username = username
        self.password = password
        self._server_version: Optional[str] = None
        self._user_id: Optional[str] = None
        self._auth_token: Optional[str] = None
        try:
            from curl_cffi.requests import AsyncSession as CurlSession
            self._curl = True
            self._session = CurlSession(base_url=self.base_url, timeout=30.0, impersonate="chrome")
        except ImportError:
            self._curl = False
            self._session = httpx.AsyncClient(base_url=self.base_url, timeout=httpx.Timeout(30.0), follow_redirects=True)

    async def close(self):
        if self._curl:
            await self._session.close()
        else:
            await self._session.aclose()

    @property
    def headers(self):
        h = {"Accept": "application/json"}
        token = self._auth_token or self.api_key
        if token:
            h["X-Emby-Token"] = token
        return h

    def _check_status(self, resp):
        if resp.status_code >= 400:
            raise Exception(f"HTTP {resp.status_code}: {resp.text[:200]}")

    async def _req(self, method, url, **kw):
        if self._curl:
            r = await self._session.request(method, url, **kw)
            return httpx.Response(status_code=r.status_code, content=r.content, headers=dict(r.headers))
        return await self._session.request(method, url, **kw)

    @retry(max_retries=3, base_delay=2.0)
    async def detect_version(self):
        resp = await self._req("GET", "/System/Info/Public", headers={"Accept": "application/json"})
        self._check_status(resp)
        info = resp.json()
        self._server_version = info.get("Version", "4.7.0.0")
        logger.info(f"Emby: {info.get('ServerName', '?')} v{self._server_version}")
        return self._server_version

    def _fake_env(self):
        import uuid as _uuid
        clients = [("Yamby", "2.1.0"), ("Yamby", "2.0.8"), ("Yamby", "2.0.5")]
        client, ver = random.choice(clients)
        devices = ["iPhone", "iPad", "Pixel 8 Pro", "SM-S918B"]
        device = random.choice(devices)
        device_id = str(_uuid.uuid4()).upper()
        return client, ver, device, device_id

    def _auth_header(self):
        client, ver, device, device_id = self._fake_env()
        return f'MediaBrowser Client="{client}", Device="{device}", DeviceId="{device_id}", Version="{ver}"'

    @retry(max_retries=2, base_delay=1.0)
    async def authenticate(self):
        if self.api_key:
            self._auth_token = self.api_key
            return self.api_key
        resp = await self._req("POST", "/Users/AuthenticateByName",
            headers={"X-Emby-Authorization": self._auth_header()},
            json={"Username": self.username, "Pw": self.password})
        self._check_status(resp)
        data = resp.json()
        self._auth_token = data["AccessToken"]
        self._user_id = data["User"]["Id"]
        logger.info(f"Auth OK: {self.username}")
        return self._auth_token

    async def _ensure_auth(self):
        if not self._auth_token:
            await self.authenticate()

    @retry(max_retries=2, base_delay=1.0)
    async def get_user_id(self):
        if self._user_id:
            return self._user_id
        await self._ensure_auth()
        resp = await self._req("GET", "/Users", headers=self.headers)
        self._check_status(resp)
        for u in resp.json():
            if u.get("Name") == self.username:
                self._user_id = u["Id"]
                return self._user_id
        raise ValueError(f"User not found: {self.username}")

    @retry(max_retries=2, base_delay=1.0)
    async def get_random_items(self, limit=20):
        await self._ensure_auth()
        uid = await self.get_user_id()
        resp = await self._req("GET", f"/Users/{uid}/Items", headers=self.headers,
            params={"Recursive": "true", "IncludeItemTypes": "Movie,Episode", "Limit": limit, "SortBy": "Random"})
        self._check_status(resp)
        return resp.json().get("Items", [])

    async def _create_playback_session(self, item_id):
        resp = await self._req("POST", "/Sessions/Playing", headers=self.headers,
            json={"ItemId": item_id, "MediaSourceId": item_id, "CanSeek": True, "IsPaused": False, "IsMuted": False})
        self._check_status(resp)
        return item_id

    async def _report_progress(self, session, progress, position, runtime):
        await self._req("POST", "/Sessions/Playing/Progress", headers=self.headers,
            json={"ItemId": session, "MediaSourceId": session, "PositionTicks": position * 10_000_000, "IsPaused": False, "IsMuted": False})

    async def _report_stopped(self, session):
        try:
            await self._req("POST", "/Sessions/Playing/Stopped", headers=self.headers,
                json={"ItemId": session, "MediaSourceId": session, "PositionTicks": 0})
        except Exception:
            pass

