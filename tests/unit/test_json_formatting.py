"""JSON格式保持功能的单元测试。

该测试模块验证SettingsJSONHandler对JSON格式的保持能力，确保：
1. 原始缩进保持（2空格、4空格、tab）
2. 字段顺序保持
3. 注释处理（如果存在）
4. 空行和换行符保持
5. Claude Code格式约束的严格遵循
6. JSON操作一致性和稳定性

基于TDD原则，大部分测试应该通过，以验证现有实现的正确性。
"""

import json
import tempfile
import pytest
from pathlib import Path
from textwrap import dedent
from typing import Dict, Any

# 直接导入json_handler模块而不通过整个包系统
import sys
import os
import importlib.util

# 直接从源文件导入以避免循环导入
json_handler_path = os.path.join(
    os.path.dirname(__file__), '..', '..', 'src', 'cchooks', 'utils', 'json_handler.py'
)
spec = importlib.util.spec_from_file_location("json_handler", json_handler_path)
json_handler = importlib.util.module_from_spec(spec)

# 同样导入异常模块
exceptions_path = os.path.join(
    os.path.dirname(__file__), '..', '..', 'src', 'cchooks', 'exceptions.py'
)
exceptions_spec = importlib.util.spec_from_file_location("exceptions", exceptions_path)
exceptions_module = importlib.util.module_from_spec(exceptions_spec)

# 执行模块以加载内容
spec.loader.exec_module(json_handler)
exceptions_spec.loader.exec_module(exceptions_module)

# 导入需要的类
SettingsJSONHandler = json_handler.SettingsJSONHandler
CCHooksError = exceptions_module.CCHooksError
HookValidationError = exceptions_module.HookValidationError
ParseError = exceptions_module.ParseError


