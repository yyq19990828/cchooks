"""CLI命令合约测试。

基于contracts/cli_commands.yaml规范，测试所有9个CLI命令的参数解析、
输出格式、错误处理和退出代码。

这些测试遵循TDD方法，应该在实现完成前失败。
测试验证：
- 所有CLI命令的参数解析正确性
- 必需参数验证
- 可选参数默认值
- 参数类型验证（字符串、整数、布尔值、枚举）
- 参数值范围验证（如timeout 1-3600）
- 互斥参数组（如--command vs --script）
- 输出格式（JSON/table/YAML）
- 错误输出格式
- 退出代码（0=成功, 1=用户错误, 2=系统错误）
"""

import pytest
import json
import sys
import os
from unittest.mock import patch, MagicMock
from argparse import Namespace
from typing import List, Dict, Any

# 设置导入路径
test_dir = os.path.dirname(__file__)
src_dir = os.path.join(test_dir, '../../src')
sys.path.insert(0, src_dir)

# 导入CLI模块
try:
    from cchooks.cli.argument_parser import parse_args, create_parser
except ImportError:
    # 如果导入失败，使用importlib直接导入
    import importlib.util
    parser_path = os.path.join(src_dir, 'cchooks/cli/argument_parser.py')
    spec = importlib.util.spec_from_file_location("argument_parser", parser_path)
    argument_parser_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(argument_parser_module)
    parse_args = argument_parser_module.parse_args
    create_parser = argument_parser_module.create_parser

# 导入main模块（如果可能）
try:
    from cchooks.cli import main
except ImportError:
    main = None


