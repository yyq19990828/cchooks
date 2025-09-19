"""
跨平台文件权限处理测试套件

这个测试套件验证权限处理模块在不同平台上的功能。
测试包括基本权限检查、错误处理、平台特定功能等。
"""

import os
import sys
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# 添加src目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from cchooks.utils.permissions import (
    PermissionLevel, PlatformType, get_current_platform,
    get_permission_info, check_permission, set_permission,
    make_script_executable, ensure_directory_writable,
    diagnose_system_permissions, validate_claude_directory_permissions
)
from cchooks.utils.file_operations import (
    FileOperationError, PermissionError as FilePermissionError,
    SecurityError, create_user_friendly_error
)


class TestPermissionLevel:
    """测试权限级别枚举"""

    def test_permission_levels_exist(self):
        """测试所有权限级别都存在"""
        levels = [
            PermissionLevel.READ,
            PermissionLevel.WRITE,
            PermissionLevel.EXECUTE,
            PermissionLevel.READ_WRITE,
            PermissionLevel.FULL
        ]
        assert len(levels) == 5

    def test_permission_levels_unique(self):
        """测试权限级别都是唯一的"""
        levels = list(PermissionLevel)
        assert len(levels) == len(set(levels))


class TestPlatformDetection:
    """测试平台检测功能"""

    def test_get_current_platform(self):
        """测试当前平台检测"""
        platform = get_current_platform()
        assert isinstance(platform, PlatformType)
        assert platform in [PlatformType.WINDOWS, PlatformType.MACOS,
                           PlatformType.LINUX, PlatformType.UNKNOWN]

    @patch('platform.system')
    def test_windows_detection(self, mock_system):
        """测试Windows平台检测"""
        mock_system.return_value = 'Windows'
        platform = get_current_platform()
        assert platform == PlatformType.WINDOWS

    @patch('platform.system')
    def test_macos_detection(self, mock_system):
        """测试macOS平台检测"""
        mock_system.return_value = 'Darwin'
        platform = get_current_platform()
        assert platform == PlatformType.MACOS

    @patch('platform.system')
    def test_linux_detection(self, mock_system):
        """测试Linux平台检测"""
        mock_system.return_value = 'Linux'
        platform = get_current_platform()
        assert platform == PlatformType.LINUX

    @patch('platform.system')
    def test_unknown_platform_detection(self, mock_system):
        """测试未知平台检测"""
        mock_system.return_value = 'UnknownOS'
        platform = get_current_platform()
        assert platform == PlatformType.UNKNOWN


class TestPermissionInfo:
    """测试权限信息获取"""

    def test_get_permission_info_existing_file(self):
        """测试获取现有文件的权限信息"""
        with tempfile.NamedTemporaryFile() as tmp_file:
            path = Path(tmp_file.name)
            info = get_permission_info(path)

            assert info.path == path
            assert info.exists is True
            assert isinstance(info.is_readable, bool)
            assert isinstance(info.is_writable, bool)
            assert isinstance(info.is_executable, bool)

    def test_get_permission_info_nonexistent_file(self):
        """测试获取不存在文件的权限信息"""
        path = Path("/nonexistent/file/path")
        info = get_permission_info(path)

        assert info.path == path
        assert info.exists is False


class TestPermissionChecking:
    """测试权限检查功能"""

    def test_check_permission_readable_file(self):
        """测试检查可读文件权限"""
        with tempfile.NamedTemporaryFile() as tmp_file:
            path = Path(tmp_file.name)
            has_permission, error = check_permission(path, PermissionLevel.READ)

            assert has_permission is True
            assert error is None

    def test_check_permission_nonexistent_file(self):
        """测试检查不存在文件的权限"""
        path = Path("/nonexistent/file/path")
        has_permission, error = check_permission(path, PermissionLevel.READ)

        assert has_permission is False
        assert error is not None
        assert error.error_code is not None


class TestDirectoryManagement:
    """测试目录权限管理"""

    def test_ensure_directory_writable_existing(self):
        """测试确保现有目录可写"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir)
            success, error = ensure_directory_writable(path)

            assert success is True
            assert error is None

    def test_ensure_directory_writable_create_new(self):
        """测试创建新目录并确保可写"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            new_dir = Path(tmp_dir) / "new_subdir"
            success, error = ensure_directory_writable(new_dir, create_if_missing=True)

            assert success is True
            assert error is None
            assert new_dir.exists()


