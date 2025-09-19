"""Built-in templates package for cchooks.

This package contains all built-in hook templates including security guards,
auto formatters, context loaders, and other predefined templates.
"""

from .auto_formatter import AutoFormatterTemplate
from .auto_linter import AutoLinterTemplate
from .cleanup_handler import CleanupHandlerTemplate
from .context_loader import ContextLoaderTemplate
from .desktop_notifier import DesktopNotifierTemplate
from .git_auto_commit import GitAutoCommitTemplate
from .permission_logger import PermissionLoggerTemplate
from .prompt_filter import PromptFilterTemplate
from .security_guard import SecurityGuardTemplate
from .task_manager import TaskManagerTemplate

__all__ = [
    "AutoFormatterTemplate",
    "AutoLinterTemplate",
    "CleanupHandlerTemplate",
    "ContextLoaderTemplate",
    "DesktopNotifierTemplate",
    "GitAutoCommitTemplate",
    "PermissionLoggerTemplate",
    "PromptFilterTemplate",
    "SecurityGuardTemplate",
    "TaskManagerTemplate",
]
