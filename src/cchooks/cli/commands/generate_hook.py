"""cc_generatehook命令实现

这个模块实现了cc_generatehook CLI命令，用于从预定义模板生成Python钩子脚本。
支持所有10种内置模板类型，提供丰富的自定义配置选项，并可选择性地自动添加到设置文件。

主要功能：
1. 参数处理和验证
2. 模板类型和事件类型兼容性检查
3. 自定义配置解析和验证
4. 脚本生成和文件写入
5. 执行权限设置
6. 可选的自动添加到settings.json
7. 详细的输出格式化

支持的模板类型：
- security-guard: 安全防护钩子
- auto-formatter: 自动格式化钩子
- auto-linter: 自动代码检查钩子
- git-auto-commit: Git自动提交钩子
- permission-logger: 权限记录钩子
- desktop-notifier: 桌面通知钩子
- task-manager: 任务管理钩子
- prompt-filter: 提示过滤钩子
- context-loader: 上下文加载钩子
- cleanup-handler: 清理处理钩子

命令用法：
    cc_generatehook <type> <event> <output> [options]

示例：
    cc_generatehook security-guard PreToolUse ./hooks/security.py --add-to-settings
    cc_generatehook auto-formatter PostToolUse ./format.py --matcher "Write"
    cc_generatehook context-loader SessionStart ./context.py --customization '{"paths": ["."]}'
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from ...api.settings_operations import add_hook_to_settings

# from ...utils.formatters import format_output, OutputFormat  # 将在后续实现中添加
from ...exceptions import CCHooksError
from ...services.script_generator import generate_hook_script, get_supported_templates


def main(args: argparse.Namespace) -> int:
    """cc_generatehook命令的主要入口点

    Args:
        args: 解析后的命令行参数

    Returns:
        int: 退出码 (0=成功, 1=用户错误, 2=系统错误)
    """
    logger = logging.getLogger(__name__)
    logger.info(f"执行cc_generatehook命令: {args}")

    try:
        # 1. 验证模板类型
        supported_templates = get_supported_templates()
        if args.type not in supported_templates:
            print(f"错误: 不支持的模板类型 '{args.type}'", file=sys.stderr)
            print(f"支持的模板类型: {', '.join(supported_templates)}", file=sys.stderr)
            return 1

        # 2. 解析自定义配置
        customization = {}
        if hasattr(args, 'customization') and args.customization:
            try:
                customization = json.loads(args.customization)
                if not isinstance(customization, dict):
                    print("错误: --customization 必须是JSON对象格式", file=sys.stderr)
                    return 1
            except json.JSONDecodeError as e:
                print(f"错误: --customization JSON格式无效: {e}", file=sys.stderr)
                return 1

        # 3. 验证matcher要求
        if args.event in ("PreToolUse", "PostToolUse") and not getattr(args, 'matcher', None):
            print(f"错误: {args.event} 事件类型需要 --matcher 参数", file=sys.stderr)
            return 1

        # 4. 生成脚本
        result = generate_hook_script(
            template_type=args.type,
            event_type=args.event,
            output_path=args.output,
            customization=customization,
            matcher=getattr(args, 'matcher', None),
            timeout=getattr(args, 'timeout', None),
            overwrite=getattr(args, 'overwrite', False)
        )

        # 5. 处理生成失败
        if not result.success:
            output_data = {
                "success": False,
                "message": result.message,
                "errors": result.errors
            }
            _print_output(output_data, getattr(args, 'format', 'table'))
            return 1

        # 6. 准备输出数据
        output_data = result.to_dict()
        output_data["added_to_settings"] = False

        # 7. 可选：添加到设置文件
        if getattr(args, 'add_to_settings', False):
            settings_result = _add_script_to_settings(
                script_path=result.generated_file,
                event_type=args.event,
                level=getattr(args, 'level', 'project'),
                matcher=getattr(args, 'matcher', None),
                timeout=getattr(args, 'timeout', None)
            )

            if settings_result.success:
                output_data["added_to_settings"] = True
                output_data["message"] += " 并已添加到设置文件"
            else:
                output_data["warnings"].extend([
                    "脚本生成成功，但添加到设置文件失败",
                    settings_result.message
                ])

        # 8. 输出结果
        _print_output(output_data, getattr(args, 'format', 'table'))
        return 0

    except KeyboardInterrupt:
        print("\n操作被中断", file=sys.stderr)
        return 130

    except Exception as e:
        logger.error(f"cc_generatehook执行失败: {e}")
        output_data = {
            "success": False,
            "message": f"命令执行失败: {e}",
            "errors": [str(e)]
        }
        _print_output(output_data, getattr(args, 'format', 'table'))
        return 2


def _add_script_to_settings(
    script_path: Path,
    event_type: str,
    level: str,
    matcher: Optional[str] = None,
    timeout: Optional[int] = None
) -> Any:
    """将生成的脚本添加到设置文件

    Args:
        script_path: 生成的脚本文件路径
        event_type: 钩子事件类型
        level: 设置级别
        matcher: 工具匹配器
        timeout: 执行超时

    Returns:
        SettingsModificationResult: 添加结果
    """
    logger = logging.getLogger(__name__)

    try:
        # 准备钩子配置
        hook_config = {
            "type": "command",
            "command": str(script_path.resolve())
        }

        if timeout:
            hook_config["timeout"] = timeout

        # 添加到设置文件
        return add_hook_to_settings(
            level=level,
            hook_config=hook_config,
            matcher=matcher,
            event_type=event_type,
            dry_run=False
        )

    except Exception as e:
        logger.error(f"添加脚本到设置文件失败: {e}")
        # 返回一个简单的失败结果对象
        class FailureResult:
            def __init__(self, message: str):
                self.success = False
                self.message = message

        return FailureResult(f"添加到设置文件失败: {e}")


def _print_output(data: Dict[str, Any], format_type: str) -> None:
    """格式化并打印输出

    Args:
        data: 要输出的数据
        format_type: 输出格式（table/json/quiet）
    """
    try:
        if format_type == "quiet":
            # 静默模式只输出错误
            if not data.get("success", False):
                print(data.get("message", "操作失败"), file=sys.stderr)
            return

        elif format_type == "json":
            # JSON格式输出
            print(json.dumps(data, indent=2, ensure_ascii=False))
            return

        else:
            # 表格格式输出（默认）
            _print_table_output(data)

    except Exception as e:
        # 输出格式化失败时的备用输出
        print(f"输出格式化失败: {e}", file=sys.stderr)
        print(f"原始数据: {data}", file=sys.stderr)


def _print_table_output(data: Dict[str, Any]) -> None:
    """以表格格式打印输出

    Args:
        data: 要输出的数据
    """
    if data.get("success", False):
        print("✓ 钩子脚本生成成功")
        print()

        # 生成的文件信息
        if data.get("generated_file"):
            print(f"生成的文件: {data['generated_file']}")

        if data.get("template_type"):
            print(f"模板类型: {data['template_type']}")

        if data.get("event_type"):
            print(f"事件类型: {data['event_type']}")

        print(f"可执行权限: {'是' if data.get('executable', False) else '否'}")

        if data.get("added_to_settings", False):
            print("已添加到设置文件: 是")
        else:
            print("已添加到设置文件: 否")

        # 警告信息
        warnings = data.get("warnings", [])
        if warnings:
            print()
            print("⚠️  警告:")
            for warning in warnings:
                print(f"  - {warning}")

    else:
        print("✗ 钩子脚本生成失败")
        print()
        print(f"错误: {data.get('message', '未知错误')}")

        # 详细错误信息
        errors = data.get("errors", [])
        if errors:
            print()
            print("详细错误:")
            for error in errors:
                print(f"  - {error}")


def cc_generatehook_main(args: argparse.Namespace) -> int:
    """cc_generatehook命令的主要入口点（与其他命令保持一致的命名）

    Args:
        args: 解析后的命令行参数

    Returns:
        int: 退出码
    """
    return main(args)


# 为了与其他CLI命令保持一致的接口
execute_generate_hook = main
create_command = lambda: main


if __name__ == "__main__":
    # 仅用于测试
    import sys

    from ..argument_parser import parse_args

    try:
        args = parse_args(["cc_generatehook"] + sys.argv[1:])
        exit_code = main(args)
        sys.exit(exit_code)
    except Exception as e:
        print(f"命令执行失败: {e}", file=sys.stderr)
        sys.exit(2)
