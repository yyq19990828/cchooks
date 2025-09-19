"""cc_addhook命令实现 - T021任务

这个模块实现cc_addhook CLI命令，用于向Claude Code设置文件添加新的Hook配置。
支持shell命令和Python脚本两种类型，遵循CLI合约规范，提供完整的参数验证和错误处理。

主要功能：
1. 命令行参数解析和验证（基于argument_parser.py）
2. Hook配置创建和验证
3. 设置文件操作（使用api/settings_operations.py）
4. 脚本文件处理（auto-chmod等）
5. 输出格式化（JSON/table/quiet）
6. 错误处理和用户反馈
7. Dry-run模式支持

使用示例：
    cc_addhook PreToolUse --command "echo '工具执行前'" --matcher "Write"
    cc_addhook SessionStart --script "./hooks/session_start.py" --auto-chmod
    cc_addhook PostToolUse --command "python analyze.py" --dry-run --format json

依赖：
- api/settings_operations.py: 设置文件操作API
- utils/formatters.py: 输出格式化
- types/enums.py: 枚举类型定义
- cli/argument_parser.py: 参数解析
"""

import logging
import os
import stat
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ...api.settings_operations import SettingsModificationResult, add_hook_to_settings
from ...models.hook_config import HookConfiguration
from ...types.enums import HookEventType, OutputFormat
from ...utils.file_operations import validate_path_security
from ...utils.formatters import create_formatter


def validate_arguments(args) -> tuple[bool, List[str]]:
    """验证cc_addhook命令的参数

    Args:
        args: 解析后的命令行参数

    Returns:
        tuple: (是否有效, 错误消息列表)
    """
    errors = []

    # 验证必需参数
    if not hasattr(args, 'event') or not args.event:
        errors.append("事件类型(event)是必需的")

    # 验证command或script二选一
    if not hasattr(args, 'command') or not hasattr(args, 'script'):
        errors.append("必须指定--command或--script参数之一")
    elif not args.command and not args.script:
        errors.append("必须指定--command或--script参数之一")
    elif args.command and args.script:
        errors.append("不能同时指定--command和--script参数")

    # 验证事件类型
    try:
        event_type = HookEventType.from_string(args.event)

        # PreToolUse和PostToolUse需要matcher
        if event_type.requires_matcher() and not getattr(args, 'matcher', None):
            errors.append(f"{args.event}事件需要--matcher参数")
    except ValueError as e:
        errors.append(str(e))

    # 验证超时时间
    if hasattr(args, 'timeout') and args.timeout is not None:
        if args.timeout < 1 or args.timeout > 3600:
            errors.append("timeout必须在1-3600秒之间")

    # 验证脚本路径（如果指定）
    if args.script:
        try:
            script_path = Path(args.script)
            if not script_path.exists():
                errors.append(f"脚本文件不存在: {args.script}")
            elif not script_path.is_file():
                errors.append(f"脚本路径不是文件: {args.script}")
            else:
                # 验证路径安全性
                try:
                    validate_path_security(script_path)
                except Exception as e:
                    errors.append(f"脚本路径安全验证失败: {e}")
        except Exception as e:
            errors.append(f"脚本路径验证失败: {e}")

    # 验证输出格式
    if hasattr(args, 'format') and args.format:
        try:
            OutputFormat.from_string(args.format)
        except ValueError:
            errors.append(f"不支持的输出格式: {args.format}")

    return len(errors) == 0, errors


def handle_script_chmod(script_path: str, auto_chmod: bool) -> tuple[bool, Optional[str]]:
    """处理脚本文件的执行权限

    Args:
        script_path: 脚本文件路径
        auto_chmod: 是否自动设置执行权限

    Returns:
        tuple: (是否成功, 错误消息)
    """
    if not auto_chmod:
        return True, None

    try:
        path = Path(script_path)
        if not path.exists():
            return False, f"脚本文件不存在: {script_path}"

        # 检查当前权限
        current_mode = path.stat().st_mode

        # 如果已经有执行权限，跳过
        if current_mode & stat.S_IEXEC:
            return True, None

        # 添加执行权限（用户、组、其他）
        new_mode = current_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH
        path.chmod(new_mode)

        return True, None

    except Exception as e:
        return False, f"设置脚本执行权限失败: {e}"


