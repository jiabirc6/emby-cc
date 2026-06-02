"""TLS 指纹工具 - curl_cffi 封装"""

from __future__ import annotations

from typing import Any

import httpx

try:
    from curl_cffi.requests import AsyncSession as CurlAsyncSession
    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False


class TLSClient:
    """带 TLS 指纹模拟的 HTTP 客户端

    优先使用 curl_cffi（模拟真实浏览器 TLS 指纹），
    不可用时降级为 httpx。
    """

    def __init__(self, impersonate: str = "chrome"):
        self._impersonate = impersonate
        self._curl_session: Any = None
        self._httpx_client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        if HAS_CURL_CFFI:
            self._curl_session = CurlAsyncSession(impersonate=self._impersonate)
        else:
            self._httpx_client = httpx.AsyncClient(
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )
        return self

    async def __aexit__(self, *args):
        if self._curl_session:
            await self._curl_session.close()
        if self._httpx_client:
            await self._httpx_client.aclose()

    async def get(self, url: str, **kwargs) -> httpx.Response:
        if self._curl_session:
            resp = await self._curl_session.get(url, **kwargs)
            return httpx.Response(
                status_code=resp.status_code,
                content=resp.content,
                headers=dict(resp.headers),
            )
        return await self._httpx_client.get(url, **kwargs)  # type: ignore[union-attr]

    async def post(self, url: str, **kwargs) -> httpx.Response:
        if self._curl_session:
            resp = await self._curl_session.post(url, **kwargs)
            return httpx.Response(
                status_code=resp.status_code,
                content=resp.content,
                headers=dict(resp.headers),
            )
        return await self._httpx_client.post(url, **kwargs)  # type: ignore[union-attr]
