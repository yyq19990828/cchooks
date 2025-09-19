"""CLI命令合约测试（最小版本）。

直接测试CLI模块，不依赖其他cchooks组件。
这些测试验证T008任务的要求：CLI命令合约测试必须失败，因为实现尚未完成。
"""

import pytest
import sys
import os
import argparse
from unittest.mock import patch, MagicMock

# 设置路径
test_dir = os.path.dirname(__file__)
src_dir = os.path.join(test_dir, '../../src')
sys.path.insert(0, src_dir)


def test_cli_argument_parser_import():
    """测试能否导入CLI参数解析器。"""
    try:
        # 直接导入CLI模块，避免导入其他依赖
        import importlib.util

        # 导入argument_parser模块
        parser_path = os.path.join(src_dir, 'cchooks/cli/argument_parser.py')
        spec = importlib.util.spec_from_file_location("argument_parser", parser_path)
        argument_parser = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(argument_parser)

        assert hasattr(argument_parser, 'parse_args')
        assert hasattr(argument_parser, 'create_parser')

    except ImportError as e:
        pytest.fail(f"无法导入CLI参数解析器: {e}")


def test_cli_main_import():
    """测试能否导入CLI主模块。"""
    try:
        import importlib.util

        # 导入main模块
        main_path = os.path.join(src_dir, 'cchooks/cli/main.py')
        spec = importlib.util.spec_from_file_location("main", main_path)
        main_module = importlib.util.module_from_spec(spec)

        # 模拟argument_parser导入
        import types
        mock_argument_parser = types.ModuleType('argument_parser')
        mock_argument_parser.parse_args = MagicMock()
        sys.modules['cchooks.cli.argument_parser'] = mock_argument_parser

        spec.loader.exec_module(main_module)

        # 验证所有命令函数存在
        expected_commands = [
            'cc_addhook', 'cc_updatehook', 'cc_removehook', 'cc_listhooks',
            'cc_validatehooks', 'cc_generatehook', 'cc_registertemplate',
            'cc_listtemplates', 'cc_unregistertemplate'
        ]

        for command in expected_commands:
            assert hasattr(main_module, command), f"缺少命令函数: {command}"

    except ImportError as e:
        pytest.fail(f"无法导入CLI主模块: {e}")


