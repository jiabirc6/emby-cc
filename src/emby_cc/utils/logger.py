"""结构化日志模块 - Rich 彩色输出"""

from __future__ import annotations

import logging
import sys
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme

# 自定义主题
THEME = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green",
    "debug": "dim",
})

console = Console(theme=THEME)


def setup_logger(
    level: str = "info",
    log_file: Optional[str] = None,
) -> logging.Logger:
    """配置并返回应用根 logger

    Args:
        level: 日志级别 (debug/info/warning/error)
        log_file: 可选的日志文件路径
    """
    root_logger = logging.getLogger("emby_cc")

    if root_logger.handlers:
        return root_logger

    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Rich 终端处理器
    rich_handler = RichHandler(
        console=console,
        show_path=False,
        show_time=True,
        show_level=True,
        rich_tracebacks=True,
        markup=True,
    )
    rich_handler.setLevel(logging.DEBUG)
    root_logger.addHandler(rich_handler)

    # 文件处理器（可选）
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        file_handler.setFormatter(fmt)
        root_logger.addHandler(file_handler)

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """获取子 logger"""
    return logging.getLogger(f"emby_cc.{name}")
