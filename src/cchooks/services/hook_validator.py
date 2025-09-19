"""Hook Validator service for Claude Code hook configuration validation.

This module implements the HookValidator service that provides comprehensive
validation for hook configurations, following the contracts/settings_file_api.yaml
specification.

The HookValidator provides:
- Event type validation
- Command validation with security checks
- Matcher pattern validation
- Complete hook configuration validation
"""

import re
import shlex
from typing import Any, Dict, List, Optional

from ..exceptions import CCHooksError
from ..models.hook_config import HookConfiguration
from ..models.validation import ValidationError, ValidationResult, ValidationWarning
from ..types.enums import HookEventType


class HookValidator:
    """Validation service for hook configurations.

    This service provides comprehensive validation for hook configurations,
    including security checks, pattern validation, and compliance with
    Claude Code format requirements.
    """

    # Security patterns to check in commands
    RISKY_COMMAND_PATTERNS = [
        r'rm\s+-rf',  # Dangerous file deletion
        r'eval\s*\(',  # Code evaluation
        r'\$\d+',  # Positional parameters
        r'\$[A-Z_][A-Z0-9_]*',  # Environment variables
        r'>\s*/dev/',  # Device access
        r'sudo\s+',  # Privilege escalation
        r'curl\s+.*\|\s*sh',  # Pipe to shell execution
        r'wget\s+.*\|\s*sh',  # Pipe to shell execution
        r';\s*rm\s+',  # Command chaining with rm
        r'&&\s*rm\s+',  # Command chaining with rm
    ]

    # Valid tool name patterns for matchers
    VALID_TOOL_PATTERNS = [
        r'^[A-Z][a-zA-Z0-9_]*$',  # Tool names like 'Write', 'Bash', 'Read'
        r'^\*$',  # Wildcard matcher
        r'^[A-Z][a-zA-Z0-9_]*\*$',  # Prefix wildcard like 'Write*'
        r'^\*[A-Z][a-zA-Z0-9_]*$',  # Suffix wildcard like '*Read'
    ]

    def validate_event_type(self, event_type: str) -> ValidationResult:
        """Validate hook event type.

        Args:
            event_type: Event type to validate

        Returns:
            Validation result for event type
        """
        result = ValidationResult(is_valid=True)

        try:
            # Try to parse as HookEventType
            HookEventType.from_string(event_type)
            result.add_suggestion("Event type is valid")

        except ValueError as e:
            result.add_error(
                field_name="event_type",
                error_code="INVALID_EVENT_TYPE",
                message=str(e),
                suggested_fix=f"Use one of: {', '.join([e.value for e in HookEventType])}"
            )

        return result

    def validate_command(self, command: str, event_type: HookEventType) -> ValidationResult:
        """Validate hook command.

        Args:
            command: Command to validate
            event_type: Context event type

        Returns:
            Validation result for command
        """
        result = ValidationResult(is_valid=True)

        # Basic validation
        if not command or not command.strip():
            result.add_error(
                field_name="command",
                error_code="EMPTY_COMMAND",
                message="Command cannot be empty or whitespace-only",
                suggested_fix="Provide a valid shell command"
            )
            return result

        command = command.strip()

        # Length validation
        if len(command) > 2000:
            result.add_error(
                field_name="command",
                error_code="COMMAND_TOO_LONG",
                message=f"Command is too long ({len(command)} characters, max 2000)",
                suggested_fix="Consider using a script file for complex commands"
            )

        # Security validation
        self._validate_command_security(command, result)

        # Shell syntax validation
        try:
            shlex.split(command)
        except ValueError as e:
            result.add_warning(
                field_name="command",
                warning_code="SHELL_SYNTAX_WARNING",
                message=f"Potential shell syntax issue: {e}"
            )

        # Event-specific validation
        if event_type in [HookEventType.PRE_TOOL_USE, HookEventType.POST_TOOL_USE]:
            self._validate_tool_command(command, event_type, result)
        elif event_type in [HookEventType.SESSION_START, HookEventType.SESSION_END]:
            self._validate_session_command(command, event_type, result)

        return result

    def validate_matcher(self, matcher: str, event_type: HookEventType) -> ValidationResult:
        """Validate tool matcher pattern.

        Args:
            matcher: Matcher pattern to validate
            event_type: Context event type

        Returns:
            Validation result for matcher
        """
        result = ValidationResult(is_valid=True)

        # Check if matcher is required for this event type
        if event_type.requires_matcher():
            if not matcher or not matcher.strip():
                result.add_error(
                    field_name="matcher",
                    error_code="MISSING_MATCHER",
                    message=f"Matcher is required for {event_type.value} hooks",
                    suggested_fix="Provide a tool name pattern (e.g., 'Write', 'Bash', '*')"
                )
                return result

            matcher = matcher.strip()

            # Validate matcher pattern
            if not self._is_valid_matcher_pattern(matcher):
                result.add_error(
                    field_name="matcher",
                    error_code="INVALID_MATCHER_PATTERN",
                    message=f"Invalid matcher pattern: '{matcher}'",
                    suggested_fix="Use tool names like 'Write', 'Bash', or wildcards like '*', 'Write*'"
                )

            # Check for overly broad matchers
            if matcher == "*":
                result.add_warning(
                    field_name="matcher",
                    warning_code="BROAD_MATCHER",
                    message="Wildcard matcher '*' will apply to all tools"
                )

        else:
            # Matcher not required for this event type
            if matcher and matcher.strip():
                result.add_warning(
                    field_name="matcher",
                    warning_code="UNNECESSARY_MATCHER",
                    message=f"Matcher is not used for {event_type.value} hooks"
                )

        return result

    def validate_complete_hook(self, hook: HookConfiguration) -> ValidationResult:
        """Comprehensive hook validation.

        Args:
            hook: Complete hook configuration

        Returns:
            Comprehensive validation result
        """
        result = ValidationResult(is_valid=True)

        try:
            # Use the hook's built-in validation
            hook_result = hook.validate()
            result.errors.extend(hook_result.errors)
            result.warnings.extend(hook_result.warnings)
            result.suggestions.extend(hook_result.suggestions)

            if hook_result.has_errors():
                result.is_valid = False

            # Additional comprehensive checks
            if hook.event_type:
                # Cross-field validation
                event_result = self.validate_event_type(hook.event_type.value)
                result.merge(event_result)

                command_result = self.validate_command(hook.command, hook.event_type)
                result.merge(command_result)

                matcher_result = self.validate_matcher(hook.matcher or "", hook.event_type)
                result.merge(matcher_result)

                # Check for logical consistency
                self._validate_hook_consistency(hook, result)

        except Exception as e:
            result.add_error(
                field_name="general",
                error_code="VALIDATION_FAILED",
                message=f"Validation failed: {str(e)}",
                suggested_fix="Check hook configuration format and values"
            )

        return result

    def _validate_command_security(self, command: str, result: ValidationResult) -> None:
        """Validate command for security issues."""
        for pattern in self.RISKY_COMMAND_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                result.add_warning(
                    field_name="command",
                    warning_code="SECURITY_RISK",
                    message=f"Command contains potentially dangerous pattern: {pattern}"
                )

        # Check for file access patterns
        if re.search(r'/etc/|/var/|/usr/|/bin/|/sbin/', command):
            result.add_warning(
                field_name="command",
                warning_code="SYSTEM_PATH_ACCESS",
                message="Command accesses system directories"
            )

        # Check for network access
        if re.search(r'curl|wget|nc|netcat|ssh|scp|rsync', command, re.IGNORECASE):
            result.add_warning(
                field_name="command",
                warning_code="NETWORK_ACCESS",
                message="Command may access network resources"
            )

    def _validate_tool_command(self, command: str, event_type: HookEventType, result: ValidationResult) -> None:
        """Validate commands for tool-related hooks."""
        if event_type == HookEventType.PRE_TOOL_USE:
            # Pre-tool commands should be fast
            if 'sleep' in command.lower():
                result.add_warning(
                    field_name="command",
                    warning_code="SLOW_PRE_TOOL_COMMAND",
                    message="Pre-tool commands should be fast to avoid delaying tool execution"
                )

        elif event_type == HookEventType.POST_TOOL_USE:
            # Post-tool commands can be more complex
            if len(command) < 10:
                result.add_suggestion("Consider adding more comprehensive post-tool processing")

    def _validate_session_command(self, command: str, event_type: HookEventType, result: ValidationResult) -> None:
        """Validate commands for session lifecycle hooks."""
        if event_type == HookEventType.SESSION_START:
            if 'cleanup' in command.lower() or 'exit' in command.lower():
                result.add_warning(
                    field_name="command",
                    warning_code="CLEANUP_IN_START",
                    message="Cleanup commands are more appropriate for session end"
                )

        elif event_type == HookEventType.SESSION_END:
            if 'init' in command.lower() or 'start' in command.lower():
                result.add_warning(
                    field_name="command",
                    warning_code="INIT_IN_END",
                    message="Initialization commands are more appropriate for session start"
                )

    def _is_valid_matcher_pattern(self, matcher: str) -> bool:
        """Check if matcher pattern is valid."""
        for pattern in self.VALID_TOOL_PATTERNS:
            if re.match(pattern, matcher):
                return True
        return False

    def _validate_hook_consistency(self, hook: HookConfiguration, result: ValidationResult) -> None:
        """Validate logical consistency of hook configuration."""
        # Check timeout appropriateness
        if hook.timeout:
            if hook.event_type == HookEventType.PRE_TOOL_USE and hook.timeout > 30:
                result.add_warning(
                    field_name="timeout",
                    warning_code="LONG_PRE_TOOL_TIMEOUT",
                    message="Pre-tool hooks with long timeouts may delay tool execution"
                )

            if hook.timeout > 300:  # 5 minutes
                result.add_warning(
                    field_name="timeout",
                    warning_code="VERY_LONG_TIMEOUT",
                    message="Very long timeouts may cause CLI operations to hang"
                )

        # Check command complexity vs event type
        if hook.event_type in [HookEventType.NOTIFICATION, HookEventType.USER_PROMPT_SUBMIT]:
            if len(hook.command) > 100:
                result.add_suggestion("Simple notification hooks usually have short commands")