def create_hook_config_dict(args) -> Dict[str, Any]:
    """根据命令行参数创建Hook配置字典

    Args:
        args: 解析后的命令行参数

    Returns:
        Hook配置字典
    """
    config = {
        "type": "command"  # 固定为Claude Code规范要求的"command"
    }

    # 设置命令
    if args.command:
        config["command"] = args.command
    elif args.script:
        # 将脚本路径转换为python调用命令
        script_path = str(Path(args.script).resolve())
        config["command"] = f"python \"{script_path}\""

    # 设置超时（可选）
    if hasattr(args, 'timeout') and args.timeout is not None:
        config["timeout"] = args.timeout

    return config


def execute_add_hook_command(args) -> int:
    """执行cc_addhook命令的核心逻辑

    Args:
        args: 解析后的命令行参数

    Returns:
        退出代码 (0=成功, 1=用户错误, 2=系统错误)
    """
    logger = logging.getLogger(__name__)

    try:
        # 1. 验证参数
        is_valid, errors = validate_arguments(args)
        if not is_valid:
            # 输出验证错误
            formatter = create_formatter(getattr(args, 'format', 'table'))
            output = formatter.format_command_result(
                success=False,
                message="参数验证失败",
                errors=errors
            )
            print(output)
            return 1

        # 2. 处理脚本权限（如果是脚本模式）
        if args.script and getattr(args, 'auto_chmod', True):
            chmod_success, chmod_error = handle_script_chmod(args.script, True)
            if not chmod_success:
                formatter = create_formatter(getattr(args, 'format', 'table'))
                output = formatter.format_command_result(
                    success=False,
                    message="脚本权限设置失败",
                    errors=[chmod_error] if chmod_error else []
                )
                print(output)
                return 2

        # 3. 创建Hook配置
        hook_config = create_hook_config_dict(args)

        # 4. 调用API添加Hook
        result = add_hook_to_settings(
            level=getattr(args, 'level', 'project'),
            hook_config=hook_config,
            matcher=getattr(args, 'matcher', None),
            event_type=args.event,
            dry_run=getattr(args, 'dry_run', False)
        )

        # 5. 准备输出数据
        success = result.success
        warnings = []
        errors = []

        # 准备data部分
        data = {}
        if success:
            data = {
                "hook": hook_config,
                "settings_file": str(result.affected_files[0]) if result.affected_files else "",
                "backup_created": len(result.backup_files) > 0
            }

            # 添加脚本相关信息
            if args.script:
                data["script_path"] = str(Path(args.script).resolve())
                data["auto_chmod_applied"] = getattr(args, 'auto_chmod', True)

        # 添加验证信息到warnings
        if result.validation_result and not result.validation_result.is_valid:
            for error in result.validation_result.errors:
                errors.append(f"验证错误: {error.message}")

            for warning in result.validation_result.warnings:
                warnings.append(f"验证警告: {warning.message}")

        # 6. 格式化并输出结果
        formatter = create_formatter(getattr(args, 'format', 'table'))
        output = formatter.format_command_result(
            success=success,
            message=result.message,
            data=data,
            warnings=warnings,
            errors=errors
        )

        print(output)

        # 7. 返回适当的退出代码
        if success:
            return 0
        else:
            # 判断是用户错误还是系统错误
            if any("验证" in err for err in errors) or any("参数" in err for err in errors):
                return 1  # 用户错误
            else:
                return 2  # 系统错误

    except KeyboardInterrupt:
        print("\n操作已取消", file=sys.stderr)
        return 130

    except Exception as e:
        logger.error(f"执行cc_addhook时发生未预期错误: {e}", exc_info=True)

        # 输出系统错误
        formatter = create_formatter(getattr(args, 'format', 'table'))
        output = formatter.format_command_result(
            success=False,
            message="系统内部错误",
            errors=[f"内部错误: {e}"]
        )
        print(output)
        return 2


def cc_addhook_main(args) -> int:
    """cc_addhook命令的主入口点

    这个函数将被cli/main.py调用以执行cc_addhook命令。

    Args:
        args: 解析后的命令行参数

    Returns:
        退出代码
    """
    # 设置日志
    logging.basicConfig(
        level=logging.WARNING,  # 默认只显示WARNING及以上级别
        format='%(levelname)s: %(message)s'
    )

    # 如果有debug标志，可以调整日志级别
    if hasattr(args, 'verbose') and args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    return execute_add_hook_command(args)


# 导出主要函数供testing使用
__all__ = [
    "cc_addhook_main",
    "validate_arguments",
    "handle_script_chmod",
    "create_hook_config_dict",
    "execute_add_hook_command"
]
