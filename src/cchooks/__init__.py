"""Claude Code hooks Python module.

This module provides a comprehensive, type-safe interface for developing
Claude Code hooks with automatic hook type detection and specialized
contexts for each hook lifecycle.

Basic Usage:
    from cchooks import create_context

    context = create_context()

    if isinstance(context, PreToolUseContext):
        tool_name = context.tool_name
        tool_input = context.tool_input
        context.output.approve(reason="Safe operation")

Hook Types:
    - PreToolUse: Runs before tool execution, can approve/block
    - PostToolUse: Runs after tool execution, can only block
    - Notification: Processes notifications, no decision control
    - Stop: Controls Claude stopping behavior
    - SubagentStop: Controls subagent stopping behavior
    - PreCompact: Runs before transcript compaction
"""

from typing import Union, TextIO
import sys

from .contexts import (
    BaseHookContext,
    BaseHookOutput,
    NotificationContext,
    NotificationOutput,
    PostToolUseContext,
    PostToolUseOutput,
    PreCompactContext,
    PreCompactOutput,
    PreToolUseContext,
    PreToolUseOutput,
    StopContext,
    StopOutput,
    SubagentStopContext,
    SubagentStopOutput,
)
from .exceptions import (
    CCHooksError,
    HookValidationError,
    InvalidHookTypeError,
    ParseError,
)
from .utils import read_json_from_stdin, validate_required_fields

# Type alias for all possible context types
HookContext = Union[
    PreToolUseContext,
    PostToolUseContext,
    NotificationContext,
    StopContext,
    SubagentStopContext,
    PreCompactContext,
]

# Mapping of hook event names to context classes
_HOOK_TYPE_MAP: dict[str, type[HookContext]] = {
    "PreToolUse": PreToolUseContext,
    "PostToolUse": PostToolUseContext,
    "Notification": NotificationContext,
    "Stop": StopContext,
    "SubagentStop": SubagentStopContext,
    "PreCompact": PreCompactContext,
}


def create_context(stdin: TextIO = sys.stdin) -> HookContext:
    """Create appropriate context based on input JSON.

    Reads JSON from stdin and automatically detects the hook type based on
    the 'hook_event_name' field, returning the appropriate specialized context.

    Returns:
        Context object specific to the detected hook type

    Raises:
        ParseError: If JSON is invalid
        InvalidHookTypeError: If hook_event_name is not recognized
        HookValidationError: If required fields are missing
    """
    input_data = read_json_from_stdin(stdin)

    hook_event_name = input_data.get("hook_event_name")
    if not hook_event_name:
        raise InvalidHookTypeError("Missing hook_event_name in input")

    context_class = _HOOK_TYPE_MAP.get(hook_event_name)
    if not context_class:
        raise InvalidHookTypeError(f"Unknown hook event type: {hook_event_name}")

    return context_class(input_data)


__all__ = [
    # Contexts
    "BaseHookContext",
    "BaseHookOutput",
    "PreToolUseContext",
    "PreToolUseOutput",
    "PostToolUseContext",
    "PostToolUseOutput",
    "NotificationContext",
    "NotificationOutput",
    "StopContext",
    "StopOutput",
    "SubagentStopContext",
    "SubagentStopOutput",
    "PreCompactContext",
    "PreCompactOutput",
    # Factory function
    "create_context",
    # Exceptions
    "CCHooksError",
    "HookValidationError",
    "ParseError",
    "InvalidHookTypeError",
    # Utilities
    "read_json_from_stdin",
    "validate_required_fields",
    # Type aliases
    "HookContext",
]
