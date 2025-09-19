"""Settings file discovery module.

This module implements the core logic for discovering Claude Code settings files
across different levels (project, user-global) with proper precedence handling,
caching for performance, and comprehensive error handling.
"""

import os
import threading
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..models.settings_file import SettingsFile
from ..types.enums import SettingsLevel
from .exceptions import (
    SettingsCacheError,
    SettingsDirectoryError,
    SettingsDiscoveryError,
    SettingsPermissionError,
)

# Cache configuration
CACHE_TTL_SECONDS = 30  # Cache discovery results for 30 seconds
CACHE_MAX_SIZE = 100   # Maximum cached entries


@dataclass
class DiscoveryCache:
    """Cache entry for discovery results."""
    files: List[SettingsFile]
    timestamp: float
    working_directory: str

    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        return time.time() - self.timestamp > CACHE_TTL_SECONDS


class SettingsDiscovery:
    """Settings file discovery engine with caching and optimization.

    This class handles the discovery of Claude Code settings files across
    different levels, implementing the precedence rules and performance
    optimizations required for CLI responsiveness.
    """

    def __init__(self):
        """Initialize discovery engine with thread-safe cache."""
        self._cache: Dict[str, DiscoveryCache] = {}
        self._cache_lock = threading.RLock()

    def discover_settings_files(
        self,
        start_path: Optional[Path] = None,
        levels: Optional[List[SettingsLevel]] = None
    ) -> List[SettingsFile]:
        """Discover settings files with caching and multi-level support.

        Args:
            start_path: Starting directory for discovery (defaults to current directory)
            levels: Specific levels to discover (defaults to all levels)

        Returns:
            List of SettingsFile objects in precedence order (highest to lowest)

        Raises:
            SettingsDiscoveryError: If discovery process fails
            SettingsPermissionError: If directory traversal fails due to permissions
        """
        if start_path is None:
            start_path = Path.cwd()
        else:
            start_path = Path(start_path).resolve()

        if levels is None:
            levels = [SettingsLevel.PROJECT, SettingsLevel.USER_GLOBAL]

        # Check cache first
        cache_key = self._get_cache_key(start_path, levels)
        cached_result = self._get_cached_result(cache_key, start_path)
        if cached_result is not None:
            return cached_result

        # Perform discovery with error handling
        try:
            discovered_files = []

            for level in levels:
                if level == SettingsLevel.PROJECT:
                    discovered_files.extend(self._discover_project_level(start_path))
                elif level == SettingsLevel.USER_GLOBAL:
                    discovered_files.extend(self._discover_user_global_level())

            # Cache the results
            self._cache_results(cache_key, discovered_files, start_path)

            return discovered_files

        except PermissionError as e:
            raise SettingsPermissionError(
                path=start_path,
                operation="directory_traversal",
                details=str(e)
            )
        except OSError as e:
            raise SettingsDiscoveryError(
                f"File system error during discovery: {e}",
                start_path
            )
        except Exception as e:
            raise SettingsDiscoveryError(
                f"Unexpected error during settings discovery: {e}",
                start_path
            )

    def _discover_project_level(self, start_path: Path) -> List[SettingsFile]:
        """Discover project-level settings files by walking up the directory tree.

        Args:
            start_path: Starting directory for upward search

        Returns:
            List of project-level SettingsFile objects
        """
        files = []
        current_path = start_path

        # Walk up the directory tree looking for .claude directories
        while current_path != current_path.parent:
            claude_dir = current_path / ".claude"
            if claude_dir.exists() and claude_dir.is_dir():
                settings_file = claude_dir / "settings.json"
                file_obj = SettingsFile(
                    path=settings_file,
                    level=SettingsLevel.PROJECT
                )
                files.append(file_obj)
                # Return first found (highest precedence)
                break

            current_path = current_path.parent

        return files

    def _discover_user_global_level(self) -> List[SettingsFile]:
        """Discover user-global settings files in the home directory.

        Returns:
            List of user-global SettingsFile objects
        """
        files = []
        home_path = Path.home()
        claude_dir = home_path / ".claude"
        settings_file = claude_dir / "settings.json"

        file_obj = SettingsFile(
            path=settings_file,
            level=SettingsLevel.USER_GLOBAL
        )
        files.append(file_obj)

        return files

    def find_project_settings(self, start_path: Optional[Path] = None) -> Optional[SettingsFile]:
        """Find the closest project-level settings file.

        Args:
            start_path: Starting directory for search (defaults to current directory)

        Returns:
            SettingsFile object for project settings, or None if not found
        """
        files = self.discover_settings_files(
            start_path=start_path,
            levels=[SettingsLevel.PROJECT]
        )
        return files[0] if files else None

    def find_user_global_settings(self) -> SettingsFile:
        """Find user-global settings file.

        Returns:
            SettingsFile object for user-global settings (always returns an object)
        """
        files = self.discover_settings_files(levels=[SettingsLevel.USER_GLOBAL])
        return files[0]  # Always has exactly one entry

    def get_effective_settings_files(
        self,
        start_path: Optional[Path] = None
    ) -> List[SettingsFile]:
        """Get all effective settings files in precedence order.

        This method returns all settings files that should be considered
        for configuration, ordered by precedence (project > user-global).

        Args:
            start_path: Starting directory for discovery

        Returns:
            List of SettingsFile objects in precedence order
        """
        all_files = self.discover_settings_files(start_path=start_path)

        # Filter to only existing files for effective settings
        existing_files = [f for f in all_files if f.exists and f.readable]

        # Sort by precedence (PROJECT first)
        existing_files.sort(key=lambda f: f.level == SettingsLevel.PROJECT, reverse=True)

        return existing_files

    def get_target_settings_file(
        self,
        level: SettingsLevel,
        start_path: Optional[Path] = None
    ) -> SettingsFile:
        """Get the target settings file for a specific level.

        This method returns the settings file that should be used for
        modifications at the specified level, regardless of whether it exists.

        Args:
            level: Target settings level
            start_path: Starting directory for discovery

        Returns:
            SettingsFile object for the target level
        """
        files = self.discover_settings_files(
            start_path=start_path,
            levels=[level]
        )

        if files:
            return files[0]
        else:
            # This shouldn't happen with current implementation, but handle gracefully
            if level == SettingsLevel.PROJECT:
                if start_path is None:
                    start_path = Path.cwd()
                claude_dir = start_path / ".claude"
                settings_path = claude_dir / "settings.json"
            else:  # USER_GLOBAL
                settings_path = Path.home() / ".claude" / "settings.json"

            return SettingsFile(path=settings_path, level=level)

    def clear_cache(self) -> None:
        """Clear the discovery cache.

        This method clears all cached discovery results, forcing fresh
        discovery on the next call. Useful when file system state changes.
        """
        with self._cache_lock:
            self._cache.clear()

    def _get_cache_key(self, start_path: Path, levels: List[SettingsLevel]) -> str:
        """Generate cache key for discovery parameters."""
        levels_str = ",".join(sorted(level.value for level in levels))
        return f"{start_path}:{levels_str}"

    def _get_cached_result(
        self,
        cache_key: str,
        start_path: Path
    ) -> Optional[List[SettingsFile]]:
        """Get cached discovery result if valid."""
        with self._cache_lock:
            if cache_key not in self._cache:
                return None

            entry = self._cache[cache_key]

            # Check if cache entry is expired
            if entry.is_expired():
                del self._cache[cache_key]
                return None

            # Check if working directory changed (invalidates project-level discovery)
            if str(start_path) != entry.working_directory:
                del self._cache[cache_key]
                return None

            # Refresh file status for cached entries
            for file_obj in entry.files:
                file_obj.update_file_status()

            return entry.files

    def _cache_results(
        self,
        cache_key: str,
        files: List[SettingsFile],
        start_path: Path
    ) -> None:
        """Cache discovery results."""
        with self._cache_lock:
            # Implement simple LRU by removing oldest entries if cache is full
            if len(self._cache) >= CACHE_MAX_SIZE:
                # Remove oldest entry
                oldest_key = min(
                    self._cache.keys(),
                    key=lambda k: self._cache[k].timestamp
                )
                del self._cache[oldest_key]

            self._cache[cache_key] = DiscoveryCache(
                files=files,
                timestamp=time.time(),
                working_directory=str(start_path)
            )

    def validate_settings_directory(self, path: Path) -> Tuple[bool, str]:
        """Validate a settings directory for proper permissions and structure.

        Args:
            path: Path to .claude directory to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            if not path.exists():
                # Check if we can create the directory
                parent = path.parent
                if not parent.exists():
                    return False, f"Parent directory does not exist: {parent}"

                if not os.access(parent, os.W_OK):
                    return False, f"No write permission to create directory: {path}"

                return True, ""

            if not path.is_dir():
                return False, f"Path exists but is not a directory: {path}"

            if not os.access(path, os.R_OK):
                return False, f"No read permission for directory: {path}"

            if not os.access(path, os.W_OK):
                return False, f"No write permission for directory: {path}"

            return True, ""

        except OSError as e:
            return False, f"File system error accessing {path}: {e}"


# Global discovery instance for convenience
_default_discovery = SettingsDiscovery()


def discover_settings_files(
    start_path: Optional[Path] = None,
    levels: Optional[List[SettingsLevel]] = None
) -> List[SettingsFile]:
    """Discover settings files using the default discovery instance.

    This is a convenience function that uses the global discovery instance
    with caching enabled.

    Args:
        start_path: Starting directory for discovery (defaults to current directory)
        levels: Specific levels to discover (defaults to all levels)

    Returns:
        List of SettingsFile objects in precedence order
    """
    return _default_discovery.discover_settings_files(start_path, levels)


def find_project_settings(start_path: Optional[Path] = None) -> Optional[SettingsFile]:
    """Find project-level settings file using the default discovery instance.

    Args:
        start_path: Starting directory for search

    Returns:
        SettingsFile object for project settings, or None if not found
    """
    return _default_discovery.find_project_settings(start_path)


def find_user_global_settings() -> SettingsFile:
    """Find user-global settings file using the default discovery instance.

    Returns:
        SettingsFile object for user-global settings
    """
    return _default_discovery.find_user_global_settings()


def get_effective_settings_files(start_path: Optional[Path] = None) -> List[SettingsFile]:
    """Get effective settings files using the default discovery instance.

    Args:
        start_path: Starting directory for discovery

    Returns:
        List of existing, readable SettingsFile objects in precedence order
    """
    return _default_discovery.get_effective_settings_files(start_path)


def get_target_settings_file(
    level: SettingsLevel,
    start_path: Optional[Path] = None
) -> SettingsFile:
    """Get target settings file using the default discovery instance.

    Args:
        level: Target settings level
        start_path: Starting directory for discovery

    Returns:
        SettingsFile object for the target level
    """
    return _default_discovery.get_target_settings_file(level, start_path)


def clear_discovery_cache() -> None:
    """Clear the global discovery cache."""
    _default_discovery.clear_cache()
