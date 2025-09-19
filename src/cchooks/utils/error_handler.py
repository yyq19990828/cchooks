"""错误处理和用户友好消息系统。

本模块提供统一的错误处理机制，将技术错误转换为用户友好的中文消息，
并提供错误恢复建议和故障排除指导。

主要功能：
1. 中文错误消息格式化
2. 错误上下文信息展示
3. 解决建议生成
4. 错误严重程度处理
5. 调试信息管理
6. 用户支持信息提供
"""

import json
import sys
import traceback
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from ..exceptions import (
    CCHooksError,
    ErrorCategory,
    ErrorRecoveryAction,
    ErrorSeverity,
    create_error_from_exception,
)


class ErrorDisplayMode(Enum):
    """错误显示模式枚举。"""
    SIMPLE = "simple"          # 简单模式：仅显示主要错误信息
    DETAILED = "detailed"      # 详细模式：显示错误详情和建议
    DEBUG = "debug"           # 调试模式：显示技术详情和堆栈跟踪
    JSON = "json"             # JSON模式：机器可读的错误信息
    INTERACTIVE = "interactive" # 交互模式：允许用户选择恢复动作


class ColorScheme(Enum):
    """颜色方案枚举。"""
    NONE = "none"             # 无颜色
    BASIC = "basic"           # 基础颜色
    RICH = "rich"             # 丰富颜色


