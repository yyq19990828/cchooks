"""cc_listtemplates命令实现 - T036任务

这个模块实现cc_listtemplates CLI命令，用于列出所有可用的钩子模板（内置和用户注册）。
支持按事件类型和来源过滤，遵循CLI合约规范，提供完整的参数验证和错误处理。

主要功能：
1. 命令行参数解析和验证（基于argument_parser.py）
2. 模板查询和过滤
3. TemplateRegistry集成
4. 模板分组和统计
5. 输出格式化（JSON/table/yaml）
6. 错误处理和用户反馈
7. 显示自定义选项支持

使用示例：
    cc_listtemplates
    cc_listtemplates --event PreToolUse --source builtin
    cc_listtemplates --show-config --format json
    cc_listtemplates --source user --format yaml

依赖：
- templates/registry.py: TemplateRegistry服务
- templates/base_template.py: BaseTemplate基类
- utils/formatters.py: 输出格式化
- types/enums.py: 枚举类型定义
"""

import json
import sys
from collections import defaultdict
from typing import Any, Dict, List, Optional, Union

from ...exceptions import CCHooksError
from ...templates.registry import (
    HookTemplate,
    TemplateRegistry,
    TemplateRegistryError,
    get_template_registry,
)
from ...types.enums import HookEventType, OutputFormat, TemplateSource
from ...utils.formatters import create_formatter


def validate_arguments(args) -> tuple[bool, List[str]]:
    """验证cc_listtemplates命令的参数

    Args:
        args: 解析后的命令行参数

    Returns:
        tuple[bool, List[str]]: (是否有效, 错误消息列表)
    """
    errors = []

    # 验证事件类型过滤器
    if hasattr(args, 'event') and args.event:
        valid_events = [event.value for event in HookEventType]
        if args.event not in valid_events:
            errors.append(f"无效的事件类型: {args.event}. 有效值: {', '.join(valid_events)}")

    # 验证来源过滤器
    if hasattr(args, 'source') and args.source:
        valid_sources = [source.value for source in TemplateSource] + ["all"]
        if args.source not in valid_sources:
            errors.append(f"无效的模板来源: {args.source}. 有效值: {', '.join(valid_sources)}")

    # 验证输出格式
    if hasattr(args, 'format') and args.format:
        valid_formats = ["json", "table", "yaml"]
        if args.format not in valid_formats:
            errors.append(f"无效的输出格式: {args.format}. 有效值: {', '.join(valid_formats)}")

    return len(errors) == 0, errors


def query_templates(
    registry: TemplateRegistry,
    event_filter: Optional[str] = None,
    source_filter: Optional[str] = None
) -> tuple[List[HookTemplate], Dict[str, Any], List[str]]:
    """查询模板列表

    Args:
        registry: 模板注册表实例
        event_filter: 事件类型过滤器
        source_filter: 来源过滤器

    Returns:
        tuple[List[HookTemplate], Dict[str, Any], List[str]]: (模板列表, 统计信息, 错误消息)
    """
    errors = []
    templates = []
    stats = {}

    try:
        # 转换过滤器参数
        event_type = None
        if event_filter:
            try:
                event_type = HookEventType.from_string(event_filter)
            except ValueError:
                errors.append(f"无效的事件类型: {event_filter}")
                return [], {}, errors

        source_type = None
        if source_filter and source_filter != "all":
            try:
                source_type = TemplateSource.from_string(source_filter)
            except ValueError:
                errors.append(f"无效的模板来源: {source_filter}")
                return [], {}, errors

        # 获取模板列表
        templates = registry.list_templates(
            event_filter=event_type,
            source_filter=source_type
        )

        # 生成统计信息
        stats = generate_template_stats(templates, registry)

    except Exception as e:
        errors.append(f"查询模板失败: {str(e)}")

    return templates, stats, errors


def generate_template_stats(templates: List[HookTemplate], registry: TemplateRegistry) -> Dict[str, Any]:
    """生成模板统计信息

    Args:
        templates: 模板列表
        registry: 模板注册表实例

    Returns:
        Dict[str, Any]: 统计信息
    """
    # 按来源分组
    by_source = defaultdict(int)
    for template in templates:
        by_source[template.source.value] += 1

    # 按事件类型分组
    by_event = defaultdict(int)
    for template in templates:
        for event in template.supported_events:
            by_event[event.value] += 1

    # 获取注册表总体统计
    registry_stats = registry.get_registry_stats()

    return {
        "total_count": len(templates),
        "by_source": dict(by_source),
        "by_event": dict(by_event),
        "registry_stats": registry_stats
    }