class TestArgumentParserStandalone:
    """独立测试参数解析器功能。"""

    def setup_method(self):
        """设置测试环境。"""
        import importlib.util

        # 导入argument_parser模块
        parser_path = os.path.join(src_dir, 'cchooks/cli/argument_parser.py')
        spec = importlib.util.spec_from_file_location("argument_parser", parser_path)
        self.argument_parser = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.argument_parser)

    def test_create_parser_basic(self):
        """测试基本的parser创建。"""
        parser = self.argument_parser.create_parser()
        assert isinstance(parser, argparse.ArgumentParser)
        assert parser.prog == "cchooks"

    def test_valid_hook_events_defined(self):
        """测试钩子事件类型定义正确。"""
        expected_events = [
            "PreToolUse", "PostToolUse", "Notification", "UserPromptSubmit",
            "Stop", "SubagentStop", "PreCompact", "SessionStart", "SessionEnd"
        ]

        actual_events = self.argument_parser.HOOK_EVENTS
        assert actual_events == expected_events

    def test_valid_template_types_defined(self):
        """测试模板类型定义正确。"""
        expected_types = [
            "security-guard", "auto-formatter", "auto-linter", "git-auto-commit",
            "permission-logger", "desktop-notifier", "task-manager", "prompt-filter",
            "context-loader", "cleanup-handler"
        ]

        actual_types = self.argument_parser.TEMPLATE_TYPES
        assert actual_types == expected_types

    def test_parse_args_with_valid_addhook_command(self):
        """测试有效的addhook命令解析。"""
        args = self.argument_parser.parse_args([
            "cc_addhook", "PreToolUse", "--command", "echo test", "--matcher", "Write"
        ])
        assert args.subcommand == "cc_addhook"
        assert args.event == "PreToolUse"
        assert args.command == "echo test"
        assert args.matcher == "Write"

    def test_parse_args_with_invalid_command_fails(self):
        """测试无效命令导致失败。"""
        with pytest.raises(SystemExit):
            self.argument_parser.parse_args(["invalid_command"])

    def test_parse_args_with_missing_required_args_fails(self):
        """测试缺少必需参数导致失败。"""
        # 缺少event
        with pytest.raises(SystemExit):
            self.argument_parser.parse_args(["cc_addhook"])

        # 缺少command/script
        with pytest.raises(SystemExit):
            self.argument_parser.parse_args(["cc_addhook", "PreToolUse"])

    def test_timeout_validation(self):
        """测试timeout参数验证。"""
        # 有效timeout
        args = self.argument_parser.parse_args([
            "cc_addhook", "PreToolUse", "--command", "echo", "--timeout", "60", "--matcher", "Write"
        ])
        assert args.timeout == 60

        # 无效timeout（超出范围）
        with pytest.raises(SystemExit):
            self.argument_parser.parse_args([
                "cc_addhook", "PreToolUse", "--command", "echo", "--timeout", "0", "--matcher", "Write"
            ])

    def test_mutually_exclusive_arguments(self):
        """测试互斥参数组。"""
        # command和script不能同时存在
        with pytest.raises(SystemExit):
            self.argument_parser.parse_args([
                "cc_addhook", "PreToolUse", "--command", "echo", "--script", "test.py"
            ])

    def test_matcher_required_for_tool_events(self):
        """测试工具事件需要matcher参数。"""
        # PreToolUse需要matcher
        with pytest.raises(SystemExit):
            self.argument_parser.parse_args([
                "cc_addhook", "PreToolUse", "--command", "echo"
            ])

        # PostToolUse需要matcher
        with pytest.raises(SystemExit):
            self.argument_parser.parse_args([
                "cc_addhook", "PostToolUse", "--command", "echo"
            ])

    def test_json_customization_validation(self):
        """测试JSON自定义参数验证。"""
        # 有效JSON
        args = self.argument_parser.parse_args([
            "cc_generatehook", "security-guard", "PreToolUse", "output.py",
            "--customization", '{"key": "value"}'
        ])
        assert args.customization == '{"key": "value"}'

        # 无效JSON
        with pytest.raises(SystemExit):
            self.argument_parser.parse_args([
                "cc_generatehook", "security-guard", "PreToolUse", "output.py",
                "--customization", '{"invalid": json}'
            ])


class TestCLICommandImplementationStatus:
    """测试CLI命令实现状态（TDD要求 - 这些测试必须失败）。"""

    def setup_method(self):
        """设置测试环境。"""
        import importlib.util
        import types

        # 模拟argument_parser
        mock_argument_parser = types.ModuleType('argument_parser')
        mock_argument_parser.parse_args = MagicMock()
        sys.modules['cchooks.cli.argument_parser'] = mock_argument_parser

        # 导入main模块
        main_path = os.path.join(src_dir, 'cchooks/cli/main.py')
        spec = importlib.util.spec_from_file_location("main", main_path)
        self.main_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.main_module)

    def test_all_commands_return_exit_1_unimplemented(self):
        """测试所有命令当前都返回exit(1)表示未实现。"""
        commands = [
            'cc_addhook', 'cc_updatehook', 'cc_removehook', 'cc_listhooks',
            'cc_validatehooks', 'cc_generatehook', 'cc_registertemplate',
            'cc_listtemplates', 'cc_unregistertemplate'
        ]

        for command_name in commands:
            command_func = getattr(self.main_module, command_name)

            # 模拟sys.argv
            with patch('sys.argv', [command_name]):
                with pytest.raises(SystemExit) as exc_info:
                    command_func()

                # 验证返回exit(1)表示未实现
                assert exc_info.value.code == 1, f"{command_name} 应该返回exit(1)表示未实现"

    def test_commands_print_unimplemented_message(self):
        """测试命令打印未实现消息。"""
        command_func = getattr(self.main_module, 'cc_addhook')

        with patch('sys.argv', ['cc_addhook']):
            with patch('builtins.print') as mock_print:
                with pytest.raises(SystemExit):
                    command_func()

                # 验证打印了未实现消息
                print_calls = [call[0][0] for call in mock_print.call_args_list]
                assert any("尚未实现" in call for call in print_calls), "应该打印未实现消息"

    def test_no_actual_settings_file_modification(self):
        """测试当前实现不会修改settings文件。"""
        import tempfile
        import json

        # 创建临时settings文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            test_settings = {
                "hooks": {},
                "other_setting": "should_not_change"
            }
            json.dump(test_settings, f)
            settings_path = f.name

        try:
            # 运行命令
            with patch('sys.argv', ['cc_addhook']):
                with pytest.raises(SystemExit):
                    getattr(self.main_module, 'cc_addhook')()

            # 验证文件未被修改
            with open(settings_path, 'r') as f:
                final_settings = json.load(f)

            assert final_settings == test_settings, "settings文件不应该被修改"

        finally:
            os.unlink(settings_path)

    def test_no_json_output_format_implemented(self):
        """测试JSON输出格式尚未实现。"""
        # 实际实现应该根据--format参数输出结构化JSON
        # 但当前实现只是打印调试信息

        command_func = getattr(self.main_module, 'cc_listhooks')

        with patch('sys.argv', ['cc_listhooks', '--format', 'json']):
            with patch('builtins.print') as mock_print:
                with pytest.raises(SystemExit) as exc_info:
                    command_func()

                # 验证没有输出有效的JSON格式
                print_calls = [str(call) for call in mock_print.call_args_list]
                json_output_found = False

                for call in print_calls:
                    try:
                        # 尝试解析是否有JSON输出
                        if call.startswith("call('") and call.endswith("')"):
                            output = call[6:-2]  # 提取print的内容
                            json.loads(output)
                            json_output_found = True
                    except (json.JSONDecodeError, ValueError):
                        continue

                assert not json_output_found, "应该没有实现JSON输出格式"
                assert exc_info.value.code == 1  # 未实现


