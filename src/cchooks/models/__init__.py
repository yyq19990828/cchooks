"""Data models package for cchooks.

This package contains all data model classes for hook configuration,
settings files, validation results, and other core entities.
"""

from .hook_config import HookConfiguration
from .settings_file import SettingsFile, SettingsFileState
from .validation import (
    ModificationResult,
    SaveResult,
    ScriptGenerationResult,
    ValidationError,
    ValidationResult,
    ValidationWarning,
)

__all__ = [
    "SettingsFile",
    "SettingsFileState",
    "ValidationResult",
    "ValidationError",
    "ValidationWarning",
    "ScriptGenerationResult",
    "SaveResult",
    "ModificationResult",
    "HookConfiguration",
]
