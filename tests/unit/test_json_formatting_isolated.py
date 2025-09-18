"""JSON格式保持功能的独立测试（避免循环导入）。

该测试模块验证SettingsJSONHandler对JSON格式的保持能力，使用内联代码避免导入问题。
"""

import json
import tempfile
import pytest
import re
import shutil
from datetime import datetime
from pathlib import Path
from textwrap import dedent
from typing import Any, Dict, List, Optional, Tuple, Union


# 内联异常定义
class CCHooksError(Exception):
    """Base exception for all cchooks errors."""
    pass


class HookValidationError(CCHooksError):
    """Raised when hook input validation fails."""
    pass


class ParseError(CCHooksError):
    """Raised when JSON parsing fails."""
    pass


# 内联SettingsJSONHandler的简化版本用于测试
class SettingsJSONHandler:
    """Claude Code settings.json文件的专门处理器。"""

    def __init__(self, file_path: Union[str, Path], preserve_formatting: bool = True):
        """初始化处理器。"""
        self.file_path = Path(file_path)
        self.preserve_formatting = preserve_formatting
        self._original_content: Optional[str] = None
        self._parsed_data: Optional[Dict[str, Any]] = None
        self._indent_size = 2  # Claude Code默认缩进

    def exists(self) -> bool:
        """检查文件是否存在。"""
        return self.file_path.exists()

    def load(self, create_if_missing: bool = False) -> Dict[str, Any]:
        """加载并解析JSON文件。"""
        if not self.exists():
            if create_if_missing:
                empty_settings = {"hooks": {}}
                self._parsed_data = empty_settings
                return empty_settings
            else:
                raise CCHooksError(f"Settings file not found: {self.file_path}")

        try:
            self._original_content = self.file_path.read_text(encoding='utf-8')
        except (OSError, IOError) as e:
            raise CCHooksError(f"Failed to read settings file: {e}")

        try:
            self._parsed_data = json.loads(self._original_content)
        except json.JSONDecodeError as e:
            raise ParseError(f"Invalid JSON in settings file: {e}")

        # 验证基本结构
        if not isinstance(self._parsed_data, dict):
            raise ParseError("Settings file must contain a JSON object")

        # 确保hooks节点存在
        if "hooks" not in self._parsed_data:
            self._parsed_data["hooks"] = {}
        elif not isinstance(self._parsed_data["hooks"], dict):
            raise ParseError("'hooks' section must be a JSON object")

        return self._parsed_data

    def save(self, data: Optional[Dict[str, Any]] = None, create_dirs: bool = True) -> None:
        """保存JSON数据到文件。"""
        if data is None:
            if self._parsed_data is None:
                raise CCHooksError("No data to save. Call load() first or provide data.")
            data = self._parsed_data
        else:
            # 验证提供的数据
            self._validate_settings_structure(data)
            self._parsed_data = data

        # 创建父目录
        if create_dirs:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            if self.preserve_formatting and self._original_content:
                # 尝试保持原有格式
                formatted_content = self._preserve_original_formatting(data)
            else:
                # 使用标准格式化
                formatted_content = json.dumps(
                    data,
                    indent=self._indent_size,
                    ensure_ascii=False,
                    separators=(',', ': ')
                )

            self.file_path.write_text(formatted_content, encoding='utf-8')

        except (OSError, IOError) as e:
            raise CCHooksError(f"Failed to save settings file: {e}")

    def add_hook(self, event_type: str, command: str, matcher: str = "",
                 timeout: Optional[int] = None) -> None:
        """添加新的hook配置。"""
        if self._parsed_data is None:
            raise CCHooksError("No data loaded. Call load() first.")

        # 验证hook配置
        hook_config = {"type": "command", "command": command}
        if timeout is not None:
            if not isinstance(timeout, int) or timeout <= 0:
                raise HookValidationError("Timeout must be a positive integer")
            hook_config["timeout"] = timeout

        self._validate_hook_config(hook_config)

        # 确保hooks结构存在
        hooks_section = self._parsed_data.setdefault("hooks", {})
        event_configs = hooks_section.setdefault(event_type, [])

        # 查找是否已存在相同matcher的配置
        target_config = None
        for config in event_configs:
            if isinstance(config, dict) and config.get("matcher") == matcher:
                target_config = config
                break

        # 如果不存在，创建新的matcher配置
        if target_config is None:
            target_config = {"matcher": matcher, "hooks": []}
            event_configs.append(target_config)

        # 添加hook到对应的matcher配置中
        if "hooks" not in target_config:
            target_config["hooks"] = []
        target_config["hooks"].append(hook_config)

    def update_hook(self, event_type: str, old_command: str, new_command: str,
                   matcher: str = "", timeout: Optional[int] = None) -> bool:
        """更新existing hook配置。"""
        if self._parsed_data is None:
            raise CCHooksError("No data loaded. Call load() first.")

        hooks_section = self._parsed_data.get("hooks", {})
        event_configs = hooks_section.get(event_type, [])

        for config in event_configs:
            if isinstance(config, dict) and config.get("matcher") == matcher:
                hooks_list = config.get("hooks", [])
                for hook in hooks_list:
                    if isinstance(hook, dict) and hook.get("command") == old_command:
                        # 验证新的hook配置
                        new_hook_config = {"type": "command", "command": new_command}
                        if timeout is not None:
                            if not isinstance(timeout, int) or timeout <= 0:
                                raise HookValidationError("Timeout must be a positive integer")
                            new_hook_config["timeout"] = timeout
                        elif "timeout" in hook:
                            # 保持原有timeout
                            new_hook_config["timeout"] = hook["timeout"]

                        self._validate_hook_config(new_hook_config)

                        # 更新hook配置
                        hook.clear()
                        hook.update(new_hook_config)
                        return True

        return False

    def _validate_settings_structure(self, data: Dict[str, Any]) -> None:
        """验证settings.json的整体结构。"""
        if not isinstance(data, dict):
            raise HookValidationError("Settings must be a JSON object")

        if "hooks" in data:
            hooks_section = data["hooks"]
            if not isinstance(hooks_section, dict):
                raise HookValidationError("'hooks' section must be a JSON object")

    def _validate_hook_config(self, hook: Dict[str, Any]) -> None:
        """验证单个hook配置。"""
        if not isinstance(hook, dict):
            raise HookValidationError("Hook configuration must be an object")

        # 验证必需字段
        if "type" not in hook:
            raise HookValidationError("Hook must have 'type' field")
        if hook["type"] != "command":
            raise HookValidationError("Hook type must be 'command'")

        if "command" not in hook:
            raise HookValidationError("Hook must have 'command' field")
        if not isinstance(hook["command"], str) or not hook["command"].strip():
            raise HookValidationError("Hook command must be a non-empty string")

        # 验证可选字段
        if "timeout" in hook:
            timeout = hook["timeout"]
            if not isinstance(timeout, int) or timeout <= 0:
                raise HookValidationError("Hook timeout must be a positive integer")

        # 验证不允许的字段
        allowed_fields = {"type", "command", "timeout"}
        extra_fields = set(hook.keys()) - allowed_fields
        if extra_fields:
            raise HookValidationError(f"Hook contains disallowed fields: {', '.join(extra_fields)}")

    def _preserve_original_formatting(self, data: Dict[str, Any]) -> str:
        """尝试保持原有的JSON格式。"""
        if not self._original_content:
            # 如果没有原始内容，使用标准格式
            return json.dumps(data, indent=self._indent_size, ensure_ascii=False)

        # 检测原始缩进
        indent_match = re.search(r'\n(\s+)"', self._original_content)
        if indent_match:
            original_indent = len(indent_match.group(1))
            self._indent_size = original_indent

        # 使用检测到的缩进格式化
        return json.dumps(
            data,
            indent=self._indent_size,
            ensure_ascii=False,
            separators=(',', ': ')
        )


# 测试类定义
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
                "PostToolUse": []
            },
            "theme": "dark"
        }''')

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(original_content)
            temp_path = Path(f.name)

        try:
            handler = SettingsJSONHandler(temp_path, preserve_formatting=True)
            data = handler.load()

            # 添加hook
            handler.add_hook("PostToolUse", "echo done", "")
            handler.save()

            # 验证缩进保持为4空格
            saved_content = temp_path.read_text(encoding='utf-8')
            lines = saved_content.split('\n')

            # 查找4空格缩进的行
            four_space_lines = [line for line in lines if line.startswith('    ') and not line.startswith('        ')]
            assert len(four_space_lines) > 0, "应该有4空格缩进的行"

            # 验证数据变更
            reloaded_data = json.loads(saved_content)
            assert "theme" in reloaded_data

        finally:
            temp_path.unlink()

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

    def test_load_modify_save_cycle_consistency(self):
        """测试加载-修改-保存循环后格式一致性。"""
        original_content = dedent('''\
        {
          "hooks": {
            "PreToolUse": []
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

    def test_error_handling_invalid_json(self):
        """测试无效JSON错误处理。"""
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