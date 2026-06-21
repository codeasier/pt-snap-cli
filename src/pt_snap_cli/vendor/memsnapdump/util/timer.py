"""
计时器工具模块

提供函数执行时间测量的装饰器。
"""

import time
import logging
from typing import Callable, Optional
from functools import wraps


def timer(name: Optional[str] = None, logger: Optional[logging.Logger] = None):
    """
    函数执行时间计时装饰器。

    用于测量函数执行时间并输出结果。可以选择输出到 logger 或控制台。

    Args:
        name: 计时器名称，默认使用函数名
        logger: 日志记录器，如果提供则使用 logger.info 输出，否则使用 print

    Returns:
        Callable: 装饰器函数

    Examples:
        >>> from ..util import get_logger
        >>> logger = get_logger(__name__)

        >>> @timer()
        ... def slow_function():
        ...     time.sleep(1)
        slow_function took 1.0012 seconds

        >>> @timer(name="数据处理", logger=logger)
        ... def process_data():
        ...     time.sleep(0.5)
        2024-01-01 12:00:00 [ INFO ][ __main__ ]: 数据处理 took 0.5023 seconds
    """

    def decorator(func: Callable):
        _name = func.__name__ if not name else name

        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = func(*args, **kwargs)
            end = time.perf_counter()
            info = f"{_name} took {end - start:.4f} seconds"
            if logger:
                logger.info(info)
            else:
                print(info)
            return result

        return wrapper

    return decorator
