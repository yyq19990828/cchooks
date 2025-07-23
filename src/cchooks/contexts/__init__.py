"""Hook-specific contexts for Claude Code hooks."""

from .base import BaseHookContext, BaseHookOutput
from .pre_tool_use import PreToolUseContext, PreToolUseOutput
from .post_tool_use import PostToolUseContext, PostToolUseOutput
from .notification import NotificationContext, NotificationOutput
from .user_prompt_submit import UserPromptSubmitContext, UserPromptSubmitOutput
from .stop import StopContext, StopOutput
from .subagent_stop import SubagentStopContext, SubagentStopOutput
from .pre_compact import PreCompactContext, PreCompactOutput

__all__ = [
    "BaseHookContext",
    "BaseHookOutput",
    "PreToolUseContext",
    "PreToolUseOutput",
    "PostToolUseContext",
    "PostToolUseOutput",
    "NotificationContext",
    "NotificationOutput",
    "UserPromptSubmitContext",
    "UserPromptSubmitOutput",
    "StopContext",
    "StopOutput",
    "SubagentStopContext",
    "SubagentStopOutput",
    "PreCompactContext",
    "PreCompactOutput",
]
