"""File discovery integration tests for settings discovery system.

This module implements comprehensive integration tests for the file discovery
functionality in src/cchooks/settings/discovery.py, testing multi-level file
discovery, caching mechanisms, real file system scenarios, and cross-platform
compatibility as specified in T012.

The tests are designed to pass with the existing implementation and validate
integration correctness while uncovering potential performance or compatibility
issues.
"""

import json
import os
import platform
import shutil
import stat
import tempfile
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from unittest.mock import Mock, patch

import pytest

# Check if we're running in the CLI project structure or the cchooks project structure
try:
    # CLI project structure
    from src.cchooks.settings.discovery import (
        SettingsDiscovery,
        discover_settings_files,
        find_project_settings,
        find_user_global_settings,
        get_effective_settings_files,
        clear_discovery_cache,
    )
    from src.cchooks.settings.exceptions import (
        SettingsDiscoveryError,
        SettingsPermissionError,
        SettingsDirectoryError,
    )
    from src.cchooks.types.enums import SettingsLevel
    from src.cchooks.models.settings_file import SettingsFile
except ImportError:
    # Original cchooks project structure - skip settings discovery tests
    pytest.skip("Settings discovery module not available in this project structure", allow_module_level=True)


class FileSystemHelper:
    """Helper class for creating isolated file system test environments."""

    def __init__(self, temp_dir: Path):
        """Initialize with a temporary directory."""
        self.temp_dir = temp_dir
        self.created_files: List[Path] = []
        self.created_dirs: List[Path] = []

    def create_project_structure(
        self,
        root_path: Path,
        levels: int = 3,
        has_settings: bool = True,
        settings_content: Optional[Dict] = None
    ) -> Tuple[Path, List[Path]]:
        """Create a multi-level project directory structure.

        Args:
            root_path: Root directory for the project
            levels: Number of nested levels to create
            has_settings: Whether to create .claude/settings.json
            settings_content: Content for settings.json

        Returns:
            Tuple of (deepest_dir, all_created_dirs)
        """
        if settings_content is None:
            settings_content = {
                "hooks": {
                    "pre_tool_use": {"type": "command", "command": "echo 'test'"}
                }
            }

        created_dirs = []
        current_path = root_path

        for i in range(levels):
            level_dir = current_path / f"level_{i}"
            level_dir.mkdir(parents=True, exist_ok=True)
            created_dirs.append(level_dir)
            self.created_dirs.append(level_dir)
            current_path = level_dir

        if has_settings:
            # Create .claude directory at the root level
            claude_dir = root_path / ".claude"
            claude_dir.mkdir(exist_ok=True)
            self.created_dirs.append(claude_dir)

            # Create settings.json
            settings_file = claude_dir / "settings.json"
            settings_file.write_text(json.dumps(settings_content, indent=2))
            self.created_files.append(settings_file)

        return current_path, created_dirs

    def create_user_home_structure(
        self,
        home_path: Path,
        has_settings: bool = True,
        settings_content: Optional[Dict] = None
    ) -> Path:
        """Create a simulated user home directory structure.

        Args:
            home_path: Path to simulate as home directory
            has_settings: Whether to create .claude/settings.json
            settings_content: Content for settings.json

        Returns:
            Path to the created .claude directory
        """
        if settings_content is None:
            settings_content = {
                "hooks": {
                    "post_tool_use": {"type": "command", "command": "echo 'global'"}
                }
            }

        claude_dir = home_path / ".claude"
        claude_dir.mkdir(parents=True, exist_ok=True)
        self.created_dirs.append(claude_dir)

        if has_settings:
            settings_file = claude_dir / "settings.json"
            settings_file.write_text(json.dumps(settings_content, indent=2))
            self.created_files.append(settings_file)

        return claude_dir

    def create_corrupted_settings(self, claude_dir: Path) -> Path:
        """Create a corrupted settings.json file.

        Args:
            claude_dir: Directory containing the settings file

        Returns:
            Path to the corrupted settings file
        """
        settings_file = claude_dir / "settings.json"
        settings_file.write_text("{ invalid json content")
        self.created_files.append(settings_file)
        return settings_file

    def create_permission_restricted_dir(self, path: Path) -> Path:
        """Create a directory with restricted permissions.

        Args:
            path: Directory path to restrict

        Returns:
            Path to the restricted directory
        """
        path.mkdir(parents=True, exist_ok=True)
        self.created_dirs.append(path)

        # Remove read/write permissions (platform-specific)
        if platform.system() != "Windows":
            try:
                path.chmod(0o000)
            except OSError:
                # Some file systems don't support permission changes
                pass
        return path

    def cleanup(self):
        """Clean up all created files and directories."""
        # Restore permissions first
        for dir_path in self.created_dirs:
            if dir_path.exists() and platform.system() != "Windows":
                try:
                    dir_path.chmod(0o755)
                except OSError:
                    pass

        # Remove files
        for file_path in reversed(self.created_files):
            try:
                if file_path.exists():
                    file_path.unlink()
            except OSError:
                pass

        # Remove directories
        for dir_path in reversed(self.created_dirs):
            try:
                if dir_path.exists():
                    dir_path.rmdir()
            except OSError:
                pass


