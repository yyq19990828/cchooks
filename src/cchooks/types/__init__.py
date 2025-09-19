"""Type definitions for CLI API Tools.

This module provides all type definitions and enumerations used by the CLI tools.
"""

import os

# Import all types from types.py to avoid circular imports
# Re-export all types from the main types module
import sys
from typing import Any, Dict

from .enums import (
    FileState,
    HookEventType,
    HookTemplateType,
    OutputFormat,
    SettingsLevel,
    TemplateSource,
)

parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
types_module = os.path.join(parent_dir, 'types.py')

# Import from types.py by reading it directly
exec(open(types_module).read(), globals())

__all__ = [
    "SettingsLevel",
    "OutputFormat",
    "HookEventType",
    "TemplateSource",
    "HookTemplateType",
    "FileState",
    "CommonOutput",
    "CompleteOutput",
    "PreCompactTrigger",
    "SessionStartSource",
    "SessionEndReason",
    "PreToolUsePermissionDecision",
    "CommonInputFields",
    "PreToolUseInput",
    "PostToolUseInput",
    "NotificationInput",
    "UserPromptSubmitInput",
    "StopInput",
    "SubagentStopInput",
    "PreCompactInput",
    "SessionStartInput",
    "SessionEndInput",
    "HookInput",
    "HookSpecificOutput",
]