def convert_template_to_dict(template: HookTemplate, show_config: bool = False) -> Dict[str, Any]:
    """将模板转换为字典格式

    Args:
        template: 模板对象
        show_config: 是否显示自定义配置选项

    Returns:
        Dict[str, Any]: 模板字典
    """
    result = {
        "template_id": template.template_id,
        "name": template.name,
        "description": template.description,
        "supported_events": [event.value for event in template.supported_events],
        "version": template.version,
        "source": template.source.value,
        "dependencies": template.dependencies.copy()
    }

    if show_config:
        result["customization_options"] = template.customization_options.copy()

    return result


def format_output_json(
    templates: List[HookTemplate],
    stats: Dict[str, Any],
    show_config: bool,
    errors: List[str],
    warnings: List[str]
) -> str:
    """格式化JSON输出

    Args:
        templates: 模板列表
        stats: 统计信息
        show_config: 是否显示配置选项
        errors: 错误消息
        warnings: 警告消息

    Returns:
        str: JSON格式输出
    """
    result = {
        "success": len(errors) == 0,
        "message": f"找到 {len(templates)} 个模板" if len(errors) == 0 else "查询模板失败",
        "data": {
            "templates": [convert_template_to_dict(t, show_config) for t in templates],
            "total_count": stats.get("total_count", 0),
            "by_source": stats.get("by_source", {}),
            "by_event": stats.get("by_event", {})
        },
        "warnings": warnings,
        "errors": errors
    }
    return json.dumps(result, indent=2, ensure_ascii=False)


def format_output_yaml(
    templates: List[HookTemplate],
    stats: Dict[str, Any],
    show_config: bool,
    errors: List[str],
    warnings: List[str]
) -> str:
    """格式化YAML输出

    Args:
        templates: 模板列表
        stats: 统计信息
        show_config: 是否显示配置选项
        errors: 错误消息
        warnings: 警告消息

    Returns:
        str: YAML格式输出
    """
    lines = []

    # 基本信息
    lines.append("success: true" if len(errors) == 0 else "success: false")
    lines.append(f"message: \"找到 {len(templates)} 个模板\"" if len(errors) == 0 else "message: \"查询模板失败\"")
    lines.append("")

    # 数据部分
    lines.append("data:")
    lines.append(f"  total_count: {stats.get('total_count', 0)}")
    lines.append("")

    # 按来源统计
    lines.append("  by_source:")
    by_source = stats.get("by_source", {})
    for source, count in sorted(by_source.items()):
        lines.append(f"    {source}: {count}")
    lines.append("")

    # 按事件统计
    lines.append("  by_event:")
    by_event = stats.get("by_event", {})
    for event, count in sorted(by_event.items()):
        lines.append(f"    {event}: {count}")
    lines.append("")

    # 模板列表
    lines.append("  templates:")
    for template in templates:
        lines.append(f"    - template_id: \"{template.template_id}\"")
        lines.append(f"      name: \"{template.name}\"")
        lines.append(f"      description: \"{template.description}\"")
        lines.append(f"      version: \"{template.version}\"")
        lines.append(f"      source: \"{template.source.value}\"")
        lines.append("      supported_events:")
        for event in template.supported_events:
            lines.append(f"        - \"{event.value}\"")
        lines.append("      dependencies:")
        for dep in template.dependencies:
            lines.append(f"        - \"{dep}\"")

        if show_config and template.customization_options:
            lines.append("      customization_options:")
            for key, value in template.customization_options.items():
                lines.append(f"        {key}: {json.dumps(value)}")
        lines.append("")

    # 错误和警告
    if warnings:
        lines.append("warnings:")
        for warning in warnings:
            lines.append(f"  - \"{warning}\"")
        lines.append("")

    if errors:
        lines.append("errors:")
        for error in errors:
            lines.append(f"  - \"{error}\"")

    return "\n".join(lines)


