"""
工具模块

提供常用的工具函数和类，包括日志、文件操作、数据库操作、计时器等。
"""

from .logger import get_logger, set_global_log_file

__all__ = ["get_logger", "set_global_log_file"]