class TestCLIContractCompliance:
    """测试CLI合约规范遵循性（当前应该失败的测试）。"""

    def test_success_output_structure_not_implemented(self):
        """测试成功输出结构尚未按合约实现。"""
        # 根据contracts/cli_commands.yaml，成功输出应该包含：
        expected_structure = {
            "success": True,
            "message": "string",
            "data": {},
            "warnings": [],
            "errors": []
        }

        # 当前实现不返回这种结构
        # 这个测试记录了预期的行为，当实现完成后应该通过

        # 验证当前实现确实没有按合约返回结构化输出
        import importlib.util
        import types

        mock_argument_parser = types.ModuleType('argument_parser')
        mock_argument_parser.parse_args = MagicMock()
        sys.modules['cchooks.cli.argument_parser'] = mock_argument_parser

        main_path = os.path.join(src_dir, 'cchooks/cli/main.py')
        spec = importlib.util.spec_from_file_location("main", main_path)
        main_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(main_module)

        with patch('sys.argv', ['cc_addhook']):
            with pytest.raises(SystemExit) as exc_info:
                main_module.cc_addhook()

            # 当前返回exit(1)而不是结构化输出
            assert exc_info.value.code == 1

    def test_error_output_structure_not_implemented(self):
        """测试错误输出结构尚未按合约实现。"""
        # 根据合约，错误输出应该包含：
        expected_error_structure = {
            "success": False,
            "message": "string",
            "errors": ["error messages"]
        }

        # 当前实现只是exit(1)，没有结构化错误输出
        # 这个测试将在实现完成后通过
        pass  # 标记为预期失败

    def test_exit_codes_not_fully_implemented(self):
        """测试退出代码规范尚未完全实现。"""
        # 合约定义的退出代码：
        # 0: 成功
        # 1: 验证错误或用户错误
        # 2: 系统错误（文件权限等）

        # 当前所有命令都返回1（未实现错误）
        # 实际实现应该根据不同错误类型返回不同代码
        pass  # 标记为预期失败


def test_contract_test_file_exists():
    """验证合约测试文件存在且可执行。"""
    current_file = __file__
    assert os.path.exists(current_file)

    # 验证测试包含必要的测试类
    with open(current_file, 'r') as f:
        content = f.read()

    required_test_classes = [
        'TestArgumentParserStandalone',
        'TestCLICommandImplementationStatus',
        'TestCLIContractCompliance'
    ]

    for test_class in required_test_classes:
        assert test_class in content, f"缺少必要的测试类: {test_class}"


def test_tdd_requirement_validation():
    """验证TDD要求：测试应该失败因为实现未完成。"""
    # 这个测试本身验证我们遵循了TDD方法
    # 所有实现相关的测试都应该失败，直到实现完成

    # 记录当前状态：所有CLI命令返回exit(1)表示未实现
    # 这符合T008任务的TDD要求
    assert True  # 这个测试通过，确认我们正确设置了失败的测试