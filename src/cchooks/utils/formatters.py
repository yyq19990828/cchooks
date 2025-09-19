"""输出格式化器用于Claude Code钩子CLI工具。

此模块提供统一的输出格式化系统，支持JSON、表格、YAML和安静模式输出。
遵循CLI合约规范，确保输出既美观又机器可读，支持自动化脚本使用。

格式化器类：
- JSONFormatter：结构化JSON输出，支持美化
- TableFormatter：人类可读的表格输出
- YAMLFormatter：YAML格式输出
- QuietFormatter：最小输出（仅错误或成功状态）

输出格式遵循CLI合约中定义的结构：
{
    "success": boolean,
    "message": string,
    "data": object,
    "warnings": array,
    "errors": array
}
"""

import json
import shutil
import sys
import textwrap
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, TextIO, Union


class BaseFormatter(ABC):
    """输出格式化器的抽象基类。

    定义所有格式化器必须实现的通用接口。
    """

    def __init__(self, file: TextIO = sys.stdout):
        """初始化格式化器。

        Args:
            file: 输出流，默认为stdout
        """
        self.file = file

    @abstractmethod
    def format_command_result(
        self,
        success: bool,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        warnings: Optional[List[str]] = None,
        errors: Optional[List[str]] = None
    ) -> str:
        """格式化CLI命令结果。

        Args:
            success: 操作是否成功
            message: 主要消息
            data: 结果数据
            warnings: 警告列表
            errors: 错误列表

        Returns:
            格式化的输出字符串
        """
        pass

    @abstractmethod
    def format_hook_list(
        self,
        hooks: List[Dict[str, Any]],
        total_count: int,
        by_event: Optional[Dict[str, int]] = None
    ) -> str:
        """格式化钩子列表。

        Args:
            hooks: 钩子配置列表
            total_count: 钩子总数
            by_event: 按事件类型统计

        Returns:
            格式化的钩子列表
        """
        pass

    @abstractmethod
    def format_validation_result(self, validation_result: Dict[str, Any]) -> str:
        """格式化验证结果。

        Args:
            validation_result: 验证结果数据

        Returns:
            格式化的验证结果
        """
        pass

    @abstractmethod
    def format_template_list(
        self,
        templates: List[Dict[str, Any]],
        total_count: int,
        by_source: Optional[Dict[str, int]] = None,
        by_event: Optional[Dict[str, int]] = None
    ) -> str:
        """格式化模板列表。

        Args:
            templates: 模板列表
            total_count: 模板总数
            by_source: 按来源统计
            by_event: 按事件类型统计

        Returns:
            格式化的模板列表
        """
        pass


