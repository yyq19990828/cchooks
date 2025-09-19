"""自定义异常模块，为Claude Code钩子系统提供统一的错误处理和中文用户友好消息。

本模块实现T041任务的核心要求：
1. 统一异常体系和继承层次结构
2. 中文用户友好错误消息
3. 错误代码标准化和分类
4. 上下文信息收集
5. 错误恢复机制支持
6. 调试和故障排除信息

异常分类：
- 用户错误：配置错误、参数错误、使用方式错误
- 系统错误：权限、网络、IO、环境问题
- 内部错误：程序逻辑错误、意外状态
- 外部依赖错误：第三方服务、库、工具问题
"""

import locale
import os
import sys
import traceback
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union


class ErrorSeverity(Enum):
    """错误严重程度枚举。"""
    LOW = "low"               # 警告或提示
    MEDIUM = "medium"         # 一般错误，用户可修复
    HIGH = "high"             # 严重错误，需要管理员介入
    CRITICAL = "critical"     # 系统级错误，可能导致数据丢失


class ErrorCategory(Enum):
    """错误分类枚举。"""
    USER = "user"             # 用户操作错误
    SYSTEM = "system"         # 系统环境错误
    INTERNAL = "internal"     # 程序内部错误
    EXTERNAL = "external"     # 外部依赖错误


class ErrorRecoveryAction(Enum):
    """错误恢复动作枚举。"""
    RETRY = "retry"           # 重试操作
    ROLLBACK = "rollback"     # 回滚到之前状态
    SKIP = "skip"             # 跳过当前操作
    ABORT = "abort"           # 中止整个流程
    MANUAL = "manual"         # 需要手动干预