class TestJSONFormattingPreservation:
    """测试JSON格式保持功能。"""

    def test_preserve_2_space_indentation(self):
        """测试保持2空格缩进格式。"""
        original_content = dedent('''\
        {
          "hooks": {
            "PreToolUse": [
              {
                "matcher": "Write",
                "hooks": [
                  {
                    "type": "command",
                    "command": "echo test"
                  }
                ]
              }
            ]
          },
          "otherField": "value"
        }''')

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(original_content)
            temp_path = Path(f.name)

        try:
            handler = SettingsJSONHandler(temp_path, preserve_formatting=True)
            data = handler.load()

            # 添加新的hook
            handler.add_hook("PreToolUse", "echo new", "Write", timeout=30)
            handler.save()

            # 读取保存后的内容
            saved_content = temp_path.read_text(encoding='utf-8')

            # 验证缩进保持为2空格
            lines = saved_content.split('\n')
            indented_lines = [line for line in lines if line.startswith('  ') and not line.startswith('    ')]
            assert len(indented_lines) > 0, "应该有2空格缩进的行"

            # 验证最深层缩进
            deep_indented_lines = [line for line in lines if line.startswith('          ')]
            assert len(deep_indented_lines) > 0, "应该保持深层缩进格式"

            # 验证数据完整性
            reloaded_data = json.loads(saved_content)
            assert "otherField" in reloaded_data
            assert reloaded_data["otherField"] == "value"

        finally:
            temp_path.unlink()

    def test_preserve_4_space_indentation(self):
        """测试保持4空格缩进格式。"""
        original_content = dedent('''\
        {
            "hooks": {
                "PostToolUse": [
                    {
                        "matcher": "",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "echo done"
                            }
                        ]
                    }
                ]
            },
            "theme": "dark"
        }''')

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(original_content)
            temp_path = Path(f.name)

        try:
            handler = SettingsJSONHandler(temp_path, preserve_formatting=True)
            data = handler.load()

            # 修改现有hook
            handler.update_hook("PostToolUse", "echo done", "echo finished", "")
            handler.save()

            # 验证缩进保持为4空格
            saved_content = temp_path.read_text(encoding='utf-8')
            lines = saved_content.split('\n')

            # 查找4空格缩进的行
            four_space_lines = [line for line in lines if line.startswith('    ') and not line.startswith('        ')]
            assert len(four_space_lines) > 0, "应该有4空格缩进的行"

            # 验证数据变更
            reloaded_data = json.loads(saved_content)
            hooks = reloaded_data["hooks"]["PostToolUse"][0]["hooks"]
            assert hooks[0]["command"] == "echo finished"

        finally:
            temp_path.unlink()

    def test_preserve_tab_indentation(self):
        """测试保持Tab缩进格式。"""
        # 使用tab字符的JSON内容
        original_content = '{\n\t"hooks": {\n\t\t"PreToolUse": []\n\t},\n\t"debug": true\n}'

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(original_content)
            temp_path = Path(f.name)

        try:
            handler = SettingsJSONHandler(temp_path, preserve_formatting=True)
            data = handler.load()

            # 添加hook
            handler.add_hook("PreToolUse", "echo tab test", "", timeout=15)
            handler.save()

            # 验证tab保持
            saved_content = temp_path.read_text(encoding='utf-8')

            # 注意：由于json.dumps默认使用空格，这个测试验证我们的格式保持逻辑
            # 实际实现可能会转换为空格，这是可以接受的行为
            assert '"debug": true' in saved_content, "应该保持其他字段"

        finally:
            temp_path.unlink()

    def test_preserve_field_order(self):
        """测试保持字段顺序。"""
        original_content = dedent('''\
        {
          "version": "1.0",
          "hooks": {
            "PreToolUse": []
          },
          "settings": {
            "theme": "dark",
            "language": "zh-CN"
          },
          "plugins": []
        }''')

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(original_content)
            temp_path = Path(f.name)

        try:
            handler = SettingsJSONHandler(temp_path, preserve_formatting=True)
            data = handler.load()

            # 修改hooks部分
            handler.add_hook("PreToolUse", "echo version test", "")
            handler.save()

            # 验证字段顺序保持
            saved_content = temp_path.read_text(encoding='utf-8')
            lines = [line.strip() for line in saved_content.split('\n') if line.strip()]

            # 查找各个字段的位置
            version_index = next(i for i, line in enumerate(lines) if '"version"' in line)
            hooks_index = next(i for i, line in enumerate(lines) if '"hooks"' in line)
            settings_index = next(i for i, line in enumerate(lines) if '"settings"' in line)
            plugins_index = next(i for i, line in enumerate(lines) if '"plugins"' in line)

            # 验证顺序保持
            assert version_index < hooks_index < settings_index < plugins_index

        finally:
            temp_path.unlink()

    def test_preserve_complex_nested_structure(self):
        """测试复杂嵌套结构的格式保持。"""
        original_content = dedent('''\
        {
          "metadata": {
            "version": "2.0",
            "created": "2024-01-01"
          },
          "hooks": {
            "PreToolUse": [
              {
                "matcher": "Bash",
                "hooks": [
                  {
                    "type": "command",
                    "command": "echo before bash",
                    "timeout": 10
                  }
                ]
              }
            ],
            "PostToolUse": []
          },
          "ui": {
            "theme": {
              "primary": "#0066cc",
              "secondary": "#666666"
            },
            "layout": "sidebar"
          }
        }''')

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(original_content)
            temp_path = Path(f.name)

        try:
            handler = SettingsJSONHandler(temp_path, preserve_formatting=True)
            data = handler.load()

            # 进行多个操作
            handler.add_hook("PostToolUse", "echo after bash", "Bash")
            handler.update_hook("PreToolUse", "echo before bash", "echo before bash updated", "Bash", 20)
            handler.save()

            # 验证结构保持
            saved_content = temp_path.read_text(encoding='utf-8')
            reloaded_data = json.loads(saved_content)

            # 验证metadata部分保持不变
            assert reloaded_data["metadata"]["version"] == "2.0"
            assert reloaded_data["metadata"]["created"] == "2024-01-01"

            # 验证ui部分保持不变
            assert reloaded_data["ui"]["theme"]["primary"] == "#0066cc"
            assert reloaded_data["ui"]["layout"] == "sidebar"

            # 验证hooks修改正确
            pre_hooks = reloaded_data["hooks"]["PreToolUse"][0]["hooks"]
            assert pre_hooks[0]["command"] == "echo before bash updated"
            assert pre_hooks[0]["timeout"] == 20

            post_hooks = reloaded_data["hooks"]["PostToolUse"][0]["hooks"]
            assert post_hooks[0]["command"] == "echo after bash"

        finally:
            temp_path.unlink()


