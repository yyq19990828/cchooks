"""cc_removehook命令实现 - T023

此模块实现cc_removehook CLI命令，用于从Claude Code设置文件中删除Hook配置。
遵循contracts/cli_commands.yaml规范，提供安全、可靠的Hook删除功能。

主要功能：
1. 命令参数处理和验证
2. Hook查找和验证存在性
3. 删除前的Hook信息展示
4. 支持干运行模式预览操作
5. 自动清理空的事件节点
6. 索引处理（支持正负索引）
7. 安全确认机制
8. 符合CLI合约的输出格式

依赖组件：
- 参数解析：使用cli/argument_parser.py的解析结果
- Hook删除：调用api/settings_operations.py的remove_hook_from_settings
- 输出格式化：使用utils/formatters.py的格式化器
- 数据模型：使用models中的Hook配置和验证结果

输出符合CLI合约的removed_hook数据结构，包含删除的Hook配置详情和统计信息。
"""

import json
import logging
import sys
from argparse import Namespace
from typing import Any, Dict, List, NoReturn, Optional

# 核心API导入
from ...api.settings_operations import (
    SettingsModificationResult,
    find_and_load_settings,
    list_hooks_from_settings,
    remove_hook_from_settings,
)
from ...exceptions import CCHooksError

# 数据模型导入
from ...models.hook_config import HookConfiguration
from ...models.settings_file import SettingsFile
from ...types.enums import HookEventType, SettingsLevel

# 工具导入
from ...utils.formatters import create_formatter

# 设置日志记录
logger = logging.getLogger(__name__)


def _find_hook_by_index(
    hooks: List[HookConfiguration],
    event_type: str,
    index: int
) -> tuple[HookConfiguration, int]:
    """根据索引查找Hook配置

    Args:
        hooks: Hook配置列表（按事件类型过滤）
        event_type: 事件类型
        index: Hook索引（支持负数）

    Returns:
        tuple: (找到的Hook配置, 实际索引)

    Raises:
        ValueError: 当索引无效时
    """
    if not hooks:
        raise ValueError(f"事件类型 {event_type} 下没有Hook配置")

    # 处理负索引
    if index < 0:
        index = len(hooks) + index

    # 验证索引范围
    if index < 0 or index >= len(hooks):
        raise ValueError(f"索引 {index} 超出范围，有效范围：0-{len(hooks)-1}")

    return hooks[index], index


def _display_hook_info(hook: HookConfiguration, index: int, event_type: str) -> None:
    """显示即将删除的Hook信息

    Args:
        hook: Hook配置
        index: Hook索引
        event_type: 事件类型
    """
    print(f"\n即将删除的Hook配置 (事件: {event_type}, 索引: {index}):")
    print(f"  类型: {hook.type}")
    print(f"  命令: {hook.command}")
    if hook.timeout:
        print(f"  超时: {hook.timeout}秒")
    if hook.matcher:
        print(f"  匹配器: {hook.matcher}")
    print()


def _confirm_deletion(hook: HookConfiguration, index: int, event_type: str) -> bool:
    """确认删除操作

    Args:
        hook: Hook配置
        index: Hook索引
        event_type: 事件类型

    Returns:
        bool: 用户确认删除
    """
    _display_hook_info(hook, index, event_type)

    try:
        response = input("确认删除此Hook配置？[y/N]: ").strip().lower()
        return response in ['y', 'yes', '是']
    except (EOFError, KeyboardInterrupt):
        print("\n操作已取消")
        return False


def _validate_arguments(args: Namespace) -> None:
    """验证命令参数

    Args:
        args: 解析后的命令行参数

    Raises:
        ValueError: 参数验证失败时
    """
    # 验证事件类型
    try:
        HookEventType.from_string(args.event)
    except ValueError:
        raise ValueError(f"无效的事件类型: {args.event}")

    # 验证设置级别
    try:
        SettingsLevel.from_string(args.level)
    except ValueError:
        raise ValueError(f"无效的设置级别: {args.level}")

    # 验证索引
    if args.index < 0:
        logger.info(f"使用负索引: {args.index}")


def _format_success_output(
    removed_hook: HookConfiguration,
    settings_file_path: str,
    backup_created: bool,
    dry_run: bool = False
) -> Dict[str, Any]:
    """格式化成功输出数据

    Args:
        removed_hook: 删除的Hook配置
        settings_file_path: 设置文件路径
        backup_created: 是否创建了备份
        dry_run: 是否为干运行模式

    Returns:
        Dict: 符合CLI合约的输出数据
    """
    return {
        "success": True,
        "message": f"{'预览：将' if dry_run else '成功'}删除Hook配置",
        "data": {
            "removed_hook": {
                "type": removed_hook.type,
                "command": removed_hook.command,
                **({"timeout": removed_hook.timeout} if removed_hook.timeout else {})
            },
            "settings_file": settings_file_path,
            "backup_created": backup_created and not dry_run
        },
        "warnings": [],
        "errors": []
    }