class JSONFormatter(BaseFormatter):
    """JSON格式输出器。

    提供结构化JSON输出，遵循CLI合约格式规范。
    支持美化JSON（缩进）和紧凑JSON选项。
    """

    def __init__(self, file: TextIO = sys.stdout, pretty: bool = True):
        """初始化JSON格式化器。

        Args:
            file: 输出流
            pretty: 是否美化JSON输出（缩进格式）
        """
        super().__init__(file)
        self.pretty = pretty

    def format_command_result(
        self,
        success: bool,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        warnings: Optional[List[str]] = None,
        errors: Optional[List[str]] = None
    ) -> str:
        """格式化CLI命令结果为JSON。"""
        result = {
            "success": success,
            "message": message,
            "data": data or {},
            "warnings": warnings or [],
            "errors": errors or []
        }

        return self._format_json(result)

    def format_hook_list(
        self,
        hooks: List[Dict[str, Any]],
        total_count: int,
        by_event: Optional[Dict[str, int]] = None
    ) -> str:
        """格式化钩子列表为JSON。"""
        data = {
            "hooks": hooks,
            "total_count": total_count,
            "by_event": by_event or {}
        }

        result = {
            "success": True,
            "message": f"找到 {total_count} 个钩子",
            "data": data,
            "warnings": [],
            "errors": []
        }

        return self._format_json(result)

    def format_validation_result(self, validation_result: Dict[str, Any]) -> str:
        """格式化验证结果为JSON。"""
        valid_count = validation_result.get("valid_hooks", 0)
        invalid_count = validation_result.get("invalid_hooks", 0)
        warning_count = validation_result.get("warnings", 0)

        success = invalid_count == 0
        message = f"验证完成: {valid_count} 个有效, {invalid_count} 个无效, {warning_count} 个警告"

        result = {
            "success": success,
            "message": message,
            "data": validation_result,
            "warnings": [],
            "errors": []
        }

        return self._format_json(result)

    def format_template_list(
        self,
        templates: List[Dict[str, Any]],
        total_count: int,
        by_source: Optional[Dict[str, int]] = None,
        by_event: Optional[Dict[str, int]] = None
    ) -> str:
        """格式化模板列表为JSON。"""
        data = {
            "templates": templates,
            "total_count": total_count,
            "by_source": by_source or {},
            "by_event": by_event or {}
        }

        result = {
            "success": True,
            "message": f"找到 {total_count} 个模板",
            "data": data,
            "warnings": [],
            "errors": []
        }

        return self._format_json(result)

    def _format_json(self, obj: Any) -> str:
        """格式化对象为JSON字符串。

        Args:
            obj: 要格式化的对象

        Returns:
            JSON字符串
        """
        if self.pretty:
            return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True)
        else:
            return json.dumps(obj, ensure_ascii=False, separators=(',', ':'))


