"""CLI特定异常模块，为命令行界面提供专门的错误处理。

本模块扩展核心异常系统，为CLI命令提供特定的异常类型和错误处理机制。
所有CLI异常都继承自核心异常系统，确保统一的错误处理和用户体验。

主要功能：
1. CLI命令特定异常
2. 参数解析和验证错误
3. 命令执行状态错误
4. 用户交互错误
5. 批量操作错误
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ..exceptions import (
    ConfigurationError,
    ErrorCategory,
    ErrorRecoveryAction,
    ErrorSeverity,
    InternalError,
    InvalidArgumentError,
    SystemError,
    UserError,
)

# ===== CLI命令错误 =====

class CLIError(UserError):
    """CLI命令错误的基类。"""

    def __init__(self, message: str, command_name: str = None, **kwargs):
        self.command_name = command_name
        kwargs.setdefault("error_code", "CLI_COMMAND_ERROR")
        kwargs.setdefault("suggested_fix", "请检查命令语法和参数，使用 --help 查看帮助信息")
        kwargs.setdefault("recovery_actions", [ErrorRecoveryAction.RETRY])
        kwargs.setdefault("help_url", "https://claude.ai/docs/hooks/cli-commands")

        if self.command_name:
            kwargs.setdefault("context", {})["command_name"] = self.command_name
            # 为特定命令生成更详细的帮助URL
            base_url = kwargs.get("help_url", "https://claude.ai/docs/hooks/cli-commands")
            kwargs["help_url"] = f"{base_url}#{self.command_name}"

        super().__init__(message, **kwargs)


class CommandNotFoundError(CLIError):
    """命令未找到错误。"""

    def __init__(self, command_name: str, available_commands: List[str] = None, **kwargs):
        self.available_commands = available_commands or []
        message = f"未知命令: {command_name}"
        if self.available_commands:
            message += f"\n可用命令: {', '.join(self.available_commands)}"

        kwargs.setdefault("error_code", "CLI_COMMAND_NOT_FOUND")
        kwargs.setdefault("severity", ErrorSeverity.LOW)
        kwargs.setdefault("recovery_actions", [ErrorRecoveryAction.RETRY])

        suggested_fix = "请检查命令名称是否正确"
        if self.available_commands:
            suggested_fix += f"，可用命令包括: {', '.join(self.available_commands[:3])}"
            if len(self.available_commands) > 3:
                suggested_fix += " 等"
            suggested_fix += "\n使用 'cchooks --help' 查看所有可用命令"
        kwargs.setdefault("suggested_fix", suggested_fix)

        context = kwargs.setdefault("context", {})
        context["available_commands"] = self.available_commands
        context["command_similarity"] = self._find_similar_commands(command_name, self.available_commands)

        super().__init__(message, command_name, **kwargs)

    def _find_similar_commands(self, command: str, available: List[str], threshold: float = 0.6) -> List[str]:
        """查找相似的命令名称。"""
        if not available:
            return []

        def similarity(a: str, b: str) -> float:
            """计算两个字符串的相似度。"""
            if not a or not b:
                return 0.0
            # 简单的相似度计算：基于字符重叠
            common = set(a.lower()) & set(b.lower())
            union = set(a.lower()) | set(b.lower())
            return len(common) / len(union) if union else 0.0

        similar = []
        for cmd in available:
            if similarity(command, cmd) >= threshold:
                similar.append(cmd)

        return similar[:3]  # 最多返回3个相似命令


class CommandSyntaxError(CLIError):
    """命令语法错误。"""

    def __init__(self, message: str, command_name: str = None, expected_syntax: str = None, **kwargs):
        self.expected_syntax = expected_syntax
        kwargs.setdefault("error_code", "CLI_SYNTAX_ERROR")

        suggested_fix = "请检查命令语法"
        if self.expected_syntax:
            suggested_fix += f"\n正确语法: {self.expected_syntax}"
        if command_name:
            suggested_fix += f"\n使用 '{command_name} --help' 查看详细帮助"
        kwargs.setdefault("suggested_fix", suggested_fix)

        if self.expected_syntax:
            kwargs.setdefault("context", {})["expected_syntax"] = self.expected_syntax

        super().__init__(message, command_name, **kwargs)


class MissingRequiredArgumentError(InvalidArgumentError):
    """缺少必需参数错误。"""

    def __init__(self, argument_name: str, command_name: str = None, **kwargs):
        message = f"缺少必需参数: {argument_name}"
        kwargs.setdefault("error_code", "CLI_MISSING_ARGUMENT")

        suggested_fix = f"请提供必需参数 '{argument_name}'"
        if command_name:
            suggested_fix += f"\n使用 '{command_name} --help' 查看参数说明"
        kwargs.setdefault("suggested_fix", suggested_fix)

        kwargs.setdefault("context", {})["command_name"] = command_name

        super().__init__(message, argument_name, **kwargs)


class InvalidArgumentValueError(InvalidArgumentError):
    """无效参数值错误。"""

    def __init__(self, argument_name: str, provided_value: str,
                 valid_values: List[str] = None, value_type: str = None, **kwargs):
        self.provided_value = provided_value
        self.value_type = value_type

        message = f"参数 '{argument_name}' 的值无效: {provided_value}"
        if valid_values:
            message += f"\n有效值: {', '.join(valid_values)}"
        elif value_type:
            message += f"\n预期类型: {value_type}"

        kwargs.setdefault("error_code", "CLI_INVALID_ARGUMENT_VALUE")

        suggested_fix = f"请为参数 '{argument_name}' 提供有效值"
        if valid_values:
            suggested_fix += f": {', '.join(valid_values)}"

        kwargs.setdefault("suggested_fix", suggested_fix)

        context = kwargs.setdefault("context", {})
        context["provided_value"] = provided_value
        if value_type:
            context["value_type"] = value_type

        super().__init__(message, argument_name, valid_values, **kwargs)


# ===== 文件和路径相关错误 =====

class CLIFileError(CLIError):
    """CLI文件操作错误。"""

    def __init__(self, message: str, file_path: Union[str, Path] = None,
                 operation: str = None, **kwargs):
        self.file_path = Path(file_path) if file_path else None
        self.operation = operation

        kwargs.setdefault("error_code", "CLI_FILE_ERROR")
        kwargs.setdefault("suggested_fix", "请检查文件路径和权限")

        context = kwargs.setdefault("context", {})
        if self.file_path:
            context["file_path"] = str(self.file_path)
        if self.operation:
            context["operation"] = self.operation

        super().__init__(message, **kwargs)


class SettingsFileError(CLIFileError):
    """设置文件相关错误。"""

    def __init__(self, message: str, settings_level: str = None, **kwargs):
        self.settings_level = settings_level
        kwargs.setdefault("error_code", "CLI_SETTINGS_FILE_ERROR")
        kwargs.setdefault("suggested_fix", "请检查设置文件是否存在且格式正确")

        if self.settings_level:
            kwargs.setdefault("context", {})["settings_level"] = self.settings_level

        super().__init__(message, operation="设置文件操作", **kwargs)


class HookScriptError(CLIFileError):
    """钩子脚本相关错误。"""

    def __init__(self, message: str, script_path: Union[str, Path] = None,
                 hook_type: str = None, **kwargs):
        self.script_path = Path(script_path) if script_path else None
        self.hook_type = hook_type

        kwargs.setdefault("error_code", "CLI_HOOK_SCRIPT_ERROR")
        kwargs.setdefault("suggested_fix", "请检查钩子脚本文件和执行权限")

        context = kwargs.setdefault("context", {})
        if self.hook_type:
            context["hook_type"] = self.hook_type

        super().__init__(message, self.script_path, "钩子脚本操作", **kwargs)


# ===== 操作执行错误 =====

class OperationError(CLIError):
    """操作执行错误基类。"""

    def __init__(self, message: str, operation_name: str = None, **kwargs):
        self.operation_name = operation_name
        kwargs.setdefault("error_code", "CLI_OPERATION_ERROR")
        kwargs.setdefault("suggested_fix", "请重试操作，如问题持续请检查系统状态")

        if self.operation_name:
            kwargs.setdefault("context", {})["operation_name"] = self.operation_name

        super().__init__(message, **kwargs)


class HookAddError(OperationError):
    """添加钩子失败错误。"""

    def __init__(self, message: str, hook_config: Dict[str, Any] = None, **kwargs):
        self.hook_config = hook_config
        kwargs.setdefault("error_code", "CLI_HOOK_ADD_ERROR")
        kwargs.setdefault("suggested_fix", "请检查钩子配置和目标设置文件")

        if self.hook_config:
            context = kwargs.setdefault("context", {})
            context["hook_type"] = self.hook_config.get("type")
            context["hook_command"] = self.hook_config.get("command")

        super().__init__(message, "添加钩子", **kwargs)


class HookUpdateError(OperationError):
    """更新钩子失败错误。"""

    def __init__(self, message: str, hook_index: int = None, **kwargs):
        self.hook_index = hook_index
        kwargs.setdefault("error_code", "CLI_HOOK_UPDATE_ERROR")
        kwargs.setdefault("suggested_fix", "请检查钩子索引和新配置")

        if self.hook_index is not None:
            kwargs.setdefault("context", {})["hook_index"] = self.hook_index

        super().__init__(message, "更新钩子", **kwargs)


class HookRemoveError(OperationError):
    """移除钩子失败错误。"""

    def __init__(self, message: str, hook_identifier: Union[int, str] = None, **kwargs):
        self.hook_identifier = hook_identifier
        kwargs.setdefault("error_code", "CLI_HOOK_REMOVE_ERROR")
        kwargs.setdefault("suggested_fix", "请检查钩子索引或标识符")

        if self.hook_identifier is not None:
            kwargs.setdefault("context", {})["hook_identifier"] = str(self.hook_identifier)

        super().__init__(message, "移除钩子", **kwargs)


class HookValidationError(OperationError):
    """钩子验证失败错误。"""

    def __init__(self, message: str, validation_errors: List[str] = None, **kwargs):
        self.validation_errors = validation_errors or []
        kwargs.setdefault("error_code", "CLI_HOOK_VALIDATION_ERROR")
        kwargs.setdefault("suggested_fix", "请修复验证错误后重试")

        if self.validation_errors:
            kwargs.setdefault("context", {})["validation_errors"] = self.validation_errors

        super().__init__(message, "钩子验证", **kwargs)


# ===== 模板相关错误 =====

class TemplateError(CLIError):
    """模板操作错误基类。"""

    def __init__(self, message: str, template_id: str = None, **kwargs):
        self.template_id = template_id
        kwargs.setdefault("error_code", "CLI_TEMPLATE_ERROR")
        kwargs.setdefault("suggested_fix", "请检查模板配置和可用性")

        if self.template_id:
            kwargs.setdefault("context", {})["template_id"] = self.template_id

        super().__init__(message, **kwargs)


class TemplateNotFoundError(TemplateError):
    """模板未找到错误。"""

    def __init__(self, template_id: str, available_templates: List[str] = None, **kwargs):
        self.available_templates = available_templates or []
        message = f"未找到模板: {template_id}"
        if self.available_templates:
            message += f"\n可用模板: {', '.join(self.available_templates)}"

        kwargs.setdefault("error_code", "CLI_TEMPLATE_NOT_FOUND")
        suggested_fix = "请检查模板ID是否正确"
        if self.available_templates:
            suggested_fix += f"，可用模板: {', '.join(self.available_templates[:3])}"
            if len(self.available_templates) > 3:
                suggested_fix += " 等"
        kwargs.setdefault("suggested_fix", suggested_fix)

        kwargs.setdefault("context", {})["available_templates"] = self.available_templates

        super().__init__(message, template_id, **kwargs)


class TemplateGenerationError(TemplateError):
    """模板生成错误。"""

    def __init__(self, message: str, template_id: str = None,
                 generation_step: str = None, **kwargs):
        self.generation_step = generation_step
        kwargs.setdefault("error_code", "CLI_TEMPLATE_GENERATION_ERROR")
        kwargs.setdefault("suggested_fix", "请检查模板配置和生成参数")

        if self.generation_step:
            kwargs.setdefault("context", {})["generation_step"] = self.generation_step

        super().__init__(message, template_id, **kwargs)


# ===== 批量操作错误 =====

class BatchOperationError(CLIError):
    """批量操作错误。"""

    def __init__(self, message: str, operation_type: str = None,
                 failed_items: List[str] = None, total_items: int = None, **kwargs):
        self.operation_type = operation_type
        self.failed_items = failed_items or []
        self.total_items = total_items

        kwargs.setdefault("error_code", "CLI_BATCH_OPERATION_ERROR")
        suggested_fix = "请检查失败的项目并重试"
        if self.failed_items:
            suggested_fix += f"\n失败项目: {', '.join(self.failed_items[:3])}"
            if len(self.failed_items) > 3:
                suggested_fix += f" 等（共{len(self.failed_items)}项）"
        kwargs.setdefault("suggested_fix", suggested_fix)

        context = kwargs.setdefault("context", {})
        if self.operation_type:
            context["operation_type"] = self.operation_type
        if self.failed_items:
            context["failed_items"] = self.failed_items
        if self.total_items is not None:
            context["total_items"] = self.total_items
            context["success_count"] = self.total_items - len(self.failed_items)

        super().__init__(message, **kwargs)


# ===== 用户交互错误 =====

class UserInteractionError(CLIError):
    """用户交互错误。"""

    def __init__(self, message: str, interaction_type: str = None, **kwargs):
        self.interaction_type = interaction_type
        kwargs.setdefault("error_code", "CLI_USER_INTERACTION_ERROR")
        kwargs.setdefault("suggested_fix", "请重新执行命令并提供正确的输入")

        if self.interaction_type:
            kwargs.setdefault("context", {})["interaction_type"] = self.interaction_type

        super().__init__(message, **kwargs)


class UserCancelledError(UserInteractionError):
    """用户取消操作错误。"""

    def __init__(self, operation_name: str = None, **kwargs):
        message = "用户取消了操作"
        if operation_name:
            message = f"用户取消了{operation_name}操作"

        kwargs.setdefault("error_code", "CLI_USER_CANCELLED")
        kwargs.setdefault("suggested_fix", "操作已取消，如需继续请重新执行命令")
        kwargs.setdefault("severity", "low")

        super().__init__(message, "用户取消", **kwargs)


class ConfirmationTimeoutError(UserInteractionError):
    """确认超时错误。"""

    def __init__(self, timeout_seconds: int = None, **kwargs):
        self.timeout_seconds = timeout_seconds
        message = "等待用户确认超时"
        if timeout_seconds:
            message += f"（{timeout_seconds}秒）"

        kwargs.setdefault("error_code", "CLI_CONFIRMATION_TIMEOUT")
        kwargs.setdefault("suggested_fix", "请重新执行命令并及时进行确认")

        if self.timeout_seconds:
            kwargs.setdefault("context", {})["timeout_seconds"] = self.timeout_seconds

        super().__init__(message, "确认超时", **kwargs)


# ===== CLI性能和监控异常 =====

class CLIPerformanceError(CLIError):
    """CLI性能相关错误。"""

    def __init__(self, message: str, operation: str = None, duration_ms: int = None, **kwargs):
        self.operation = operation
        self.duration_ms = duration_ms
        kwargs.setdefault("error_code", "CLI_PERFORMANCE_ERROR")
        kwargs.setdefault("severity", ErrorSeverity.MEDIUM)
        kwargs.setdefault("suggested_fix", "优化操作参数或检查系统资源")
        kwargs.setdefault("recovery_actions", [ErrorRecoveryAction.RETRY, ErrorRecoveryAction.SKIP])

        context = kwargs.setdefault("context", {})
        if self.operation:
            context["operation"] = self.operation
        if self.duration_ms:
            context["duration_ms"] = self.duration_ms

        super().__init__(message, **kwargs)


class CLIResourceError(CLIError):
    """CLI资源使用错误。"""

    def __init__(self, message: str, resource_type: str = None, limit_exceeded: bool = False, **kwargs):
        self.resource_type = resource_type
        self.limit_exceeded = limit_exceeded
        kwargs.setdefault("error_code", "CLI_RESOURCE_ERROR")
        kwargs.setdefault("severity", ErrorSeverity.HIGH if limit_exceeded else ErrorSeverity.MEDIUM)
        kwargs.setdefault("suggested_fix", "减少资源使用或调整系统限制")
        kwargs.setdefault("recovery_actions", [ErrorRecoveryAction.MANUAL])

        context = kwargs.setdefault("context", {})
        if self.resource_type:
            context["resource_type"] = self.resource_type
        context["limit_exceeded"] = self.limit_exceeded

        super().__init__(message, **kwargs)


class CLIVersionCompatibilityError(CLIError):
    """CLI版本兼容性错误。"""

    def __init__(self, message: str, required_version: str = None, current_version: str = None, **kwargs):
        self.required_version = required_version
        self.current_version = current_version
        kwargs.setdefault("error_code", "CLI_VERSION_COMPATIBILITY")
        kwargs.setdefault("severity", ErrorSeverity.HIGH)
        kwargs.setdefault("suggested_fix", "升级到兼容版本或使用兼容性模式")
        kwargs.setdefault("recovery_actions", [ErrorRecoveryAction.MANUAL])

        context = kwargs.setdefault("context", {})
        if self.required_version:
            context["required_version"] = self.required_version
        if self.current_version:
            context["current_version"] = self.current_version

        super().__init__(message, **kwargs)


class CLIConfigurationMigrationError(CLIError):
    """CLI配置迁移错误。"""

    def __init__(self, message: str, from_version: str = None, to_version: str = None, **kwargs):
        self.from_version = from_version
        self.to_version = to_version
        kwargs.setdefault("error_code", "CLI_CONFIG_MIGRATION")
        kwargs.setdefault("severity", ErrorSeverity.MEDIUM)
        kwargs.setdefault("suggested_fix", "手动调整配置或使用迁移工具")
        kwargs.setdefault("recovery_actions", [ErrorRecoveryAction.ROLLBACK, ErrorRecoveryAction.MANUAL])

        context = kwargs.setdefault("context", {})
        if self.from_version:
            context["from_version"] = self.from_version
        if self.to_version:
            context["to_version"] = self.to_version

        super().__init__(message, **kwargs)


# ===== CLI异常处理辅助函数 =====

def create_cli_usage_error(command_name: str, expected_usage: str, provided_args: List[str] = None) -> CommandSyntaxError:
    """创建CLI用法错误。

    Args:
        command_name: 命令名称
        expected_usage: 期望的用法
        provided_args: 提供的参数

    Returns:
        命令语法错误对象
    """
    message = f"命令 '{command_name}' 用法错误"
    if provided_args:
        message += f"\n提供的参数: {' '.join(provided_args)}"

    return CommandSyntaxError(
        message=message,
        command_name=command_name,
        expected_syntax=expected_usage,
        context={"provided_args": provided_args or []}
    )


def suggest_command_alternatives(invalid_command: str, available_commands: List[str]) -> List[str]:
    """为无效命令建议替代方案。

    Args:
        invalid_command: 无效的命令
        available_commands: 可用命令列表

    Returns:
        建议的命令列表
    """
    suggestions = []

    # 精确匹配
    for cmd in available_commands:
        if invalid_command in cmd or cmd in invalid_command:
            suggestions.append(cmd)

    # 如果没有精确匹配，使用模糊匹配
    if not suggestions:
        def levenshtein_distance(s1: str, s2: str) -> int:
            """计算两个字符串的编辑距离。"""
            if len(s1) > len(s2):
                s1, s2 = s2, s1

            distances = range(len(s1) + 1)
            for i2, c2 in enumerate(s2):
                distances_ = [i2 + 1]
                for i1, c1 in enumerate(s1):
                    if c1 == c2:
                        distances_.append(distances[i1])
                    else:
                        distances_.append(1 + min((distances[i1], distances[i1 + 1], distances_[-1])))
                distances = distances_
            return distances[-1]

        # 找出编辑距离最小的命令
        command_distances = [(cmd, levenshtein_distance(invalid_command.lower(), cmd.lower()))
                           for cmd in available_commands]
        command_distances.sort(key=lambda x: x[1])

        # 只返回编辑距离较小的命令
        max_distance = min(3, len(invalid_command) // 2)
        suggestions = [cmd for cmd, dist in command_distances if dist <= max_distance]

    return suggestions[:3]  # 最多返回3个建议


# ===== 导出的异常类型列表 =====

__all__ = [
    # CLI基础错误
    "CLIError",
    "CommandNotFoundError",
    "CommandSyntaxError",
    "MissingRequiredArgumentError",
    "InvalidArgumentValueError",
    # 文件操作错误
    "CLIFileError",
    "SettingsFileError",
    "HookScriptError",
    # 操作执行错误
    "OperationError",
    "HookAddError",
    "HookUpdateError",
    "HookRemoveError",
    "HookValidationError",
    # 模板错误
    "TemplateError",
    "TemplateNotFoundError",
    "TemplateGenerationError",
    # 批量操作错误
    "BatchOperationError",
    # 用户交互错误
    "UserInteractionError",
    "UserCancelledError",
    "ConfirmationTimeoutError",
    # 性能和监控错误
    "CLIPerformanceError",
    "CLIResourceError",
    "CLIVersionCompatibilityError",
    "CLIConfigurationMigrationError",
    # 辅助函数
    "create_cli_usage_error",
    "suggest_command_alternatives"
]