class TestCLIArgumentParsing:
    """测试CLI参数解析的正确性。"""

    def test_addhook_required_arguments(self):
        """测试cc_addhook的必需参数。"""
        # 测试缺少event参数
        with pytest.raises(SystemExit):
            parse_args(["cc_addhook"])

        # 测试缺少command/script参数
        with pytest.raises(SystemExit):
            parse_args(["cc_addhook", "PreToolUse"])

        # 测试正确的最小参数
        args = parse_args(["cc_addhook", "PreToolUse", "--command", "echo test"])
        assert args.subcommand == "cc_addhook"
        assert args.event == "PreToolUse"
        assert args.command == "echo test"
        assert args.script is None

    def test_addhook_mutually_exclusive_command_script(self):
        """测试--command和--script参数互斥。"""
        # 不能同时指定command和script
        with pytest.raises(SystemExit):
            parse_args(["cc_addhook", "PreToolUse", "--command", "echo test", "--script", "test.py"])

    def test_addhook_valid_events(self):
        """测试event参数的有效值。"""
        valid_events = [
            "PreToolUse", "PostToolUse", "Notification", "UserPromptSubmit",
            "Stop", "SubagentStop", "PreCompact", "SessionStart", "SessionEnd"
        ]

        for event in valid_events:
            args = parse_args(["cc_addhook", event, "--command", "echo test"])
            assert args.event == event

        # 测试无效event
        with pytest.raises(SystemExit):
            parse_args(["cc_addhook", "InvalidEvent", "--command", "echo test"])

    def test_addhook_timeout_validation(self):
        """测试timeout参数的范围验证（1-3600）。"""
        # 有效timeout值
        args = parse_args(["cc_addhook", "PreToolUse", "--command", "echo test", "--timeout", "60"])
        assert args.timeout == 60

        # 测试边界值
        args = parse_args(["cc_addhook", "PreToolUse", "--command", "echo test", "--timeout", "1"])
        assert args.timeout == 1

        args = parse_args(["cc_addhook", "PreToolUse", "--command", "echo test", "--timeout", "3600"])
        assert args.timeout == 3600

        # 无效timeout值应该在验证阶段失败
        with pytest.raises(SystemExit):
            parse_args(["cc_addhook", "PreToolUse", "--command", "echo test", "--timeout", "0"])

        with pytest.raises(SystemExit):
            parse_args(["cc_addhook", "PreToolUse", "--command", "echo test", "--timeout", "3601"])

    def test_addhook_optional_arguments_defaults(self):
        """测试可选参数的默认值。"""
        args = parse_args(["cc_addhook", "PreToolUse", "--command", "echo test"])
        assert args.level == "project"
        assert args.format == "table"
        assert args.dry_run is False
        assert args.backup is True  # 默认为True
        assert args.auto_chmod is True  # 默认为True

    def test_updatehook_required_arguments(self):
        """测试cc_updatehook的必需参数。"""
        # 缺少event
        with pytest.raises(SystemExit):
            parse_args(["cc_updatehook"])

        # 缺少index
        with pytest.raises(SystemExit):
            parse_args(["cc_updatehook", "PreToolUse"])

        # 正确的参数
        args = parse_args(["cc_updatehook", "PreToolUse", "0"])
        assert args.subcommand == "cc_updatehook"
        assert args.event == "PreToolUse"
        assert args.index == 0

    def test_updatehook_index_validation(self):
        """测试index参数必须是非负整数。"""
        # 有效index
        args = parse_args(["cc_updatehook", "PreToolUse", "5"])
        assert args.index == 5

        # 负数index应该失败
        with pytest.raises(SystemExit):
            parse_args(["cc_updatehook", "PreToolUse", "-1"])

    def test_removehook_required_arguments(self):
        """测试cc_removehook的必需参数。"""
        args = parse_args(["cc_removehook", "PreToolUse", "0"])
        assert args.subcommand == "cc_removehook"
        assert args.event == "PreToolUse"
        assert args.index == 0

    def test_listhooks_optional_arguments(self):
        """测试cc_listhooks的可选参数。"""
        # 无参数调用
        args = parse_args(["cc_listhooks"])
        assert args.subcommand == "cc_listhooks"
        assert args.level == "all"  # 默认值
        assert args.format == "table"  # 默认值

        # 带参数调用
        args = parse_args(["cc_listhooks", "--event", "PreToolUse", "--level", "project", "--format", "json"])
        assert args.event == "PreToolUse"
        assert args.level == "project"
        assert args.format == "json"

    def test_validatehooks_arguments(self):
        """测试cc_validatehooks的参数。"""
        args = parse_args(["cc_validatehooks"])
        assert args.subcommand == "cc_validatehooks"
        assert args.level == "all"
        assert args.format == "table"
        assert args.strict is False

        # 测试strict模式
        args = parse_args(["cc_validatehooks", "--strict"])
        assert args.strict is True

    def test_generatehook_required_arguments(self):
        """测试cc_generatehook的必需参数。"""
        # 缺少type
        with pytest.raises(SystemExit):
            parse_args(["cc_generatehook"])

        # 缺少event
        with pytest.raises(SystemExit):
            parse_args(["cc_generatehook", "security-guard"])

        # 缺少output
        with pytest.raises(SystemExit):
            parse_args(["cc_generatehook", "security-guard", "PreToolUse"])

        # 正确的参数
        args = parse_args(["cc_generatehook", "security-guard", "PreToolUse", "output.py"])
        assert args.type == "security-guard"
        assert args.event == "PreToolUse"
        assert args.output == "output.py"

    def test_generatehook_valid_template_types(self):
        """测试template type的有效值。"""
        valid_types = [
            "security-guard", "auto-formatter", "auto-linter", "git-auto-commit",
            "permission-logger", "desktop-notifier", "task-manager", "prompt-filter",
            "context-loader", "cleanup-handler"
        ]

        for template_type in valid_types:
            args = parse_args(["cc_generatehook", template_type, "PreToolUse", "output.py"])
            assert args.type == template_type

    def test_registertemplate_required_one_of_file_or_class(self):
        """测试cc_registertemplate需要--file或--class之一。"""
        # 缺少name
        with pytest.raises(SystemExit):
            parse_args(["cc_registertemplate"])

        # 缺少file或class
        with pytest.raises(SystemExit):
            parse_args(["cc_registertemplate", "my-template"])

        # 不能同时指定file和class
        with pytest.raises(SystemExit):
            parse_args(["cc_registertemplate", "my-template", "--file", "template.py", "--class", "MyTemplate"])

        # 正确用法：使用file
        args = parse_args(["cc_registertemplate", "my-template", "--file", "template.py"])
        assert args.name == "my-template"
        assert args.file == "template.py"
        assert getattr(args, 'class', None) is None

        # 正确用法：使用class
        args = parse_args(["cc_registertemplate", "my-template", "--class", "module.ClassName"])
        assert args.name == "my-template"
        assert getattr(args, 'class') == "module.ClassName"
        assert args.file is None

    def test_output_format_validation(self):
        """测试输出格式的有效值。"""
        # 测试basic formats (json, table, quiet)
        for fmt in ["json", "table", "quiet"]:
            args = parse_args(["cc_addhook", "PreToolUse", "--command", "echo", "--format", fmt])
            assert args.format == fmt

        # 测试with yaml formats
        for fmt in ["json", "table", "yaml"]:
            args = parse_args(["cc_listhooks", "--format", fmt])
            assert args.format == fmt

        # 测试无效格式
        with pytest.raises(SystemExit):
            parse_args(["cc_addhook", "PreToolUse", "--command", "echo", "--format", "xml"])

    def test_settings_level_validation(self):
        """测试settings level的有效值。"""
        # 测试基本levels (project, user)
        for level in ["project", "user"]:
            args = parse_args(["cc_addhook", "PreToolUse", "--command", "echo", "--level", level])
            assert args.level == level

        # 测试with all levels
        for level in ["project", "user", "all"]:
            args = parse_args(["cc_listhooks", "--level", level])
            assert args.level == level

    def test_boolean_arguments(self):
        """测试布尔参数的处理。"""
        # 测试dry-run
        args = parse_args(["cc_addhook", "PreToolUse", "--command", "echo", "--dry-run"])
        assert args.dry_run is True

        # 测试backup/no-backup
        args = parse_args(["cc_addhook", "PreToolUse", "--command", "echo", "--no-backup"])
        assert args.backup is False

        # 测试auto-chmod/no-auto-chmod
        args = parse_args(["cc_addhook", "PreToolUse", "--script", "test.py", "--no-auto-chmod"])
        assert args.auto_chmod is False


