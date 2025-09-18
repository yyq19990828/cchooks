"""简化的Settings文件操作基础测试

只测试file_operations.py和json_handler.py的核心功能，
避免复杂的包级别导入。
"""

import json
import os
import shutil
import stat
import sys
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional
from unittest.mock import patch, mock_open, MagicMock

import pytest

# 直接导入相关模块，避免包级别的复杂依赖
test_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(test_dir / "src"))

# 直接导入工具模块
from cchooks.utils.file_operations import (
    FileOperationError,
    PermissionError as FilePermissionError,
    SecurityError,
    SettingsFileNotFoundError,
    validate_path_security,
    get_home_directory,
    find_project_root,
    discover_settings_files,
    get_settings_file_path,
    check_file_permissions,
    ensure_directory_exists,
    create_backup,
    restore_from_backup,
    read_json_file,
    write_json_file,
    safe_delete_file,
    get_file_info,
)

from cchooks.utils.json_handler import (
    SettingsJSONHandler,
    load_settings_file,
    save_settings_file,
    validate_hook_configuration,
    create_empty_settings,
)

from cchooks.exceptions import (
    CCHooksError,
    HookValidationError,
    ParseError,
)


class TestBasicFileOperations:
    """测试基础文件操作功能"""

    def test_get_home_directory(self):
        """测试获取用户主目录"""
        home = get_home_directory()
        assert isinstance(home, Path)
        assert home.exists()
        assert home.is_dir()

    def test_validate_path_security_normal_path(self, tmp_path):
        """测试正常路径的安全验证"""
        safe_path = tmp_path / "normal_file.json"
        result = validate_path_security(safe_path)
        assert isinstance(result, Path)

    def test_validate_path_security_path_traversal(self, tmp_path):
        """测试路径遍历攻击检测"""
        with pytest.raises(SecurityError, match="路径包含可疑模式"):
            validate_path_security("../../../etc/passwd")

    def test_ensure_directory_exists(self, tmp_path):
        """测试创建新目录"""
        new_dir = tmp_path / "new" / "nested" / "dir"
        result = ensure_directory_exists(new_dir)

        assert result == new_dir
        assert new_dir.exists()
        assert new_dir.is_dir()

    def test_check_file_permissions_existing_file(self, tmp_path):
        """测试检查现有文件的权限"""
        test_file = tmp_path / "test.json"
        test_file.write_text('{"test": true}')

        # 检查读权限
        assert check_file_permissions(test_file, need_read=True)

        # 检查写权限
        assert check_file_permissions(test_file, need_write=True)


class TestJSONFileOperations:
    """测试JSON文件的读写操作"""

    def test_read_json_file_success(self, tmp_path):
        """测试成功读取JSON文件"""
        json_file = tmp_path / "test.json"
        test_data = {"hooks": {"PreToolUse": []}}
        json_file.write_text(json.dumps(test_data))

        result = read_json_file(json_file)
        assert result == test_data

    def test_read_json_file_invalid_json(self, tmp_path):
        """测试读取无效JSON文件"""
        json_file = tmp_path / "invalid.json"
        json_file.write_text('{"invalid": json}')  # 无效JSON

        with pytest.raises(FileOperationError, match="JSON解析错误"):
            read_json_file(json_file)

    def test_write_json_file_success(self, tmp_path):
        """测试成功写入JSON文件"""
        json_file = tmp_path / "output.json"
        test_data = {"hooks": {"PreToolUse": []}}

        backup_path = write_json_file(json_file, test_data, create_backup=False)

        assert backup_path is None  # 没有创建备份
        assert json_file.exists()

        # 验证写入的内容
        written_data = json.loads(json_file.read_text())
        assert written_data == test_data

    def test_write_json_file_with_backup(self, tmp_path):
        """测试写入时创建备份"""
        json_file = tmp_path / "existing.json"
        original_data = {"original": True}
        new_data = {"hooks": {"PreToolUse": []}}

        # 先创建原始文件
        json_file.write_text(json.dumps(original_data))

        # 写入新数据并创建备份
        backup_path = write_json_file(json_file, new_data, create_backup=True)

        assert backup_path is not None
        assert backup_path.exists()

        # 验证备份内容
        backup_data = json.loads(backup_path.read_text())
        assert backup_data == original_data

        # 验证新文件内容
        new_file_data = json.loads(json_file.read_text())
        assert new_file_data == new_data


