"""cc_listhooks命令实现 - T024任务

这个模块实现cc_listhooks命令，基于contracts/cli_commands.yaml规范。

主要功能：
1. 命令参数处理：
   - 可选过滤：--event（特定事件类型）
   - 级别选择：--level（project/user/all，默认all）
   - 输出格式：--format（json/table/yaml，默认table）

2. 核心功能实现：
   - 使用api/settings_operations.py列出所有或过滤的Hook
   - 支持多级别查询（project和user设置文件）
   - 按事件类型分组和排序
   - 显示Hook来源（哪个设置文件）

3. 丰富的显示信息：
   - Hook配置详情（type/command/timeout/matcher）
   - Hook索引编号（用于update/remove命令）
   - 设置文件路径和级别
   - Hook数量统计

4. 表格输出优化：
   - 自动列宽调整
   - 支持长命令的折行显示
   - 事件类型分组显示
   - 颜色编码（如果终端支持）

5. JSON输出结构：
   - 符合CLI合约的hooks数组
   - total_count统计
   - by_event分组数据
   - 包含设置文件元数据

6. 过滤和排序：
   - 按事件类型过滤
   - 按优先级排序（project > user）
   - 按Hook添加顺序排序

7. 空状态处理：
   - 友好的"无Hook配置"消息
   - 建议添加Hook的帮助信息
   - 正确的退出代码
"""

import logging
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ...api.settings_operations import find_and_load_settings, list_hooks_from_settings
from ...exceptions import CCHooksError
from ...models.hook_config import HookConfiguration
from ...models.settings_file import SettingsFile
from ...types.enums import HookEventType, OutputFormat, SettingsLevel
from ...utils.formatters import create_formatter


def execute_list_hooks_command(
    event_filter: Optional[str] = None,
    level: str = "all",
    format_type: str = "table"
) -> int:
    """执行cc_listhooks命令的核心逻辑

    Args:
        event_filter: 事件类型过滤器（如："PreToolUse", "PostToolUse"等）
        level: 设置级别（"project", "user", "all"）
        format_type: 输出格式（"json", "table", "yaml"）

    Returns:
        退出代码：0=成功, 1=用户错误, 2=系统错误
    """
    logger = logging.getLogger(__name__)

    try:
        # 验证参数
        if event_filter:
            try:
                HookEventType.from_string(event_filter)
            except ValueError:
                print(f"错误：无效的事件类型 '{event_filter}'", file=sys.stderr)
                print(f"有效的事件类型：{', '.join(HookEventType)}", file=sys.stderr)
                return 1

        try:
            OutputFormat.from_string(format_type)
        except ValueError:
            print(f"错误：无效的输出格式 '{format_type}'", file=sys.stderr)
            print(f"有效的格式：{', '.join(OutputFormat)}", file=sys.stderr)
            return 1

        if level not in SettingsLevel.get_cli_levels_with_all():
            print(f"错误：无效的设置级别 '{level}'", file=sys.stderr)
            print(f"有效的级别：{', '.join(SettingsLevel.get_cli_levels_with_all())}", file=sys.stderr)
            return 1

        # 列出Hook配置
        logger.info(f"列出Hook配置，级别：{level}，事件过滤器：{event_filter}，格式：{format_type}")

        # 获取Hook配置列表
        hooks = list_hooks_from_settings(level=level, event_filter=event_filter)

        # 构建详细的Hook信息
        detailed_hooks, by_event_stats, settings_metadata = _build_detailed_hook_info(hooks, level)

        # 生成输出
        formatter = create_formatter(format_type)

        if format_type.lower() == "json":
            output = _format_json_output(detailed_hooks, by_event_stats, settings_metadata)
        else:
            output = formatter.format_hook_list(
                hooks=detailed_hooks,
                total_count=len(detailed_hooks),
                by_event=by_event_stats
            )

        # 处理空状态
        if not detailed_hooks:
            if format_type.lower() == "quiet":
                print("0")  # 在安静模式下只输出数量
            elif format_type.lower() == "json":
                print(output)
            else:
                _print_empty_state_message(level, event_filter)
            return 0

        print(output)
        logger.info(f"成功列出 {len(detailed_hooks)} 个Hook配置")
        return 0

    except CCHooksError as e:
        logger.error(f"CCHooks错误：{e}")
        print(f"错误：{e}", file=sys.stderr)
        return 1

    except FileNotFoundError as e:
        logger.error(f"文件未找到：{e}")
        print("错误：找不到设置文件", file=sys.stderr)
        return 2

    except PermissionError as e:
        logger.error(f"权限错误：{e}")
        print("错误：没有权限访问设置文件", file=sys.stderr)
        return 2

    except Exception as e:
        logger.error(f"执行cc_listhooks时出现意外错误：{e}")
        print(f"系统错误：{e}", file=sys.stderr)
        return 2


