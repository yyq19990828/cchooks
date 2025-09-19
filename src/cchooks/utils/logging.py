"""结构化日志系统，为CCHooks提供统一的日志记录和错误追踪。

本模块实现T041任务的日志需求：
1. 结构化日志记录
2. 错误分级和追踪
3. 性能监控
4. 操作审计
5. 调试支持
6. 日志轮转和管理

支持多种输出格式：
- JSON格式（机器可读）
- 人类友好格式
- 调试详细格式
- 审计专用格式
"""

import json
import logging
import logging.handlers
import sys
import threading
import time
import traceback
from contextlib import contextmanager
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, TextIO, Union

from ..exceptions import CCHooksError, ErrorCategory, ErrorSeverity


class LogLevel(Enum):
    """日志级别枚举。"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class LogFormat(Enum):
    """日志格式枚举。"""
    JSON = "json"           # JSON格式，机器可读
    HUMAN = "human"         # 人类友好格式
    DEBUG = "debug"         # 调试详细格式
    AUDIT = "audit"         # 审计专用格式


class LoggerType(Enum):
    """日志器类型枚举。"""
    GENERAL = "general"     # 一般日志
    ERROR = "error"         # 错误日志
    AUDIT = "audit"         # 审计日志
    PERFORMANCE = "performance"  # 性能日志


class StructuredLogger:
    """结构化日志记录器。

    提供统一的日志记录接口，支持多种格式和输出目标。
    """

    def __init__(self, name: str = "cchooks",
                 log_dir: Optional[Path] = None,
                 log_format: LogFormat = LogFormat.HUMAN,
                 log_level: LogLevel = LogLevel.INFO,
                 enable_console: bool = True,
                 enable_file: bool = True,
                 max_file_size: int = 10 * 1024 * 1024,  # 10MB
                 backup_count: int = 5):
        """初始化结构化日志记录器。

        Args:
            name: 日志记录器名称
            log_dir: 日志目录路径
            log_format: 日志格式
            log_level: 日志级别
            enable_console: 是否启用控制台输出
            enable_file: 是否启用文件输出
            max_file_size: 最大文件大小（字节）
            backup_count: 备份文件数量
        """
        self.name = name
        self.log_format = log_format
        self.log_level = log_level
        self.enable_console = enable_console
        self.enable_file = enable_file

        # 设置日志目录
        if log_dir is None:
            log_dir = Path.home() / ".claude" / "logs"
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # 创建不同类型的日志记录器
        self.loggers = {}
        self._setup_loggers(max_file_size, backup_count)

        # 性能监控
        self._operation_start_times = {}
        self._lock = threading.Lock()

    def _setup_loggers(self, max_file_size: int, backup_count: int) -> None:
        """设置各种类型的日志记录器。"""
        for logger_type in LoggerType:
            logger = logging.getLogger(f"{self.name}.{logger_type.value}")
            logger.setLevel(self._get_logging_level(self.log_level))
            logger.handlers.clear()  # 清除已有处理器

            # 文件处理器
            if self.enable_file:
                log_file = self.log_dir / f"{logger_type.value}.log"
                file_handler = logging.handlers.RotatingFileHandler(
                    log_file, maxBytes=max_file_size, backupCount=backup_count,
                    encoding='utf-8'
                )
                file_handler.setFormatter(self._get_formatter(self.log_format))
                logger.addHandler(file_handler)

            # 控制台处理器（仅对一般日志和错误日志）
            if self.enable_console and logger_type in [LoggerType.GENERAL, LoggerType.ERROR]:
                console_handler = logging.StreamHandler(sys.stderr)
                console_handler.setFormatter(self._get_formatter(LogFormat.HUMAN))
                logger.addHandler(console_handler)

            self.loggers[logger_type] = logger

    def _get_logging_level(self, level: LogLevel) -> int:
        """转换日志级别为logging模块级别。"""
        mapping = {
            LogLevel.DEBUG: logging.DEBUG,
            LogLevel.INFO: logging.INFO,
            LogLevel.WARNING: logging.WARNING,
            LogLevel.ERROR: logging.ERROR,
            LogLevel.CRITICAL: logging.CRITICAL
        }
        return mapping[level]

    def _get_formatter(self, format_type: LogFormat) -> logging.Formatter:
        """获取指定格式的日志格式化器。"""
        if format_type == LogFormat.JSON:
            return JsonFormatter()
        elif format_type == LogFormat.DEBUG:
            return DebugFormatter()
        elif format_type == LogFormat.AUDIT:
            return AuditFormatter()
        else:  # HUMAN
            return HumanFormatter()

    def debug(self, message: str, **kwargs) -> None:
        """记录调试信息。"""
        self._log(LogLevel.DEBUG, LoggerType.GENERAL, message, **kwargs)

    def info(self, message: str, **kwargs) -> None:
        """记录一般信息。"""
        self._log(LogLevel.INFO, LoggerType.GENERAL, message, **kwargs)

    def warning(self, message: str, **kwargs) -> None:
        """记录警告信息。"""
        self._log(LogLevel.WARNING, LoggerType.GENERAL, message, **kwargs)

    def error(self, message: str, error: Exception = None, **kwargs) -> None:
        """记录错误信息。"""
        extra_data = kwargs.copy()
        if error:
            extra_data.update({
                "error_type": type(error).__name__,
                "error_message": str(error),
                "traceback": traceback.format_exc()
            })

            # 如果是CCHooks异常，添加更多信息
            if isinstance(error, CCHooksError):
                extra_data.update({
                    "error_id": error.error_id,
                    "error_code": error.error_code,
                    "severity": error.severity.value if hasattr(error.severity, 'value') else error.severity,
                    "category": error.category.value if hasattr(error.category, 'value') else error.category,
                    "context": error.context
                })

        self._log(LogLevel.ERROR, LoggerType.ERROR, message, **extra_data)

    def critical(self, message: str, error: Exception = None, **kwargs) -> None:
        """记录严重错误信息。"""
        extra_data = kwargs.copy()
        if error:
            extra_data.update({
                "error_type": type(error).__name__,
                "error_message": str(error),
                "traceback": traceback.format_exc()
            })

        self._log(LogLevel.CRITICAL, LoggerType.ERROR, message, **extra_data)

    def audit(self, action: str, user: str = None, resource: str = None,
              result: str = "success", **kwargs) -> None:
        """记录审计信息。"""
        audit_data = {
            "action": action,
            "user": user or "system",
            "resource": resource,
            "result": result,
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }

        self._log(LogLevel.INFO, LoggerType.AUDIT, f"Audit: {action}", **audit_data)

    def performance(self, operation: str, duration_ms: float,
                   status: str = "completed", **kwargs) -> None:
        """记录性能信息。"""
        perf_data = {
            "operation": operation,
            "duration_ms": duration_ms,
            "status": status,
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }

        self._log(LogLevel.INFO, LoggerType.PERFORMANCE,
                 f"Performance: {operation} ({duration_ms:.2f}ms)", **perf_data)

    @contextmanager
    def operation_timer(self, operation_name: str, **kwargs):
        """操作计时上下文管理器。"""
        start_time = time.time()
        operation_id = f"{operation_name}_{threading.get_ident()}_{start_time}"

        with self._lock:
            self._operation_start_times[operation_id] = start_time

        try:
            self.debug(f"开始操作: {operation_name}", operation=operation_name, **kwargs)
            yield operation_id

            # 操作成功完成
            duration_ms = (time.time() - start_time) * 1000
            self.performance(operation_name, duration_ms, "completed", **kwargs)

        except Exception as e:
            # 操作失败
            duration_ms = (time.time() - start_time) * 1000
            self.performance(operation_name, duration_ms, "failed",
                           error_type=type(e).__name__, **kwargs)
            self.error(f"操作失败: {operation_name}", error=e, **kwargs)
            raise

        finally:
            with self._lock:
                self._operation_start_times.pop(operation_id, None)

    def _log(self, level: LogLevel, logger_type: LoggerType, message: str, **kwargs) -> None:
        """内部日志记录方法。"""
        logger = self.loggers.get(logger_type)
        if not logger:
            return

        # 添加通用的上下文信息
        extra = {
            "logger_type": logger_type.value,
            "thread_id": threading.get_ident(),
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }

        # 根据级别调用相应的日志方法
        log_method = getattr(logger, level.value.lower())
        log_method(message, extra=extra)

    def get_log_stats(self) -> Dict[str, Any]:
        """获取日志统计信息。"""
        stats = {
            "log_directory": str(self.log_dir),
            "loggers": {},
            "active_operations": len(self._operation_start_times)
        }

        for logger_type, logger in self.loggers.items():
            log_file = self.log_dir / f"{logger_type.value}.log"
            stats["loggers"][logger_type.value] = {
                "level": logger.level,
                "handlers": len(logger.handlers),
                "log_file_exists": log_file.exists(),
                "log_file_size": log_file.stat().st_size if log_file.exists() else 0
            }

        return stats


class JsonFormatter(logging.Formatter):
    """JSON格式化器。"""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }

        # 添加额外数据
        if hasattr(record, 'extra'):
            log_data.update(record.extra)

        # 添加异常信息
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False, separators=(',', ':'))


class HumanFormatter(logging.Formatter):
    """人类友好格式化器。"""

    def __init__(self):
        super().__init__(
            fmt='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )


class DebugFormatter(logging.Formatter):
    """调试详细格式化器。"""

    def __init__(self):
        super().__init__(
            fmt='%(asctime)s [%(levelname)s] %(name)s:%(module)s:%(funcName)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    def format(self, record: logging.LogRecord) -> str:
        result = super().format(record)

        # 添加额外信息
        if hasattr(record, 'extra') and record.extra:
            extra_info = ", ".join(f"{k}={v}" for k, v in record.extra.items()
                                 if k not in ['logger_type', 'thread_id', 'timestamp'])
            if extra_info:
                result += f" | {extra_info}"

        return result


class AuditFormatter(logging.Formatter):
    """审计专用格式化器。"""

    def format(self, record: logging.LogRecord) -> str:
        if hasattr(record, 'extra'):
            extra = record.extra
            return (f"{extra.get('timestamp', 'UNKNOWN')} | "
                   f"ACTION:{extra.get('action', 'UNKNOWN')} | "
                   f"USER:{extra.get('user', 'UNKNOWN')} | "
                   f"RESOURCE:{extra.get('resource', 'NONE')} | "
                   f"RESULT:{extra.get('result', 'UNKNOWN')} | "
                   f"MESSAGE:{record.getMessage()}")
        else:
            return f"{datetime.now().isoformat()} | {record.getMessage()}"


# 全局日志记录器实例
_global_logger: Optional[StructuredLogger] = None


def get_logger() -> StructuredLogger:
    """获取全局日志记录器。"""
    global _global_logger
    if _global_logger is None:
        _global_logger = StructuredLogger()
    return _global_logger


def configure_logging(log_dir: Optional[Path] = None,
                     log_format: LogFormat = LogFormat.HUMAN,
                     log_level: LogLevel = LogLevel.INFO,
                     enable_console: bool = True,
                     enable_file: bool = True,
                     max_file_size: int = 10 * 1024 * 1024,
                     backup_count: int = 5) -> None:
    """配置全局日志设置。"""
    global _global_logger
    _global_logger = StructuredLogger(
        log_dir=log_dir,
        log_format=log_format,
        log_level=log_level,
        enable_console=enable_console,
        enable_file=enable_file,
        max_file_size=max_file_size,
        backup_count=backup_count
    )


def log_error(error: Exception, message: str = None, **kwargs) -> None:
    """便捷的错误日志记录函数。"""
    logger = get_logger()
    log_message = message or f"发生错误: {type(error).__name__}"
    logger.error(log_message, error=error, **kwargs)


def log_operation(operation_name: str, **kwargs):
    """便捷的操作日志记录装饰器/上下文管理器。"""
    logger = get_logger()
    return logger.operation_timer(operation_name, **kwargs)


# 导出的类和函数
__all__ = [
    # 枚举类型
    "LogLevel",
    "LogFormat",
    "LoggerType",
    # 主要类
    "StructuredLogger",
    # 格式化器
    "JsonFormatter",
    "HumanFormatter",
    "DebugFormatter",
    "AuditFormatter",
    # 全局函数
    "get_logger",
    "configure_logging",
    "log_error",
    "log_operation"
]