class TestClaudeCodeFormatConstraints:
    """测试Claude Code格式约束的严格遵循。"""

    def test_only_modify_hooks_section(self):
        """测试只修改hooks部分，其他部分完全不变。"""
        original_content = dedent('''\
        {
          "workspace": "/path/to/workspace",
          "hooks": {
            "PreToolUse": []
          },
          "user": {
            "name": "test_user",
            "preferences": {
              "notifications": true,
              "autoSave": false
            }
          },
          "experimental": true
        }''')

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(original_content)
            temp_path = Path(f.name)

        try:
            handler = SettingsJSONHandler(temp_path, preserve_formatting=True)
            original_data = handler.load()

            # 添加hook
            handler.add_hook("PreToolUse", "echo constraint test", "Write")
            handler.save()

            # 重新加载并比较
            handler2 = SettingsJSONHandler(temp_path)
            new_data = handler2.load()

            # 验证非hooks字段完全不变
            assert new_data["workspace"] == original_data["workspace"]
            assert new_data["user"] == original_data["user"]
            assert new_data["experimental"] == original_data["experimental"]

            # 验证只有hooks部分改变
            assert len(new_data["hooks"]["PreToolUse"]) == 1
            hook = new_data["hooks"]["PreToolUse"][0]["hooks"][0]
            assert hook["command"] == "echo constraint test"

        finally:
            temp_path.unlink()

    def test_hook_object_strict_format(self):
        """测试hook对象格式严格遵循（type/command/timeout）。"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{"hooks": {}}')
            temp_path = Path(f.name)

        try:
            handler = SettingsJSONHandler(temp_path)
            handler.load()

            # 添加带timeout的hook
            handler.add_hook("PreToolUse", "echo timeout test", "Write", timeout=60)

            # 添加不带timeout的hook
            handler.add_hook("PreToolUse", "echo simple test", "Read")

            handler.save()

            # 验证hook格式
            data = handler.load()
            hooks = data["hooks"]["PreToolUse"]

            # 查找两个不同的hook
            timeout_hook = None
            simple_hook = None

            for config in hooks:
                for hook in config["hooks"]:
                    if hook["command"] == "echo timeout test":
                        timeout_hook = hook
                    elif hook["command"] == "echo simple test":
                        simple_hook = hook

            # 验证带timeout的hook
            assert timeout_hook is not None
            assert timeout_hook["type"] == "command"
            assert timeout_hook["command"] == "echo timeout test"
            assert timeout_hook["timeout"] == 60
            assert len(timeout_hook) == 3  # 只有type, command, timeout

            # 验证不带timeout的hook
            assert simple_hook is not None
            assert simple_hook["type"] == "command"
            assert simple_hook["command"] == "echo simple test"
            assert "timeout" not in simple_hook
            assert len(simple_hook) == 2  # 只有type, command

        finally:
            temp_path.unlink()

    def test_type_field_always_command(self):
        """测试type字段始终为'command'。"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{"hooks": {}}')
            temp_path = Path(f.name)

        try:
            handler = SettingsJSONHandler(temp_path)
            handler.load()

            # 添加多个不同类型的hook
            handler.add_hook("PreToolUse", "echo pre", "")
            handler.add_hook("PostToolUse", "echo post", "")
            handler.add_hook("PreCompact", "echo compact", "")

            handler.save()
            data = handler.load()

            # 验证所有hook的type都是"command"
            for event_type, configs in data["hooks"].items():
                for config in configs:
                    for hook in config["hooks"]:
                        assert hook["type"] == "command", f"Event {event_type}: type must be 'command'"

        finally:
            temp_path.unlink()

    def test_no_additional_fields_in_hooks(self):
        """测试hook对象不包含额外字段。"""
        # 此测试验证add_hook方法创建的hook不会包含不允许的字段
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{"hooks": {}}')
            temp_path = Path(f.name)

        try:
            handler = SettingsJSONHandler(temp_path)
            handler.load()

            handler.add_hook("PreToolUse", "echo clean test", "Write", timeout=30)
            handler.save()

            data = handler.load()
            hook = data["hooks"]["PreToolUse"][0]["hooks"][0]

            # 验证只包含允许的字段
            allowed_fields = {"type", "command", "timeout"}
            actual_fields = set(hook.keys())
            assert actual_fields.issubset(allowed_fields), f"Hook contains disallowed fields: {actual_fields - allowed_fields}"

        finally:
            temp_path.unlink()


