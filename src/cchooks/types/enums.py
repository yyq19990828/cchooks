"""Enumerations for CLI API Tools for Hook Management.

This module contains all enumeration types used by the CLI API tools,
following the data model specifications from the design documents.

All enums inherit from str and Enum to support JSON serialization and
provide utility methods for validation and parsing.
"""

from enum import Enum
from typing import List, Optional, Set


class SettingsLevel(str, Enum):
    """Settings file discovery levels with precedence order.

    Defines the different levels where Claude Code settings files can be found,
    ordered by precedence (PROJECT > USER_GLOBAL).

    NOTE: The data-model.md mentions USER_LOCAL ("user-local"), but the CLI contracts
    and argument_parser.py only use "project" and "user" for CLI operations.
    USER_LOCAL is kept for potential future use in internal file discovery.

    Values:
        PROJECT: Project-level settings (.claude/settings.json) - highest precedence
        USER_LOCAL: User-local settings (.claude/settings.local.json) - internal use
        USER_GLOBAL: User-level settings (~/.claude/settings.json) - lowest precedence
    """
    PROJECT = "project"
    USER_LOCAL = "user-local"  # 保留用于内部文件发现
    USER_GLOBAL = "user"  # CLI API使用的实际值

    @classmethod
    def from_string(cls, value: str) -> "SettingsLevel":
        """Parse settings level from string.

        Args:
            value: String value to parse

        Returns:
            SettingsLevel enum value

        Raises:
            ValueError: If value is not a valid settings level
        """
        try:
            return cls(value)
        except ValueError:
            valid_values = [level.value for level in cls]
            raise ValueError(f"Invalid settings level '{value}'. Valid values: {valid_values}")

    @classmethod
    def get_all_levels(cls) -> List[str]:
        """Get all valid settings level values.

        Returns:
            List of all settings level string values
        """
        return [level.value for level in cls]

    @classmethod
    def get_cli_levels(cls) -> List[str]:
        """Get settings levels used by CLI commands.

        Returns:
            List of CLI-supported level values (project, user)
        """
        return [cls.PROJECT.value, cls.USER_GLOBAL.value]

    @classmethod
    def get_cli_levels_with_all(cls) -> List[str]:
        """Get CLI levels plus 'all' option for list/query commands.

        Returns:
            List of CLI levels plus 'all' (project, user, all)
        """
        return cls.get_cli_levels() + ["all"]

    def get_precedence(self) -> int:
        """Get numerical precedence value (higher = more precedence).

        Returns:
            Precedence value (PROJECT=3, USER_LOCAL=2, USER_GLOBAL=1)
        """
        precedence_map = {
            self.PROJECT: 3,
            self.USER_LOCAL: 2,
            self.USER_GLOBAL: 1
        }
        return precedence_map[self]


class OutputFormat(str, Enum):
    """Output format options for CLI commands.

    Defines the supported output formats for CLI command results.

    Values:
        JSON: Structured JSON output for programmatic consumption
        TABLE: Human-readable table format
        YAML: YAML format for configuration-style output
        QUIET: Minimal output (success/error status only)
    """
    JSON = "json"
    TABLE = "table"
    YAML = "yaml"
    QUIET = "quiet"

    @classmethod
    def from_string(cls, value: str) -> "OutputFormat":
        """Parse output format from string.

        Args:
            value: String value to parse

        Returns:
            OutputFormat enum value

        Raises:
            ValueError: If value is not a valid output format
        """
        try:
            return cls(value)
        except ValueError:
            valid_values = [fmt.value for fmt in cls]
            raise ValueError(f"Invalid output format '{value}'. Valid values: {valid_values}")

    @classmethod
    def get_structured_formats(cls) -> List[str]:
        """Get formats that support structured data output.

        Returns:
            List of structured format values (JSON, YAML)
        """
        return [cls.JSON.value, cls.YAML.value]

    @classmethod
    def get_human_readable_formats(cls) -> List[str]:
        """Get formats optimized for human consumption.

        Returns:
            List of human-readable format values (TABLE)
        """
        return [cls.TABLE.value]

    def is_structured(self) -> bool:
        """Check if this format supports structured data.

        Returns:
            True if format is JSON or YAML
        """
        return self.value in self.get_structured_formats()

    def is_quiet(self) -> bool:
        """Check if this is the quiet format.

        Returns:
            True if format is QUIET
        """
        return self == self.QUIET


