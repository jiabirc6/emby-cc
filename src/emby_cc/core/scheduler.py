"""Task scheduler - coordinate checkin and keepalive"""
from __future__ import annotations
import asyncio
import random
from datetime import datetime, timedelta
from emby_cc.config import AppConfig, AccountConfig
from emby_cc.core.health import health_status
from emby_cc.core.keepalive import KeepAliveRunner
from emby_cc.utils.logger import get_logger
logger = get_logger("scheduler")

class Scheduler:
    def __init__(self, config: AppConfig, plugin_registry: dict = None):
        self.config = config
        self._plugin_registry = plugin_registry or {}
        self._running = False

    def register_plugin(self, plugin):
        self._plugin_registry[plugin.name] = plugin

    async def run_checkin(self, account: AccountConfig) -> dict[str, bool]:
        results = {}
        for bot_name in account.checkin.telegram_bots:
            plugin_cls = self._plugin_registry.get(bot_name)
            if plugin_cls is None:
                logger.warning(f"[{account.name}] plugin not found: {bot_name}")
                results[bot_name] = False
                continue
            plugin = plugin_cls()
            try:
                success = await plugin.checkin(account)
                results[bot_name] = success
                health_status.record_checkin(account.name, bot_name, success)
                s = "OK" if success else "FAIL"
                logger.info(f"[{account.name}] checkin {bot_name}: {s}")
            except Exception as e:
                results[bot_name] = False
                health_status.record_checkin(account.name, bot_name, False)
                logger.error(f"[{account.name}] checkin {bot_name} error: {e}")
        return results

    async def run_all_checkins(self) -> dict[str, dict[str, bool]]:
        all_results = {}
        for account in self.config.accounts:
            if not account.checkin.telegram_bots:
                continue
            logger.info(f"checkin start: {account.name}")
            all_results[account.name] = await self.run_checkin(account)
            delay = random.uniform(5, 30)
            await asyncio.sleep(delay)
        return all_results

    async def run_keepalive(self, account: AccountConfig) -> bool:
        runner = KeepAliveRunner(account)
        success = await runner.run_once()
        health_status.record_keepalive(account.name, success)
        return success

    async def run_all_keepalives(self) -> dict[str, bool]:
        results = {}
        for account in self.config.accounts:
            if not account.keepalive.enabled:
                continue
            logger.info(f"keepalive start: {account.name}")
            results[account.name] = await self.run_keepalive(account)
            delay = random.uniform(10, 60)
            await asyncio.sleep(delay)
        return results

    async def start_loop(self):
        self._running = True
        logger.info("scheduler started")
        logger.info(f"loaded {len(self.config.accounts)} accounts")
        while self._running:
            now = datetime.now()
            if 8 <= now.hour <= 23:
                logger.info("=== daily checkin ===")
                results = await self.run_all_checkins()
                total = sum(len(v) for v in results.values())
                success = sum(1 for v in results.values() for s in v.values() if s)
                logger.info(f"checkin done: {success}/{total} OK")
            for account in self.config.accounts:
                if account.keepalive.enabled:
                    await self.run_keepalive(account)
            next_run = now + timedelta(hours=1)
            logger.info(f"next check: {next_run.strftime('%H:%M:%S')}")
            await asyncio.sleep(3600)

    def stop(self):
        self._running = False
        logger.info("scheduler stopped")
