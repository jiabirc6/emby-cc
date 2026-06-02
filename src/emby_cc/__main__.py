"""Emby-CC CLI 入口"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel

from emby_cc import __version__
from emby_cc.config import load_config, find_config
from emby_cc.core.scheduler import Scheduler
from emby_cc.utils.logger import setup_logger, get_logger

console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="emby-cc")
@click.option("--config", "-c", "config_path", type=click.Path(), default=None, help="配置文件路径")
@click.pass_context
def cli(ctx: click.Context, config_path: str | None):
    """Emby-CC: Emby 签到与保活工具"""
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config_path


@cli.command()
@click.pass_context
def run(ctx: click.Context):
    """启动签到和保活服务"""
    config_path = ctx.obj.get("config_path") or find_config()
    config = load_config(config_path)

    setup_logger(config.general.log_level)
    logger = get_logger("main")

    console.print(Panel.fit(
        f"[bold green]Emby-CC v{__version__}[/bold green]\n"
        f"已加载 [cyan]{len(config.accounts)}[/cyan] 个账号",
        title="启动",
    ))

    scheduler = Scheduler(config)

    try:
        asyncio.run(scheduler.start_loop())
    except KeyboardInterrupt:
        scheduler.stop()
        logger.info("用户中断，已停止")


@cli.command()
@click.pass_context
def checkin(ctx: click.Context):
    """仅执行签到"""
    config_path = ctx.obj.get("config_path") or find_config()
    config = load_config(config_path)

    setup_logger(config.general.log_level)
    logger = get_logger("main")

    async def _run():
        scheduler = Scheduler(config)
        results = await scheduler.run_all_checkins()
        for account, bots in results.items():
            for bot, success in bots.items():
                status = "[green]OK[/green]" if success else "[red]FAIL[/red]"
                console.print(f"  {account} / {bot}: {status}")

    asyncio.run(_run())


@cli.command()
@click.pass_context
def keepalive(ctx: click.Context):
    """仅执行保活"""
    config_path = ctx.obj.get("config_path") or find_config()
    config = load_config(config_path)

    setup_logger(config.general.log_level)
    logger = get_logger("main")

    async def _run():
        scheduler = Scheduler(config)
        results = await scheduler.run_all_keepalives()
        for account, success in results.items():
            status = "[green]OK[/green]" if success else "[red]FAIL[/red]"
            console.print(f"  {account}: {status}")

    asyncio.run(_run())


@cli.command()
@click.pass_context
def status(ctx: click.Context):
    """查看当前状态"""
    config_path = ctx.obj.get("config_path") or find_config()
    config = load_config(config_path)

    console.print(Panel.fit(
        f"[bold]Emby-CC v{__version__}[/bold]\n\n"
        f"账号数: [cyan]{len(config.accounts)}[/cyan]\n"
        f"日志级别: [yellow]{config.general.log_level}[/yellow]\n"
        f"热更新: {'是' if config.general.hot_reload else '否'}\n"
        f"仪表盘: {'开启' if config.dashboard.enabled else '关闭'}",
        title="状态",
    ))

    for acc in config.accounts:
        bots = ", ".join(acc.checkin.telegram_bots) or "无"
        kl = f"{acc.keepalive.interval_hours}h" if acc.keepalive.enabled else "关闭"
        console.print(
            f"  [bold]{acc.name}[/bold]\n"
            f"    URL: {acc.emby_url}\n"
            f"    签到: {bots}\n"
            f"    保活: {kl}"
        )


def main():
    cli(obj={})
