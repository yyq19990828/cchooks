"""cc_updatehook命令实现 - T022实现

基于contracts/cli_commands.yaml规范实现Hook更新功能。

主要功能：
1. 根据事件类型和索引查找现有Hook
2. 验证并应用部分更新（只更新指定字段）
3. 保持其他Hook配置不变
4. 支持索引验证和负索引
5. 提供dry-run模式预览更改
6. 创建备份并保存更新

支持的更新字段：
- --command: 更新shell命令
- --matcher: 更新工具匹配模式
- --timeout: 更新执行超时时间

命令格式：
cc_updatehook EVENT INDEX [--command COMMAND] [--matcher MATCHER]
           [--timeout TIMEOUT] [--level LEVEL] [--format FORMAT]
           [--dry-run] [--backup]

示例：
cc_updatehook PreToolUse 0 --command "echo 'Updated hook'" --timeout 120
cc_updatehook PostToolUse 1 --matcher "Write" --dry-run
"""

import logging
import sys
from argparse import Namespace
from typing import Any, Dict, List, Optional

from ...api.settings_operations import (
    SettingsModificationResult,
    find_and_load_settings,
    list_hooks_from_settings,
    update_hook_in_settings,
)
from ...exceptions import CCHooksError
from ...types.enums import HookEventType
from ...utils.formatters import create_formatter


def execute_update_hook(args: Namespace) -> int:
    """执行cc_updatehook命令的核心逻辑。

    Args:
        args: 解析后的命令行参数

    Returns:
        退出代码：0=成功, 1=用户错误, 2=系统错误
    """
    logger = logging.getLogger(__name__)

    try:
        # 1. 验证参数
        logger.info(f"开始更新Hook: event={args.event}, index={args.index}")

        validation_result = _validate_update_arguments(args)
        if not validation_result["valid"]:
            return _handle_error(
                validation_result["message"],
                validation_result.get("errors", []),
                args.format,
                exit_code=1
            )

        # 2. 查找现有Hook以验证索引
        existing_hooks = list_hooks_from_settings(
            level=args.level,
            event_filter=args.event
        )

        index_result = _validate_hook_index(args.index, existing_hooks, args.event)
        if not index_result["valid"]:
            return _handle_error(
                index_result["message"],
                [index_result["message"]],
                args.format,
                exit_code=1
            )

        # 3. 构建更新字典
        updates = _build_update_dict(args)
        if not updates:
            return _handle_error(
                "未指定要更新的字段，请提供 --command、--matcher 或 --timeout 参数",
                ["至少需要指定一个更新字段"],
                args.format,
                exit_code=1
            )

        logger.info(f"应用更新: {updates}")

        # 4. 执行更新操作
        result = update_hook_in_settings(
            level=args.level,
            event_type=args.event,
            index=args.index,
            updates=updates,
            dry_run=args.dry_run
        )

        # 5. 处理结果并输出
        if result.success:
            return _handle_success(result, args.format, updates)
        else:
            return _handle_error(
                result.message,
                [result.message],
                args.format,
                exit_code=2 if "系统" in result.message or "文件" in result.message else 1
            )

    except Exception as e:
        logger.error(f"更新Hook时发生未预期错误: {e}")
        return _handle_error(
            f"更新Hook失败: {e}",
            [str(e)],
            args.format,
            exit_code=2
        )


def _validate_update_arguments(args: Namespace) -> Dict[str, Any]:
    """验证更新命令的参数。

    Args:
        args: 命令行参数

    Returns:
        验证结果字典
    """
    errors = []

    # 验证事件类型
    try:
        HookEventType.from_string(args.event)
    except ValueError:
        errors.append(f"无效的事件类型: {args.event}")

    # 验证索引
    if args.index < 0:
        errors.append(f"索引不能为负数: {args.index}")

    # 验证timeout范围
    if hasattr(args, 'timeout') and args.timeout is not None:
        if args.timeout < 1 or args.timeout > 3600:
            errors.append(f"timeout必须在1-3600秒范围内: {args.timeout}")

    # 验证至少提供了一个更新字段
    update_fields_provided = any([
        hasattr(args, 'command') and args.command is not None,
        hasattr(args, 'matcher') and args.matcher is not None,
        hasattr(args, 'timeout') and args.timeout is not None
    ])

    if not update_fields_provided:
        errors.append("必须指定至少一个更新字段: --command, --matcher, 或 --timeout")

    return {
        "valid": len(errors) == 0,
        "message": "参数验证失败" if errors else "参数验证通过",
        "errors": errors
    }