class TableFormatter(BaseFormatter):
    """表格格式输出器。

    提供人类可读的表格输出，支持：
    - 自动列宽调整
    - 嵌套数据展示
    - 颜色支持（如果终端支持）
    - 分页支持（长列表）
    """

    def __init__(self, file: TextIO = sys.stdout, max_width: Optional[int] = None):
        """初始化表格格式化器。

        Args:
            file: 输出流
            max_width: 最大表格宽度，None表示使用终端宽度
        """
        super().__init__(file)
        self.max_width = max_width or self._get_terminal_width()
        self._supports_color = self._check_color_support()

    def format_command_result(
        self,
        success: bool,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        warnings: Optional[List[str]] = None,
        errors: Optional[List[str]] = None
    ) -> str:
        """格式化CLI命令结果为表格。"""
        lines = []

        # 状态头部
        status_symbol = "✓" if success else "✗"
        status_color = self._green if success else self._red
        lines.append(f"{status_color}{status_symbol} {message}{self._reset}")

        # 数据部分
        if data:
            lines.append("")
            lines.append(self._format_data_table(data))

        # 警告
        if warnings:
            lines.append("")
            lines.append(f"{self._yellow}警告:{self._reset}")
            for warning in warnings:
                lines.append(f"  ⚠ {warning}")

        # 错误
        if errors:
            lines.append("")
            lines.append(f"{self._red}错误:{self._reset}")
            for error in errors:
                lines.append(f"  ✗ {error}")

        return "\n".join(lines)

    def format_hook_list(
        self,
        hooks: List[Dict[str, Any]],
        total_count: int,
        by_event: Optional[Dict[str, int]] = None
    ) -> str:
        """格式化钩子列表为表格。"""
        if not hooks:
            return f"{self._yellow}未找到钩子配置{self._reset}"

        lines = []
        lines.append(f"{self._bold}钩子配置 ({total_count}){self._reset}")
        lines.append("")

        # 创建表格
        table_data = []
        headers = ["索引", "事件", "类型", "命令", "超时"]

        for i, hook in enumerate(hooks):
            row = [
                str(i),
                hook.get("event", "N/A"),
                hook.get("type", "N/A"),
                self._truncate(hook.get("command", "N/A"), 50),
                str(hook.get("timeout", "N/A"))
            ]
            table_data.append(row)

        lines.append(self._create_table(headers, table_data))

        # 按事件统计
        if by_event:
            lines.append("")
            lines.append(f"{self._bold}按事件类型统计:{self._reset}")
            for event, count in sorted(by_event.items()):
                lines.append(f"  {event}: {count}")

        return "\n".join(lines)

    def format_validation_result(self, validation_result: Dict[str, Any]) -> str:
        """格式化验证结果为表格。"""
        valid_count = validation_result.get("valid_hooks", 0)
        invalid_count = validation_result.get("invalid_hooks", 0)
        warning_count = validation_result.get("warnings", 0)

        lines = []

        # 验证摘要
        if invalid_count > 0:
            lines.append(f"{self._red}✗ 验证失败{self._reset}")
        elif warning_count > 0:
            lines.append(f"{self._yellow}⚠ 验证完成，有警告{self._reset}")
        else:
            lines.append(f"{self._green}✓ 验证通过{self._reset}")

        lines.append("")

        # 统计表格
        stats_data = [
            ["有效钩子", str(valid_count)],
            ["无效钩子", str(invalid_count)],
            ["警告", str(warning_count)]
        ]
        lines.append(self._create_table(["项目", "数量"], stats_data))

        # 详细结果
        results = validation_result.get("validation_results", [])
        if results:
            lines.append("")
            lines.append(f"{self._bold}详细结果:{self._reset}")

            for result in results:
                status = result.get("status", "unknown")
                event = result.get("event", "N/A")
                index = result.get("index", "N/A")
                message = result.get("message", "N/A")

                if status == "valid":
                    lines.append(f"  {self._green}✓{self._reset} {event}[{index}]: {message}")
                elif status == "warning":
                    lines.append(f"  {self._yellow}⚠{self._reset} {event}[{index}]: {message}")
                else:
                    lines.append(f"  {self._red}✗{self._reset} {event}[{index}]: {message}")

        return "\n".join(lines)

    def format_template_list(
        self,
        templates: List[Dict[str, Any]],
        total_count: int,
        by_source: Optional[Dict[str, int]] = None,
        by_event: Optional[Dict[str, int]] = None
    ) -> str:
        """格式化模板列表为表格。"""
        if not templates:
            return f"{self._yellow}未找到模板{self._reset}"

        lines = []
        lines.append(f"{self._bold}钩子模板 ({total_count}){self._reset}")
        lines.append("")

        # 创建表格
        table_data = []
        headers = ["名称", "类型", "来源", "支持事件", "描述"]

        for template in templates:
            events = template.get("supported_events", [])
            events_str = ", ".join(events) if events else "N/A"

            row = [
                template.get("name", "N/A"),
                template.get("type", "N/A"),
                template.get("source", "N/A"),
                self._truncate(events_str, 30),
                self._truncate(template.get("description", "N/A"), 40)
            ]
            table_data.append(row)

        lines.append(self._create_table(headers, table_data))

        # 统计信息
        if by_source or by_event:
            lines.append("")

            if by_source:
                lines.append(f"{self._bold}按来源统计:{self._reset}")
                for source, count in sorted(by_source.items()):
                    lines.append(f"  {source}: {count}")

            if by_event:
                lines.append("")
                lines.append(f"{self._bold}按事件类型统计:{self._reset}")
                for event, count in sorted(by_event.items()):
                    lines.append(f"  {event}: {count}")

        return "\n".join(lines)

    def _create_table(self, headers: List[str], rows: List[List[str]]) -> str:
        """创建格式化的表格。

        Args:
            headers: 表头列表
            rows: 行数据列表

        Returns:
            格式化的表格字符串
        """
        if not rows:
            return ""

        # 计算列宽
        col_widths = [len(header) for header in headers]
        for row in rows:
            for i, cell in enumerate(row):
                if i < len(col_widths):
                    col_widths[i] = max(col_widths[i], len(str(cell)))

        # 调整列宽以适应终端宽度
        total_width = sum(col_widths) + len(headers) * 3 - 1
        if total_width > self.max_width:
            # 按比例缩减列宽
            scale = (self.max_width - len(headers) * 3 + 1) / sum(col_widths)
            col_widths = [max(8, int(w * scale)) for w in col_widths]

        lines = []

        # 表头
        header_line = " │ ".join(
            header.ljust(col_widths[i]) for i, header in enumerate(headers)
        )
        lines.append(f"{self._bold}{header_line}{self._reset}")

        # 分隔线
        separator = "─┼─".join("─" * w for w in col_widths)
        lines.append(separator)

        # 数据行
        for row in rows:
            row_line = " │ ".join(
                str(cell).ljust(col_widths[i]) if i < len(col_widths)
                else str(cell)
                for i, cell in enumerate(row)
            )
            lines.append(row_line)

        return "\n".join(lines)

    def _format_data_table(self, data: Dict[str, Any]) -> str:
        """格式化数据字典为简单表格。"""
        lines = []

        for key, value in data.items():
            if isinstance(value, dict):
                lines.append(f"{self._bold}{key}:{self._reset}")
                for sub_key, sub_value in value.items():
                    lines.append(f"  {sub_key}: {sub_value}")
            elif isinstance(value, list):
                lines.append(f"{self._bold}{key}:{self._reset}")
                for item in value:
                    lines.append(f"  - {item}")
            else:
                lines.append(f"{self._bold}{key}:{self._reset} {value}")

        return "\n".join(lines)

    def _truncate(self, text: str, max_length: int) -> str:
        """截断文本到指定长度。"""
        if len(text) <= max_length:
            return text
        return text[:max_length - 3] + "..."

    def _get_terminal_width(self) -> int:
        """获取终端宽度。"""
        try:
            return shutil.get_terminal_size().columns
        except (AttributeError, OSError):
            return 80  # 默认宽度

    def _check_color_support(self) -> bool:
        """检查终端是否支持颜色。"""
        # 简化的颜色支持检测
        import os
        return (
            hasattr(sys.stdout, 'isatty') and sys.stdout.isatty() and
            os.environ.get('TERM', '').lower() != 'dumb' and
            os.environ.get('NO_COLOR') is None
        )

    # 颜色代码
    @property
    def _reset(self) -> str:
        return "\033[0m" if self._supports_color else ""

    @property
    def _bold(self) -> str:
        return "\033[1m" if self._supports_color else ""

    @property
    def _green(self) -> str:
        return "\033[32m" if self._supports_color else ""

    @property
    def _red(self) -> str:
        return "\033[31m" if self._supports_color else ""

    @property
    def _yellow(self) -> str:
        return "\033[33m" if self._supports_color else ""


