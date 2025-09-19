"""CC Validate Hooks Command - T025实现

实现cc_validatehooks命令，提供全面的Hook配置验证功能。

主要功能：
1. 命令参数处理：--level、--format、--strict选项
2. 核心验证功能：使用api/settings_operations.py和services/hook_validator.py
3. 详细报告：按设置文件分组的验证结果
4. 多种输出格式：表格和JSON格式
5. 退出代码语义：0（全部有效）、1（警告）、2（错误）

符合contracts/cli_commands.yaml中cc_validatehooks的规范。
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ...api.settings_operations import (
    find_and_load_settings,
    list_hooks_from_settings,
    validate_all_hooks,
)
from ...exceptions import CCHooksError
from ...models.hook_config import HookConfiguration
from ...models.validation import ValidationError, ValidationResult, ValidationWarning
from ...services.hook_validator import HookValidator
from ...types.enums import HookEventType
from ...utils.formatters import JSONFormatter, TableFormatter


@dataclass
class ValidationSummary:
    """Hook验证汇总结果"""
    total_files: int = 0
    total_hooks: int = 0
    valid_hooks: int = 0
    invalid_hooks: int = 0
    warnings: int = 0
    errors: int = 0
    by_file: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    validation_results: List[Dict[str, Any]] = field(default_factory=list)

    def has_errors(self) -> bool:
        """是否有验证错误"""
        return self.errors > 0

    def has_warnings(self) -> bool:
        """是否有警告"""
        return self.warnings > 0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "total_files": self.total_files,
            "total_hooks": self.total_hooks,
            "valid_hooks": self.valid_hooks,
            "invalid_hooks": self.invalid_hooks,
            "warnings": self.warnings,
            "errors": self.errors,
            "by_file": self.by_file,
            "validation_results": self.validation_results
        }


class ValidateHooksCommand:
    """CC Validate Hooks命令实现"""

    def __init__(self):
        self.hook_validator = HookValidator()

    def setup_parser(self, parser: argparse.ArgumentParser) -> None:
        """设置命令行参数解析器

        Args:
            parser: 父命令的参数解析器
        """
        # 级别选择参数
        parser.add_argument(
            '--level',
            choices=['project', 'user', 'all'],
            default='all',
            help='设置级别：project（项目级）、user（用户级）、all（全部级别，默认）'
        )

        # 输出格式参数
        parser.add_argument(
            '--format',
            choices=['json', 'table'],
            default='table',
            help='输出格式：table（表格，默认）、json（JSON格式）'
        )

        # 严格模式参数
        parser.add_argument(
            '--strict',
            action='store_true',
            help='严格模式：将警告视为错误'
        )

    def execute(self, args: argparse.Namespace) -> int:
        """执行验证命令

        Args:
            args: 解析后的命令行参数

        Returns:
            退出代码：0（全部有效）、1（有警告）、2（有错误）
        """
        try:
            # 收集并验证Hook配置
            summary = self._perform_validation(args.level, args.strict)

            # 输出结果
            self._output_results(summary, args.format, args.strict)

            # 确定退出代码
            if summary.has_errors():
                return 2  # 有验证错误
            elif summary.has_warnings() and args.strict:
                return 2  # 严格模式下警告变为错误
            elif summary.has_warnings():
                return 1  # 有警告
            else:
                return 0  # 全部有效

        except CCHooksError as e:
            self._output_error(str(e), args.format)
            return 2
        except Exception as e:
            self._output_error(f"验证过程失败: {e}", args.format)
            return 2

    def _perform_validation(self, level: str, strict_mode: bool) -> ValidationSummary:
        """执行Hook配置验证

        Args:
            level: 设置级别过滤器
            strict_mode: 是否为严格模式

        Returns:
            验证汇总结果
        """
        summary = ValidationSummary()

        # 查找设置文件
        settings_files = find_and_load_settings(level)
        summary.total_files = len(settings_files)

        if not settings_files:
            # 没有找到设置文件
            summary.validation_results.append({
                "file_path": "无",
                "status": "no_files",
                "message": f"未找到级别为 '{level}' 的设置文件",
                "hooks": [],
                "suggestions": ["创建新的settings.json文件并添加Hook配置"]
            })
            return summary

        # 验证每个设置文件
        for settings_file in settings_files:
            file_result = self._validate_settings_file(
                settings_file, strict_mode
            )

            # 更新汇总统计
            file_path = str(settings_file.path)
            summary.by_file[file_path] = file_result
            summary.validation_results.append(file_result)

            # 累计统计
            summary.total_hooks += file_result.get("total_hooks", 0)
            summary.valid_hooks += file_result.get("valid_hooks", 0)
            summary.invalid_hooks += file_result.get("invalid_hooks", 0)
            summary.warnings += file_result.get("warnings", 0)
            summary.errors += file_result.get("errors", 0)

        return summary

    def _validate_settings_file(self, settings_file, strict_mode: bool) -> Dict[str, Any]:
        """验证单个设置文件中的Hook配置

        Args:
            settings_file: 设置文件对象
            strict_mode: 是否为严格模式

        Returns:
            文件验证结果字典
        """
        file_path = str(settings_file.path)

        try:
            # 获取文件中的所有Hook配置
            hooks_section = settings_file.get_hooks_section()

            if not hooks_section:
                return {
                    "file_path": file_path,
                    "status": "empty",
                    "message": "设置文件中没有Hook配置",
                    "total_hooks": 0,
                    "valid_hooks": 0,
                    "invalid_hooks": 0,
                    "warnings": 0,
                    "errors": 0,
                    "hooks": [],
                    "suggestions": ["考虑添加一些Hook配置以增强Claude Code功能"]
                }

            # 验证所有Hook
            hook_results = []
            total_hooks = 0
            valid_hooks = 0
            invalid_hooks = 0
            total_warnings = 0
            total_errors = 0

            for event_type, event_configs in hooks_section.items():
                for config in event_configs:
                    if "hooks" in config and isinstance(config["hooks"], list):
                        matcher = config.get("matcher", "")

                        for hook_index, hook_data in enumerate(config["hooks"]):
                            total_hooks += 1

                            # 验证单个Hook
                            hook_result = self._validate_single_hook(
                                hook_data, event_type, matcher, hook_index, strict_mode
                            )
                            hook_results.append(hook_result)

                            # 统计结果
                            if hook_result["is_valid"]:
                                valid_hooks += 1
                            else:
                                invalid_hooks += 1

                            total_warnings += len(hook_result.get("warnings", []))
                            total_errors += len(hook_result.get("errors", []))

            # 文件级别的建议
            suggestions = self._generate_file_suggestions(
                hooks_section, total_hooks, total_warnings, total_errors
            )

            return {
                "file_path": file_path,
                "status": "validated",
                "message": f"验证了{total_hooks}个Hook配置",
                "total_hooks": total_hooks,
                "valid_hooks": valid_hooks,
                "invalid_hooks": invalid_hooks,
                "warnings": total_warnings,
                "errors": total_errors,
                "hooks": hook_results,
                "suggestions": suggestions
            }

        except Exception as e:
            return {
                "file_path": file_path,
                "status": "error",
                "message": f"验证文件时出错: {e}",
                "total_hooks": 0,
                "valid_hooks": 0,
                "invalid_hooks": 0,
                "warnings": 0,
                "errors": 1,
                "hooks": [],
                "suggestions": ["检查文件格式和权限"]
            }

    def _validate_single_hook(
        self,
        hook_data: Dict[str, Any],
        event_type: str,
        matcher: str,
        index: int,
        strict_mode: bool
    ) -> Dict[str, Any]:
        """验证单个Hook配置

        Args:
            hook_data: Hook配置数据
            event_type: 事件类型
            matcher: 匹配器模式
            index: Hook索引
            strict_mode: 是否为严格模式

        Returns:
            Hook验证结果字典
        """
        try:
            # 尝试解析事件类型
            hook_event_type = None
            try:
                hook_event_type = HookEventType.from_string(event_type)
            except ValueError:
                pass

            # 创建Hook配置对象
            hook = HookConfiguration.from_dict(
                hook_data,
                event_type=hook_event_type,
                matcher=matcher
            )

            # 执行全面验证
            validation_result = self.hook_validator.validate_complete_hook(hook)

            # 构建结果
            result = {
                "index": index,
                "event_type": event_type,
                "matcher": matcher,
                "command": hook.command,
                "timeout": hook.timeout,
                "is_valid": validation_result.is_valid,
                "errors": [error.to_dict() for error in validation_result.errors],
                "warnings": [warning.to_dict() for warning in validation_result.warnings],
                "suggestions": validation_result.suggestions
            }

            # 添加详细分析
            result["analysis"] = self._analyze_hook_configuration(hook)

            return result

        except Exception as e:
            return {
                "index": index,
                "event_type": event_type,
                "matcher": matcher,
                "command": hook_data.get("command", "未知"),
                "timeout": hook_data.get("timeout"),
                "is_valid": False,
                "errors": [{
                    "field_name": "general",
                    "error_code": "PARSE_ERROR",
                    "message": f"无法解析Hook配置: {e}",
                    "suggested_fix": "检查Hook配置的格式和字段"
                }],
                "warnings": [],
                "suggestions": [],
                "analysis": {}
            }

    def _analyze_hook_configuration(self, hook: HookConfiguration) -> Dict[str, Any]:
        """分析Hook配置，提供额外的见解

        Args:
            hook: Hook配置对象

        Returns:
            分析结果字典
        """
        analysis = {
            "complexity": "low",  # low, medium, high
            "security_level": "safe",  # safe, caution, risky
            "performance_impact": "minimal",  # minimal, moderate, significant
            "cross_platform_compatible": True,
            "recommendations": []
        }

        # 复杂度分析
        if len(hook.command) > 100:
            analysis["complexity"] = "medium"
            analysis["recommendations"].append("考虑将复杂命令拆分为多个步骤")

        if len(hook.command) > 300:
            analysis["complexity"] = "high"
            analysis["recommendations"].append("建议使用脚本文件而非内联命令")

        # 安全性分析
        risky_patterns = ['rm', 'sudo', 'eval', 'curl.*sh', 'wget.*sh']
        for pattern in risky_patterns:
            if pattern.lower() in hook.command.lower():
                analysis["security_level"] = "risky"
                analysis["recommendations"].append(f"检查命令中的潜在安全风险: {pattern}")
                break

        # 性能影响分析
        if hook.timeout and hook.timeout > 60:
            analysis["performance_impact"] = "significant"
            analysis["recommendations"].append("长时间运行的命令可能影响用户体验")
        elif hook.timeout and hook.timeout > 10:
            analysis["performance_impact"] = "moderate"

        # 跨平台兼容性分析
        windows_specific = ['cmd.exe', '.bat', '.exe', 'powershell']
        unix_specific = ['bash', 'sh', '/usr/', '/bin/']

        has_windows = any(term in hook.command.lower() for term in windows_specific)
        has_unix = any(term in hook.command.lower() for term in unix_specific)

        if has_windows and has_unix:
            analysis["cross_platform_compatible"] = False
            analysis["recommendations"].append("命令包含平台特定元素，考虑使用条件逻辑")
        elif has_windows or has_unix:
            analysis["cross_platform_compatible"] = False
            analysis["recommendations"].append("命令可能不兼容所有平台")

        return analysis

    def _generate_file_suggestions(
        self,
        hooks_section: Dict[str, Any],
        total_hooks: int,
        warnings: int,
        errors: int
    ) -> List[str]:
        """生成文件级别的建议

        Args:
            hooks_section: Hook配置部分
            total_hooks: 总Hook数量
            warnings: 警告数量
            errors: 错误数量

        Returns:
            建议列表
        """
        suggestions = []

        # 基于Hook数量的建议
        if total_hooks == 0:
            suggestions.append("考虑添加一些Hook配置以增强Claude Code功能")
        elif total_hooks > 20:
            suggestions.append("Hook配置较多，考虑按功能分组管理")

        # 基于覆盖率的建议
        covered_events = set(hooks_section.keys())
        all_events = set(event.value for event in HookEventType)
        uncovered = all_events - covered_events

        if len(uncovered) > 5:
            suggestions.append(f"考虑为未覆盖的事件类型添加Hook: {', '.join(sorted(uncovered))}")

        # 基于质量的建议
        if errors > 0:
            suggestions.append("修复所有配置错误以确保Hook正常工作")

        if warnings > 3:
            suggestions.append("解决警告以改善Hook配置质量")

        # 最佳实践建议
        if total_hooks > 0:
            suggestions.extend([
                "定期备份设置文件",
                "考虑为Hook命令添加适当的超时设置",
                "确保所有Hook命令都经过充分测试"
            ])

        return suggestions

    def _output_results(self, summary: ValidationSummary, output_format: str, strict_mode: bool) -> None:
        """输出验证结果

        Args:
            summary: 验证汇总结果
            output_format: 输出格式（table或json）
            strict_mode: 是否为严格模式
        """
        if output_format == 'json':
            self._output_json(summary, strict_mode)
        else:
            self._output_table(summary, strict_mode)

    def _output_json(self, summary: ValidationSummary, strict_mode: bool) -> None:
        """输出JSON格式结果

        Args:
            summary: 验证汇总结果
            strict_mode: 是否为严格模式
        """
        # 符合CLI合约的输出结构
        output = {
            "success": not summary.has_errors() and (not strict_mode or not summary.has_warnings()),
            "message": self._generate_summary_message(summary, strict_mode),
            "data": {
                "valid_hooks": summary.valid_hooks,
                "invalid_hooks": summary.invalid_hooks,
                "warnings": summary.warnings,
                "validation_results": summary.validation_results
            },
            "warnings": [],
            "errors": []
        }

        # 添加汇总级别的警告和错误
        if summary.has_warnings():
            output["warnings"].append(f"发现 {summary.warnings} 个警告")

        if summary.has_errors():
            output["errors"].append(f"发现 {summary.errors} 个错误")

        print(json.dumps(output, ensure_ascii=False, indent=2))

    def _output_table(self, summary: ValidationSummary, strict_mode: bool) -> None:
        """输出表格格式结果

        Args:
            summary: 验证汇总结果
            strict_mode: 是否为严格模式
        """
        # 打印总体汇总
        print("Hook配置验证报告")
        print("=" * 60)

        if summary.total_files == 0:
            print("未找到任何设置文件。")
            return

        print(f"验证文件数: {summary.total_files}")
        print(f"总Hook数量: {summary.total_hooks}")
        print(f"有效Hook: {summary.valid_hooks}")
        print(f"无效Hook: {summary.invalid_hooks}")
        print(f"警告数: {summary.warnings}")
        print(f"错误数: {summary.errors}")

        if strict_mode:
            print("(严格模式: 警告将被视为错误)")

        print()

        # 按文件显示详细结果
        for file_result in summary.validation_results:
            self._print_file_result(file_result)

        # 打印总体状态
        print("=" * 60)
        if summary.has_errors():
            print("❌ 验证失败: 发现配置错误")
        elif summary.has_warnings() and strict_mode:
            print("❌ 严格模式验证失败: 发现警告")
        elif summary.has_warnings():
            print("⚠️  验证通过但有警告")
        else:
            print("✅ 所有Hook配置验证通过")

    def _print_file_result(self, file_result: Dict[str, Any]) -> None:
        """打印单个文件的验证结果

        Args:
            file_result: 文件验证结果
        """
        print(f"文件: {file_result['file_path']}")
        print(f"状态: {file_result['message']}")

        if file_result['status'] == 'validated' and file_result.get('hooks'):
            # 显示Hook详情表格
            headers = ["索引", "事件类型", "命令", "状态", "问题"]
            rows = []

            for hook in file_result['hooks']:
                status = "✅" if hook['is_valid'] else "❌"
                issues = len(hook.get('errors', []) + hook.get('warnings', []))
                issue_text = f"{issues}个问题" if issues > 0 else "无"

                command = hook['command'][:40] + "..." if len(hook['command']) > 40 else hook['command']

                rows.append([
                    str(hook['index']),
                    hook['event_type'],
                    command,
                    status,
                    issue_text
                ])

            # 简单的表格输出
            print()
            print(f"{'索引':<6} {'事件类型':<15} {'命令':<35} {'状态':<6} {'问题'}")
            print("-" * 80)
            for row in rows:
                print(f"{row[0]:<6} {row[1]:<15} {row[2]:<35} {row[3]:<6} {row[4]}")

        # 显示建议
        if file_result.get('suggestions'):
            print("\n建议:")
            for suggestion in file_result['suggestions']:
                print(f"  • {suggestion}")

        print()

    def _generate_summary_message(self, summary: ValidationSummary, strict_mode: bool) -> str:
        """生成汇总消息

        Args:
            summary: 验证汇总结果
            strict_mode: 是否为严格模式

        Returns:
            汇总消息字符串
        """
        if summary.total_files == 0:
            return "未找到任何设置文件"

        if summary.total_hooks == 0:
            return "设置文件中没有Hook配置"

        if summary.has_errors():
            return f"验证失败: 发现{summary.errors}个错误，{summary.warnings}个警告"
        elif summary.has_warnings() and strict_mode:
            return f"严格模式验证失败: 发现{summary.warnings}个警告"
        elif summary.has_warnings():
            return f"验证通过但有{summary.warnings}个警告"
        else:
            return f"所有{summary.total_hooks}个Hook配置验证通过"

    def _output_error(self, message: str, output_format: str) -> None:
        """输出错误消息

        Args:
            message: 错误消息
            output_format: 输出格式
        """
        if output_format == 'json':
            error_output = {
                "success": False,
                "message": message,
                "errors": [message]
            }
            print(json.dumps(error_output, ensure_ascii=False, indent=2))
        else:
            print(f"错误: {message}", file=sys.stderr)


def create_command() -> ValidateHooksCommand:
    """创建ValidateHooks命令实例

    Returns:
        ValidateHooks命令对象
    """
    return ValidateHooksCommand()