class CCHooksError(Exception):
    """CCHooks系统的基础异常类。

    所有CCHooks相关异常的父类，提供统一的错误处理接口和中文用户友好消息。

    属性:
        message: 用户友好的中文错误消息
        error_code: 标准化错误代码 (格式: CATEGORY_SPECIFIC_CODE)
        suggested_fix: 解决建议
        context: 错误上下文信息
        original_error: 原始异常对象（如果有）
        debug_info: 调试信息字典
        timestamp: 错误发生时间
        severity: 错误严重程度
        category: 错误分类
        error_id: 唯一错误标识符
        recovery_actions: 建议的恢复动作列表
        help_url: 相关帮助文档链接
        user_locale: 用户语言环境
    """

    def __init__(
        self,
        message: str,
        error_code: str = "UNKNOWN_ERROR",
        suggested_fix: str = None,
        context: Dict[str, Any] = None,
        original_error: Exception = None,
        severity: Union[str, ErrorSeverity] = ErrorSeverity.MEDIUM,
        category: Union[str, ErrorCategory] = ErrorCategory.INTERNAL,
        recovery_actions: List[ErrorRecoveryAction] = None,
        help_url: str = None
    ):
        """初始化CCHooks基础异常。

        Args:
            message: 中文错误消息
            error_code: 错误代码
            suggested_fix: 解决建议
            context: 错误上下文信息
            original_error: 原始异常
            severity: 严重程度
            category: 错误分类
            recovery_actions: 建议的恢复动作
            help_url: 帮助文档链接
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.suggested_fix = suggested_fix or "请检查配置并重试，如问题持续请查看文档或联系支持"
        self.context = context or {}
        self.original_error = original_error

        # 处理枚举类型
        self.severity = severity if isinstance(severity, ErrorSeverity) else ErrorSeverity(severity)
        self.category = category if isinstance(category, ErrorCategory) else ErrorCategory(category)
        self.recovery_actions = recovery_actions or []

        # 生成唯一错误ID
        self.error_id = str(uuid.uuid4())[:8]
        self.timestamp = datetime.now()
        self.user_locale = self._detect_user_locale()

        # 设置帮助URL
        self.help_url = help_url or self._generate_help_url()

        # 收集调试信息
        self.debug_info = self._collect_debug_info()

    def _collect_debug_info(self) -> Dict[str, Any]:
        """收集调试信息。"""
        return {
            "python_version": sys.version,
            "platform": sys.platform,
            "cwd": str(Path.cwd()),
            "user_home": str(Path.home()),
            "environment_vars": {
                "CLAUDE_DEBUG": os.getenv("CLAUDE_DEBUG"),
                "PYTHONPATH": os.getenv("PYTHONPATH"),
                "PATH": os.getenv("PATH", "")[:200] + "..." if len(os.getenv("PATH", "")) > 200 else os.getenv("PATH", "")
            },
            "traceback": traceback.format_exc() if self.original_error else None,
            "context_keys": list(self.context.keys()) if self.context else [],
            "memory_usage": self._get_memory_usage(),
            "process_id": os.getpid()
        }

    def _detect_user_locale(self) -> str:
        """检测用户语言环境。"""
        try:
            return locale.getdefaultlocale()[0] or "zh_CN"
        except Exception:
            return "zh_CN"

    def _generate_help_url(self) -> str:
        """生成帮助文档URL。"""
        base_url = "https://claude.ai/docs/hooks/errors"
        return f"{base_url}#{self.error_code.lower()}"

    def _get_memory_usage(self) -> Optional[str]:
        """获取内存使用情况。"""
        try:
            import psutil
            process = psutil.Process()
            return f"{process.memory_info().rss / 1024 / 1024:.1f}MB"
        except ImportError:
            return None
        except Exception:
            return "unknown"

    def get_user_message(self) -> str:
        """获取用户友好的错误消息。"""
        severity_icons = {
            ErrorSeverity.LOW: "💡",
            ErrorSeverity.MEDIUM: "⚠️",
            ErrorSeverity.HIGH: "❌",
            ErrorSeverity.CRITICAL: "🚨"
        }

        icon = severity_icons.get(self.severity, "❓")
        user_msg = f"{icon} {self.message}"

        if self.error_id:
            user_msg += f" (错误ID: {self.error_id})"

        if self.suggested_fix:
            user_msg += f"\n\n💡 建议解决方案：\n{self.suggested_fix}"

        if self.recovery_actions:
            user_msg += "\n\n🔧 可尝试的恢复操作："
            for action in self.recovery_actions:
                action_text = self._translate_recovery_action(action)
                user_msg += f"\n• {action_text}"

        if self.help_url:
            user_msg += f"\n\n📖 详细帮助：{self.help_url}"

        return user_msg

    def get_full_details(self) -> Dict[str, Any]:
        """获取完整的错误详情，用于调试和报告。"""
        return {
            "error_id": self.error_id,
            "error_code": self.error_code,
            "message": self.message,
            "category": self.category.value if isinstance(self.category, ErrorCategory) else self.category,
            "severity": self.severity.value if isinstance(self.severity, ErrorSeverity) else self.severity,
            "timestamp": self.timestamp.isoformat(),
            "user_locale": self.user_locale,
            "suggested_fix": self.suggested_fix,
            "recovery_actions": [action.value for action in self.recovery_actions],
            "help_url": self.help_url,
            "context": self.context,
            "debug_info": self.debug_info,
            "original_error": str(self.original_error) if self.original_error else None
        }

    def _translate_recovery_action(self, action: ErrorRecoveryAction) -> str:
        """翻译恢复动作为中文描述。"""
        translations = {
            ErrorRecoveryAction.RETRY: "重试操作",
            ErrorRecoveryAction.ROLLBACK: "回滚到之前状态",
            ErrorRecoveryAction.SKIP: "跳过当前操作继续",
            ErrorRecoveryAction.ABORT: "中止整个流程",
            ErrorRecoveryAction.MANUAL: "需要手动干预"
        }
        return translations.get(action, action.value)

    def add_context(self, key: str, value: Any) -> None:
        """添加上下文信息。"""
        self.context[key] = value

    def add_recovery_action(self, action: ErrorRecoveryAction) -> None:
        """添加恢复动作建议。"""
        if action not in self.recovery_actions:
            self.recovery_actions.append(action)

    def is_recoverable(self) -> bool:
        """判断错误是否可恢复。"""
        return len(self.recovery_actions) > 0 and ErrorRecoveryAction.ABORT not in self.recovery_actions


# ===== 用户错误类别 =====

class UserError(CCHooksError):
    """用户操作错误的基类。

    用于用户配置错误、参数错误、使用方式错误等用户可以直接修正的问题。
    """

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault("category", ErrorCategory.USER)
        kwargs.setdefault("severity", ErrorSeverity.MEDIUM)
        kwargs.setdefault("recovery_actions", [ErrorRecoveryAction.RETRY])
        super().__init__(message, **kwargs)


class ConfigurationError(UserError):
    """配置文件错误。"""

    def __init__(self, message: str, config_path: Union[str, Path] = None, **kwargs):
        self.config_path = Path(config_path) if config_path else None
        kwargs.setdefault("error_code", "USER_CONFIG_INVALID")
        kwargs.setdefault("suggested_fix", "请检查配置文件格式和内容，确保所有必需字段都已正确设置")
        if self.config_path:
            kwargs.setdefault("context", {}).update({"config_path": str(self.config_path)})
        super().__init__(message, **kwargs)


class InvalidArgumentError(UserError):
    """无效参数错误。"""

    def __init__(self, message: str, argument_name: str = None, valid_values: List[str] = None, **kwargs):
        self.argument_name = argument_name
        self.valid_values = valid_values or []
        kwargs.setdefault("error_code", "USER_INVALID_ARGUMENT")

        suggested_fix = "请检查命令参数"
        if self.argument_name:
            suggested_fix += f"，确保'{self.argument_name}'"
        if self.valid_values:
            suggested_fix += f"的值为: {', '.join(self.valid_values)}"
        kwargs.setdefault("suggested_fix", suggested_fix)

        context = kwargs.setdefault("context", {})
        if self.argument_name:
            context["argument_name"] = self.argument_name
        if self.valid_values:
            context["valid_values"] = self.valid_values

        super().__init__(message, **kwargs)


class HookValidationError(UserError):
    """钩子输入验证错误。"""

    def __init__(self, message: str, hook_type: str = None, **kwargs):
        self.hook_type = hook_type
        kwargs.setdefault("error_code", "USER_HOOK_VALIDATION")
        kwargs.setdefault("suggested_fix", "请检查钩子配置和输入数据格式")
        if self.hook_type:
            kwargs.setdefault("context", {}).update({"hook_type": self.hook_type})
        super().__init__(message, **kwargs)


class ValidationError(UserError):
    """通用验证错误，保持向后兼容。"""

    def __init__(self, message: str, field_name: str = None, error_code: str = None, suggested_fix: str = None):
        self.field_name = field_name
        kwargs = {
            "error_code": error_code or "USER_VALIDATION_ERROR",
            "suggested_fix": suggested_fix
        }
        if field_name:
            kwargs.setdefault("context", {})["field_name"] = field_name
        super().__init__(message, **kwargs)


class DuplicateHookError(UserError):
    """重复钩子错误。"""

    def __init__(self, message: str, existing_hook: dict = None, existing_index: int = None, **kwargs):
        self.existing_hook = existing_hook
        self.existing_index = existing_index
        kwargs.setdefault("error_code", "USER_DUPLICATE_HOOK")
        kwargs.setdefault("suggested_fix", "请移除重复的钩子配置或使用更新命令修改现有钩子")

        context = kwargs.setdefault("context", {})
        if existing_index is not None:
            context["existing_index"] = existing_index
        if existing_hook:
            context["existing_hook_type"] = existing_hook.get("type")

        super().__init__(message, **kwargs)


# ===== 系统错误类别 =====

class SystemError(CCHooksError):
    """系统级错误的基类。

    用于权限、网络、IO、环境等系统相关问题。
    """

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault("category", ErrorCategory.SYSTEM)
        kwargs.setdefault("severity", ErrorSeverity.HIGH)
        kwargs.setdefault("recovery_actions", [ErrorRecoveryAction.RETRY, ErrorRecoveryAction.MANUAL])
        super().__init__(message, **kwargs)


class PermissionError(SystemError):
    """权限错误。"""

    def __init__(self, message: str, path: Union[str, Path] = None, operation: str = None, **kwargs):
        self.path = Path(path) if path else None
        self.operation = operation
        kwargs.setdefault("error_code", "SYSTEM_PERMISSION_DENIED")
        kwargs.setdefault("suggested_fix", "请检查文件权限或以管理员身份运行")

        context = kwargs.setdefault("context", {})
        if self.path:
            context["path"] = str(self.path)
        if self.operation:
            context["operation"] = self.operation

        super().__init__(message, **kwargs)


class NetworkError(SystemError):
    """网络连接错误。"""

    def __init__(self, message: str, url: str = None, **kwargs):
        self.url = url
        kwargs.setdefault("error_code", "SYSTEM_NETWORK_ERROR")
        kwargs.setdefault("suggested_fix", "请检查网络连接和防火墙设置")
        if self.url:
            kwargs.setdefault("context", {})["url"] = self.url
        super().__init__(message, **kwargs)


class DiskSpaceError(SystemError):
    """磁盘空间不足错误。"""

    def __init__(self, message: str, required_bytes: int = None, available_bytes: int = None, **kwargs):
        self.required_bytes = required_bytes
        self.available_bytes = available_bytes
        kwargs.setdefault("error_code", "SYSTEM_DISK_SPACE")
        kwargs.setdefault("suggested_fix", "请清理磁盘空间或选择其他位置")

        context = kwargs.setdefault("context", {})
        if self.required_bytes:
            context["required_bytes"] = self.required_bytes
        if self.available_bytes:
            context["available_bytes"] = self.available_bytes

        super().__init__(message, **kwargs)


class EnvironmentError(SystemError):
    """环境配置错误。"""

    def __init__(self, message: str, missing_dependency: str = None, **kwargs):
        self.missing_dependency = missing_dependency
        kwargs.setdefault("error_code", "SYSTEM_ENVIRONMENT_ERROR")
        kwargs.setdefault("suggested_fix", "请检查系统环境和依赖项")
        if self.missing_dependency:
            kwargs.setdefault("context", {})["missing_dependency"] = self.missing_dependency
        super().__init__(message, **kwargs)


# ===== 内部错误类别 =====

class InternalError(CCHooksError):
    """内部程序错误的基类。

    用于程序逻辑错误、意外状态等开发者需要修复的问题。
    """

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault("category", ErrorCategory.INTERNAL)
        kwargs.setdefault("severity", ErrorSeverity.HIGH)
        kwargs.setdefault("recovery_actions", [ErrorRecoveryAction.ABORT])
        super().__init__(message, **kwargs)


class ParseError(InternalError):
    """JSON或数据解析错误。"""

    def __init__(self, message: str, data_type: str = None, **kwargs):
        self.data_type = data_type
        kwargs.setdefault("error_code", "INTERNAL_PARSE_ERROR")
        kwargs.setdefault("suggested_fix", "请报告此错误，可能需要程序修复")
        if self.data_type:
            kwargs.setdefault("context", {})["data_type"] = self.data_type
        super().__init__(message, **kwargs)


class InvalidHookTypeError(InternalError):
    """无效钩子类型错误。"""

    def __init__(self, message: str, hook_type: str = None, **kwargs):
        self.hook_type = hook_type
        kwargs.setdefault("error_code", "INTERNAL_INVALID_HOOK_TYPE")
        kwargs.setdefault("suggested_fix", "这是程序内部错误，请报告给开发者")
        if self.hook_type:
            kwargs.setdefault("context", {})["hook_type"] = self.hook_type
        super().__init__(message, **kwargs)


class StateError(InternalError):
    """程序状态错误。"""

    def __init__(self, message: str, expected_state: str = None, actual_state: str = None, **kwargs):
        self.expected_state = expected_state
        self.actual_state = actual_state
        kwargs.setdefault("error_code", "INTERNAL_STATE_ERROR")
        kwargs.setdefault("suggested_fix", "程序状态异常，请重启并报告此问题")

        context = kwargs.setdefault("context", {})
        if self.expected_state:
            context["expected_state"] = self.expected_state
        if self.actual_state:
            context["actual_state"] = self.actual_state

        super().__init__(message, **kwargs)


# ===== 外部依赖错误类别 =====

class ExternalError(CCHooksError):
    """外部依赖错误的基类。

    用于第三方服务、库、工具等外部依赖问题。
    """

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault("category", ErrorCategory.EXTERNAL)
        kwargs.setdefault("severity", ErrorSeverity.MEDIUM)
        kwargs.setdefault("recovery_actions", [ErrorRecoveryAction.RETRY, ErrorRecoveryAction.SKIP])
        super().__init__(message, **kwargs)


class TemplateError(ExternalError):
    """模板相关错误。"""

    def __init__(self, message: str, template_id: str = None, **kwargs):
        self.template_id = template_id
        kwargs.setdefault("error_code", "EXTERNAL_TEMPLATE_ERROR")
        kwargs.setdefault("suggested_fix", "请检查模板配置和可用性")
        if self.template_id:
            kwargs.setdefault("context", {})["template_id"] = self.template_id
        super().__init__(message, **kwargs)


class ExternalToolError(ExternalError):
    """外部工具执行错误。"""

    def __init__(self, message: str, tool_name: str = None, exit_code: int = None, **kwargs):
        self.tool_name = tool_name
        self.exit_code = exit_code
        kwargs.setdefault("error_code", "EXTERNAL_TOOL_ERROR")
        kwargs.setdefault("suggested_fix", "请检查外部工具是否正确安装和配置")

        context = kwargs.setdefault("context", {})
        if self.tool_name:
            context["tool_name"] = self.tool_name
        if self.exit_code is not None:
            context["exit_code"] = self.exit_code

        super().__init__(message, **kwargs)


# ===== 新增异常类型 =====

class TimeoutError(SystemError):
    """操作超时错误。"""

    def __init__(self, message: str, timeout_seconds: int = None, operation: str = None, **kwargs):
        self.timeout_seconds = timeout_seconds
        self.operation = operation
        kwargs.setdefault("error_code", "SYSTEM_OPERATION_TIMEOUT")
        kwargs.setdefault("suggested_fix", "请检查网络连接或增加超时时间")
        kwargs.setdefault("recovery_actions", [ErrorRecoveryAction.RETRY])

        context = kwargs.setdefault("context", {})
        if self.timeout_seconds:
            context["timeout_seconds"] = self.timeout_seconds
        if self.operation:
            context["operation"] = self.operation

        super().__init__(message, **kwargs)


class DataIntegrityError(InternalError):
    """数据完整性错误。"""

    def __init__(self, message: str, data_type: str = None, **kwargs):
        self.data_type = data_type
        kwargs.setdefault("error_code", "INTERNAL_DATA_INTEGRITY")
        kwargs.setdefault("suggested_fix", "数据损坏，需要恢复或重新生成")
        kwargs.setdefault("recovery_actions", [ErrorRecoveryAction.ROLLBACK, ErrorRecoveryAction.MANUAL])
        kwargs.setdefault("severity", ErrorSeverity.CRITICAL)

        if self.data_type:
            kwargs.setdefault("context", {})["data_type"] = self.data_type

        super().__init__(message, **kwargs)


class SecurityError(SystemError):
    """安全相关错误。"""

    def __init__(self, message: str, security_violation: str = None, **kwargs):
        self.security_violation = security_violation
        kwargs.setdefault("error_code", "SYSTEM_SECURITY_VIOLATION")
        kwargs.setdefault("suggested_fix", "检查权限设置和安全配置")
        kwargs.setdefault("recovery_actions", [ErrorRecoveryAction.ABORT])
        kwargs.setdefault("severity", ErrorSeverity.CRITICAL)

        if self.security_violation:
            kwargs.setdefault("context", {})["security_violation"] = self.security_violation

        super().__init__(message, **kwargs)


class ResourceExhaustionError(SystemError):
    """资源耗尽错误。"""

    def __init__(self, message: str, resource_type: str = None, current_usage: str = None, **kwargs):
        self.resource_type = resource_type
        self.current_usage = current_usage
        kwargs.setdefault("error_code", "SYSTEM_RESOURCE_EXHAUSTION")
        kwargs.setdefault("suggested_fix", "释放资源或增加系统容量")
        kwargs.setdefault("recovery_actions", [ErrorRecoveryAction.RETRY, ErrorRecoveryAction.MANUAL])

        context = kwargs.setdefault("context", {})
        if self.resource_type:
            context["resource_type"] = self.resource_type
        if self.current_usage:
            context["current_usage"] = self.current_usage

        super().__init__(message, **kwargs)


# ===== 异常处理辅助函数 =====

def create_error_from_exception(exc: Exception, message: str = None, **kwargs) -> CCHooksError:
    """从标准异常创建CCHooks异常。

    Args:
        exc: 原始异常
        message: 自定义错误消息
        **kwargs: 其他参数

    Returns:
        CCHooks异常对象
    """
    error_message = message or str(exc)

    # 根据异常类型确定分类
    if isinstance(exc, (PermissionError, OSError)):
        return SystemError(
            error_message,
            original_error=exc,
            error_code="SYSTEM_OS_ERROR",
            **kwargs
        )
    elif isinstance(exc, FileNotFoundError):
        return UserError(
            error_message,
            original_error=exc,
            error_code="USER_FILE_NOT_FOUND",
            **kwargs
        )
    elif isinstance(exc, (ValueError, TypeError)):
        return UserError(
            error_message,
            original_error=exc,
            error_code="USER_INVALID_INPUT",
            **kwargs
        )
    elif isinstance(exc, ImportError):
        return ExternalError(
            error_message,
            original_error=exc,
            error_code="EXTERNAL_DEPENDENCY_MISSING",
            **kwargs
        )
    else:
        return InternalError(
            error_message,
            original_error=exc,
            error_code="INTERNAL_UNEXPECTED_ERROR",
            **kwargs
        )


def handle_exception_context(func: Callable) -> Callable:
    """装饰器：为函数提供异常上下文处理。

    Args:
        func: 被装饰的函数

    Returns:
        装饰后的函数
    """
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except CCHooksError:
            # 已经是CCHooks异常，直接重新抛出
            raise
        except Exception as e:
            # 转换为CCHooks异常
            error = create_error_from_exception(
                e,
                f"函数 {func.__name__} 执行失败: {str(e)}",
                context={
                    "function_name": func.__name__,
                    "module": func.__module__,
                    "args_count": len(args),
                    "kwargs_keys": list(kwargs.keys())
                }
            )
            raise error from e

    return wrapper


# ===== 向后兼容性别名 =====

# 保持现有代码的兼容性
CCHooksError.__doc__ = """CCHooks系统的基础异常类（向后兼容）。"""

# 导出的异常类型
__all__ = [
    # 枚举类型
    "ErrorSeverity",
    "ErrorCategory",
    "ErrorRecoveryAction",

    # 基础异常类
    "CCHooksError",

    # 分类异常类
    "UserError",
    "SystemError",
    "InternalError",
    "ExternalError",

    # 具体异常类
    "ConfigurationError",
    "InvalidArgumentError",
    "HookValidationError",
    "ValidationError",
    "DuplicateHookError",
    "PermissionError",
    "NetworkError",
    "DiskSpaceError",
    "EnvironmentError",
    "ParseError",
    "InvalidHookTypeError",
    "StateError",
    "TemplateError",
    "ExternalToolError",
    "TimeoutError",
    "DataIntegrityError",
    "SecurityError",
    "ResourceExhaustionError",

    # 辅助函数
    "create_error_from_exception",
    "handle_exception_context"
]
