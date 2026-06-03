"""Emby API client with curl_cffi TLS fingerprint"""
from __future__ import annotations
import asyncio, random, uuid as _uuid
from typing import Optional
import httpx
from emby_cc.utils.logger import get_logger
from emby_cc.utils.retry import retry

logger = get_logger("emby_client")

DEVICE_PROFILE = {
    "MaxStreamingBitrate": 120000000,
    "MaxStaticBitrate": 100000000,
    "MusicStreamingTranscodingBitrate": 192000,
    "DirectPlayProfiles": [
        {"Container": "mp4", "Type": "Video", "VideoCodec": "hevc,h264,vp9", "AudioCodec": "aac,ac3,eac3,opus,mp3"},
        {"Container": "mkv", "Type": "Video", "VideoCodec": "hevc,h264,vp9", "AudioCodec": "aac,ac3,eac3,opus,mp3"},
        {"Container": "ts", "Type": "Video", "VideoCodec": "hevc,h264", "AudioCodec": "aac,ac3,eac3,mp3"},
        {"Container": "mp3", "Type": "Audio", "AudioCodec": "mp3"},
        {"Container": "aac", "Type": "Audio", "AudioCodec": "aac"},
        {"Container": "flac", "Type": "Audio", "AudioCodec": "flac"},
        {"Container": "ogg", "Type": "Audio", "AudioCodec": "vorbis"},
    ],
    "TranscodingProfiles": [
        {"Container": "ts", "Type": "Video", "AudioCodec": "aac", "VideoCodec": "h264", "Protocol": "hls"},
        {"Container": "mp3", "Type": "Audio", "AudioCodec": "mp3", "Protocol": "http"},
    ],
    "ContainerProfiles": [],
    "CodecProfiles": [
        {"Type": "Video", "Codec": "h264", "Conditions": [], "ApplyToSubtitles": False, "ApplyToVideo": False},
        {"Type": "Video", "Codec": "hevc", "Conditions": [], "ApplyToSubtitles": False, "ApplyToVideo": False},
        {"Type": "VideoAudio", "Codec": "aac", "Conditions": [], "ApplyToSubtitles": False, "ApplyToVideo": False},
    ],
    "SubtitleProfiles": [
        {"Format": "srt", "Method": "External"},
        {"Format": "ass", "Method": "External"},
        {"Format": "vtt", "Method": "External"},
    ],
}


class EmbyClient:
    def __init__(self, base_url: str, api_key: str = "", username: str = "", password: str = ""):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.username = username
        self.password = password
        self._server_version: Optional[str] = None
        self._user_id: Optional[str] = None
        self._auth_token: Optional[str] = None
        self._device_id = str(_uuid.uuid4()).upper()
        self._device_info: Optional[str] = None
        try:
            from curl_cffi.requests import AsyncSession as CurlSession
            self._curl = True
            self._session = CurlSession(base_url=self.base_url, timeout=30.0)
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
        if self._device_info:
            h["X-Emby-Authorization"] = self._device_info
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

    def _build_auth_header(self):
        clients = [("Yamby", "2.1.0"), ("Yamby", "2.0.8"), ("Yamby", "2.0.5")]
        client, ver = random.choice(clients)
        devices = ["iPhone", "iPad", "Pixel 8 Pro", "SM-S918B"]
        device = random.choice(devices)
        self._device_info = (
            f'MediaBrowser Client="{client}", Device="{device}", '
            f'DeviceId="{self._device_id}", Version="{ver}"'
        )
        return self._device_info

    @retry(max_retries=2, base_delay=1.0)
    async def authenticate(self):
        if self.api_key:
            self._auth_token = self.api_key
            return self.api_key
        resp = await self._req("POST", "/Users/AuthenticateByName",
            headers={**self.headers, "X-Emby-Authorization": self._build_auth_header()},
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
        if not self._device_info:
            self._build_auth_header()

    async def get_user_id(self):
        if self._user_id:
            return self._user_id
        await self._ensure_auth()
        return self._user_id

    @retry(max_retries=2, base_delay=1.0)
    async def get_random_items(self, limit=20):
        await self._ensure_auth()
        uid = await self.get_user_id()
        resp = await self._req("GET", f"/Users/{uid}/Items", headers=self.headers,
            params={"Recursive": "true", "IncludeItemTypes": "Movie,Episode", "Limit": limit,
                    "SortBy": "Random", "Fields": "MediaSources"})
        self._check_status(resp)
        return resp.json().get("Items", [])

    async def get_item_detail(self, item_id: str) -> dict:
        await self._ensure_auth()
        uid = await self.get_user_id()
        resp = await self._req("GET", f"/Users/{uid}/Items/{item_id}", headers=self.headers)
        self._check_status(resp)
        return resp.json()

    async def get_playback_info(self, item_id: str, media_source_id: str, is_playback: bool = False) -> dict:
        await self._ensure_auth()
        uid = await self.get_user_id()
        body = {
            "UserId": uid,
            "MediaSourceId": media_source_id,
            "IsPlayback": is_playback,
            "AutoOpenLiveStream": is_playback,
            "DeviceProfile": DEVICE_PROFILE,
        }
        if is_playback:
            body["PlaybackStartTimeTicks"] = 0
        resp = await self._req("POST", f"/Items/{item_id}/PlaybackInfo",
            headers=self.headers, json=body)
        self._check_status(resp)
        return resp.json()

    async def start_playback(self, item_id: str, media_source_id: str, play_session_id: str) -> int:
        resp = await self._req("POST", "/Sessions/Playing", headers=self.headers, json={
            "ItemId": item_id,
            "MediaSourceId": media_source_id,
            "PlaySessionId": play_session_id,
            "CanSeek": True,
            "IsPaused": False,
            "IsMuted": False,
        })
        self._check_status(resp)
        return resp.status_code

    async def report_progress(self, item_id: str, media_source_id: str, play_session_id: str,
                               position_ticks: int, event_name: str = "timeupdate") -> int:
        resp = await self._req("POST", "/Sessions/Playing/Progress", headers=self.headers, json={
            "ItemId": item_id,
            "MediaSourceId": media_source_id,
            "PlaySessionId": play_session_id,
            "IsPaused": False,
            "IsMuted": False,
            "PositionTicks": position_ticks,
            "EventName": event_name,
        })
        self._check_status(resp)
        return resp.status_code

    async def stop_playback(self, item_id: str, media_source_id: str, play_session_id: str) -> int:
        try:
            resp = await self._req("POST", "/Sessions/Playing/Stopped", headers=self.headers, json={
                "ItemId": item_id,
                "MediaSourceId": media_source_id,
                "PlaySessionId": play_session_id,
                "PositionTicks": 0,
            })
            self._check_status(resp)
            return resp.status_code
        except Exception:
            return 0