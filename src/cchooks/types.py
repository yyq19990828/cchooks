"""Type definitions for Claude Code hooks."""

from typing import Any, Dict, Literal, Union, Optional

# Hook event types
HookEventType = Literal[
    "PreToolUse",
    "PostToolUse",
    "Notification",
    "UserPromptSubmit",
    "Stop",
    "SubagentStop",
    "PreCompact",
]

# Trigger types for PreCompact
PreCompactTrigger = Literal["manual", "auto"]

# Permission decision types for PreToolUse
PreToolUsePermissionDecision = Literal["allow", "deny", "ask"]

# Common fields present in all hook inputs
CommonInputFields = Dict[str, Any]  # session_id, transcript_path, hook_event_name

# Hook-specific input types
PreToolUseInput = Dict[str, Any]  # + tool_name, tool_input, cwd
PostToolUseInput = Dict[str, Any]  # + tool_name, tool_input, tool_response, cwd
NotificationInput = Dict[str, Any]  # + message, cwd
UserPromptSubmitInput = Dict[str, Any]  # + prompt, cwd
StopInput = Dict[str, Any]  # + stop_hook_active
SubagentStopInput = Dict[str, Any]  # + stop_hook_active
PreCompactInput = Dict[str, Any]  # + trigger, custom_instructions

# Hook input union
HookInput = Union[
    PreToolUseInput,
    PostToolUseInput,
    NotificationInput,
    UserPromptSubmitInput,
    StopInput,
    SubagentStopInput,
    PreCompactInput,
]


# Hook-specific output types
class HookSpecificOutput(Dict[str, Any]):
    """Base class for hook-specific output."""

    pass


class PreToolUseHookSpecificOutput(HookSpecificOutput):
    """Hook-specific output for PreToolUse."""

    hookEventName: Literal["PreToolUse"]
    permissionDecision: PreToolUsePermissionDecision
    permissionDecisionReason: str


class UserPromptSubmitHookSpecificOutput(HookSpecificOutput):
    """Hook-specific output for UserPromptSubmit."""

    hookEventName: Literal["UserPromptSubmit"]
    additionalContext: Optional[str] = None


class PostToolUseHookSpecificOutput(HookSpecificOutput):
    """Hook-specific output for PostToolUse."""

    hookEventName: Literal["PostToolUse"]


class StopHookSpecificOutput(HookSpecificOutput):
    """Hook-specific output for Stop."""

    hookEventName: Literal["Stop"]


class SubagentStopHookSpecificOutput(HookSpecificOutput):
    """Hook-specific output for SubagentStop."""

    hookEventName: Literal["SubagentStop"]


class PreCompactHookSpecificOutput(HookSpecificOutput):
    """Hook-specific output for PreCompact."""

    hookEventName: Literal["PreCompact"]


# JSON output types
CompleteOutput = Dict[str, Any]
CommonOutput = Dict[
    str, Any
]  # continue, stopReason, suppressOutput, hookSpecificOutput