def _format_error_output(message: str) -> Dict[str, Any]:
    """格式化错误输出数据

    Args:
        message: 错误消息

    Returns:
        Dict: 符合CLI合约的错误输出数据
    """
    return {
        "success": False,
        "message": message,
        "errors": [message]
    }


def execute_remove_hook(args: Namespace) -> int:
    """执行cc_removehook命令的核心逻辑

    Args:
        args: 解析后的命令行参数

    Returns:
        int: 退出码 (0=成功, 1=用户错误, 2=系统错误)
    """
    try:
        # 1. 验证参数
        _validate_arguments(args)

        logger.info(f"开始删除Hook - 事件: {args.event}, 索引: {args.index}, 级别: {args.level}")

        # 2. 查找设置文件
        settings_files = find_and_load_settings(args.level)
        if not settings_files:
            result = _format_error_output(f"未找到级别为 {args.level} 的设置文件")
            formatter = create_formatter(args.format)
            output = formatter.format_command_result(**result)
            print(output)
            return 1

        # 3. 列出指定事件类型的Hooks
        hooks = list_hooks_from_settings(args.level, args.event)
        if not hooks:
            result = _format_error_output(f"事件类型 {args.event} 下没有Hook配置")
            formatter = create_formatter(args.format)
            output = formatter.format_command_result(**result)
            print(output)
            return 1

        # 4. 根据索引查找Hook
        try:
            target_hook, actual_index = _find_hook_by_index(hooks, args.event, args.index)
        except ValueError as e:
            result = _format_error_output(str(e))
            formatter = create_formatter(args.format)
            output = formatter.format_command_result(**result)
            print(output)
            return 1

        # 5. 干运行模式 - 只显示预览
        if args.dry_run:
            # 只在非quiet和非json模式下显示详细信息
            if args.format not in ["quiet", "json"]:
                _display_hook_info(target_hook, actual_index, args.event)

            result = _format_success_output(
                target_hook,
                str(settings_files[0].path),
                args.backup,
                dry_run=True
            )
            formatter = create_formatter(args.format)
            output = formatter.format_command_result(**result)
            print(output)
            return 0

        # 6. 非quiet和非json模式显示Hook信息并确认
        if args.format not in ["quiet", "json"]:
            if not _confirm_deletion(target_hook, actual_index, args.event):
                print("操作已取消")
                return 0

        # 7. 执行删除操作
        modification_result = remove_hook_from_settings(
            level=args.level,
            event_type=args.event,
            index=actual_index,
            dry_run=False
        )

        if not modification_result.success:
            result = _format_error_output(modification_result.message)
            formatter = create_formatter(args.format)
            output = formatter.format_command_result(**result)
            print(output)
            return 1

        # 8. 格式化成功输出
        result = _format_success_output(
            target_hook,
            str(settings_files[0].path),
            bool(modification_result.backup_files),
            dry_run=False
        )

        formatter = create_formatter(args.format)
        formatter.format_command_result(**result)

        logger.info(f"成功删除Hook - 事件: {args.event}, 索引: {actual_index}")
        return 0

    except ValueError as e:
        print(f"输出格式化错误: {e}", file=sys.stderr)
        return 2
    except CCHooksError as e:
        result = _format_error_output(f"CCHooks错误: {e}")
        try:
            formatter = create_formatter(args.format)
            output = formatter.format_command_result(**result)
            print(output)
        except:
            print(f"错误: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        logger.error(f"删除Hook时发生未预期错误: {e}")
        result = _format_error_output(f"未预期错误: {e}")
        try:
            formatter = create_formatter(args.format)
            output = formatter.format_command_result(**result)
            print(output)
        except:
            print(f"错误: {e}", file=sys.stderr)
        return 2


def main_remove_hook() -> NoReturn:
    """cc_removehook命令的主入口点

    这个函数被cli/main.py中的cc_removehook调用。
    处理参数解析、日志设置和错误处理。
    """
    # 设置日志级别
    logging.basicConfig(level=logging.INFO)

    try:
        # 注意：参数已经在main.py中解析，这里直接使用
        # 由于我们在main.py调用时会传递args，这里暂时模拟
        # 实际集成时会从main.py接收args参数
        print("cc_removehook命令实现 - 请通过main.py调用")
        sys.exit(1)

    except KeyboardInterrupt:
        print("\n操作被用户中断", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        logger.error(f"cc_removehook命令执行失败: {e}")
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main_remove_hook()