class UserFriendlyErrorHandler:
    """用户友好的错误处理器。

    将技术异常转换为用户友好的中文消息，提供解决建议和支持信息。
    """

    def __init__(self, display_mode: ErrorDisplayMode = ErrorDisplayMode.DETAILED,
                 show_suggestions: bool = True, show_context: bool = False,
                 enable_debug_info: bool = False, color_scheme: ColorScheme = ColorScheme.BASIC,
                 enable_recovery_prompts: bool = False, max_context_items: int = 10):
        """初始化错误处理器。

        Args:
            display_mode: 错误显示模式
            show_suggestions: 是否显示解决建议
            show_context: 是否显示上下文信息
            enable_debug_info: 是否启用调试信息
            color_scheme: 颜色方案
            enable_recovery_prompts: 是否启用恢复提示
            max_context_items: 最大上下文项目数
        """
        self.display_mode = display_mode
        self.show_suggestions = show_suggestions
        self.show_context = show_context
        self.enable_debug_info = enable_debug_info
        self.color_scheme = color_scheme
        self.enable_recovery_prompts = enable_recovery_prompts
        self.max_context_items = max_context_items

        # 错误消息模板
        self._error_templates = self._load_error_templates()

        # 常见解决方案库
        self._solution_library = self._load_solution_library()

        # 颜色映射
        self._color_map = self._load_color_map()

    def _load_color_map(self) -> Dict[str, str]:
        """加载颜色映射。"""
        if self.color_scheme == ColorScheme.NONE:
            return dict.fromkeys(["error", "warning", "info", "success", "reset", "bold", "dim"], "")
        elif self.color_scheme == ColorScheme.BASIC:
            return {
                "error": "\033[91m",      # 红色
                "warning": "\033[93m",    # 黄色
                "info": "\033[94m",       # 蓝色
                "success": "\033[92m",    # 绿色
                "reset": "\033[0m",       # 重置
                "bold": "\033[1m",        # 粗体
                "dim": "\033[2m"          # 暗淡
            }
        else:  # RICH
            return {
                "error": "\033[38;5;196m",      # 鲜红色
                "warning": "\033[38;5;208m",    # 橙色
                "info": "\033[38;5;39m",        # 亮蓝色
                "success": "\033[38;5;40m",     # 亮绿色
                "reset": "\033[0m",             # 重置
                "bold": "\033[1m",              # 粗体
                "dim": "\033[2m",               # 暗淡
                "underline": "\033[4m"          # 下划线
            }

    def _load_error_templates(self) -> Dict[str, str]:
        """加载错误消息模板。"""
        return {
            "header": "🔴 发生错误",
            "category_user": "📝 用户操作问题",
            "category_system": "⚙️ 系统问题",
            "category_internal": "🐛 程序内部问题",
            "category_external": "🔗 外部依赖问题",
            "severity_low": "💡",
            "severity_medium": "⚠️",
            "severity_high": "❌",
            "severity_critical": "🚨",
            "suggestion_header": "💡 建议解决方案",
            "context_header": "🔍 详细信息",
            "debug_header": "🐛 调试信息",
            "support_header": "🆘 需要帮助？",
            "recovery_header": "🔧 恢复选项",
            "error_id_header": "🆔 错误标识"
        }

    def _load_solution_library(self) -> Dict[str, List[str]]:
        """加载常见解决方案库。"""
        return {
            "permission_denied": [
                "检查文件权限设置",
                "尝试以管理员身份运行命令",
                "确保对目标目录有写入权限",
                "检查文件是否被其他程序占用"
            ],
            "file_not_found": [
                "确认文件路径是否正确",
                "检查文件是否存在",
                "尝试使用绝对路径",
                "检查文件名拼写"
            ],
            "config_error": [
                "检查配置文件格式（JSON语法）",
                "验证所有必需字段是否存在",
                "参考示例配置文件",
                "使用配置验证工具检查"
            ],
            "network_error": [
                "检查网络连接",
                "确认代理设置",
                "检查防火墙配置",
                "重试操作"
            ],
            "template_error": [
                "确认模板ID是否正确",
                "检查模板是否已注册",
                "验证模板文件完整性",
                "重新注册模板"
            ]
        }

    def format_error(self, error: Exception) -> str:
        """格式化错误消息。

        Args:
            error: 异常对象

        Returns:
            格式化后的错误消息字符串
        """
        # 如果不是CCHooks异常，先转换
        if not isinstance(error, CCHooksError):
            error = create_error_from_exception(error)

        if self.display_mode == ErrorDisplayMode.JSON:
            return self._format_json_error(error)
        elif self.display_mode == ErrorDisplayMode.DEBUG:
            return self._format_debug_error(error)
        elif self.display_mode == ErrorDisplayMode.SIMPLE:
            return self._format_simple_error(error)
        elif self.display_mode == ErrorDisplayMode.INTERACTIVE:
            return self._format_interactive_error(error)
        else:  # DETAILED
            return self._format_detailed_error(error)

    def _format_simple_error(self, error: Exception) -> str:
        """格式化简单错误消息。"""
        if isinstance(error, CCHooksError):
            return f"❌ {error.message}"
        else:
            return f"❌ 发生未知错误: {str(error)}"

    def _format_detailed_error(self, error: CCHooksError) -> str:
        """格式化详细错误消息。"""
        lines = []

        # 错误头部
        severity_icon = self._get_severity_icon(error.severity)
        category_icon = self._get_category_icon(error.category)
        header_color = self._get_severity_color(error.severity)

        header_line = f"{header_color}{severity_icon} {category_icon} {error.message}{self._color_map['reset']}"
        lines.append(header_line)
        lines.append("")

        # 错误ID和代码
        if error.error_id or error.error_code:
            lines.append(f"{self._error_templates['error_id_header']}:")
            if error.error_id:
                lines.append(f"  ID: {self._color_map['dim']}{error.error_id}{self._color_map['reset']}")
            if error.error_code:
                lines.append(f"  代码: {self._color_map['dim']}{error.error_code}{self._color_map['reset']}")
            lines.append("")

        # 恢复动作
        if error.recovery_actions and self.enable_recovery_prompts:
            lines.append(f"{self._color_map['info']}{self._error_templates['recovery_header']}:{self._color_map['reset']}")
            for i, action in enumerate(error.recovery_actions, 1):
                action_text = error._translate_recovery_action(action)
                lines.append(f"  {i}. {action_text}")
            lines.append("")

        # 解决建议
        if self.show_suggestions and error.suggested_fix:
            lines.append(f"{self._color_map['success']}{self._error_templates['suggestion_header']}:{self._color_map['reset']}")
            lines.append(f"  {error.suggested_fix}")
            lines.append("")

            # 添加通用解决方案
            generic_solutions = self._get_generic_solutions(error)
            if generic_solutions:
                lines.append("其他可尝试的解决方案:")
                for i, solution in enumerate(generic_solutions, 1):
                    lines.append(f"  {i}. {solution}")
                lines.append("")

        # 上下文信息
        if self.show_context and error.context:
            lines.append(f"{self._color_map['info']}{self._error_templates['context_header']}:{self._color_map['reset']}")
            context_items = list(error.context.items())[:self.max_context_items]
            for key, value in context_items:
                key_translated = self._translate_context_key(key)
                lines.append(f"  {key_translated}: {self._color_map['dim']}{value}{self._color_map['reset']}")

            if len(error.context) > self.max_context_items:
                remaining = len(error.context) - self.max_context_items
                lines.append(f"  ... 还有 {remaining} 项上下文信息")
            lines.append("")

        # 帮助链接
        if error.help_url:
            lines.append(f"📖 详细帮助: {self._color_map['info']}{error.help_url}{self._color_map['reset']}")
            lines.append("")

        # 支持信息
        lines.extend(self._get_support_info())

        return "\n".join(lines)

    def _format_debug_error(self, error: Exception) -> str:
        """格式化调试错误消息。"""
        lines = []

        # 基本详细信息
        lines.append(self._format_detailed_error(error))
        lines.append("")

        # 调试信息
        lines.append(f"{self._error_templates['debug_header']}:")

        if isinstance(error, CCHooksError):
            lines.append(f"时间戳: {error.timestamp}")
            lines.append(f"错误分类: {error.category}")
            lines.append(f"严重程度: {error.severity}")

            if error.debug_info:
                lines.append("系统信息:")
                for key, value in error.debug_info.items():
                    if key != "traceback" and value is not None:
                        lines.append(f"  {key}: {value}")

            if error.original_error:
                lines.append(f"原始错误: {error.original_error}")

        # 堆栈跟踪
        if hasattr(error, 'debug_info') and error.debug_info.get('traceback'):
            lines.append("")
            lines.append("堆栈跟踪:")
            lines.append(error.debug_info['traceback'])
        else:
            lines.append("")
            lines.append("堆栈跟踪:")
            lines.append(traceback.format_exc())

        return "\n".join(lines)

    def _format_json_error(self, error: Exception) -> str:
        """格式化JSON错误消息。"""
        if isinstance(error, CCHooksError):
            error_data = error.get_full_details()
        else:
            error_data = {
                "error_code": "UNKNOWN_ERROR",
                "message": str(error),
                "category": "unknown",
                "severity": "medium",
                "timestamp": datetime.now().isoformat(),
                "suggested_fix": "请检查错误信息并重试",
                "context": {},
                "debug_info": {
                    "python_version": sys.version,
                    "platform": sys.platform,
                    "traceback": traceback.format_exc()
                }
            }

        return json.dumps(error_data, ensure_ascii=False, indent=2)

    def _format_interactive_error(self, error: CCHooksError) -> str:
        """格式化交互式错误消息。"""
        lines = []

        # 基础详细信息
        lines.append(self._format_detailed_error(error))
        lines.append("")

        # 交互式恢复选项
        if error.recovery_actions:
            lines.append(f"{self._color_map['bold']}可执行的恢复动作:{self._color_map['reset']}")
            for i, action in enumerate(error.recovery_actions, 1):
                action_text = error._translate_recovery_action(action)
                key_color = self._color_map['success']
                lines.append(f"  [{key_color}{i}{self._color_map['reset']}] {action_text}")

            lines.append("")
            lines.append("请选择一个选项（输入数字），或按 Enter 跳过:")

        return "\n".join(lines)

    def _get_severity_icon(self, severity: Union[str, ErrorSeverity]) -> str:
        """获取严重程度图标。"""
        if isinstance(severity, ErrorSeverity):
            severity = severity.value
        return self._error_templates.get(f"severity_{severity}", "❓")

    def _get_category_icon(self, category: Union[str, ErrorCategory]) -> str:
        """获取分类图标。"""
        if isinstance(category, ErrorCategory):
            category = category.value
        return self._error_templates.get(f"category_{category}", "📋")

    def _get_severity_color(self, severity: Union[str, ErrorSeverity]) -> str:
        """获取严重程度对应的颜色。"""
        if isinstance(severity, ErrorSeverity):
            severity = severity.value

        color_map = {
            "low": self._color_map.get("info", ""),
            "medium": self._color_map.get("warning", ""),
            "high": self._color_map.get("error", ""),
            "critical": self._color_map.get("error", "") + self._color_map.get("bold", "")
        }
        return color_map.get(severity, "")

    def _get_generic_solutions(self, error: CCHooksError) -> List[str]:
        """获取通用解决方案。"""
        solutions = []

        # 根据错误代码匹配解决方案
        error_code = error.error_code.lower()
        for pattern, solution_list in self._solution_library.items():
            if pattern in error_code:
                solutions.extend(solution_list[:2])  # 最多2个通用方案

        # 根据上下文添加特定建议
        if error.context.get("file_path"):
            if "permission" in error_code:
                solutions.append("检查文件所有者和权限设置")

        return solutions[:3]  # 最多3个建议

    def _translate_context_key(self, key: str) -> str:
        """翻译上下文键名为中文。"""
        translations = {
            "file_path": "文件路径",
            "command_name": "命令名称",
            "argument_name": "参数名称",
            "template_id": "模板ID",
            "hook_type": "钩子类型",
            "error_code": "错误代码",
            "operation": "操作类型",
            "validation_errors": "验证错误",
            "config_path": "配置路径",
            "required_bytes": "所需空间",
            "available_bytes": "可用空间",
            "python_version": "Python版本",
            "platform": "操作系统"
        }
        return translations.get(key, key)

    def _get_support_info(self) -> List[str]:
        """获取用户支持信息。"""
        return [
            f"{self._error_templates['support_header']}",
            "• 查看文档: https://claude.ai/docs/hooks",
            "• 常见问题: https://claude.ai/docs/faq",
            "• 报告问题: https://github.com/anthropic/claude-code/issues",
            "• 获取帮助: claude-support@anthropic.com"
        ]

    def print_error(self, error: Exception, file=None) -> Optional[ErrorRecoveryAction]:
        """打印格式化的错误消息。

        Args:
            error: 异常对象
            file: 输出文件对象，默认为stderr

        Returns:
            用户选择的恢复动作（如果是交互模式）
        """
        if file is None:
            file = sys.stderr

        formatted_error = self.format_error(error)
        print(formatted_error, file=file)

        # 如果是交互模式并且有恢复动作，处理用户输入
        if (self.display_mode == ErrorDisplayMode.INTERACTIVE and
            isinstance(error, CCHooksError) and error.recovery_actions):
            return self._handle_interactive_recovery(error)

        return None

    def _handle_interactive_recovery(self, error: CCHooksError) -> Optional[ErrorRecoveryAction]:
        """处理交互式恢复选择。

        Args:
            error: CCHooks异常对象

        Returns:
            用户选择的恢复动作
        """
        try:
            choice = input().strip()
            if not choice:
                return None

            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(error.recovery_actions):
                return error.recovery_actions[choice_idx]
            else:
                print(f"无效选择: {choice}，请输入 1-{len(error.recovery_actions)} 之间的数字")
                return None

        except (ValueError, KeyboardInterrupt):
            return None

    def create_error_report(self, error: Exception) -> Dict[str, Any]:
        """创建错误报告。

        Args:
            error: 异常对象

        Returns:
            错误报告字典
        """
        if not isinstance(error, CCHooksError):
            error = create_error_from_exception(error)

        report = error.get_full_details()
        report.update({
            "report_generated_at": datetime.now().isoformat(),
            "handler_config": {
                "display_mode": self.display_mode.value,
                "color_scheme": self.color_scheme.value,
                "show_suggestions": self.show_suggestions,
                "show_context": self.show_context,
                "enable_debug_info": self.enable_debug_info
            }
        })

        return report

    def log_error(self, error: Exception, log_file: Optional[Path] = None) -> None:
        """记录错误到日志文件。

        Args:
            error: 异常对象
            log_file: 日志文件路径，默认为系统日志位置
        """
        if log_file is None:
            log_file = Path.home() / ".claude" / "logs" / "errors.log"

        # 确保日志目录存在
        log_file.parent.mkdir(parents=True, exist_ok=True)

        # 记录详细错误信息
        old_mode = self.display_mode
        self.display_mode = ErrorDisplayMode.DEBUG

        try:
            error_info = self.format_error(error)
            timestamp = datetime.now().isoformat()

            with log_file.open("a", encoding="utf-8") as f:
                f.write(f"\n{'='*60}\n")
                f.write(f"时间: {timestamp}\n")
                f.write(error_info)
                f.write(f"\n{'='*60}\n")

        except Exception as log_error:
            # 如果日志记录失败，输出到stderr
            print(f"警告：无法记录错误日志: {log_error}", file=sys.stderr)
        finally:
            self.display_mode = old_mode