def format_output_table(
    templates: List[HookTemplate],
    stats: Dict[str, Any],
    show_config: bool,
    errors: List[str],
    warnings: List[str]
) -> str:
    """格式化表格输出

    Args:
        templates: 模板列表
        stats: 统计信息
        show_config: 是否显示配置选项
        errors: 错误消息
        warnings: 警告消息

    Returns:
        str: 表格格式输出
    """
    lines = []

    if errors:
        lines.append("✗ 查询模板失败")
        lines.append("")
        lines.append("错误:")
        for error in errors:
            lines.append(f"  - {error}")
        return "\n".join(lines)

    # 标题和总计
    lines.append(f"✓ 找到 {len(templates)} 个可用模板")
    lines.append("")

    # 统计信息
    lines.append("统计信息:")
    lines.append(f"  总数: {stats.get('total_count', 0)}")

    by_source = stats.get("by_source", {})
    if by_source:
        lines.append("  按来源分布:")
        for source, count in sorted(by_source.items()):
            source_name = {
                "builtin": "内置",
                "user": "用户",
                "file": "文件",
                "plugin": "插件"
            }.get(source, source)
            lines.append(f"    {source_name}: {count}")

    by_event = stats.get("by_event", {})
    if by_event:
        lines.append("  按事件类型分布:")
        for event, count in sorted(by_event.items()):
            lines.append(f"    {event}: {count}")

    lines.append("")

    # 模板列表
    if templates:
        lines.append("模板列表:")
        lines.append("")

        for i, template in enumerate(templates, 1):
            lines.append(f"{i}. {template.name} ({template.template_id})")
            lines.append(f"   描述: {template.description}")
            lines.append(f"   版本: {template.version}")
            lines.append(f"   来源: {template.source.value}")
            lines.append(f"   支持事件: {', '.join(event.value for event in template.supported_events)}")

            if template.dependencies:
                lines.append(f"   依赖: {', '.join(template.dependencies)}")

            if show_config and template.customization_options:
                lines.append("   自定义选项:")
                for key, schema in template.customization_options.items():
                    option_type = schema.get("type", "unknown")
                    description = schema.get("description", "")
                    lines.append(f"     - {key} ({option_type}): {description}")

            lines.append("")

    # 警告
    if warnings:
        lines.append("警告:")
        for warning in warnings:
            lines.append(f"  - {warning}")

    return "\n".join(lines)


def format_output(
    templates: List[HookTemplate],
    stats: Dict[str, Any],
    show_config: bool,
    format_type: str,
    errors: List[str],
    warnings: List[str]
) -> str:
    """格式化输出结果

    Args:
        templates: 模板列表
        stats: 统计信息
        show_config: 是否显示配置选项
        format_type: 输出格式
        errors: 错误消息
        warnings: 警告消息

    Returns:
        str: 格式化后的输出
    """
    if format_type == "json":
        return format_output_json(templates, stats, show_config, errors, warnings)
    elif format_type == "yaml":
        return format_output_yaml(templates, stats, show_config, errors, warnings)
    else:  # table format
        return format_output_table(templates, stats, show_config, errors, warnings)


def cc_listtemplates_main(args) -> int:
    """cc_listtemplates命令的主要执行函数

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
            output = format_output([], {}, False, getattr(args, 'format', 'table'), validation_errors, [])
            print(output)
            return 1

        # 2. 获取模板注册表
        try:
            registry = get_template_registry()
        except Exception as e:
            error = f"获取模板注册表失败: {str(e)}"
            output = format_output([], {}, False, getattr(args, 'format', 'table'), [error], [])
            print(output)
            return 2

        # 3. 查询模板
        templates, stats, query_errors = query_templates(
            registry=registry,
            event_filter=getattr(args, 'event', None),
            source_filter=getattr(args, 'source', None)
        )

        if query_errors:
            output = format_output([], {}, False, getattr(args, 'format', 'table'), query_errors, warnings)
            print(output)
            return 2

        # 4. 输出结果
        show_config = getattr(args, 'show_config', False)
        output = format_output(
            templates=templates,
            stats=stats,
            show_config=show_config,
            format_type=getattr(args, 'format', 'table'),
            errors=[],
            warnings=warnings
        )
        print(output)

        # 返回码：如果没有找到模板但没有错误，返回1
        if not templates and not query_errors:
            return 1

        return 0

    except KeyboardInterrupt:
        print("\n操作被用户中断", file=sys.stderr)
        return 130
    except Exception as e:
        error = f"系统错误: {str(e)}"
        output = format_output([], {}, False, getattr(args, 'format', 'table'), [error], [])
        print(output)
        return 2


# 为兼容性提供的别名
main = cc_listtemplates_main