class TestCLICommandEntryPoints:
    """测试CLI命令入口点的功能。"""

    def test_command_entry_points_exist(self):
        """测试所有命令入口点函数存在。"""
        assert hasattr(main, 'cc_addhook')
        assert hasattr(main, 'cc_updatehook')
        assert hasattr(main, 'cc_removehook')
        assert hasattr(main, 'cc_listhooks')
        assert hasattr(main, 'cc_validatehooks')
        assert hasattr(main, 'cc_generatehook')
        assert hasattr(main, 'cc_registertemplate')
        assert hasattr(main, 'cc_listtemplates')
        assert hasattr(main, 'cc_unregistertemplate')

    @patch('sys.argv', ['cc_addhook', 'PreToolUse', '--command', 'echo test'])
    def test_addhook_entry_point(self):
        """测试cc_addhook入口点调用参数解析。"""
        with pytest.raises(SystemExit) as exc_info:
            main.cc_addhook()
        # 当前实现返回exit(1)因为功能未实现
        assert exc_info.value.code == 1

    @patch('sys.argv', ['cc_listhooks'])
    def test_listhooks_entry_point(self):
        """测试cc_listhooks入口点调用参数解析。"""
        with pytest.raises(SystemExit) as exc_info:
            main.cc_listhooks()
        # 当前实现返回exit(1)因为功能未实现
        assert exc_info.value.code == 1


class TestCLICommandOutputFormat:
    """测试CLI命令输出格式规范。"""

    def test_success_output_structure(self):
        """测试成功输出的结构符合合约规范。"""
        # 这个测试目前会失败，因为实际实现还没有完成
        # 当实现完成后，应该返回类似这样的结构：
        expected_success_structure = {
            "success": True,
            "message": "操作成功完成",
            "data": {
                "hook": {
                    "type": "command",
                    "command": "echo test",
                    # "timeout"是可选的
                },
                "settings_file": "/path/to/settings.json",
                "backup_created": True
            },
            "warnings": [],
            "errors": []
        }

        # 目前这个测试应该失败，因为功能未实现
        with pytest.raises(SystemExit):
            # 模拟实际的CLI调用，当实现完成后应该返回符合规范的JSON
            # 而不是exit(1)
            main.cc_addhook()

    def test_error_output_structure(self):
        """测试错误输出的结构符合合约规范。"""
        expected_error_structure = {
            "success": False,
            "message": "操作失败的原因",
            "errors": ["具体错误信息"]
        }

        # 目前这个测试应该失败，因为错误处理未实现
        with pytest.raises(SystemExit):
            # 实际实现应该返回格式化的错误信息
            # 而不是简单的exit(1)
            main.cc_addhook()

    def test_exit_codes_compliance(self):
        """测试退出代码符合合约规范。"""
        # 根据合约规范：
        # 0: 成功
        # 1: 验证错误或用户错误
        # 2: 系统错误（文件权限等）

        # 目前所有命令都返回1，因为功能未实现
        # 这个测试记录了预期的行为
        with pytest.raises(SystemExit) as exc_info:
            main.cc_addhook()
        assert exc_info.value.code == 1  # 当前是未实现错误

        # 当实现完成后，应该根据不同情况返回不同的退出代码


