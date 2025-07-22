"""Type definitions for Claude Code hooks."""

from typing import Any, Dict, Literal, Union

# Hook event types
HookEventType = Literal[
    "PreToolUse", "PostToolUse", "Notification", "Stop", "SubagentStop", "PreCompact"
]

# Tool names
# ToolName = Literal[
#     "Task",
#     "Bash",
#     "Glob",
#     "Grep",
#     "Read",
#     "Edit",
#     "MultiEdit",
#     "Write",
#     "WebFetch",
#     "WebSearch",
# ]

# Trigger types for PreCompact
PreCompactTrigger = Literal["manual", "auto"]

# JSON output decision types
PreToolUseDecision = Literal["approve", "block"]
PostToolUseDecision = Literal["block"]
StopDecision = Literal["block"]

# Common fields present in all hook inputs
CommonInputFields = Dict[str, Any]  # session_id, transcript_path, hook_event_name

# Hook-specific input types
PreToolUseInput = Dict[str, Any]  # + tool_name, tool_input, cwd
PostToolUseInput = Dict[str, Any]  # + tool_name, tool_input, tool_response, cwd
NotificationInput = Dict[str, Any]  # + message, cwd
StopInput = Dict[str, Any]  # + stop_hook_active
SubagentStopInput = Dict[str, Any]  # + stop_hook_active
PreCompactInput = Dict[str, Any]  # + trigger, custom_instructions

# Hook input union
HookInput = Union[
    PreToolUseInput,
    PostToolUseInput,
    NotificationInput,
    StopInput,
    SubagentStopInput,
    PreCompactInput,
]

# JSON output types
BaseOutput = Dict[str, bool | str]
PreToolUseOutput = Dict[str, bool | str]  # + decision, reason
PostToolUseOutput = Dict[str, bool | str]  # + decision, reason
StopOutput = Dict[str, bool | str]  # + decision, reason
