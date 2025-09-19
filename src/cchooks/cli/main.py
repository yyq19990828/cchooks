"""Main CLI entry points for cchooks commands.

This module provides the main entry point functions for all CLI commands
as defined in contracts/cli_commands.yaml. Each function corresponds to
a console script entry point defined in pyproject.toml.

These functions parse command line arguments and delegate to the actual
command implementations with unified error handling, performance monitoring,
and consistent user experience.
"""

import logging
import os
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, NoReturn, Optional, Tuple

from ..utils.formatters import format_error_message
from .argument_parser import parse_args

# 全局配置
CLI_VERSION = "1.0.0"
PERFORMANCE_THRESHOLD_MS = 100
DEBUG_MODE = os.getenv("CCHOOKS_DEBUG", "false").lower() == "true"
LOG_LEVEL = os.getenv("CCHOOKS_LOG_LEVEL", "INFO").upper()

# 配置日志
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s' if DEBUG_MODE else '%(message)s'
)
logger = logging.getLogger(__name__)

# 命令映射表 - 统一管理所有命令的导入和执行
COMMAND_REGISTRY = {
    "cc_addhook": ("commands.add_hook", "cc_addhook_main", "添加新的钩子配置"),
    "cc_updatehook": ("commands.update_hook", "main", "更新现有钩子配置"),
    "cc_removehook": ("commands.remove_hook", "execute_remove_hook", "移除钩子配置"),
    "cc_listhooks": ("commands.list_hooks", "execute_list_hooks_command", "列出已配置的钩子"),
    "cc_validatehooks": ("commands.validate_hooks", "create_command", "验证钩子配置"),
    "cc_generatehook": ("commands.generate_hook", "cc_generatehook_main", "从模板生成钩子脚本"),
    "cc_registertemplate": ("commands.register_template", "cc_registertemplate_main", "注册自定义钩子模板"),
    "cc_listtemplates": ("commands.list_templates", "cc_listtemplates_main", "列出可用的钩子模板"),
    "cc_unregistertemplate": ("commands.unregister_template", "cc_unregistertemplate_main", "注销自定义钩子模板"),
    "backup": ("commands.backup_manager", "handle_backup_command", "备份管理工具"),
}


class ProgressIndicator:
    """简单的进度指示器，用于长时间运行的操作。"""

    def __init__(self, message: str, show_spinner: bool = True):
        self.message = message
        self.show_spinner = show_spinner
        self._stop_event = threading.Event()
        self._thread = None
        self._spinner_chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        self._spinner_index = 0

    def start(self) -> None:
        """开始显示进度指示器。"""
        if self.show_spinner and not DEBUG_MODE:
            self._thread = threading.Thread(target=self._spin)
            self._thread.daemon = True
            self._thread.start()
        elif not self.show_spinner:
            print(f"{self.message}...", end="", flush=True)

    def stop(self, success_message: str = "完成") -> None:
        """停止进度指示器。"""
        if self._thread:
            self._stop_event.set()
            self._thread.join(timeout=1)
            # 清除spinner并显示完成消息
            print(f"\r{self.message}... {success_message}")
        elif not self.show_spinner:
            print(f" {success_message}")

    def _spin(self) -> None:
        """在单独线程中运行spinner动画。"""
        while not self._stop_event.is_set():
            char = self._spinner_chars[self._spinner_index % len(self._spinner_chars)]
            print(f"\r{char} {self.message}...", end="", flush=True)
            self._spinner_index += 1
            time.sleep(0.1)


def _setup_signal_handlers() -> None:
    """设置信号处理器以优雅处理中断。"""
    def signal_handler(signum: int, frame: Any) -> None:
        """信号处理函数。"""
        logger.debug(f"接收到信号: {signum}")
        print("\n\n操作被中断", file=sys.stderr)
        sys.exit(130)  # 标准的SIGINT退出码

    signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, signal_handler)


def _measure_performance(func_name: str):
    """测量并记录性能数据。"""
    class PerformanceMonitor:
        def __init__(self, command: str):
            self.command = command
            self.start_time = time.perf_counter()
            self.memory_start = None
            # 仅在调试模式下监控内存使用
            if DEBUG_MODE:
                try:
                    import psutil
                    process = psutil.Process()
                    self.memory_start = process.memory_info().rss / 1024 / 1024  # MB
                except ImportError:
                    pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            elapsed_ms = (time.perf_counter() - self.start_time) * 1000

            # 性能报告
            if elapsed_ms > PERFORMANCE_THRESHOLD_MS:
                logger.warning(f"{self.command} 执行时间超过阈值: {elapsed_ms:.2f}ms (目标: <{PERFORMANCE_THRESHOLD_MS}ms)")
            elif DEBUG_MODE:
                logger.debug(f"{self.command} 执行时间: {elapsed_ms:.2f}ms")

            # 内存使用报告（仅调试模式）
            if DEBUG_MODE and self.memory_start is not None:
                try:
                    import psutil
                    process = psutil.Process()
                    memory_end = process.memory_info().rss / 1024 / 1024  # MB
                    memory_diff = memory_end - self.memory_start
                    if memory_diff > 10:  # 如果内存增长超过10MB
                        logger.debug(f"{self.command} 内存使用: {memory_diff:+.1f}MB (开始: {self.memory_start:.1f}MB, 结束: {memory_end:.1f}MB)")
                except ImportError:
                    pass

    return PerformanceMonitor(func_name)