class HookEventType(str, Enum):
    """Hook event types supported by Claude Code.

    These match the exact event names used by Claude Code's hook system.
    Each event represents a different point in Claude's execution lifecycle.

    Tool-related events (PRE_TOOL_USE, POST_TOOL_USE) require a matcher field
    to specify which tools they apply to.
    """
    PRE_TOOL_USE = "PreToolUse"
    POST_TOOL_USE = "PostToolUse"
    NOTIFICATION = "Notification"
    USER_PROMPT_SUBMIT = "UserPromptSubmit"
    STOP = "Stop"
    SUBAGENT_STOP = "SubagentStop"
    PRE_COMPACT = "PreCompact"
    SESSION_START = "SessionStart"
    SESSION_END = "SessionEnd"

    @classmethod
    def from_string(cls, value: str) -> "HookEventType":
        """Parse hook event type from string.

        Args:
            value: String value to parse

        Returns:
            HookEventType enum value

        Raises:
            ValueError: If value is not a valid hook event type
        """
        try:
            return cls(value)
        except ValueError:
            valid_values = [event.value for event in cls]
            raise ValueError(f"Invalid hook event type '{value}'. Valid values: {valid_values}")

    @classmethod
    def get_tool_events(cls) -> List[str]:
        """Get hook events that are tool-related and require a matcher.

        Returns:
            List of tool event type values (PreToolUse, PostToolUse)
        """
        return [cls.PRE_TOOL_USE.value, cls.POST_TOOL_USE.value]

    @classmethod
    def get_lifecycle_events(cls) -> List[str]:
        """Get hook events related to session lifecycle.

        Returns:
            List of lifecycle event values (SessionStart, SessionEnd)
        """
        return [cls.SESSION_START.value, cls.SESSION_END.value]

    @classmethod
    def get_stop_events(cls) -> List[str]:
        """Get hook events related to stopping behavior.

        Returns:
            List of stop event values (Stop, SubagentStop)
        """
        return [cls.STOP.value, cls.SUBAGENT_STOP.value]

    def is_tool_event(self) -> bool:
        """Check if this event type is tool-related and requires a matcher.

        Returns:
            True if event is PreToolUse or PostToolUse
        """
        return self.value in self.get_tool_events()

    def is_lifecycle_event(self) -> bool:
        """Check if this event type is session lifecycle-related.

        Returns:
            True if event is SessionStart or SessionEnd
        """
        return self.value in self.get_lifecycle_events()

    def is_stop_event(self) -> bool:
        """Check if this event type is stop-related.

        Returns:
            True if event is Stop or SubagentStop
        """
        return self.value in self.get_stop_events()

    def requires_matcher(self) -> bool:
        """Check if this event type requires a matcher field.

        Returns:
            True if matcher is required (tool events)
        """
        return self.is_tool_event()


class TemplateSource(str, Enum):
    """Source types for hook templates.

    Defines where hook templates can be defined and loaded from.
    """
    BUILTIN = "builtin"      # Built-in templates
    USER = "user"           # User-registered templates
    FILE = "file"           # File-based templates
    PLUGIN = "plugin"       # Plugin-provided templates

    @classmethod
    def from_string(cls, value: str) -> "TemplateSource":
        """Parse template source from string.

        Args:
            value: String value to parse

        Returns:
            TemplateSource enum value

        Raises:
            ValueError: If value is not a valid template source
        """
        try:
            return cls(value)
        except ValueError:
            valid_values = [source.value for source in cls]
            raise ValueError(f"Invalid template source '{value}'. Valid values: {valid_values}")

    @classmethod
    def get_system_sources(cls) -> List[str]:
        """Get template sources provided by the system.

        Returns:
            List of system source values (BUILTIN, PLUGIN)
        """
        return [cls.BUILTIN.value, cls.PLUGIN.value]

    @classmethod
    def get_user_sources(cls) -> List[str]:
        """Get template sources provided by users.

        Returns:
            List of user source values (USER, FILE)
        """
        return [cls.USER.value, cls.FILE.value]

    def is_system_source(self) -> bool:
        """Check if this is a system-provided template source.

        Returns:
            True if source is BUILTIN or PLUGIN
        """
        return self.value in self.get_system_sources()

    def is_user_source(self) -> bool:
        """Check if this is a user-provided template source.

        Returns:
            True if source is USER or FILE
        """
        return self.value in self.get_user_sources()


