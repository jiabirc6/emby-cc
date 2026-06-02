"""任务调度器 - 协调签到和保活"""

from __future__ import annotations

import asyncio
import random
from datetime import datetime, timedelta

from emby_cc.config import AppConfig, AccountConfig
from emby_cc.core.health import health_status
from emby_cc.core.keepalive import KeepAliveRunner
from emby_cc.plugins import CheckinPlugin
from emby_cc.utils.logger import get_logger

logger = get_logger("scheduler")


class Scheduler:
    """任务调度器"""

    def __init__(self, config: AppConfig):
        self.config = config
        self._plugins: list[CheckinPlugin] = []
        self._running = False

    def register_plugin(self, plugin: CheckinPlugin):
        self._plugins.append(plugin)

    async def run_checkin(self, account: AccountConfig) -> dict[str, bool]:
        """对单个账号执行所有签到"""
        results = {}
        for bot_name in account.checkin.telegram_bots:
            for plugin in self._plugins:
                if plugin.name == bot_name and plugin.enabled:
                    try:
                        success = await plugin.checkin(account)
                        results[bot_name] = success
                        health_status.record_checkin(account.name, bot_name, success)
                        status = "成功" if success else "失败"
                        logger.info(f"[{account.name}] 签到 {bot_name}: {status}")
                    except Exception as e:
                        results[bot_name] = False
                        health_status.record_checkin(account.name, bot_name, False)
                        logger.error(f"[{account.name}] 签到 {bot_name} 异常: {e}")
                    break
            else:
                logger.warning(f"[{account.name}] 未找到签到插件: {bot_name}")
                results[bot_name] = False
        return results

    async def run_all_checkins(self) -> dict[str, dict[str, bool]]:
        """对所有账号执行签到"""
        all_results = {}
        for account in self.config.accounts:
            if not account.checkin.telegram_bots:
                continue
            logger.info(f"开始签到: {account.name}")
            all_results[account.name] = await self.run_checkin(account)
            # 签到之间随机延迟
            delay = random.uniform(5, 30)
            await asyncio.sleep(delay)
        return all_results

    async def run_keepalive(self, account: AccountConfig) -> bool:
        """对单个账号执行保活"""
        runner = KeepAliveRunner(account)
        success = await runner.run_once()
        health_status.record_keepalive(account.name, success)
        return success

    async def run_all_keepalives(self) -> dict[str, bool]:
        """对所有账号执行保活"""
        results = {}
        for account in self.config.accounts:
            if not account.keepalive.enabled:
                continue
            logger.info(f"开始保活: {account.name}")
            results[account.name] = await self.run_keepalive(account)
            delay = random.uniform(10, 60)
            await asyncio.sleep(delay)
        return results

    async def start_loop(self):
        """启动持续运行循环"""
        self._running = True
        logger.info("调度器启动")
        logger.info(f"已加载 {len(self.config.accounts)} 个账号")

        while self._running:
            now = datetime.now()

            # 签到检查（每天在窗口期内执行）
            if 8 <= now.hour <= 23:
                logger.info("=== 开始每日签到 ===")
                results = await self.run_all_checkins()
                total = sum(len(v) for v in results.values())
                success = sum(1 for v in results.values() for s in v.values() if s)
                logger.info(f"签到完成: {success}/{total} 成功")

            # 保活检查（按各账号间隔执行）
            for account in self.config.accounts:
                if account.keepalive.enabled:
                    await self.run_keepalive(account)

            # 下次检查间隔 1 小时
            next_run = now + timedelta(hours=1)
            logger.info(f"下次检查: {next_run.strftime('%H:%M:%S')}")
            await asyncio.sleep(3600)

    def stop(self):
        self._running = False
        logger.info("调度器停止")
