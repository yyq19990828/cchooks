"""Hook-specific contexts for Claude Code hooks."""

from .base import BaseHookContext, BaseHookOutput
from .notification import NotificationContext, NotificationOutput
from .post_tool_use import PostToolUseContext, PostToolUseOutput
from .pre_compact import PreCompactContext, PreCompactOutput
from .pre_tool_use import PreToolUseContext, PreToolUseOutput
from .session_end import SessionEndContext, SessionEndOutput
from .session_start import SessionStartContext, SessionStartOutput
from .stop import StopContext, StopOutput
from .subagent_stop import SubagentStopContext, SubagentStopOutput
from .user_prompt_submit import UserPromptSubmitContext, UserPromptSubmitOutput

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
    "SessionStartContext",
    "SessionStartOutput",
    "SessionEndContext",
    "SessionEndOutput",
]
