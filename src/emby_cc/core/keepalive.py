"""Keepalive module - Emby session-based playback simulation"""
from __future__ import annotations

import asyncio
import random
from datetime import datetime, timedelta

from emby_cc.config import AccountConfig
from emby_cc.core.emby_client import EmbyClient
from emby_cc.utils.logger import get_logger
from emby_cc.utils.retry import retry

logger = get_logger("keepalive")


class KeepAliveRunner:
    """Emby keepalive executor - session-based playback simulation"""

    def __init__(self, account: AccountConfig):
        self.account = account
        self.client = EmbyClient(
            base_url=account.emby_url,
            api_key=account.api_key,
            username=account.username,
            password=account.password,
        )

    @retry(max_retries=3, base_delay=5.0)
    async def run_once(self) -> bool:
        try:
            await self.client.detect_version()
            user_id = await self.client.get_user_id()

            items = await self.client.get_random_items(limit=20)
            if not items:
                logger.warning(f"[{self.account.name}] No available items")
                return False

            item = random.choice(items)
            item_name = item.get("Name", "Unknown")
            item_type = item.get("Type", "Unknown")
            item_id = item["Id"]

            ms_list = item.get("MediaSources", [])
            if not ms_list:
                detail = await self.client.get_item_detail(item_id)
                ms_list = detail.get("MediaSources", [])
            if not ms_list:
                logger.warning(f"[{self.account.name}] No media sources for {item_name}")
                return False

            ms = random.choice(ms_list)
            media_source_id = ms.get("Id", item_id)
            runtime_ticks = ms.get("RunTimeTicks", 0)

            duration = random.randint(
                self.account.keepalive.min_minutes * 60,
                self.account.keepalive.max_minutes * 60,
            )
            if runtime_ticks > 0:
                duration = min(duration, int(runtime_ticks / 10_000_000))

            logger.info(
                f"[{self.account.name}] Keepalive: {item_name} ({item_type}) - {duration // 60}min"
            )

            success = await self._session_playback(
                item_id, media_source_id, runtime_ticks, duration
            )

            if success:
                logger.info(f"[{self.account.name}] Keepalive done: {item_name}")
            return success

        except Exception as e:
            logger.error(f"[{self.account.name}] Keepalive failed: {e}")
            return False

    async def _session_playback(self, item_id: str, media_source_id: str,
                                 runtime_ticks: int, duration_seconds: int) -> bool:
        """Full session-based playback flow"""
        # Step 1: PlaybackInfo (IsPlayback=False) to get PlaySessionId
        pi = await self.client.get_playback_info(item_id, media_source_id, is_playback=False)
        play_session_id = pi.get("PlaySessionId", "")
        if not play_session_id:
            import uuid
            play_session_id = uuid.uuid4().hex

        # Step 2: PlaybackInfo (IsPlayback=True)
        await self.client.get_playback_info(item_id, media_source_id, is_playback=True)

        # Step 3: Sessions/Playing
        await self.client.start_playback(item_id, media_source_id, play_session_id)
        logger.info(f"Playback started, session={play_session_id[:16]}...")

        # Step 4: Report progress periodically
        progress_steps = random.randint(3, 6)
        step_delay = duration_seconds / progress_steps

        for i in range(1, progress_steps + 1):
            pct = i / progress_steps
            if runtime_ticks > 0:
                pos_ticks = int(runtime_ticks * pct)
            else:
                pos_ticks = int(pct * duration_seconds * 10_000_000)

            jitter_delay = step_delay * random.uniform(0.8, 1.2)
            await asyncio.sleep(jitter_delay)

            try:
                await self.client.report_progress(
                    item_id, media_source_id, play_session_id, pos_ticks
                )
                logger.info(f"Progress {int(pct*100)}%")
            except Exception as e:
                logger.warning(f"Progress report error: {e}")

        # Step 5: Sessions/Playing/Stopped
        await self.client.stop_playback(item_id, media_source_id, play_session_id)
        logger.info("Playback stopped")

        return True

    async def run_loop(self):
        interval = self.account.keepalive.interval_hours * 3600
        logger.info(f"[{self.account.name}] Keepalive loop started, interval {self.account.keepalive.interval_hours}h")
        while True:
            try:
                await self.run_once()
            except Exception as e:
                logger.error(f"[{self.account.name}] Keepalive loop error: {e}")
            next_run = datetime.now() + timedelta(seconds=interval)
            logger.info(f"[{self.account.name}] Next keepalive: {next_run.strftime('%H:%M:%S')}")
            await asyncio.sleep(interval)