@pytest.fixture
def temp_environment():
    """Create a temporary environment for file system tests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        helper = FileSystemHelper(temp_path)

        yield temp_path, helper

        # Cleanup is handled by the helper and tempfile


@pytest.fixture
def discovery_instance():
    """Create a fresh SettingsDiscovery instance for testing."""
    return SettingsDiscovery()


class TestMultiLevelFileDiscovery:
    """Test multi-level file discovery functionality."""

    def test_project_level_discovery_upward_search(self, temp_environment, discovery_instance):
        """Test project-level settings discovery with upward directory search."""
        temp_path, helper = temp_environment

        # Create nested project structure with settings at root
        project_root = temp_path / "project"
        deepest_dir, created_dirs = helper.create_project_structure(
            project_root, levels=3, has_settings=True
        )

        # Search from the deepest directory
        files = discovery_instance.discover_settings_files(
            start_path=deepest_dir,
            levels=[SettingsLevel.PROJECT]
        )

        assert len(files) == 1
        assert files[0].level == SettingsLevel.PROJECT
        assert files[0].path == project_root / ".claude" / "settings.json"
        assert files[0].exists is True

    def test_project_level_no_settings_found(self, temp_environment, discovery_instance):
        """Test project-level discovery when no settings file exists."""
        temp_path, helper = temp_environment

        # Create project structure without settings
        project_root = temp_path / "project"
        deepest_dir, _ = helper.create_project_structure(
            project_root, levels=2, has_settings=False
        )

        files = discovery_instance.discover_settings_files(
            start_path=deepest_dir,
            levels=[SettingsLevel.PROJECT]
        )

        assert len(files) == 0

    def test_user_global_discovery(self, temp_environment, discovery_instance):
        """Test user-global settings discovery."""
        temp_path, helper = temp_environment

        # Create simulated home directory
        fake_home = temp_path / "home" / "user"
        claude_dir = helper.create_user_home_structure(fake_home, has_settings=True)

        with patch("pathlib.Path.home", return_value=fake_home):
            files = discovery_instance.discover_settings_files(
                levels=[SettingsLevel.USER_GLOBAL]
            )

            assert len(files) == 1
            assert files[0].level == SettingsLevel.USER_GLOBAL
            assert files[0].path == fake_home / ".claude" / "settings.json"

    def test_combined_level_discovery_precedence(self, temp_environment, discovery_instance):
        """Test discovery of both project and user-global levels with correct precedence."""
        temp_path, helper = temp_environment

        # Create project structure
        project_root = temp_path / "project"
        work_dir, _ = helper.create_project_structure(project_root, levels=2, has_settings=True)

        # Create user home structure
        fake_home = temp_path / "home" / "user"
        helper.create_user_home_structure(fake_home, has_settings=True)

        with patch("pathlib.Path.home", return_value=fake_home):
            files = discovery_instance.discover_settings_files(start_path=work_dir)

            # Should find both files
            assert len(files) == 2

            # Project level should come first (higher precedence)
            project_files = [f for f in files if f.level == SettingsLevel.PROJECT]
            user_files = [f for f in files if f.level == SettingsLevel.USER_GLOBAL]

            assert len(project_files) == 1
            assert len(user_files) == 1

    def test_effective_settings_files_filtering(self, temp_environment, discovery_instance):
        """Test filtering of effective settings files (existing and readable only)."""
        temp_path, helper = temp_environment

        # Create project with settings
        project_root = temp_path / "project"
        work_dir, _ = helper.create_project_structure(project_root, levels=1, has_settings=True)

        # Create user home without settings file
        fake_home = temp_path / "home" / "user"
        helper.create_user_home_structure(fake_home, has_settings=False)

        with patch("pathlib.Path.home", return_value=fake_home):
            effective_files = discovery_instance.get_effective_settings_files(start_path=work_dir)

            # Should only include existing, readable files
            assert len(effective_files) == 1
            assert effective_files[0].level == SettingsLevel.PROJECT
            assert effective_files[0].exists is True
            assert effective_files[0].readable is True


class TestRealFileSystemScenarios:
    """Test realistic file system scenarios and edge cases."""

    def test_multiple_nested_projects(self, temp_environment, discovery_instance):
        """Test discovery in multiple nested projects."""
        temp_path, helper = temp_environment

        # Create outer project
        outer_project = temp_path / "outer_project"
        helper.create_project_structure(outer_project, levels=1, has_settings=True,
                                        settings_content={"name": "outer"})

        # Create inner project nested in outer
        inner_project = outer_project / "level_0" / "inner_project"
        inner_work_dir, _ = helper.create_project_structure(inner_project, levels=2,
                                                            has_settings=True,
                                                            settings_content={"name": "inner"})

        # Search from inner project work directory
        files = discovery_instance.discover_settings_files(
            start_path=inner_work_dir,
            levels=[SettingsLevel.PROJECT]
        )

        # Should find the closest (inner) project settings
        assert len(files) == 1
        assert files[0].path == inner_project / ".claude" / "settings.json"

    def test_symlink_handling(self, temp_environment, discovery_instance):
        """Test handling of symbolic links in directory traversal."""
        temp_path, helper = temp_environment

        # Skip symlink tests on Windows due to permission requirements
        if platform.system() == "Windows":
            pytest.skip("Symbolic links require special permissions on Windows")

        # Create real project structure
        real_project = temp_path / "real_project"
        real_work_dir, _ = helper.create_project_structure(real_project, levels=2, has_settings=True)

        # Create symlink to work directory
        symlink_dir = temp_path / "symlink_work"
        symlink_dir.symlink_to(real_work_dir)

        # Discovery should work through symlinks
        files = discovery_instance.discover_settings_files(
            start_path=symlink_dir,
            levels=[SettingsLevel.PROJECT]
        )

        assert len(files) == 1
        assert files[0].exists is True

    def test_very_deep_directory_structure(self, temp_environment, discovery_instance):
        """Test discovery in very deep directory structures."""
        temp_path, helper = temp_environment

        # Create a deep directory structure (20 levels)
        project_root = temp_path / "deep_project"
        deep_dir, _ = helper.create_project_structure(project_root, levels=20, has_settings=True)

        # Search from the deepest level
        start_time = time.time()
        files = discovery_instance.discover_settings_files(
            start_path=deep_dir,
            levels=[SettingsLevel.PROJECT]
        )
        end_time = time.time()

        # Should find settings and complete within reasonable time
        assert len(files) == 1
        assert files[0].exists is True

        # Performance requirement: should complete within 100ms
        assert end_time - start_time < 0.1

    def test_concurrent_directory_access(self, temp_environment, discovery_instance):
        """Test discovery under concurrent file system access."""
        temp_path, helper = temp_environment

        # Create project structure
        project_root = temp_path / "concurrent_project"
        work_dir, _ = helper.create_project_structure(project_root, levels=3, has_settings=True)

        results = []
        errors = []

        def discover_worker():
            try:
                files = discovery_instance.discover_settings_files(
                    start_path=work_dir,
                    levels=[SettingsLevel.PROJECT]
                )
                results.append(files)
            except Exception as e:
                errors.append(e)

        # Run multiple discovery operations concurrently
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=discover_worker)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # All operations should succeed
        assert len(errors) == 0
        assert len(results) == 10

        # All should find the same file
        for files in results:
            assert len(files) == 1
            assert files[0].path == project_root / ".claude" / "settings.json"


class TestCachingMechanism:
    """Test caching functionality and performance requirements."""

    def test_cache_hit_performance(self, temp_environment, discovery_instance):
        """Test that cached results meet <100ms performance requirement."""
        temp_path, helper = temp_environment

        # Create project structure
        project_root = temp_path / "cache_project"
        work_dir, _ = helper.create_project_structure(project_root, levels=5, has_settings=True)

        # First discovery (populates cache)
        discovery_instance.discover_settings_files(start_path=work_dir)

        # Second discovery (should hit cache)
        start_time = time.time()
        files = discovery_instance.discover_settings_files(start_path=work_dir)
        end_time = time.time()

        assert len(files) == 2  # PROJECT + USER_GLOBAL
        assert end_time - start_time < 0.1  # <100ms requirement

    def test_cache_invalidation_on_working_directory_change(self, temp_environment, discovery_instance):
        """Test cache invalidation when working directory changes."""
        temp_path, helper = temp_environment

        # Create two different project structures
        project1 = temp_path / "project1"
        work_dir1, _ = helper.create_project_structure(project1, levels=2, has_settings=True)

        project2 = temp_path / "project2"
        work_dir2, _ = helper.create_project_structure(project2, levels=2, has_settings=True)

        # Discover from first project
        files1 = discovery_instance.discover_settings_files(start_path=work_dir1)
        project_files1 = [f for f in files1 if f.level == SettingsLevel.PROJECT]

        # Discover from second project
        files2 = discovery_instance.discover_settings_files(start_path=work_dir2)
        project_files2 = [f for f in files2 if f.level == SettingsLevel.PROJECT]

        # Should find different project files
        assert project_files1[0].path != project_files2[0].path

    def test_cache_expiration(self, temp_environment, discovery_instance):
        """Test cache expiration after TTL."""
        temp_path, helper = temp_environment

        # Create project structure
        project_root = temp_path / "expire_project"
        work_dir, _ = helper.create_project_structure(project_root, levels=1, has_settings=True)

        # Mock time to test expiration
        with patch('time.time') as mock_time:
            # First discovery at time 0
            mock_time.return_value = 0
            discovery_instance.discover_settings_files(start_path=work_dir)

            # Access cache at time 31 (expired, TTL is 30 seconds)
            mock_time.return_value = 31
            files = discovery_instance.discover_settings_files(start_path=work_dir)

            # Should still work (cache miss but re-discovery succeeds)
            assert len(files) >= 1

    def test_cache_thread_safety(self, temp_environment, discovery_instance):
        """Test thread safety of cache operations."""
        temp_path, helper = temp_environment

        # Create project structure
        project_root = temp_path / "thread_project"
        work_dir, _ = helper.create_project_structure(project_root, levels=2, has_settings=True)

        results = []
        errors = []

        def cached_discovery():
            try:
                files = discovery_instance.discover_settings_files(start_path=work_dir)
                results.append(len(files))
            except Exception as e:
                errors.append(e)

        # Run many concurrent operations
        threads = []
        for _ in range(50):
            thread = threading.Thread(target=cached_discovery)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # All operations should succeed
        assert len(errors) == 0
        assert len(results) == 50

        # All should return consistent results
        assert all(count >= 1 for count in results)

    def test_cache_memory_limit(self, temp_environment, discovery_instance):
        """Test cache LRU eviction to prevent memory bloat."""
        temp_path, helper = temp_environment

        # Create many different project structures to exceed cache limit
        project_dirs = []
        for i in range(150):  # Exceed CACHE_MAX_SIZE (100)
            project_root = temp_path / f"project_{i}"
            work_dir, _ = helper.create_project_structure(project_root, levels=1, has_settings=True)
            project_dirs.append(work_dir)

        # Fill cache beyond limit
        for work_dir in project_dirs:
            discovery_instance.discover_settings_files(start_path=work_dir)

        # Cache should not exceed maximum size
        assert len(discovery_instance._cache) <= 100

    def test_cache_clear_functionality(self, temp_environment, discovery_instance):
        """Test manual cache clearing."""
        temp_path, helper = temp_environment

        # Create project and populate cache
        project_root = temp_path / "clear_project"
        work_dir, _ = helper.create_project_structure(project_root, levels=1, has_settings=True)

        discovery_instance.discover_settings_files(start_path=work_dir)
        assert len(discovery_instance._cache) > 0

        # Clear cache
        discovery_instance.clear_cache()
        assert len(discovery_instance._cache) == 0


class TestBoundaryConditions:
    """Test edge cases and error conditions."""

    def test_no_settings_files_anywhere(self, temp_environment, discovery_instance):
        """Test behavior when no settings files exist at any level."""
        temp_path, helper = temp_environment

        # Create project structure without settings
        project_root = temp_path / "empty_project"
        work_dir, _ = helper.create_project_structure(project_root, levels=2, has_settings=False)

        # Create fake home without settings
        fake_home = temp_path / "home" / "user"
        helper.create_user_home_structure(fake_home, has_settings=False)

        with patch("pathlib.Path.home", return_value=fake_home):
            files = discovery_instance.discover_settings_files(start_path=work_dir)

            # Should return SettingsFile objects even if files don't exist
            assert len(files) == 1  # Only USER_GLOBAL level
            assert files[0].level == SettingsLevel.USER_GLOBAL
            assert files[0].exists is False

    def test_permission_denied_directory_traversal(self, temp_environment, discovery_instance):
        """Test handling of permission denied during directory traversal."""
        temp_path, helper = temp_environment

        # Skip permission tests on Windows due to different permission model
        if platform.system() == "Windows":
            pytest.skip("Permission model differs on Windows")

        # Create project structure
        project_root = temp_path / "restricted_project"
        work_dir, created_dirs = helper.create_project_structure(project_root, levels=2, has_settings=True)

        # Restrict permissions on intermediate directory
        restricted_dir = created_dirs[0]  # level_0 directory
        helper.create_permission_restricted_dir(restricted_dir)

        # Should handle permission errors gracefully
        with pytest.raises(SettingsPermissionError):
            discovery_instance.discover_settings_files(start_path=work_dir)

    def test_corrupted_settings_file_handling(self, temp_environment, discovery_instance):
        """Test handling of corrupted settings files."""
        temp_path, helper = temp_environment

        # Create project with corrupted settings
        project_root = temp_path / "corrupted_project"
        work_dir, _ = helper.create_project_structure(project_root, levels=1, has_settings=False)

        claude_dir = project_root / ".claude"
        claude_dir.mkdir(exist_ok=True)
        helper.create_corrupted_settings(claude_dir)

        # Discovery should still work (it only checks file existence)
        files = discovery_instance.discover_settings_files(start_path=work_dir)
        project_files = [f for f in files if f.level == SettingsLevel.PROJECT]

        assert len(project_files) == 1
        assert project_files[0].exists is True
        # Note: readable status depends on file content validation in SettingsFile

    def test_network_drive_simulation(self, temp_environment, discovery_instance):
        """Test behavior with network drives (simulated with slow operations)."""
        temp_path, helper = temp_environment

        # Create project structure
        project_root = temp_path / "network_project"
        work_dir, _ = helper.create_project_structure(project_root, levels=3, has_settings=True)

        # Mock Path.exists to simulate slow network operations
        original_exists = Path.exists

        def slow_exists(self):
            time.sleep(0.01)  # Simulate 10ms network delay
            return original_exists(self)

        with patch.object(Path, 'exists', slow_exists):
            start_time = time.time()
            files = discovery_instance.discover_settings_files(start_path=work_dir)
            end_time = time.time()

            # Should still complete within reasonable time
            assert len(files) >= 1
            assert end_time - start_time < 1.0  # Allow 1 second for network simulation

    def test_root_directory_traversal_limit(self, temp_environment, discovery_instance):
        """Test that directory traversal stops at filesystem root."""
        temp_path, helper = temp_environment

        # Create a project structure without settings
        project_root = temp_path / "roottest_project"
        work_dir, _ = helper.create_project_structure(project_root, levels=1, has_settings=False)

        # For this test, we'll use the actual file system behavior
        # The discovery should naturally stop at filesystem root without infinite recursion
        files = discovery_instance.discover_settings_files(
            start_path=work_dir,
            levels=[SettingsLevel.PROJECT]
        )

        # Should handle gracefully and not find project settings (since we didn't create any)
        assert len(files) == 0


class TestCrossPlatformCompatibility:
    """Test cross-platform compatibility aspects."""

    def test_windows_path_handling(self, temp_environment, discovery_instance):
        """Test Windows-style path handling."""
        temp_path, helper = temp_environment

        # Create project structure
        project_root = temp_path / "windows_project"
        work_dir, _ = helper.create_project_structure(project_root, levels=2, has_settings=True)

        # Test with Windows-style path separators (if not on Windows)
        if platform.system() != "Windows":
            with patch('os.sep', '\\'):
                files = discovery_instance.discover_settings_files(start_path=work_dir)
                assert len(files) >= 1
        else:
            # On actual Windows, just test normal operation
            files = discovery_instance.discover_settings_files(start_path=work_dir)
            assert len(files) >= 1

    def test_user_home_directory_detection(self, temp_environment, discovery_instance):
        """Test user home directory detection across platforms."""
        temp_path, helper = temp_environment

        # Test different home directory scenarios
        test_homes = [
            temp_path / "home" / "user",  # Unix-style
            temp_path / "Users" / "user",  # macOS-style
            temp_path / "home" / "windows_user",  # Windows-style variation
        ]

        for i, fake_home in enumerate(test_homes):
            # Create separate instances to avoid cache interference
            fresh_discovery = SettingsDiscovery()

            helper.create_user_home_structure(fake_home, has_settings=True)

            with patch("pathlib.Path.home", return_value=fake_home):
                user_file = fresh_discovery.find_user_global_settings()
                assert user_file.path == fake_home / ".claude" / "settings.json"

    def test_file_permission_checking_cross_platform(self, temp_environment, discovery_instance):
        """Test file permission checking across different platforms."""
        temp_path, helper = temp_environment

        # Create project structure
        project_root = temp_path / "permission_project"
        work_dir, _ = helper.create_project_structure(project_root, levels=1, has_settings=True)

        files = discovery_instance.discover_settings_files(start_path=work_dir)
        project_files = [f for f in files if f.level == SettingsLevel.PROJECT]

        # File permission checking should work regardless of platform
        assert len(project_files) == 1
        settings_file = project_files[0]

        # These properties should be determined regardless of platform
        assert isinstance(settings_file.exists, bool)
        assert isinstance(settings_file.readable, bool)
        assert isinstance(settings_file.writable, bool)

    def test_path_resolution_with_case_sensitivity(self, temp_environment, discovery_instance):
        """Test path resolution considering case sensitivity differences."""
        temp_path, helper = temp_environment

        # Create project structure
        project_root = temp_path / "Case_Project"
        work_dir, _ = helper.create_project_structure(project_root, levels=1, has_settings=True)

        # Test discovery with different case (behavior depends on filesystem)
        try:
            alt_case_work_dir = temp_path / "case_project" / "level_0"
            if alt_case_work_dir.exists():  # Case-insensitive filesystem
                files = discovery_instance.discover_settings_files(start_path=alt_case_work_dir)
                assert len(files) >= 1
            else:  # Case-sensitive filesystem
                files = discovery_instance.discover_settings_files(start_path=work_dir)
                assert len(files) >= 1
        except OSError:
            # Some platforms may have restrictions, that's OK
            pass


class TestIntegrationWithConvenienceFunctions:
    """Test integration with convenience functions and global discovery instance."""

    def test_global_convenience_functions(self, temp_environment):
        """Test that global convenience functions work correctly."""
        temp_path, helper = temp_environment

        # Create project structure
        project_root = temp_path / "global_project"
        work_dir, _ = helper.create_project_structure(project_root, levels=1, has_settings=True)

        # Create fake home
        fake_home = temp_path / "home" / "user"
        helper.create_user_home_structure(fake_home, has_settings=True)

        # Clear global cache before testing
        clear_discovery_cache()

        with patch("pathlib.Path.home", return_value=fake_home):
            # Test discover_settings_files function
            files = discover_settings_files(start_path=work_dir)
            assert len(files) == 2

            # Test find_project_settings function
            project_file = find_project_settings(start_path=work_dir)
            assert project_file is not None
            assert project_file.level == SettingsLevel.PROJECT

            # Test find_user_global_settings function
            user_file = find_user_global_settings()
            assert user_file.level == SettingsLevel.USER_GLOBAL

            # Test get_effective_settings_files function
            effective_files = get_effective_settings_files(start_path=work_dir)
            assert len(effective_files) == 2
            assert all(f.exists for f in effective_files)

    def test_default_path_behavior(self, temp_environment):
        """Test default path behavior when no start_path is provided."""
        temp_path, helper = temp_environment

        # Create project structure in current working directory simulation
        current_dir = temp_path / "current_work"
        work_dir, _ = helper.create_project_structure(current_dir, levels=1, has_settings=True)

        with patch("pathlib.Path.cwd", return_value=work_dir):
            # Test without providing start_path
            files = discover_settings_files()
            project_files = [f for f in files if f.level == SettingsLevel.PROJECT]
            assert len(project_files) == 1

    def test_settings_level_filtering(self, temp_environment):
        """Test filtering by specific settings levels."""
        temp_path, helper = temp_environment

        # Create both project and user settings
        project_root = temp_path / "filter_project"
        work_dir, _ = helper.create_project_structure(project_root, levels=1, has_settings=True)

        fake_home = temp_path / "home" / "user"
        helper.create_user_home_structure(fake_home, has_settings=True)

        clear_discovery_cache()

        with patch("pathlib.Path.home", return_value=fake_home):
            # Test project-only filtering
            project_files = discover_settings_files(
                start_path=work_dir,
                levels=[SettingsLevel.PROJECT]
            )
            assert len(project_files) == 1
            assert all(f.level == SettingsLevel.PROJECT for f in project_files)

            # Test user-only filtering
            user_files = discover_settings_files(
                start_path=work_dir,
                levels=[SettingsLevel.USER_GLOBAL]
            )
            assert len(user_files) == 1
            assert all(f.level == SettingsLevel.USER_GLOBAL for f in user_files)


class TestPerformanceRequirements:
    """Test performance requirements and optimization."""

    def test_cli_response_time_requirement(self, temp_environment, discovery_instance):
        """Test that discovery meets <100ms CLI response time requirement."""
        temp_path, helper = temp_environment

        # Create realistic project structure
        project_root = temp_path / "perf_project"
        work_dir, _ = helper.create_project_structure(project_root, levels=5, has_settings=True)

        # Create user home
        fake_home = temp_path / "home" / "user"
        helper.create_user_home_structure(fake_home, has_settings=True)

        with patch("pathlib.Path.home", return_value=fake_home):
            # Time the full discovery process
            start_time = time.time()
            files = discovery_instance.discover_settings_files(start_path=work_dir)
            end_time = time.time()

            # Should complete within 100ms requirement
            assert end_time - start_time < 0.1
            assert len(files) == 2

    def test_large_directory_structure_performance(self, temp_environment, discovery_instance):
        """Test performance with large directory structures."""
        temp_path, helper = temp_environment

        # Create a moderately large directory structure
        project_root = temp_path / "large_project"

        # Create many sibling directories (but not in search path)
        for i in range(100):
            sibling_dir = project_root / f"sibling_{i}"
            sibling_dir.mkdir(parents=True, exist_ok=True)

        # Create actual work directory with settings
        work_dir, _ = helper.create_project_structure(project_root / "work", levels=3, has_settings=True)

        start_time = time.time()
        files = discovery_instance.discover_settings_files(start_path=work_dir)
        end_time = time.time()

        # Should still complete quickly despite many sibling directories
        assert end_time - start_time < 0.2
        assert len(files) >= 1

    def test_repeated_discovery_caching_benefit(self, temp_environment, discovery_instance):
        """Test that caching provides measurable performance benefit."""
        temp_path, helper = temp_environment

        # Create project structure
        project_root = temp_path / "cache_benefit_project"
        work_dir, _ = helper.create_project_structure(project_root, levels=3, has_settings=True)

        # First discovery (no cache)
        start_time = time.time()
        files1 = discovery_instance.discover_settings_files(start_path=work_dir)
        first_time = time.time() - start_time

        # Second discovery (should hit cache)
        start_time = time.time()
        files2 = discovery_instance.discover_settings_files(start_path=work_dir)
        second_time = time.time() - start_time

        # Results should be identical
        assert len(files1) == len(files2)

        # Second call should be significantly faster (at least 2x)
        assert second_time < first_time / 2 or second_time < 0.01  # Or very fast


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])