class TestFileBackupAndRestore:
    """测试文件备份和恢复功能"""

    def test_create_backup_success(self, tmp_path):
        """测试成功创建备份"""
        original = tmp_path / "original.json"
        original.write_text('{"original": true}')

        backup_path = create_backup(original)

        assert backup_path.exists()
        assert backup_path.name.startswith("original.json.backup.")
        assert backup_path.read_text() == '{"original": true}'

    def test_create_backup_non_existing_file(self, tmp_path):
        """测试备份不存在的文件"""
        non_existing = tmp_path / "non_existing.json"

        with pytest.raises(FileOperationError, match="源文件不存在"):
            create_backup(non_existing)

    def test_restore_from_backup_success(self, tmp_path):
        """测试从备份恢复文件"""
        # 创建原始文件和备份
        original = tmp_path / "original.json"
        original.write_text('{"original": true}')

        backup_path = create_backup(original)

        # 修改原始文件
        original.write_text('{"modified": true}')

        # 从备份恢复
        restored_path = restore_from_backup(backup_path)

        assert restored_path == original
        assert original.read_text() == '{"original": true}'


class TestSettingsJSONHandler:
    """测试SettingsJSONHandler类的基础功能"""

    def test_handler_initialization(self, tmp_path):
        """测试处理器初始化"""
        settings_file = tmp_path / "settings.json"
        handler = SettingsJSONHandler(settings_file)

        assert handler.file_path == settings_file
        assert handler.preserve_formatting is True

    def test_load_create_if_missing(self, tmp_path):
        """测试在文件不存在时创建空结构"""
        settings_file = tmp_path / "non_existing.json"
        handler = SettingsJSONHandler(settings_file)

        data = handler.load(create_if_missing=True)

        assert data == {"hooks": {}}

    def test_load_existing_file(self, tmp_path):
        """测试加载现有文件"""
        settings_file = tmp_path / "settings.json"
        test_data = {"hooks": {"PreToolUse": []}}
        settings_file.write_text(json.dumps(test_data))

        handler = SettingsJSONHandler(settings_file)
        data = handler.load()

        assert data == test_data

    def test_save_basic_data(self, tmp_path):
        """测试保存基础数据"""
        settings_file = tmp_path / "output.json"
        handler = SettingsJSONHandler(settings_file)

        test_data = {"hooks": {"PreToolUse": []}}
        handler.save(test_data)

        assert settings_file.exists()
        saved_data = json.loads(settings_file.read_text())
        assert saved_data == test_data


class TestHooksOperations:
    """测试hooks节点的增删改查操作"""

    def test_add_hook_to_empty_settings(self, tmp_path):
        """测试向空设置添加hook"""
        settings_file = tmp_path / "settings.json"
        handler = SettingsJSONHandler(settings_file)

        handler.load(create_if_missing=True)
        handler.add_hook("PreToolUse", "echo 'test'", "", 30)

        hooks = handler.get_hooks_for_event("PreToolUse")
        assert len(hooks) == 1

        hook = hooks[0]
        assert hook["type"] == "command"
        assert hook["command"] == "echo 'test'"
        assert hook["timeout"] == 30

    def test_add_hook_with_matcher(self, tmp_path):
        """测试添加带匹配器的hook"""
        settings_file = tmp_path / "settings.json"
        handler = SettingsJSONHandler(settings_file)

        handler.load(create_if_missing=True)
        handler.add_hook("PreToolUse", "security-check.py", "Bash|Write", 60)

        hooks = handler.get_hooks_for_event("PreToolUse")
        assert len(hooks) == 1
        assert hooks[0]["_matcher"] == "Bash|Write"

    def test_remove_hook_success(self, tmp_path):
        """测试成功删除hook"""
        settings_file = tmp_path / "settings.json"
        handler = SettingsJSONHandler(settings_file)

        handler.load(create_if_missing=True)
        handler.add_hook("PreToolUse", "to_remove.py", "")
        handler.add_hook("PreToolUse", "to_keep.py", "")

        # 删除一个hook
        success = handler.remove_hook("PreToolUse", "to_remove.py", "")
        assert success is True

        # 验证只剩下一个hook
        hooks = handler.get_hooks_for_event("PreToolUse")
        assert len(hooks) == 1
        assert hooks[0]["command"] == "to_keep.py"

    def test_update_hook_success(self, tmp_path):
        """测试成功更新hook"""
        settings_file = tmp_path / "settings.json"
        handler = SettingsJSONHandler(settings_file)

        handler.load(create_if_missing=True)
        handler.add_hook("PreToolUse", "old_command.py", "", 30)

        # 更新hook
        success = handler.update_hook("PreToolUse", "old_command.py", "new_command.py", "", 60)
        assert success is True

        # 验证更新结果
        hooks = handler.get_hooks_for_event("PreToolUse")
        assert len(hooks) == 1

        hook = hooks[0]
        assert hook["command"] == "new_command.py"
        assert hook["timeout"] == 60