class HookTemplateType(str, Enum):
    """Built-in hook template types.

    Defines the available built-in templates for Python hook generation.
    Each template is designed for specific use cases and hook event types.
    """
    SECURITY_GUARD = "security-guard"
    AUTO_FORMATTER = "auto-formatter"
    AUTO_LINTER = "auto-linter"
    GIT_AUTO_COMMIT = "git-auto-commit"
    PERMISSION_LOGGER = "permission-logger"
    DESKTOP_NOTIFIER = "desktop-notifier"
    TASK_MANAGER = "task-manager"
    PROMPT_FILTER = "prompt-filter"
    CONTEXT_LOADER = "context-loader"
    CLEANUP_HANDLER = "cleanup-handler"

    @classmethod
    def from_string(cls, value: str) -> "HookTemplateType":
        """Parse hook template type from string.

        Args:
            value: String value to parse

        Returns:
            HookTemplateType enum value

        Raises:
            ValueError: If value is not a valid template type
        """
        try:
            return cls(value)
        except ValueError:
            valid_values = [template.value for template in cls]
            raise ValueError(f"Invalid template type '{value}'. Valid values: {valid_values}")

    @classmethod
    def get_security_templates(cls) -> List[str]:
        """Get templates related to security and validation.

        Returns:
            List of security template values
        """
        return [cls.SECURITY_GUARD.value, cls.PERMISSION_LOGGER.value, cls.PROMPT_FILTER.value]

    @classmethod
    def get_automation_templates(cls) -> List[str]:
        """Get templates for automation tasks.

        Returns:
            List of automation template values
        """
        return [cls.AUTO_FORMATTER.value, cls.AUTO_LINTER.value, cls.GIT_AUTO_COMMIT.value]

    @classmethod
    def get_integration_templates(cls) -> List[str]:
        """Get templates for external integrations.

        Returns:
            List of integration template values
        """
        return [cls.DESKTOP_NOTIFIER.value, cls.CONTEXT_LOADER.value]

    @classmethod
    def get_control_templates(cls) -> List[str]:
        """Get templates for flow control and cleanup.

        Returns:
            List of control template values
        """
        return [cls.TASK_MANAGER.value, cls.CLEANUP_HANDLER.value]

    def get_category(self) -> str:
        """Get the category of this template type.

        Returns:
            Template category string
        """
        if self.value in self.get_security_templates():
            return "security"
        elif self.value in self.get_automation_templates():
            return "automation"
        elif self.value in self.get_integration_templates():
            return "integration"
        elif self.value in self.get_control_templates():
            return "control"
        else:
            return "other"

    def is_security_template(self) -> bool:
        """Check if this is a security-related template.

        Returns:
            True if template is security-related
        """
        return self.value in self.get_security_templates()


class FileState(str, Enum):
    """File state tracking for hook configuration management.

    Represents the current state of files during CLI operations,
    enabling proper state management and validation.

    Values:
        NOT_FOUND: File does not exist at the specified path
        EXISTS: File exists but has not been loaded into memory
        LOADED: File has been loaded and parsed successfully
        MODIFIED: File content has been modified in memory
        SAVED: Modified content has been written back to file
    """
    NOT_FOUND = "not_found"
    EXISTS = "exists"
    LOADED = "loaded"
    MODIFIED = "modified"
    SAVED = "saved"

    @classmethod
    def from_string(cls, value: str) -> "FileState":
        """Parse file state from string.

        Args:
            value: String value to parse

        Returns:
            FileState enum value

        Raises:
            ValueError: If value is not a valid file state
        """
        try:
            return cls(value)
        except ValueError:
            valid_values = [state.value for state in cls]
            raise ValueError(f"Invalid file state '{value}'. Valid values: {valid_values}")

    @classmethod
    def get_valid_transitions(cls, current_state: "FileState") -> Set["FileState"]:
        """Get valid state transitions from the current state.

        Args:
            current_state: Current file state

        Returns:
            Set of valid next states
        """
        transitions = {
            cls.NOT_FOUND: {cls.EXISTS},  # File can be created
            cls.EXISTS: {cls.LOADED, cls.NOT_FOUND},  # Can load or be deleted
            cls.LOADED: {cls.MODIFIED, cls.NOT_FOUND},  # Can modify or be deleted
            cls.MODIFIED: {cls.SAVED, cls.LOADED, cls.NOT_FOUND},  # Can save, reload, or delete
            cls.SAVED: {cls.LOADED, cls.NOT_FOUND}  # Can reload or be deleted
        }
        return transitions.get(current_state, set())

    def can_transition_to(self, target_state: "FileState") -> bool:
        """Check if transition to target state is valid.

        Args:
            target_state: Target state to transition to

        Returns:
            True if transition is valid
        """
        valid_targets = self.get_valid_transitions(self)
        return target_state in valid_targets

    def is_readable(self) -> bool:
        """Check if file can be read in this state.

        Returns:
            True if file is readable (EXISTS, LOADED, MODIFIED, SAVED)
        """
        return self in {self.EXISTS, self.LOADED, self.MODIFIED, self.SAVED}

    def is_writable(self) -> bool:
        """Check if file can be written in this state.

        Returns:
            True if file is writable (EXISTS, LOADED, MODIFIED)
        """
        return self in {self.EXISTS, self.LOADED, self.MODIFIED}

    def has_unsaved_changes(self) -> bool:
        """Check if file has unsaved changes.

        Returns:
            True if state is MODIFIED
        """
        return self == self.MODIFIED

    def is_persistent(self) -> bool:
        """Check if file state represents persistent storage.

        Returns:
            True if state is EXISTS or SAVED
        """
        return self in {self.EXISTS, self.SAVED}