class ErrorRecoveryManager:
    """错误恢复管理器。

    提供错误恢复机制，包括重试、回滚、降级等策略。
    """

    def __init__(self):
        self.recovery_strategies = {}
        self.retry_policies = {}

    def register_recovery_strategy(self, error_code: str,
                                 strategy: Callable[[Exception], bool]) -> None:
        """注册错误恢复策略。

        Args:
            error_code: 错误代码模式
            strategy: 恢复策略函数，返回True表示恢复成功
        """
        self.recovery_strategies[error_code] = strategy

    def register_retry_policy(self, error_code: str, max_retries: int = 3,
                            delay_seconds: float = 1.0, backoff_factor: float = 2.0) -> None:
        """注册重试策略。

        Args:
            error_code: 错误代码模式
            max_retries: 最大重试次数
            delay_seconds: 初始延迟秒数
            backoff_factor: 延迟倍增因子
        """
        self.retry_policies[error_code] = {
            "max_retries": max_retries,
            "delay_seconds": delay_seconds,
            "backoff_factor": backoff_factor
        }

    def attempt_recovery(self, error: Exception) -> bool:
        """尝试错误恢复。

        Args:
            error: 异常对象

        Returns:
            恢复是否成功
        """
        if not isinstance(error, CCHooksError):
            return False

        error_code = error.error_code

        # 查找匹配的恢复策略
        for pattern, strategy in self.recovery_strategies.items():
            if pattern in error_code:
                try:
                    return strategy(error)
                except Exception:
                    continue

        return False

    def should_retry(self, error: Exception, attempt_count: int) -> tuple[bool, float]:
        """判断是否应该重试。

        Args:
            error: 异常对象
            attempt_count: 当前尝试次数

        Returns:
            (是否重试, 延迟时间)
        """
        if not isinstance(error, CCHooksError):
            return False, 0.0

        error_code = error.error_code

        # 查找匹配的重试策略
        for pattern, policy in self.retry_policies.items():
            if pattern in error_code:
                if attempt_count < policy["max_retries"]:
                    delay = policy["delay_seconds"] * (policy["backoff_factor"] ** attempt_count)
                    return True, delay
                break

        return False, 0.0


