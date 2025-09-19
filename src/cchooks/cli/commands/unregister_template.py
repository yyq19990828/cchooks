"""cc_unregistertemplate命令实现 - T037任务

这个模块实现cc_unregistertemplate CLI命令，用于从TemplateRegistry注销自定义模板。
防止注销内置模板，遵循CLI合约规范，提供完整的参数验证和错误处理。

主要功能：
1. 命令行参数解析和验证（基于argument_parser.py）
2. 模板存在性验证
3. TemplateRegistry集成
4. 内置模板保护
5. 输出格式化（JSON/table/quiet）
6. 错误处理和用户反馈
7. 确认机制支持

使用示例：
    cc_unregistertemplate --name "custom-security"
    cc_unregistertemplate --name "my-template" --global --force
    cc_unregistertemplate --name "test-template" --format json

依赖：
- templates/registry.py: TemplateRegistry服务
- templates/base_template.py: BaseTemplate基类
- utils/formatters.py: 输出格式化
- types/enums.py: 枚举类型定义
"""

import json
import sys
from typing import Any, Dict, List, Optional

from ...exceptions import CCHooksError
from ...templates.registry import (
    HookTemplate,
    TemplateRegistry,
    TemplateRegistryError,
    get_template_registry,
)
from ...types.enums import TemplateSource


def validate_arguments(args) -> tuple[bool, List[str]]:
    """验证cc_unregistertemplate命令的参数

    Args:
        args: 解析后的命令行参数

    Returns:
        tuple[bool, List[str]]: (是否有效, 错误消息列表)
    """
    errors = []

    # 验证模板名称
    if not hasattr(args, 'name') or not args.name:
        errors.append("模板名称 (--name) 是必需的")
    elif not args.name.replace("-", "").replace("_", "").isalnum():
        errors.append("模板名称只能包含字母、数字、连字符和下划线")

    # 验证输出格式
    if hasattr(args, 'format') and args.format:
        valid_formats = ["json", "table", "quiet"]
        if args.format not in valid_formats:
            errors.append(f"无效的输出格式: {args.format}. 有效值: {', '.join(valid_formats)}")

    return len(errors) == 0, errors


def check_template_exists(registry: TemplateRegistry, template_name: str) -> tuple[bool, Optional[HookTemplate], List[str]]:
    """检查模板是否存在

    Args:
        registry: 模板注册表实例
        template_name: 模板名称

    Returns:
        tuple[bool, Optional[HookTemplate], List[str]]: (是否存在, 模板对象, 错误消息)
    """
    errors = []
    template = None

    try:
        template = registry.get_template(template_name)
        return True, template, []
    except TemplateRegistryError:
        errors.append(f"模板 '{template_name}' 不存在")
        return False, None, errors
    except Exception as e:
        errors.append(f"检查模板时发生错误: {str(e)}")
        return False, None, errors


def validate_template_unregistration(template: HookTemplate) -> tuple[bool, List[str]]:
    """验证模板是否可以注销

    Args:
        template: 模板对象

    Returns:
        tuple[bool, List[str]]: (是否可以注销, 错误消息)
    """
    errors = []

    # 检查是否为内置模板
    if template.source == TemplateSource.BUILTIN:
        errors.append(f"不能注销内置模板 '{template.template_id}'")

    return len(errors) == 0, errors


def confirm_unregistration(template_name: str, force: bool) -> bool:
    """确认模板注销操作

    Args:
        template_name: 模板名称
        force: 是否强制执行

    Returns:
        bool: 用户是否确认
    """
    if force:
        return True

    try:
        response = input(f"确定要注销模板 '{template_name}' 吗？此操作不可逆。(y/N): ")
        return response.lower() in ['y', 'yes', '是']
    except (EOFError, KeyboardInterrupt):
        return False


