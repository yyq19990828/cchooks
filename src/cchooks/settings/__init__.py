"""Settings management package for Claude Code CLI tools.

This package provides settings file discovery, management, and manipulation
functionality for Claude Code hook configurations.
"""

from .discovery import (
    SettingsDiscovery,
    clear_discovery_cache,
    discover_settings_files,
    find_project_settings,
    find_user_global_settings,
    get_effective_settings_files,
    get_target_settings_file,
)
from .exceptions import (
    SettingsCacheError,
    SettingsConfigError,
    SettingsDirectoryError,
    SettingsDiscoveryError,
    SettingsError,
    SettingsFileNotFoundError,
    SettingsPermissionError,
    SettingsValidationError,
)

__all__ = [
    # Discovery functions
    "SettingsDiscovery",
    "discover_settings_files",
    "find_project_settings",
    "find_user_global_settings",
    "get_effective_settings_files",
    "get_target_settings_file",
    "clear_discovery_cache",
    # Exception classes
    "SettingsError",
    "SettingsDiscoveryError",
    "SettingsFileNotFoundError",
    "SettingsPermissionError",
    "SettingsValidationError",
    "SettingsCacheError",
    "SettingsDirectoryError",
    "SettingsConfigError",
]