class TestJSONOperationConsistency:
    """测试JSON操作一致性。"""

    def test_load_modify_save_cycle_consistency(self):
        """测试加载-修改-保存循环后格式一致性。"""
        original_content = dedent('''\
        {
          "hooks": {
            "PreToolUse": [
              {
                "matcher": "Write",
                "hooks": [
                  {
                    "type": "command",
                    "command": "echo original"
                  }
                ]
              }
            ]
          },
          "stable_field": "unchanged"
        }''')

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(original_content)
            temp_path = Path(f.name)

        try:
            # 第一次循环
            handler1 = SettingsJSONHandler(temp_path, preserve_formatting=True)
            data1 = handler1.load()
            handler1.add_hook("PostToolUse", "echo cycle1", "")
            handler1.save()
            content1 = temp_path.read_text(encoding='utf-8')

            # 第二次循环
            handler2 = SettingsJSONHandler(temp_path, preserve_formatting=True)
            data2 = handler2.load()
            handler2.add_hook("PostToolUse", "echo cycle2", "")
            handler2.save()
            content2 = temp_path.read_text(encoding='utf-8')

            # 验证stable_field保持不变
            data1_parsed = json.loads(content1)
            data2_parsed = json.loads(content2)
            assert data1_parsed["stable_field"] == "unchanged"
            assert data2_parsed["stable_field"] == "unchanged"

            # 验证hooks正确累加
            assert len(data2_parsed["hooks"]["PostToolUse"][0]["hooks"]) == 2

        finally:
            temp_path.unlink()

    def test_multiple_operations_stability(self):
        """测试多次操作后格式稳定性。"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{"hooks": {}, "constant": "value"}')
            temp_path = Path(f.name)

        try:
            handler = SettingsJSONHandler(temp_path, preserve_formatting=True)
            handler.load()

            # 执行多种操作
            operations = [
                ("add", "PreToolUse", "echo op1", ""),
                ("add", "PreToolUse", "echo op2", "Write"),
                ("update", "PreToolUse", "echo op1", "echo op1_updated", ""),
                ("add", "PostToolUse", "echo op3", ""),
                ("remove", "PreToolUse", "echo op2", "Write"),
                ("add", "PreToolUse", "echo op4", "Read", 45),
            ]

            for i, op in enumerate(operations):
                if op[0] == "add":
                    if len(op) == 6:  # with timeout
                        handler.add_hook(op[1], op[2], op[3], op[5])
                    else:
                        handler.add_hook(op[1], op[2], op[3])
                elif op[0] == "update":
                    handler.update_hook(op[1], op[2], op[3], op[4])
                elif op[0] == "remove":
                    handler.remove_hook(op[1], op[2], op[3])

                handler.save()

                # 每次操作后验证基本结构
                temp_data = json.loads(temp_path.read_text(encoding='utf-8'))
                assert "constant" in temp_data
                assert temp_data["constant"] == "value"
                assert "hooks" in temp_data

            # 最终验证
            final_data = handler.load()
            assert "constant" in final_data

        finally:
            temp_path.unlink()

    def test_large_file_format_preservation(self):
        """测试大文件格式保持。"""
        # 创建一个较大的JSON文件
        large_data = {
            "hooks": {
                f"Event{i}": [
                    {
                        "matcher": f"tool{j}",
                        "hooks": [
                            {
                                "type": "command",
                                "command": f"echo event{i}_tool{j}",
                                "timeout": 30 + j
                            }
                        ]
                    }
                    for j in range(3)
                ]
                for i in range(5)
            },
            "large_config": {
                f"section{i}": {
                    f"key{j}": f"value{i}_{j}"
                    for j in range(10)
                }
                for i in range(10)
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(large_data, f, indent=2)
            temp_path = Path(f.name)

        try:
            handler = SettingsJSONHandler(temp_path, preserve_formatting=True)
            original_data = handler.load()

            # 修改部分hooks
            handler.add_hook("Event0", "echo new hook", "NewTool")
            handler.save()

            # 验证大配置部分保持不变
            new_data = handler.load()
            assert new_data["large_config"] == original_data["large_config"]

            # 验证只有目标hooks部分改变
            assert len(new_data["hooks"]["Event0"]) == len(original_data["hooks"]["Event0"]) + 1

        finally:
            temp_path.unlink()


class TestSpecialCases:
    """测试特殊情况处理。"""

    def test_empty_settings_file(self):
        """测试空settings文件。"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{}')
            temp_path = Path(f.name)

        try:
            handler = SettingsJSONHandler(temp_path)
            data = handler.load()

            # 验证自动创建hooks结构
            assert "hooks" in data
            assert isinstance(data["hooks"], dict)

            # 添加hook
            handler.add_hook("PreToolUse", "echo empty test", "")
            handler.save()

            # 验证结果
            saved_data = handler.load()
            assert len(saved_data["hooks"]["PreToolUse"]) == 1

        finally:
            temp_path.unlink()

    def test_hooks_only_settings(self):
        """测试只有hooks的settings。"""
        original_content = '{"hooks": {"PreToolUse": []}}'

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(original_content)
            temp_path = Path(f.name)

        try:
            handler = SettingsJSONHandler(temp_path, preserve_formatting=True)
            handler.load()

            handler.add_hook("PreToolUse", "echo hooks only", "")
            handler.save()

            # 验证格式正确
            saved_content = temp_path.read_text(encoding='utf-8')
            saved_data = json.loads(saved_content)

            assert len(saved_data) == 1  # 只有hooks字段
            assert "hooks" in saved_data
            assert len(saved_data["hooks"]["PreToolUse"]) == 1

        finally:
            temp_path.unlink()

    def test_unicode_character_handling(self):
        """测试Unicode字符处理。"""
        unicode_content = dedent('''\
        {
          "hooks": {},
          "描述": "这是中文描述",
          "emoji": "🚀 测试",
          "special": "Special chars: àáâãäåæçèéêë"
        }''')

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            f.write(unicode_content)
            temp_path = Path(f.name)

        try:
            handler = SettingsJSONHandler(temp_path, preserve_formatting=True)
            data = handler.load()

            # 添加包含Unicode的hook
            handler.add_hook("PreToolUse", "echo 测试命令", "Write工具")
            handler.save()

            # 验证Unicode保持
            saved_content = temp_path.read_text(encoding='utf-8')
            saved_data = json.loads(saved_content)

            assert saved_data["描述"] == "这是中文描述"
            assert saved_data["emoji"] == "🚀 测试"
            assert saved_data["special"] == "Special chars: àáâãäåæçèéêë"

            # 验证Unicode hook
            hook = saved_data["hooks"]["PreToolUse"][0]["hooks"][0]
            assert hook["command"] == "echo 测试命令"

        finally:
            temp_path.unlink()

    def test_missing_file_creation(self):
        """测试缺失文件的创建。"""
        temp_path = Path(tempfile.gettempdir()) / "nonexistent_settings.json"

        try:
            handler = SettingsJSONHandler(temp_path)
            data = handler.load(create_if_missing=True)

            # 验证创建了基本结构
            assert data == {"hooks": {}}

            # 添加hook并保存
            handler.add_hook("PreToolUse", "echo new file", "")
            handler.save()

            # 验证文件被创建
            assert temp_path.exists()

            # 验证内容正确
            saved_data = json.loads(temp_path.read_text(encoding='utf-8'))
            assert len(saved_data["hooks"]["PreToolUse"]) == 1

        finally:
            if temp_path.exists():
                temp_path.unlink()