class YAMLFormatter(BaseFormatter):
    """YAML格式输出器。

    提供YAML格式输出，适用于配置风格的数据展示。
    注意：仅使用Python标准库，不依赖外部YAML库。
    """

    def __init__(self, file: TextIO = sys.stdout):
        """初始化YAML格式化器。"""
        super().__init__(file)

    def format_command_result(
        self,
        success: bool,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        warnings: Optional[List[str]] = None,
        errors: Optional[List[str]] = None
    ) -> str:
        """格式化CLI命令结果为YAML。"""
        result = {
            "success": success,
            "message": message,
            "data": data or {},
            "warnings": warnings or [],
            "errors": errors or []
        }

        return self._format_yaml(result)

    def format_hook_list(
        self,
        hooks: List[Dict[str, Any]],
        total_count: int,
        by_event: Optional[Dict[str, int]] = None
    ) -> str:
        """格式化钩子列表为YAML。"""
        data = {
            "hooks": hooks,
            "total_count": total_count,
            "by_event": by_event or {}
        }

        result = {
            "success": True,
            "message": f"找到 {total_count} 个钩子",
            "data": data,
            "warnings": [],
            "errors": []
        }

        return self._format_yaml(result)

    def format_validation_result(self, validation_result: Dict[str, Any]) -> str:
        """格式化验证结果为YAML。"""
        valid_count = validation_result.get("valid_hooks", 0)
        invalid_count = validation_result.get("invalid_hooks", 0)
        warning_count = validation_result.get("warnings", 0)

        success = invalid_count == 0
        message = f"验证完成: {valid_count} 个有效, {invalid_count} 个无效, {warning_count} 个警告"

        result = {
            "success": success,
            "message": message,
            "data": validation_result,
            "warnings": [],
            "errors": []
        }

        return self._format_yaml(result)

    def format_template_list(
        self,
        templates: List[Dict[str, Any]],
        total_count: int,
        by_source: Optional[Dict[str, int]] = None,
        by_event: Optional[Dict[str, int]] = None
    ) -> str:
        """格式化模板列表为YAML。"""
        data = {
            "templates": templates,
            "total_count": total_count,
            "by_source": by_source or {},
            "by_event": by_event or {}
        }

        result = {
            "success": True,
            "message": f"找到 {total_count} 个模板",
            "data": data,
            "warnings": [],
            "errors": []
        }

        return self._format_yaml(result)

    def _format_yaml(self, obj: Any, indent: int = 0) -> str:
        """格式化对象为YAML字符串（简化实现）。

        Args:
            obj: 要格式化的对象
            indent: 缩进级别

        Returns:
            YAML字符串
        """
        indent_str = "  " * indent

        if isinstance(obj, dict):
            if not obj:
                return "{}"
            lines = []
            for key, value in obj.items():
                if isinstance(value, (dict, list)):
                    lines.append(f"{indent_str}{key}:")
                    lines.append(self._format_yaml(value, indent + 1))
                else:
                    lines.append(f"{indent_str}{key}: {self._format_yaml_value(value)}")
            return "\n".join(lines)

        elif isinstance(obj, list):
            if not obj:
                return "[]"
            lines = []
            for item in obj:
                if isinstance(item, (dict, list)):
                    lines.append(f"{indent_str}-")
                    nested = self._format_yaml(item, indent + 1)
                    # 合并第一行
                    nested_lines = nested.split("\n")
                    if nested_lines:
                        lines[-1] += " " + nested_lines[0].strip()
                        lines.extend(nested_lines[1:])
                else:
                    lines.append(f"{indent_str}- {self._format_yaml_value(item)}")
            return "\n".join(lines)

        else:
            return self._format_yaml_value(obj)

    def _format_yaml_value(self, value: Any) -> str:
        """格式化单个值为YAML格式。"""
        if value is None:
            return "null"
        elif isinstance(value, bool):
            return "true" if value else "false"
        elif isinstance(value, str):
            # 简单的字符串转义
            if any(c in value for c in ['\n', '\r', '\t', '"', "'"]) or value.strip() != value:
                return json.dumps(value, ensure_ascii=False)
            return value
        else:
            return str(value)


