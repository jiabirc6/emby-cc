"""Emby-CC CLI"""
from __future__ import annotations
import asyncio
import click
from rich.console import Console
from rich.panel import Panel
from emby_cc import __version__
from emby_cc.config import load_config, find_config
from emby_cc.core.scheduler import Scheduler
from emby_cc.utils.logger import setup_logger, get_logger
from emby_cc.plugins.telegram import PLUGIN_REGISTRY

console = Console()

@click.group()
@click.version_option(version=__version__, prog_name="emby-cc")
@click.option("--config", "-c", "config_path", type=click.Path(), default=None)
@click.pass_context
def cli(ctx, config_path):
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config_path

@cli.command()
@click.pass_context
def run(ctx):
    config_path = ctx.obj.get("config_path") or find_config()
    config = load_config(config_path)
    setup_logger(config.general.log_level)
    logger = get_logger("main")
    console.print(Panel.fit(
        f"[bold green]Emby-CC v{__version__}[/bold green]\n"
        f"Loaded [cyan]{len(config.accounts)}[/cyan] accounts, "
        f"[cyan]{len(PLUGIN_REGISTRY)}[/cyan] plugins",
        title="Start",
    ))
    scheduler = Scheduler(config, plugin_registry=PLUGIN_REGISTRY)
    try:
        asyncio.run(scheduler.start_loop())
    except KeyboardInterrupt:
        scheduler.stop()
        logger.info("Stopped")

@cli.command()
@click.pass_context
def checkin(ctx):
    config_path = ctx.obj.get("config_path") or find_config()
    config = load_config(config_path)
    setup_logger(config.general.log_level)
    async def _run():
        scheduler = Scheduler(config, plugin_registry=PLUGIN_REGISTRY)
        results = await scheduler.run_all_checkins()
        for account, bots in results.items():
            for bot, success in bots.items():
                status = "[green]OK[/green]" if success else "[red]FAIL[/red]"
                console.print(f"  {account} / {bot}: {status}")
    asyncio.run(_run())

@cli.command()
@click.pass_context
def keepalive(ctx):
    config_path = ctx.obj.get("config_path") or find_config()
    config = load_config(config_path)
    setup_logger(config.general.log_level)
    async def _run():
        scheduler = Scheduler(config, plugin_registry=PLUGIN_REGISTRY)
        results = await scheduler.run_all_keepalives()
        for account, success in results.items():
            status = "[green]OK[/green]" if success else "[red]FAIL[/red]"
            console.print(f"  {account}: {status}")
    asyncio.run(_run())

@cli.command()
@click.pass_context
def status(ctx):
    config_path = ctx.obj.get("config_path") or find_config()
    config = load_config(config_path)
    console.print(Panel.fit(
        f"[bold]Emby-CC v{__version__}[/bold]\n"
        f"Accounts: [cyan]{len(config.accounts)}[/cyan]\n"
        f"Plugins: [cyan]{len(PLUGIN_REGISTRY)}[/cyan]",
        title="Status",
    ))
    for acc in config.accounts:
        bots = ", ".join(acc.checkin.telegram_bots) or "none"
        kl = f"{acc.keepalive.interval_hours}h" if acc.keepalive.enabled else "off"
        console.print(f"  [bold]{acc.name}[/bold]\n    URL: {acc.emby_url}\n    Checkin: {bots}\n    Keepalive: {kl}")

def main():
    cli(obj={})