def _validate_hook_index(index: int, hooks: List[Any], event_type: str) -> Dict[str, Any]:
    """验证Hook索引是否有效。

    Args:
        index: 要验证的索引
        hooks: Hook列表 (HookConfiguration对象列表)
        event_type: 事件类型

    Returns:
        验证结果字典
    """
    # 筛选出指定事件类型的hooks
    event_hooks = []
    for hook in hooks:
        # 处理HookConfiguration对象
        if hasattr(hook, 'event_type') and hook.event_type:
            hook_event = hook.event_type.value if hasattr(hook.event_type, 'value') else str(hook.event_type)
        else:
            # 回退：尝试从dict形式获取
            hook_event = hook.get("event") if hasattr(hook, 'get') else None

        if hook_event == event_type:
            event_hooks.append(hook)

    if not event_hooks:
        return {
            "valid": False,
            "message": f"未找到事件类型为 {event_type} 的Hook配置"
        }

    if index >= len(event_hooks):
        return {
            "valid": False,
            "message": f"索引 {index} 超出范围，{event_type} 事件只有 {len(event_hooks)} 个Hook"
        }

    return {
        "valid": True,
        "message": f"找到索引 {index} 的Hook配置"
    }


def _build_update_dict(args: Namespace) -> Dict[str, Any]:
    """构建更新字典，只包含明确指定的字段。

    Args:
        args: 命令行参数

    Returns:
        更新字典
    """
    updates = {}

    if hasattr(args, 'command') and args.command is not None:
        updates['command'] = args.command

    if hasattr(args, 'matcher') and args.matcher is not None:
        updates['matcher'] = args.matcher

    if hasattr(args, 'timeout') and args.timeout is not None:
        updates['timeout'] = args.timeout

    return updates


def _handle_success(
    result: SettingsModificationResult,
    output_format: str,
    updates: Dict[str, Any]
) -> int:
    """处理成功的更新结果。

    Args:
        result: 更新操作结果
        output_format: 输出格式
        updates: 应用的更新

    Returns:
        退出代码0
    """
    formatter = create_formatter(output_format)

    # 构建输出数据
    data = {
        "updated_fields": updates,
        "affected_files": [str(p) for p in result.affected_files],
        "backup_files": [str(p) for p in result.backup_files],
        "hooks_modified": result.hooks_modified,
        "dry_run": result.dry_run
    }

    # 添加验证信息
    if result.validation_result:
        data["validation"] = result.validation_result.to_dict()

    # 格式化输出
    output = formatter.format_command_result(
        success=True,
        message=result.message,
        data=data,
        warnings=[],
        errors=[]
    )

    print(output)
    return 0


def _handle_error(
    message: str,
    errors: List[str],
    output_format: str,
    exit_code: int
) -> int:
    """处理错误情况。

    Args:
        message: 错误消息
        errors: 错误列表
        output_format: 输出格式
        exit_code: 退出代码

    Returns:
        指定的退出代码
    """
    formatter = create_formatter(output_format)

    output = formatter.format_command_result(
        success=False,
        message=message,
        data={},
        warnings=[],
        errors=errors
    )

    print(output, file=sys.stderr)
    return exit_code


def _show_hook_diff(
    original_hook: Dict[str, Any],
    updated_hook: Dict[str, Any]
) -> str:
    """显示Hook更新前后的差异。

    Args:
        original_hook: 原始Hook配置
        updated_hook: 更新后Hook配置

    Returns:
        差异说明字符串
    """
    diff_lines = ["Hook配置变更:"]

    # 检查每个字段的变化
    all_fields = set(original_hook.keys()) | set(updated_hook.keys())

    for field in sorted(all_fields):
        original_value = original_hook.get(field, "<未设置>")
        updated_value = updated_hook.get(field, "<未设置>")

        if original_value != updated_value:
            diff_lines.append(f"  {field}: {original_value} → {updated_value}")

    return "\n".join(diff_lines)


def _get_hook_summary(hook: Dict[str, Any]) -> str:
    """获取Hook的简要描述。

    Args:
        hook: Hook配置字典

    Returns:
        Hook描述字符串
    """
    parts = []

    if hook.get("type"):
        parts.append(f"类型={hook['type']}")

    if hook.get("command"):
        command = hook["command"]
        if len(command) > 50:
            command = command[:47] + "..."
        parts.append(f"命令={command}")

    if hook.get("matcher"):
        parts.append(f"匹配器={hook['matcher']}")

    if hook.get("timeout"):
        parts.append(f"超时={hook['timeout']}s")

    return ", ".join(parts) if parts else "未知Hook配置"


# 为了与add_hook.py等其他命令保持一致的接口
def main(args: Namespace) -> int:
    """cc_updatehook命令的主入口点。

    Args:
        args: 解析后的命令行参数

    Returns:
        退出代码
    """
    # 配置日志
    logging.basicConfig(
        level=logging.INFO if args.format != "quiet" else logging.WARNING,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    return execute_update_hook(args)


# 导出的公共接口
__all__ = ["main", "execute_update_hook"]