class QuietFormatter(BaseFormatter):
    """安静模式输出器。

    提供最小输出，仅显示错误或成功状态。
    适用于脚本自动化和批处理场景。
    """

    def __init__(self, file: TextIO = sys.stdout):
        """初始化安静模式格式化器。"""
        super().__init__(file)

    def format_command_result(
        self,
        success: bool,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        warnings: Optional[List[str]] = None,
        errors: Optional[List[str]] = None
    ) -> str:
        """格式化CLI命令结果为安静输出。"""
        if not success and errors:
            # 仅在失败时输出错误
            return "\n".join(errors)
        elif not success:
            # 如果没有具体错误，输出消息
            return message
        else:
            # 成功时不输出任何内容
            return ""

    def format_hook_list(
        self,
        hooks: List[Dict[str, Any]],
        total_count: int,
        by_event: Optional[Dict[str, int]] = None
    ) -> str:
        """格式化钩子列表为安静输出。"""
        # 在安静模式下，仅输出数量
        return str(total_count)

    def format_validation_result(self, validation_result: Dict[str, Any]) -> str:
        """格式化验证结果为安静输出。"""
        invalid_count = validation_result.get("invalid_hooks", 0)

        if invalid_count > 0:
            # 输出错误数量
            return str(invalid_count)
        else:
            # 验证通过时不输出
            return ""

    def format_template_list(
        self,
        templates: List[Dict[str, Any]],
        total_count: int,
        by_source: Optional[Dict[str, int]] = None,
        by_event: Optional[Dict[str, int]] = None
    ) -> str:
        """格式化模板列表为安静输出。"""
        # 在安静模式下，仅输出数量
        return str(total_count)