# 全局错误处理器实例
_global_error_handler = UserFriendlyErrorHandler()
_global_recovery_manager = ErrorRecoveryManager()


def get_error_handler() -> UserFriendlyErrorHandler:
    """获取全局错误处理器。"""
    return _global_error_handler


def get_recovery_manager() -> ErrorRecoveryManager:
    """获取全局恢复管理器。"""
    return _global_recovery_manager


def configure_error_handling(display_mode: ErrorDisplayMode = ErrorDisplayMode.DETAILED,
                           show_suggestions: bool = True,
                           show_context: bool = False,
                           enable_debug_info: bool = False,
                           color_scheme: ColorScheme = ColorScheme.BASIC,
                           enable_recovery_prompts: bool = False,
                           max_context_items: int = 10) -> None:
    """配置全局错误处理设置。"""
    global _global_error_handler
    _global_error_handler = UserFriendlyErrorHandler(
        display_mode=display_mode,
        show_suggestions=show_suggestions,
        show_context=show_context,
        enable_debug_info=enable_debug_info,
        color_scheme=color_scheme,
        enable_recovery_prompts=enable_recovery_prompts,
        max_context_items=max_context_items
    )


def handle_error(error: Exception, auto_recovery: bool = True,
                log_error: bool = True) -> bool:
    """统一错误处理入口。

    Args:
        error: 异常对象
        auto_recovery: 是否尝试自动恢复
        log_error: 是否记录错误日志

    Returns:
        错误是否已恢复
    """
    # 记录错误日志
    if log_error:
        _global_error_handler.log_error(error)

    # 显示用户友好错误消息
    _global_error_handler.print_error(error)

    # 尝试自动恢复
    if auto_recovery:
        return _global_recovery_manager.attempt_recovery(error)

    return False


# 导出的函数和类
__all__ = [
    # 枚举类型
    "ErrorDisplayMode",
    "ColorScheme",
    # 处理器类
    "UserFriendlyErrorHandler",
    "ErrorRecoveryManager",
    # 全局函数
    "get_error_handler",
    "get_recovery_manager",
    "configure_error_handling",
    "handle_error"
]