def _build_detailed_hook_info(
    hooks: List[HookConfiguration],
    level: str
) -> Tuple[List[Dict[str, Any]], Dict[str, int], Dict[str, Any]]:
    """构建详细的Hook信息，包括索引、来源文件等

    Args:
        hooks: Hook配置列表
        level: 设置级别

    Returns:
        元组包含：(详细Hook信息列表, 按事件统计, 设置文件元数据)
    """
    detailed_hooks = []
    by_event_stats = defaultdict(int)
    settings_files_info = {}

    # 获取设置文件信息
    try:
        settings_files = find_and_load_settings(level)
        for settings_file in settings_files:
            settings_files_info[str(settings_file.path)] = {
                "level": settings_file.level.value,
                "path": str(settings_file.path),
                "exists": settings_file.path.exists()
            }
    except Exception as e:
        logging.getLogger(__name__).warning(f"获取设置文件信息时出错：{e}")

    # 为每个Hook添加详细信息
    for index, hook in enumerate(hooks):
        # 统计事件类型
        event_name = hook.event_type.value if hook.event_type else "Unknown"
        by_event_stats[event_name] += 1

        # 构建详细信息
        hook_detail = {
            "index": index,
            "event": event_name,
            "type": hook.type,
            "command": hook.command or "",
            "timeout": hook.timeout,
            "matcher": hook.matcher or "",
            "source_file": str(hook.source_file) if hasattr(hook, 'source_file') and hook.source_file else "N/A",
            "source_level": "N/A"
        }

        # 尝试确定Hook的来源级别
        if hasattr(hook, 'source_file') and hook.source_file:
            source_path = str(hook.source_file)
            if source_path in settings_files_info:
                hook_detail["source_level"] = settings_files_info[source_path]["level"]

        detailed_hooks.append(hook_detail)

    # 设置文件元数据
    settings_metadata = {
        "settings_files": list(settings_files_info.values()),
        "query_level": level,
        "total_files": len(settings_files_info)
    }

    return detailed_hooks, dict(by_event_stats), settings_metadata


def _format_json_output(
    hooks: List[Dict[str, Any]],
    by_event_stats: Dict[str, int],
    settings_metadata: Dict[str, Any]
) -> str:
    """格式化JSON输出，符合CLI合约规范

    Args:
        hooks: 详细Hook信息列表
        by_event_stats: 按事件类型统计
        settings_metadata: 设置文件元数据

    Returns:
        JSON格式的输出字符串
    """
    import json

    result = {
        "success": True,
        "message": f"找到 {len(hooks)} 个钩子配置",
        "data": {
            "hooks": hooks,
            "total_count": len(hooks),
            "by_event": by_event_stats,
            "settings_metadata": settings_metadata
        },
        "warnings": [],
        "errors": []
    }

    return json.dumps(result, ensure_ascii=False, indent=2)


def _print_empty_state_message(level: str, event_filter: Optional[str]) -> None:
    """打印友好的空状态消息

    Args:
        level: 查询的设置级别
        event_filter: 事件类型过滤器
    """
    print("未找到符合条件的钩子配置")
    print()

    if event_filter:
        print(f"查询条件：事件类型 = {event_filter}, 级别 = {level}")
        print("提示：尝试移除事件过滤器或检查其他级别的设置")
    else:
        print(f"查询级别：{level}")
        print("提示：尝试以下命令开始配置钩子：")
        print("  cc_addhook PreToolUse --command 'echo 工具执行前' --matcher Write")
        print("  cc_addhook PostToolUse --command 'echo 工具执行后' --matcher Write")

    print()
    print("使用 cc_addhook --help 查看添加钩子的详细说明")


def _add_hook_index_to_configs(hooks: List[HookConfiguration]) -> List[HookConfiguration]:
    """为Hook配置添加索引信息（用于update/remove命令）

    Args:
        hooks: Hook配置列表

    Returns:
        带有索引信息的Hook配置列表
    """
    # 为每个Hook添加索引属性
    for i, hook in enumerate(hooks):
        # 动态添加索引属性，供其他命令使用
        hook._cli_index = i

    return hooks


def _group_hooks_by_event_and_level(
    hooks: List[HookConfiguration]
) -> Dict[str, Dict[str, List[HookConfiguration]]]:
    """按事件类型和级别分组Hook配置

    Args:
        hooks: Hook配置列表

    Returns:
        嵌套字典：{event_type: {level: [hooks]}}
    """
    grouped = defaultdict(lambda: defaultdict(list))

    for hook in hooks:
        event_name = hook.event_type.value if hook.event_type else "Unknown"

        # 尝试确定级别
        level = "unknown"
        if hasattr(hook, 'source_file') and hook.source_file:
            source_path = str(hook.source_file)
            if '.claude' in source_path:
                if '/home/' in source_path and '/.claude/' in source_path:
                    level = "user"
                else:
                    level = "project"

        grouped[event_name][level].append(hook)

    return dict(grouped)


def _calculate_display_priorities(
    hooks: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """计算Hook显示优先级（project > user）

    Args:
        hooks: Hook配置列表

    Returns:
        按优先级排序的Hook配置列表
    """
    def get_priority(hook_detail: Dict[str, Any]) -> Tuple[int, str, int]:
        """获取排序优先级元组

        Returns:
            (级别优先级, 事件名称, 索引)
        """
        level = hook_detail.get("source_level", "unknown")
        event = hook_detail.get("event", "")
        index = hook_detail.get("index", 0)

        # 级别优先级：project=0, user=1, unknown=2
        level_priority = {"project": 0, "user": 1}.get(level, 2)

        return (level_priority, event, index)

    return sorted(hooks, key=get_priority)


# 导出的公共接口
__all__ = [
    "execute_list_hooks_command"
]