class TestHookValidation:
    """测试hook配置验证功能"""

    def test_validate_hook_config_valid(self):
        """测试验证有效的hook配置"""
        valid_hook = {
            "type": "command",
            "command": "echo 'test'",
            "timeout": 30
        }

        # 不应该抛出异常
        validate_hook_configuration(valid_hook)

    def test_validate_hook_config_missing_type(self):
        """测试缺少type字段的hook配置"""
        invalid_hook = {
            "command": "echo 'test'"
        }

        with pytest.raises(HookValidationError, match="Hook must have 'type' field"):
            validate_hook_configuration(invalid_hook)

    def test_validate_hook_config_wrong_type(self):
        """测试错误的type字段值"""
        invalid_hook = {
            "type": "script",  # 应该是"command"
            "command": "echo 'test'"
        }

        with pytest.raises(HookValidationError, match="Hook type must be 'command'"):
            validate_hook_configuration(invalid_hook)

    def test_validate_hook_config_extra_fields(self):
        """测试包含额外字段的hook配置"""
        invalid_hook = {
            "type": "command",
            "command": "echo 'test'",
            "extra_field": "not_allowed"
        }

        with pytest.raises(HookValidationError, match="Hook contains disallowed fields"):
            validate_hook_configuration(invalid_hook)


class TestConvenienceFunctions:
    """测试便捷函数"""

    def test_load_settings_file_convenience(self, tmp_path):
        """测试便捷的设置文件加载函数"""
        settings_file = tmp_path / "settings.json"
        test_data = {"hooks": {"PreToolUse": []}}
        settings_file.write_text(json.dumps(test_data))

        handler, data = load_settings_file(settings_file)

        assert isinstance(handler, SettingsJSONHandler)
        assert data == test_data

    def test_save_settings_file_convenience(self, tmp_path):
        """测试便捷的设置文件保存函数"""
        settings_file = tmp_path / "output.json"
        test_data = {"hooks": {"PreToolUse": []}}

        backup_path = save_settings_file(settings_file, test_data, create_backup=False)

        assert backup_path is None
        assert settings_file.exists()

        saved_data = json.loads(settings_file.read_text())
        assert saved_data == test_data

    def test_create_empty_settings(self):
        """测试创建空设置结构"""
        empty = create_empty_settings()

        assert empty == {"hooks": {}}
        assert isinstance(empty["hooks"], dict)


class TestErrorHandling:
    """测试错误处理和边缘情况"""

    def test_permission_denied_simulation(self, tmp_path):
        """模拟权限不足的情况"""
        settings_file = tmp_path / "settings.json"

        # 模拟权限检查失败
        with patch('cchooks.utils.file_operations.check_file_permissions', return_value=False):
            with pytest.raises(FilePermissionError, match="没有写入文件的权限"):
                write_json_file(settings_file, {"test": True})

    def test_corrupted_json_recovery(self, tmp_path):
        """测试损坏JSON文件的处理"""
        settings_file = tmp_path / "corrupted.json"
        settings_file.write_text('{"hooks": {')  # 不完整的JSON

        handler = SettingsJSONHandler(settings_file)

        with pytest.raises(ParseError, match="Invalid JSON in settings file"):
            handler.load()

    def test_missing_hooks_section_auto_fix(self, tmp_path):
        """测试自动修复缺少hooks节点的设置文件"""
        settings_file = tmp_path / "no_hooks.json"
        settings_file.write_text('{"other_config": "value"}')

        handler = SettingsJSONHandler(settings_file)
        data = handler.load()

        # 应该自动添加hooks节点
        assert "hooks" in data
        assert isinstance(data["hooks"], dict)
        assert data["other_config"] == "value"  # 保持原有配置


# TDD失败测试 - 这些测试展示期望的功能但会失败
class TestFutureFeatures:
    """
    高级Settings管理功能测试（这些测试会失败，因为相关组件未实现）
    """

    def test_settings_discovery_integration(self, tmp_path):
        """测试设置文件发现功能的集成测试"""
        # 创建项目结构
        project_root = tmp_path / "project"
        claude_dir = project_root / ".claude"
        claude_dir.mkdir(parents=True)

        settings_file = claude_dir / "settings.json"
        settings_file.write_text('{"hooks": {}}')

        # 使用patch模拟find_project_root返回我们的测试项目
        with patch('cchooks.utils.file_operations.find_project_root', return_value=project_root):
            files = discover_settings_files()
            assert len(files) == 1
            assert files[0] == ('project', settings_file)

    def test_project_root_discovery(self, tmp_path):
        """测试项目根目录发现功能"""
        # 创建项目结构
        project_root = tmp_path / "project"
        claude_dir = project_root / ".claude"
        claude_dir.mkdir(parents=True)

        # 在子目录中查找
        sub_dir = project_root / "sub" / "deeper"
        sub_dir.mkdir(parents=True)

        result = find_project_root(sub_dir)
        assert result == project_root