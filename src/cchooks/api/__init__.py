"""API package for cchooks.

This package contains public API interfaces for settings file operations,
hook management, and other core functionality.
"""

from .settings_operations import (
    SettingsModificationResult,
    add_hook_to_settings,
    create_new_settings_file,
    find_and_load_settings,
    list_hooks_from_settings,
    remove_hook_from_settings,
    update_hook_in_settings,
    validate_all_hooks,
)

__all__ = [
    'create_new_settings_file',
    'find_and_load_settings',
    'add_hook_to_settings',
    'update_hook_in_settings',
    'remove_hook_from_settings',
    'list_hooks_from_settings',
    'validate_all_hooks',
    'SettingsModificationResult'
]