# 格式化器工厂函数

def create_formatter(format_type: str, file: TextIO = sys.stdout) -> BaseFormatter:
    """创建指定类型的格式化器。

    Args:
        format_type: 格式类型 ("json", "table", "yaml", "quiet")
        file: 输出流

    Returns:
        格式化器实例

    Raises:
        ValueError: 如果格式类型不支持
    """
    format_type = format_type.lower()

    if format_type == "json":
        return JSONFormatter(file)
    elif format_type == "table":
        return TableFormatter(file)
    elif format_type == "yaml":
        return YAMLFormatter(file)
    elif format_type == "quiet":
        return QuietFormatter(file)
    else:
        raise ValueError(f"不支持的格式类型: {format_type}")


# 便利函数

def format_command_result(
    success: bool,
    message: str,
    data: Optional[Dict[str, Any]] = None,
    warnings: Optional[List[str]] = None,
    errors: Optional[List[str]] = None,
    format_type: str = "table",
    file: TextIO = sys.stdout
) -> str:
    """格式化CLI命令结果的便利函数。

    Args:
        success: 操作是否成功
        message: 主要消息
        data: 结果数据
        warnings: 警告列表
        errors: 错误列表
        format_type: 输出格式类型
        file: 输出流

    Returns:
        格式化的输出字符串
    """
    formatter = create_formatter(format_type, file)
    return formatter.format_command_result(success, message, data, warnings, errors)


def format_hook_list(
    hooks: List[Dict[str, Any]],
    total_count: int,
    by_event: Optional[Dict[str, int]] = None,
    format_type: str = "table",
    file: TextIO = sys.stdout
) -> str:
    """格式化钩子列表的便利函数。

    Args:
        hooks: 钩子配置列表
        total_count: 钩子总数
        by_event: 按事件类型统计
        format_type: 输出格式类型
        file: 输出流

    Returns:
        格式化的钩子列表
    """
    formatter = create_formatter(format_type, file)
    return formatter.format_hook_list(hooks, total_count, by_event)


def format_validation_result(
    validation_result: Dict[str, Any],
    format_type: str = "table",
    file: TextIO = sys.stdout
) -> str:
    """格式化验证结果的便利函数。

    Args:
        validation_result: 验证结果数据
        format_type: 输出格式类型
        file: 输出流

    Returns:
        格式化的验证结果
    """
    formatter = create_formatter(format_type, file)
    return formatter.format_validation_result(validation_result)


def format_template_list(
    templates: List[Dict[str, Any]],
    total_count: int,
    by_source: Optional[Dict[str, int]] = None,
    by_event: Optional[Dict[str, int]] = None,
    format_type: str = "table",
    file: TextIO = sys.stdout
) -> str:
    """格式化模板列表的便利函数。

    Args:
        templates: 模板列表
        total_count: 模板总数
        by_source: 按来源统计
        by_event: 按事件类型统计
        format_type: 输出格式类型
        file: 输出流

    Returns:
        格式化的模板列表
    """
    formatter = create_formatter(format_type, file)
    return formatter.format_template_list(templates, total_count, by_source, by_event)


def format_error_message(command_name: str, error_message: str) -> str:
    """格式化错误消息的便利函数。

    Args:
        command_name: 命令名称
        error_message: 错误消息

    Returns:
        格式化的错误消息
    """
    return f"{command_name}: {error_message}"