def _format_error_message(command_name: str, error: Exception) -> str:
    """格式化统一的错误消息。"""
    error_type = type(error).__name__
    if isinstance(error, FileNotFoundError):
        return f"错误: 文件未找到: {error}"
    elif isinstance(error, PermissionError):
        return f"错误: 权限错误: {error}"
    elif isinstance(error, KeyboardInterrupt):
        return "操作被中断"
    elif DEBUG_MODE:
        return f"错误: {error_type}: {error}"
    else:
        return "内部错误，请使用 CCHOOKS_DEBUG=true 获取详细信息"


def _execute_command_safely(command_name: str, command_func: Callable, args: Any) -> int:
    """安全执行命令，包含统一的错误处理和性能监控。"""
    try:
        with _measure_performance(command_name):
            # 对于特殊的命令处理不同的参数传递方式
            if command_name == "cc_listhooks":
                return command_func(
                    event_filter=getattr(args, 'event', None),
                    level=getattr(args, 'level', 'all'),
                    format_type=getattr(args, 'format', 'table')
                )
            elif command_name == "cc_validatehooks":
                # create_command 返回的是命令对象，需要调用execute
                command_obj = command_func()
                return command_obj.execute(args)
            else:
                return command_func(args)

    except KeyboardInterrupt:
        logger.debug(f"{command_name} 被用户中断")
        print(f"\n{_format_error_message(command_name, KeyboardInterrupt())}", file=sys.stderr)
        return 130
    except FileNotFoundError as e:
        logger.error(f"{command_name} 文件未找到: {e}")
        print(_format_error_message(command_name, e), file=sys.stderr)
        return 2
    except PermissionError as e:
        logger.error(f"{command_name} 权限错误: {e}")
        print(_format_error_message(command_name, e), file=sys.stderr)
        return 3
    except Exception as e:
        logger.exception(f"{command_name} 未预期的错误")
        print(_format_error_message(command_name, e), file=sys.stderr)
        return 4


def _create_command_function(command_name: str) -> Callable[[], NoReturn]:
    """动态创建命令函数。"""
    def command_function() -> NoReturn:
        module_path, func_name, description = COMMAND_REGISTRY[command_name]

        # 只为可能长时间运行的命令显示进度指示器
        show_progress = command_name in [
            "cc_validatehooks", "cc_generatehook", "cc_registertemplate",
            "cc_listhooks", "backup"
        ]

        progress = None
        if show_progress:
            progress = ProgressIndicator(description, show_spinner=not DEBUG_MODE)
            progress.start()

        try:
            # 解析参数
            args = parse_args([command_name] + sys.argv[1:])

            # 动态导入命令模块
            module = __import__(f"cchooks.cli.{module_path}", fromlist=[func_name])
            command_func = getattr(module, func_name)

            # 执行命令
            exit_code = _execute_command_safely(command_name, command_func, args)

            if progress:
                progress.stop("完成")
            sys.exit(exit_code)

        except Exception as e:
            if progress:
                progress.stop("失败")
            logger.exception(f"命令 {command_name} 执行失败")
            print(_format_error_message(command_name, e), file=sys.stderr)
            sys.exit(1)

    command_function.__doc__ = COMMAND_REGISTRY[command_name][2]
    command_function.__name__ = command_name
    return command_function


