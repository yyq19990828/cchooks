"""设置文件发现和管理的异常模块。

本模块定义了设置发现和管理系统使用的自定义异常，提供清晰的错误报告。
现已集成核心异常系统，提供统一的中文用户友好消息和错误恢复机制。
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from ..exceptions import (
    CCHooksError,
    ErrorCategory,
    ErrorRecoveryAction,
    ErrorSeverity,
    InternalError,
    SystemError,
    UserError,
)


class SettingsError(UserError):
    """设置相关错误的基类。"""

    def __init__(self, message: str, path: Optional[Path] = None, **kwargs):
        """初始化设置错误。

        Args:
            message: 错误消息
            path: 相关的文件路径
            **kwargs: 其他参数
        """
        self.path = path
        kwargs.setdefault("error_code", "SETTINGS_ERROR")
        kwargs.setdefault("category", ErrorCategory.USER)
        kwargs.setdefault("severity", ErrorSeverity.MEDIUM)
        kwargs.setdefault("recovery_actions", [ErrorRecoveryAction.RETRY])

        if path:
            kwargs.setdefault("context", {})["settings_path"] = str(path)

        super().__init__(message, **kwargs)


class SettingsDiscoveryError(SettingsError):
    """设置文件发现过程中引发的异常。"""

    def __init__(self, message: str, start_path: Optional[Path] = None, **kwargs):
        """初始化发现错误。

        Args:
            message: 错误消息
            start_path: 开始搜索的路径
            **kwargs: 其他参数
        """
        self.start_path = start_path
        kwargs.setdefault("error_code", "SETTINGS_DISCOVERY_ERROR")
        kwargs.setdefault("suggested_fix", "检查目录结构和文件权限，确保settings.json文件存在")
        kwargs.setdefault("recovery_actions", [ErrorRecoveryAction.RETRY, ErrorRecoveryAction.MANUAL])

        if start_path:
            kwargs.setdefault("context", {})["start_path"] = str(start_path)

        super().__init__(message, start_path, **kwargs)


class SettingsFileNotFoundError(SettingsError):
    """找不到所需设置文件时引发的异常。"""

    def __init__(self, path: Path, level: Optional[str] = None, **kwargs):
        """初始化文件未找到错误。

        Args:
            path: 缺失文件的路径
            level: 可选的设置级别名称
            **kwargs: 其他参数
        """
        self.level = level
        level_info = f"（{level}级别）" if level else ""
        message = f"找不到设置文件{level_info}: {path}"

        kwargs.setdefault("error_code", "SETTINGS_FILE_NOT_FOUND")
        kwargs.setdefault("severity", ErrorSeverity.MEDIUM)

        # 根据级别提供不同的建议
        if level == "user":
            suggested_fix = f"创建用户设置文件：{path}\n或使用 'cchooks init --user' 初始化用户配置"
        elif level == "project":
            suggested_fix = f"创建项目设置文件：{path}\n或使用 'cchooks init --project' 初始化项目配置"
        else:
            suggested_fix = f"创建设置文件：{path}\n或使用 'cchooks init' 初始化配置"

        kwargs.setdefault("suggested_fix", suggested_fix)
        kwargs.setdefault("recovery_actions", [ErrorRecoveryAction.MANUAL])

        context = kwargs.setdefault("context", {})
        if level:
            context["settings_level"] = level

        super().__init__(message, path, **kwargs)


class SettingsPermissionError(SystemError):
    """设置文件操作因权限问题失败时引发的异常。"""

    def __init__(self, path: Path, operation: str, details: Optional[str] = None, **kwargs):
        """初始化权限错误。

        Args:
            path: 导致权限错误的路径
            operation: 失败的操作（读取、写入、创建等）
            details: 可选的附加详情
            **kwargs: 其他参数
        """
        self.operation = operation
        self.details = details

        operation_translations = {
            "read": "读取",
            "write": "写入",
            "create": "创建",
            "delete": "删除",
            "modify": "修改"
        }
        op_text = operation_translations.get(operation, operation)

        message = f"对设置文件执行{op_text}操作时权限被拒绝: {path}"
        if details:
            message += f"（{details}）"

        kwargs.setdefault("error_code", "SETTINGS_PERMISSION_DENIED")
        kwargs.setdefault("category", ErrorCategory.SYSTEM)
        kwargs.setdefault("severity", ErrorSeverity.HIGH)
        kwargs.setdefault("suggested_fix", f"检查文件权限或以管理员身份运行\n尝试: chmod 644 {path}")
        kwargs.setdefault("recovery_actions", [ErrorRecoveryAction.MANUAL])

        context = kwargs.setdefault("context", {})
        context["operation"] = operation
        if details:
            context["details"] = details

        super().__init__(message, **kwargs)


class SettingsValidationError(SettingsError):
    """设置文件内容验证失败时引发的异常。"""

    def __init__(self, path: Path, validation_errors: List[str], **kwargs):
        """初始化验证错误。

        Args:
            path: 无效设置文件的路径
            validation_errors: 验证错误消息列表
            **kwargs: 其他参数
        """
        self.validation_errors = validation_errors
        error_list = "\n  ".join(validation_errors)
        message = f"设置文件验证失败: {path}\n错误:\n  {error_list}"

        kwargs.setdefault("error_code", "SETTINGS_VALIDATION_FAILED")
        kwargs.setdefault("severity", ErrorSeverity.MEDIUM)
        kwargs.setdefault("suggested_fix", "修正设置文件中的验证错误\n检查JSON语法和必需字段")
        kwargs.setdefault("recovery_actions", [ErrorRecoveryAction.MANUAL, ErrorRecoveryAction.ROLLBACK])

        context = kwargs.setdefault("context", {})
        context["validation_errors"] = validation_errors
        context["error_count"] = len(validation_errors)

        super().__init__(message, path, **kwargs)


class SettingsCacheError(InternalError):
    """设置缓存操作失败时引发的异常。"""

    def __init__(self, message: str, cache_key: Optional[str] = None, **kwargs):
        """初始化缓存错误。

        Args:
            message: 错误消息
            cache_key: 可选的导致错误的缓存键
            **kwargs: 其他参数
        """
        self.cache_key = cache_key
        kwargs.setdefault("error_code", "SETTINGS_CACHE_ERROR")
        kwargs.setdefault("category", ErrorCategory.INTERNAL)
        kwargs.setdefault("severity", ErrorSeverity.LOW)
        kwargs.setdefault("suggested_fix", "清除设置缓存或重启应用程序")
        kwargs.setdefault("recovery_actions", [ErrorRecoveryAction.RETRY])

        if cache_key:
            kwargs.setdefault("context", {})["cache_key"] = cache_key

        super().__init__(message, **kwargs)


class SettingsDirectoryError(SystemError):
    """Claude目录操作失败时引发的异常。"""

    def __init__(self, path: Path, operation: str, reason: str, **kwargs):
        """初始化目录错误。

        Args:
            path: Claude目录的路径
            operation: 失败的操作
            reason: 失败原因
            **kwargs: 其他参数
        """
        self.operation = operation
        self.reason = reason

        operation_translations = {
            "create": "创建",
            "access": "访问",
            "write": "写入",
            "read": "读取"
        }
        op_text = operation_translations.get(operation, operation)

        message = f"无法{op_text}.claude目录: {path} - {reason}"

        kwargs.setdefault("error_code", "SETTINGS_DIRECTORY_ERROR")
        kwargs.setdefault("category", ErrorCategory.SYSTEM)
        kwargs.setdefault("severity", ErrorSeverity.HIGH)
        kwargs.setdefault("suggested_fix", f"检查目录权限并确保可以{op_text}目录\n或手动创建目录: mkdir -p {path}")
        kwargs.setdefault("recovery_actions", [ErrorRecoveryAction.MANUAL])

        context = kwargs.setdefault("context", {})
        context["operation"] = operation
        context["reason"] = reason

        super().__init__(message, **kwargs)


class SettingsConfigError(SettingsError):
    """设置配置无效时引发的异常。"""

    def __init__(self, message: str, config_key: Optional[str] = None, **kwargs):
        """初始化配置错误。

        Args:
            message: 错误消息
            config_key: 可选的导致错误的配置键
            **kwargs: 其他参数
        """
        self.config_key = config_key
        kwargs.setdefault("error_code", "SETTINGS_CONFIG_INVALID")
        kwargs.setdefault("severity", ErrorSeverity.MEDIUM)
        kwargs.setdefault("suggested_fix", "检查配置格式和值的有效性")
        kwargs.setdefault("recovery_actions", [ErrorRecoveryAction.MANUAL])

        if config_key:
            kwargs.setdefault("context", {})["config_key"] = config_key

        super().__init__(message, **kwargs)


# ===== 新增设置相关异常 =====

class SettingsBackupError(SystemError):
    """设置备份操作失败时引发的异常。"""

    def __init__(self, message: str, backup_path: Optional[Path] = None, original_path: Optional[Path] = None, **kwargs):
        """初始化备份错误。

        Args:
            message: 错误消息
            backup_path: 备份文件路径
            original_path: 原始文件路径
            **kwargs: 其他参数
        """
        self.backup_path = backup_path
        self.original_path = original_path
        kwargs.setdefault("error_code", "SETTINGS_BACKUP_ERROR")
        kwargs.setdefault("severity", ErrorSeverity.MEDIUM)
        kwargs.setdefault("suggested_fix", "检查磁盘空间和写入权限")
        kwargs.setdefault("recovery_actions", [ErrorRecoveryAction.MANUAL])

        context = kwargs.setdefault("context", {})
        if backup_path:
            context["backup_path"] = str(backup_path)
        if original_path:
            context["original_path"] = str(original_path)

        super().__init__(message, **kwargs)


class SettingsCorruptionError(InternalError):
    """设置文件损坏时引发的异常。"""

    def __init__(self, message: str, corruption_type: str = None, **kwargs):
        """初始化损坏错误。

        Args:
            message: 错误消息
            corruption_type: 损坏类型（json、encoding等）
            **kwargs: 其他参数
        """
        self.corruption_type = corruption_type
        kwargs.setdefault("error_code", "SETTINGS_FILE_CORRUPTED")
        kwargs.setdefault("severity", ErrorSeverity.HIGH)
        kwargs.setdefault("suggested_fix", "从备份恢复设置文件或重新创建")
        kwargs.setdefault("recovery_actions", [ErrorRecoveryAction.ROLLBACK, ErrorRecoveryAction.MANUAL])

        if corruption_type:
            kwargs.setdefault("context", {})["corruption_type"] = corruption_type

        super().__init__(message, **kwargs)


class SettingsVersionError(UserError):
    """设置文件版本不兼容时引发的异常。"""

    def __init__(self, message: str, current_version: str = None, required_version: str = None, **kwargs):
        """初始化版本错误。

        Args:
            message: 错误消息
            current_version: 当前版本
            required_version: 所需版本
            **kwargs: 其他参数
        """
        self.current_version = current_version
        self.required_version = required_version
        kwargs.setdefault("error_code", "SETTINGS_VERSION_INCOMPATIBLE")
        kwargs.setdefault("severity", ErrorSeverity.MEDIUM)
        kwargs.setdefault("suggested_fix", "升级设置文件格式或使用兼容版本的工具")
        kwargs.setdefault("recovery_actions", [ErrorRecoveryAction.MANUAL])

        context = kwargs.setdefault("context", {})
        if current_version:
            context["current_version"] = current_version
        if required_version:
            context["required_version"] = required_version

        super().__init__(message, **kwargs)


# ===== 设置异常处理辅助函数 =====

def create_settings_recovery_suggestion(error: SettingsError) -> str:
    """为设置错误创建恢复建议。

    Args:
        error: 设置错误对象

    Returns:
        恢复建议字符串
    """
    suggestions = []

    if isinstance(error, SettingsFileNotFoundError):
        suggestions.append("使用 'cchooks init' 创建默认设置文件")
        if error.level:
            suggestions.append(f"检查{error.level}级别的配置路径")

    elif isinstance(error, SettingsValidationError):
        suggestions.append("使用 'cchooks validate' 检查设置文件")
        suggestions.append("参考文档中的设置文件示例")

    elif isinstance(error, SettingsPermissionError):
        suggestions.append(f"检查文件权限: ls -la {error.path}")
        suggestions.append("确保当前用户有相应的文件操作权限")

    elif isinstance(error, SettingsCorruptionError):
        suggestions.append("从 .claude/backups/ 目录恢复备份文件")
        suggestions.append("重新创建设置文件")

    else:
        suggestions.append("检查设置文件的格式和内容")
        suggestions.append("参考官方文档")

    return "\n".join(f"• {suggestion}" for suggestion in suggestions)


def is_settings_recoverable(error: SettingsError) -> bool:
    """判断设置错误是否可恢复。

    Args:
        error: 设置错误对象

    Returns:
        是否可恢复
    """
    # 权限错误和目录错误通常需要手动干预
    if isinstance(error, (SettingsPermissionError, SettingsDirectoryError)):
        return False

    # 缓存错误通常可以通过重试恢复
    if isinstance(error, SettingsCacheError):
        return True

    # 文件未找到可以通过创建文件恢复
    if isinstance(error, SettingsFileNotFoundError):
        return True

    # 其他错误需要具体分析
    return error.is_recoverable()


# ===== 导出列表 =====

__all__ = [
    # 基础异常类
    "SettingsError",
    "SettingsDiscoveryError",
    "SettingsFileNotFoundError",
    "SettingsPermissionError",
    "SettingsValidationError",
    "SettingsCacheError",
    "SettingsDirectoryError",
    "SettingsConfigError",
    # 新增异常类
    "SettingsBackupError",
    "SettingsCorruptionError",
    "SettingsVersionError",
    # 辅助函数
    "create_settings_recovery_suggestion",
    "is_settings_recoverable"
]