class TestScriptExecutable:
    """测试脚本可执行权限设置"""

    def test_make_python_script_executable(self):
        """测试设置Python脚本可执行"""
        with tempfile.NamedTemporaryFile(suffix='.py') as tmp_file:
            path = Path(tmp_file.name)
            success, error = make_script_executable(path)

            # 结果取决于平台，但不应该抛出异常
            assert isinstance(success, bool)
            if not success:
                assert error is not None

    def test_make_shell_script_executable(self):
        """测试设置shell脚本可执行"""
        with tempfile.NamedTemporaryFile(suffix='.sh') as tmp_file:
            path = Path(tmp_file.name)
            success, error = make_script_executable(path)

            # 结果取决于平台，但不应该抛出异常
            assert isinstance(success, bool)


class TestErrorHandling:
    """测试错误处理功能"""

    def test_create_user_friendly_error_file_not_found(self):
        """测试文件不存在错误的用户友好消息"""
        original_error = FileNotFoundError("No such file or directory")
        error = create_user_friendly_error('read', '/nonexistent/file', original_error)

        assert isinstance(error, FileOperationError)
        assert error.error_code == "FILE_NOT_FOUND"
        assert error.suggested_fix is not None
        assert len(error.alternative_solutions) > 0

    def test_create_user_friendly_error_permission_denied(self):
        """测试权限拒绝错误的用户友好消息"""
        original_error = PermissionError("Permission denied")
        original_error.errno = 13
        error = create_user_friendly_error('write', '/protected/file', original_error)

        assert isinstance(error, FilePermissionError)
        assert error.required_permission == 'write'
        assert error.suggested_fix is not None

    def test_file_operation_error_to_dict(self):
        """测试FileOperationError转换为字典"""
        error = FileOperationError(
            message="测试错误",
            error_code="TEST_ERROR",
            suggested_fix="测试修复",
            alternative_solutions=["方案1", "方案2"],
            file_path="/test/path"
        )

        error_dict = error.to_dict()
        assert error_dict["error_type"] == "FileOperationError"
        assert error_dict["error_code"] == "TEST_ERROR"
        assert error_dict["message"] == "测试错误"
        assert error_dict["file_path"] == "/test/path"


class TestSystemDiagnosis:
    """测试系统诊断功能"""

    def test_diagnose_system_permissions(self):
        """测试系统权限诊断"""
        diagnosis = diagnose_system_permissions()

        assert "platform" in diagnosis
        assert "timestamp" in diagnosis
        assert "issues" in diagnosis
        assert "recommendations" in diagnosis
        assert "system_info" in diagnosis

        # 验证平台是有效值
        assert diagnosis["platform"] in ["windows", "darwin", "linux", "unknown"]

    def test_validate_claude_directory_permissions(self):
        """测试Claude目录权限验证"""
        errors = validate_claude_directory_permissions()

        # errors应该是一个列表
        assert isinstance(errors, list)

        # 每个错误都应该有必要的属性
        for error in errors:
            assert hasattr(error, 'error_code')
            assert hasattr(error, 'message')


class TestCrossPlatformCompatibility:
    """测试跨平台兼容性"""

    def test_permission_functions_dont_crash(self):
        """测试权限函数在当前平台不会崩溃"""
        # 创建临时文件进行测试
        with tempfile.NamedTemporaryFile() as tmp_file:
            path = Path(tmp_file.name)

            # 这些函数不应该抛出异常，即使返回失败
            try:
                get_permission_info(path)
                check_permission(path, PermissionLevel.READ)
                set_permission(path, PermissionLevel.READ_WRITE)
            except Exception as e:
                pytest.fail(f"权限函数抛出了未预期的异常: {e}")

    def test_platform_specific_info_structure(self):
        """测试平台特定信息的结构"""
        with tempfile.NamedTemporaryFile() as tmp_file:
            path = Path(tmp_file.name)
            info = get_permission_info(path)

            # 验证platform_specific是字典
            assert isinstance(info.platform_specific, dict)

            # 验证包含平台信息
            if "platform" in info.platform_specific:
                assert isinstance(info.platform_specific["platform"], str)


if __name__ == "__main__":
    # 如果直接运行此文件，执行基本测试
    print("运行跨平台权限处理测试...")

    # 测试平台检测
    platform = get_current_platform()
    print(f"检测到平台: {platform.value}")

    # 测试权限信息获取
    current_file = Path(__file__)
    info = get_permission_info(current_file)
    print(f"当前文件权限: 可读={info.is_readable}, 可写={info.is_writable}, 可执行={info.is_executable}")

    # 测试系统诊断
    diagnosis = diagnose_system_permissions()
    print(f"系统诊断完成，发现 {len(diagnosis['issues'])} 个问题")

    print("基本测试完成！")