def unregister_template_from_registry(
    registry: TemplateRegistry,
    template_name: str,
    global_registry: bool = False,
    force: bool = False
) -> tuple[bool, Optional[Dict[str, Any]], List[str]]:
    """从注册表注销模板

    Args:
        registry: 模板注册表实例
        template_name: 模板名称
        global_registry: 是否从全局注册表注销
        force: 是否强制执行

    Returns:
        tuple[bool, Optional[Dict[str, Any]], List[str]]: (成功状态, 模板信息, 错误消息)
    """
    errors = []
    template_info = None

    try:
        # 1. 检查模板是否存在
        exists, template, check_errors = check_template_exists(registry, template_name)
        if not exists:
            return False, None, check_errors

        # 2. 验证是否可以注销
        can_unregister, validation_errors = validate_template_unregistration(template)
        if not can_unregister:
            return False, None, validation_errors

        # 3. 确认操作
        if not confirm_unregistration(template_name, force):
            errors.append("用户取消了注销操作")
            return False, None, errors

        # 4. 记录模板信息
        template_info = {
            "unregistered_template": template.template_id,
            "registry_location": "global" if global_registry else "project"
        }

        # 5. 执行注销
        registry.unregister_template(template_name)

        return True, template_info, []

    except TemplateRegistryError as e:
        errors.append(f"注销模板失败: {str(e)}")
    except Exception as e:
        errors.append(f"注销模板时发生错误: {str(e)}")

    return False, None, errors


def format_output(
    success: bool,
    template_info: Optional[Dict[str, Any]],
    errors: List[str],
    warnings: List[str],
    format_type: str
) -> str:
    """格式化输出结果

    Args:
        success: 操作是否成功
        template_info: 模板信息
        errors: 错误消息列表
        warnings: 警告消息列表
        format_type: 输出格式

    Returns:
        str: 格式化后的输出
    """
    if format_type == "json":
        result = {
            "success": success,
            "message": "模板注销成功" if success else "模板注销失败",
            "data": template_info if success else None,
            "warnings": warnings,
            "errors": errors
        }
        return json.dumps(result, indent=2, ensure_ascii=False)

    elif format_type == "quiet":
        # 静默模式只输出错误
        if errors:
            return "\n".join(errors)
        return ""

    else:  # table format
        lines = []

        if success and template_info:
            lines.append("✓ 模板注销成功")
            lines.append("")
            lines.append("注销信息:")
            lines.append(f"  模板ID: {template_info['unregistered_template']}")
            lines.append(f"  注册位置: {template_info['registry_location']}")
        else:
            lines.append("✗ 模板注销失败")

        if warnings:
            lines.append("")
            lines.append("警告:")
            for warning in warnings:
                lines.append(f"  - {warning}")

        if errors:
            lines.append("")
            lines.append("错误:")
            for error in errors:
                lines.append(f"  - {error}")

        return "\n".join(lines)


def cc_unregistertemplate_main(args) -> int:
    """cc_unregistertemplate命令的主要执行函数

    Args:
        args: 解析后的命令行参数

    Returns:
        int: 退出代码 (0=成功, 1=用户错误, 2=系统错误)
    """
    warnings = []

    try:
        # 1. 验证参数
        is_valid, validation_errors = validate_arguments(args)
        if not is_valid:
            output = format_output(False, None, validation_errors, [], getattr(args, 'format', 'table'))
            print(output)
            return 1

        # 2. 获取模板注册表
        try:
            registry = get_template_registry()
        except Exception as e:
            error = f"获取模板注册表失败: {str(e)}"
            output = format_output(False, None, [error], [], getattr(args, 'format', 'table'))
            print(output)
            return 2

        # 3. 注销模板
        success, template_info, unreg_errors = unregister_template_from_registry(
            registry=registry,
            template_name=args.name,
            global_registry=getattr(args, 'global', False),
            force=getattr(args, 'force', False)
        )

        if not success:
            # 检查是否是用户取消操作
            if any("用户取消" in error for error in unreg_errors):
                output = format_output(False, None, unreg_errors, warnings, getattr(args, 'format', 'table'))
                print(output)
                return 0  # 用户取消不算错误
            else:
                output = format_output(False, None, unreg_errors, warnings, getattr(args, 'format', 'table'))
                print(output)
                return 1

        # 4. 输出结果
        output = format_output(success, template_info, [], warnings, getattr(args, 'format', 'table'))
        print(output)
        return 0

    except KeyboardInterrupt:
        print("\n操作被用户中断", file=sys.stderr)
        return 130
    except Exception as e:
        error = f"系统错误: {str(e)}"
        output = format_output(False, None, [error], [], getattr(args, 'format', 'table'))
        print(output)
        return 2


# 为兼容性提供的别名
main = cc_unregistertemplate_main