def _handle_common_exceptions(command_name: str):
    """通用异常处理装饰器（保留用于向后兼容）。"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                with _measure_performance(command_name):
                    return func(*args, **kwargs)
            except KeyboardInterrupt:
                logger.debug(f"{command_name} 被用户中断")
                print("\n操作被中断", file=sys.stderr)
                sys.exit(130)
            except FileNotFoundError as e:
                logger.error(f"{command_name} 文件未找到: {e}")
                print(f"错误: 文件未找到: {e}", file=sys.stderr)
                sys.exit(2)
            except PermissionError as e:
                logger.error(f"{command_name} 权限错误: {e}")
                print(f"错误: 权限错误: {e}", file=sys.stderr)
                sys.exit(3)
            except Exception as e:
                logger.exception(f"{command_name} 未预期的错误")
                if DEBUG_MODE:
                    print(f"错误: 未预期的错误: {e}\n{type(e).__name__}: {e}", file=sys.stderr)
                else:
                    print("内部错误，请使用 CCHOOKS_DEBUG=true 获取详细信息", file=sys.stderr)
                sys.exit(4)
        return wrapper
    return decorator


# 动态生成所有命令函数
for command_name in COMMAND_REGISTRY:
    globals()[command_name] = _create_command_function(command_name)


def main() -> NoReturn:
    """主入口点 - 统一的CLI调度器。

    这是cchooks命令的主入口点，提供统一的帮助系统、版本信息和命令调度。
    可以通过 'cchooks <command>' 或直接使用 'cc_<command>' 调用各个命令。
    """
    _setup_signal_handlers()

    # 如果没有参数，显示帮助
    if len(sys.argv) == 1:
        _show_main_help()
        sys.exit(0)

    # 处理全局选项
    if sys.argv[1] in ["-h", "--help"]:
        _show_main_help()
        sys.exit(0)
    elif sys.argv[1] in ["-v", "--version"]:
        _show_version_info()
        sys.exit(0)

    # 调度到具体命令
    command = sys.argv[1]

    # 创建简化的命令映射（从 cc_addhook 到 addhook）
    simplified_command_map = {
        cmd.replace("cc_", ""): globals()[cmd]
        for cmd in COMMAND_REGISTRY.keys()
    }

    if command in simplified_command_map:
        # 移除命令名，保留剩余参数
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        simplified_command_map[command]()
    else:
        _show_command_not_found_error(command)
        sys.exit(1)


def _show_version_info() -> None:
    """显示版本信息。"""
    print(f"""cchooks {CLI_VERSION}

Claude Code 钩子管理工具
- 支持 9 种钩子事件类型
- 零外部运行时依赖
- 完整的CLI命令集

更多信息: https://github.com/gowaylee/cchooks
""")


def _show_command_not_found_error(command: str) -> None:
    """显示命令未找到的友好错误消息。"""
    print(f"错误: 未知命令 '{command}'", file=sys.stderr)
    print("", file=sys.stderr)

    # 提供相似命令建议
    available_commands = [cmd.replace("cc_", "") for cmd in COMMAND_REGISTRY.keys() if cmd.startswith("cc_")]

    # 使用difflib提供更智能的建议
    import difflib
    suggestions = difflib.get_close_matches(command, available_commands, n=3, cutoff=0.5)

    # 如果difflib没有找到建议，尝试简单的部分匹配
    if not suggestions:
        for available_cmd in available_commands:
            if command.lower() in available_cmd.lower() or available_cmd.lower() in command.lower():
                suggestions.append(available_cmd)
                if len(suggestions) >= 3:
                    break

    if suggestions:
        print("您是否想要使用以下命令之一？", file=sys.stderr)
        for suggestion in suggestions:
            description = ""
            # 获取命令描述
            full_cmd = f"cc_{suggestion}"
            if full_cmd in COMMAND_REGISTRY:
                description = f" - {COMMAND_REGISTRY[full_cmd][2]}"
            print(f"  cchooks {suggestion}{description}", file=sys.stderr)
        print("", file=sys.stderr)

    print("使用 'cchooks --help' 查看所有可用命令", file=sys.stderr)


def _show_main_help() -> None:
    """显示主帮助信息。"""
    help_text = f"""cchooks {CLI_VERSION} - Claude Code 钩子管理工具

用法: cchooks <command> [options]
      cc_<command> [options]  (直接调用)

钩子管理命令:
  addhook              添加新的钩子配置到设置文件
  updatehook           更新现有钩子配置
  removehook           从设置中移除钩子配置
  listhooks            列出已配置的钩子
  validatehooks        验证钩子配置

模板管理命令:
  generatehook         从模板生成Python钩子脚本
  registertemplate     注册新的自定义钩子模板
  listtemplates        列出可用的钩子模板
  unregistertemplate   注销自定义钩子模板

工具命令:
  backup               备份管理工具（创建、恢复、验证备份）

全局选项:
  -h, --help           显示此帮助信息
  -v, --version        显示详细版本信息

环境变量:
  CCHOOKS_DEBUG        启用调试模式 (true/false)
  CCHOOKS_LOG_LEVEL    设置日志级别 (DEBUG/INFO/WARNING/ERROR)

常用示例:
  # 添加一个工具执行前的钩子
  cchooks addhook PreToolUse --command "echo '工具执行前'" --matcher "Write"

  # 列出所有已配置的钩子
  cchooks listhooks --format json

  # 从模板生成安全守护钩子
  cchooks generatehook security-guard PreToolUse output.py --add-to-settings

  # 验证所有钩子配置
  cchooks validatehooks --strict

支持的钩子事件类型:
  PreToolUse, PostToolUse, Notification, UserPromptSubmit,
  Stop, SubagentStop, PreCompact, SessionStart, SessionEnd

使用 'cchooks <command> --help' 获取特定命令的详细帮助。
更多文档: https://github.com/gowaylee/cchooks/blob/main/docs/api-reference.md
"""
    print(help_text)


if __name__ == "__main__":
    main()
