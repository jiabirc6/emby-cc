"""重试装饰器 - 指数退避"""

from __future__ import annotations

import asyncio
import functools
import random
from typing import Any, Callable, Type

from emby_cc.utils.logger import get_logger

logger = get_logger("retry")


def retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exceptions: tuple[Type[Exception], ...] = (Exception,),
) -> Callable:
    """异步重试装饰器，指数退避 + 随机抖动

    Args:
        max_retries: 最大重试次数
        base_delay: 基础延迟（秒）
        max_delay: 最大延迟（秒）
        exceptions: 需要重试的异常类型
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_retries:
                        logger.error(
                            f"{func.__name__} 在 {max_retries} 次重试后仍然失败: {e}"
                        )
                        raise

                    delay = min(base_delay * (2 ** attempt), max_delay)
                    jitter = random.uniform(0, delay * 0.3)
                    total_delay = delay + jitter

                    logger.warning(
                        f"{func.__name__} 第 {attempt + 1} 次失败: {e}, "
                        f"{total_delay:.1f}s 后重试..."
                    )
                    await asyncio.sleep(total_delay)

            raise last_exception  # type: ignore[misc]
        return wrapper
    return decorator