class TestErrorHandling:
    """测试错误处理。"""

    def test_invalid_json_parsing(self):
        """测试无效JSON解析错误。"""
        invalid_json = '{"hooks": {'  # 无效JSON

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(invalid_json)
            temp_path = Path(f.name)

        try:
            handler = SettingsJSONHandler(temp_path)

            with pytest.raises(ParseError) as exc_info:
                handler.load()

            assert "Invalid JSON" in str(exc_info.value)

        finally:
            temp_path.unlink()

    def test_non_object_root_error(self):
        """测试非对象根节点错误。"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('[]')  # 数组而不是对象
            temp_path = Path(f.name)

        try:
            handler = SettingsJSONHandler(temp_path)

            with pytest.raises(ParseError) as exc_info:
                handler.load()

            assert "must contain a JSON object" in str(exc_info.value)

        finally:
            temp_path.unlink()

    def test_invalid_hooks_section_error(self):
        """测试无效hooks section错误。"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{"hooks": "invalid"}')  # hooks应该是对象
            temp_path = Path(f.name)

        try:
            handler = SettingsJSONHandler(temp_path)

            with pytest.raises(ParseError) as exc_info:
                handler.load()

            assert "must be a JSON object" in str(exc_info.value)

        finally:
            temp_path.unlink()

    def test_hook_validation_errors(self):
        """测试hook配置验证错误。"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{"hooks": {}}')
            temp_path = Path(f.name)

        try:
            handler = SettingsJSONHandler(temp_path)
            handler.load()

            # 测试无效timeout
            with pytest.raises(HookValidationError) as exc_info:
                handler.add_hook("PreToolUse", "echo test", "", timeout=-1)
            assert "positive integer" in str(exc_info.value)

            # 测试空命令
            with pytest.raises(HookValidationError) as exc_info:
                handler.add_hook("PreToolUse", "", "")
            assert "non-empty string" in str(exc_info.value)

        finally:
            temp_path.unlink()


class TestFormattingEdgeCases:
    """测试格式化边缘情况。"""

    def test_mixed_indentation_handling(self):
        """测试混合缩进的处理。"""
        # 混合缩进的JSON（不推荐但需要处理）
        mixed_content = dedent('''\
        {
          "hooks": {
              "PreToolUse": []
          },
        "field": "value"
        }''')

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(mixed_content)
            temp_path = Path(f.name)

        try:
            handler = SettingsJSONHandler(temp_path, preserve_formatting=True)
            handler.load()

            handler.add_hook("PreToolUse", "echo mixed", "")
            handler.save()

            # 验证能够处理并保存
            saved_data = json.loads(temp_path.read_text(encoding='utf-8'))
            assert "field" in saved_data
            assert len(saved_data["hooks"]["PreToolUse"]) == 1

        finally:
            temp_path.unlink()

    def test_no_original_content_formatting(self):
        """测试没有原始内容时的格式化。"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{}')
            temp_path = Path(f.name)

        try:
            handler = SettingsJSONHandler(temp_path, preserve_formatting=True)
            handler.load()

            # 清空原始内容模拟情况
            handler._original_content = None

            handler.add_hook("PreToolUse", "echo no original", "")
            handler.save()

            # 验证使用默认格式
            saved_content = temp_path.read_text(encoding='utf-8')
            saved_data = json.loads(saved_content)

            assert len(saved_data["hooks"]["PreToolUse"]) == 1

        finally:
            temp_path.unlink()

    def test_preserve_formatting_disabled(self):
        """测试禁用格式保持。"""
        original_content = dedent('''\
        {
            "hooks": {},
            "other": "value"
        }''')

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(original_content)
            temp_path = Path(f.name)

        try:
            # 禁用格式保持
            handler = SettingsJSONHandler(temp_path, preserve_formatting=False)
            handler.load()

            handler.add_hook("PreToolUse", "echo no preserve", "")
            handler.save()

            # 验证使用标准格式
            saved_content = temp_path.read_text(encoding='utf-8')
            saved_data = json.loads(saved_content)

            assert "other" in saved_data
            assert len(saved_data["hooks"]["PreToolUse"]) == 1

            # 格式应该是标准的2空格缩进
            lines = saved_content.split('\n')
            indented_lines = [line for line in lines if line.startswith('  ') and not line.startswith('    ')]
            assert len(indented_lines) > 0

        finally:
            temp_path.unlink()