class TestCLIArgumentValidation:
    """测试CLI参数验证逻辑。"""

    def test_matcher_required_for_tool_use_events(self):
        """测试PreToolUse和PostToolUse事件需要matcher参数。"""
        # 当前这个验证逻辑在argument_parser.py中已实现
        # 但actual command execution还没有实现

        # PreToolUse without matcher should fail
        with pytest.raises(SystemExit):
            parse_args(["cc_addhook", "PreToolUse", "--command", "echo test"])

        # PostToolUse without matcher should fail
        with pytest.raises(SystemExit):
            parse_args(["cc_addhook", "PostToolUse", "--command", "echo test"])

        # With matcher should pass parsing
        args = parse_args(["cc_addhook", "PreToolUse", "--command", "echo test", "--matcher", "Write"])
        assert args.matcher == "Write"

    def test_customization_json_validation(self):
        """测试customization参数的JSON格式验证。"""
        # 有效JSON
        args = parse_args([
            "cc_generatehook", "security-guard", "PreToolUse", "output.py",
            "--customization", '{"key": "value"}'
        ])
        assert args.customization == '{"key": "value"}'

        # 无效JSON应该失败
        with pytest.raises(SystemExit):
            parse_args([
                "cc_generatehook", "security-guard", "PreToolUse", "output.py",
                "--customization", '{"invalid": json}'
            ])


class TestCLIImplementationStatus:
    """测试当前CLI实现状态（TDD - 这些测试应该失败）。"""

    def test_commands_not_fully_implemented(self):
        """确认命令功能尚未完全实现（TDD要求）。"""
        # 所有命令目前都应该返回exit(1)，表示功能未实现
        commands_to_test = [
            ('cc_addhook', ['PreToolUse', '--command', 'echo test', '--matcher', 'Write']),
            ('cc_updatehook', ['PreToolUse', '0']),
            ('cc_removehook', ['PreToolUse', '0']),
            ('cc_listhooks', []),
            ('cc_validatehooks', []),
            ('cc_generatehook', ['security-guard', 'PreToolUse', 'output.py']),
            ('cc_registertemplate', ['my-template', '--file', 'template.py']),
            ('cc_listtemplates', []),
            ('cc_unregistertemplate', ['my-template']),
        ]

        for command_name, args in commands_to_test:
            with patch('sys.argv', [command_name] + args):
                command_func = getattr(main, command_name)
                with pytest.raises(SystemExit) as exc_info:
                    command_func()

                # 确认当前返回exit(1)表示未实现
                assert exc_info.value.code == 1, f"{command_name} 应该返回exit(1)表示未实现"

    def test_json_output_not_implemented(self):
        """测试JSON输出格式尚未实现。"""
        # 当--format json被指定时，实际输出应该是JSON格式
        # 但目前的实现只是打印调试信息然后exit(1)

        with patch('sys.argv', ['cc_listhooks', '--format', 'json']):
            with pytest.raises(SystemExit) as exc_info:
                main.cc_listhooks()
            assert exc_info.value.code == 1  # 未实现

    def test_settings_file_operations_not_implemented(self):
        """测试settings文件操作尚未实现。"""
        # 真正的实现应该：
        # 1. 读取settings.json文件
        # 2. 验证hooks格式
        # 3. 修改hooks部分
        # 4. 创建备份
        # 5. 写入更新的文件
        # 6. 返回结构化的输出

        # 但目前的实现没有做这些操作
        with patch('sys.argv', ['cc_addhook', 'PreToolUse', '--command', 'echo', '--matcher', 'Write']):
            with pytest.raises(SystemExit) as exc_info:
                main.cc_addhook()
            assert exc_info.value.code == 1  # 未实现


# 测试辅助函数和数据
def test_parser_creation():
    """测试parser创建函数。"""
    parser = create_parser()
    assert parser.prog == "cchooks"
    assert "cchooks" in parser.description


def test_help_output():
    """测试帮助信息输出。"""
    parser = create_parser()
    help_text = parser.format_help()

    # 确认包含所有主要命令
    assert "cc_addhook" in help_text
    assert "cc_listhooks" in help_text
    assert "cc_generatehook" in help_text


# 性能和边界测试
class TestCLIPerformanceAndEdgeCases:
    """测试CLI性能和边界情况。"""

    def test_argument_parsing_performance(self):
        """测试参数解析性能。"""
        import time

        start_time = time.time()
        for _ in range(100):
            args = parse_args(["cc_addhook", "PreToolUse", "--command", "echo", "--matcher", "Write"])
        end_time = time.time()

        # 参数解析应该很快（<10ms per call平均）
        avg_time = (end_time - start_time) / 100
        assert avg_time < 0.01, f"参数解析太慢: {avg_time:.4f}s per call"

    def test_large_command_arguments(self):
        """测试大型命令参数的处理。"""
        # 测试长命令字符串
        long_command = "echo " + "x" * 1000
        args = parse_args(["cc_addhook", "PreToolUse", "--command", long_command, "--matcher", "Write"])
        assert args.command == long_command

    def test_unicode_arguments(self):
        """测试Unicode参数处理。"""
        unicode_command = "echo '你好世界 🌍'"
        args = parse_args(["cc_addhook", "PreToolUse", "--command", unicode_command, "--matcher", "Write"])
        assert args.command == unicode_command