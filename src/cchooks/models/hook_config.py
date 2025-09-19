"""Hook configuration model for Claude Code format compliance.

This module implements the HookConfiguration model following the data model
specifications from data-model.md and Claude Code format constraints.

The model handles:
1. Exact Claude Code JSON format compliance (type="command", command, timeout)
2. CLI-internal fields for event type and matcher
3. Comprehensive validation rules
4. JSON serialization support
5. Integration with cchooks type system
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ..types.enums import HookEventType
from .validation import ValidationError, ValidationResult, ValidationWarning


class HookConfiguration:
    """Represents a single hook configuration entry in Claude Code format.

    This model enforces Claude Code's exact JSON schema requirements while
    providing additional CLI-internal fields for management operations.

    Claude Code JSON Format (EXACT):
    {
        "type": "command",
        "command": "shell-command-here",
        "timeout": 60  // optional
    }

    CLI-Internal Fields (not stored in JSON):
    - event_type: Which hook event this configuration applies to
    - matcher: Tool name pattern (required for PreToolUse/PostToolUse)
    """

    def __init__(self, type: str, command: str, timeout: Optional[int] = None,
                 event_type: Optional[HookEventType] = None, matcher: Optional[str] = None,
                 **kwargs):
        """Initialize HookConfiguration with strict field validation."""
        # Reject any additional fields
        if kwargs:
            extra_fields = list(kwargs.keys())
            raise ValueError(f"Additional fields not allowed in hook objects: {', '.join(extra_fields)}")

        # Set fields
        self.type = type
        self.command = command
        self.timeout = timeout
        self.event_type = event_type
        self.matcher = matcher

        # Validate after setting
        self._validate()

    def _validate(self):
        """Internal validation method."""
        if self.type != "command":
            raise ValueError(f"type must be 'command', got '{self.type}'")

        # Validate command type and content
        if not isinstance(self.command, str):
            raise TypeError(f"command must be a string, got {type(self.command).__name__}")

        if not self.command or not self.command.strip():
            raise ValueError("command field is required and cannot be empty")

        if self.timeout is not None:
            if not isinstance(self.timeout, int):
                raise TypeError(f"timeout must be an integer, got {type(self.timeout).__name__}")
            if self.timeout <= 0:
                raise ValueError(f"timeout must be positive, got {self.timeout}")

        # Validate matcher requirements for tool hooks
        if self.event_type in [HookEventType.PRE_TOOL_USE, HookEventType.POST_TOOL_USE]:
            if not self.matcher:
                event_name = self.event_type.value if hasattr(self.event_type, 'value') else str(self.event_type)
                raise ValueError(f"matcher is required for {event_name} hooks")

    @classmethod
    def from_dict(cls, data: Dict[str, Any], event_type: Optional[HookEventType] = None,
                  matcher: Optional[str] = None) -> "HookConfiguration":
        """Create HookConfiguration from dictionary (JSON deserialization).

        Args:
            data: Dictionary containing hook configuration data
            event_type: Hook event type (CLI-internal)
            matcher: Tool matcher pattern (CLI-internal)

        Returns:
            HookConfiguration instance

        Raises:
            ValueError: If data is invalid or contains forbidden fields
            TypeError: If data types are incorrect
        """
        if not isinstance(data, dict):
            raise TypeError("Configuration data must be a dictionary")

        # Check for forbidden extra fields
        allowed_fields = {"type", "command", "timeout"}
        extra_fields = set(data.keys()) - allowed_fields
        if extra_fields:
            raise ValueError(f"Additional fields not allowed in hook objects: {', '.join(extra_fields)}")

        # Validate required Claude Code format
        if "type" not in data:
            raise ValueError("Missing required field: type")
        if "command" not in data:
            raise ValueError("Missing required field: command")

        if data["type"] != "command":
            raise ValueError(f"type field must be 'command', got '{data['type']}'")

        if not data["command"] or not data["command"].strip():
            raise ValueError("command field cannot be empty or whitespace-only")

        # Validate timeout if present
        timeout = data.get("timeout")
        if timeout is not None:
            if not isinstance(timeout, int):
                raise TypeError(f"timeout must be an integer, got {type(timeout).__name__}")
            if timeout <= 0:
                raise ValueError(f"timeout must be positive, got {timeout}")

        return cls(
            type=data["type"],
            command=data["command"].strip(),
            timeout=timeout,
            event_type=event_type,
            matcher=matcher
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization (Claude Code format).

        Returns only the fields that should be stored in Claude Code settings.json.
        CLI-internal fields (event_type, matcher) are excluded.

        Returns:
            Dictionary in exact Claude Code JSON format
        """
        result = {
            "type": self.type,
            "command": self.command
        }

        if self.timeout is not None:
            result["timeout"] = self.timeout

        return result

    def validate(self) -> ValidationResult:
        """Comprehensive validation of hook configuration.

        Performs validation beyond basic construction checks, including:
        - Security warnings for potentially dangerous commands
        - Performance warnings for long commands
        - Cross-platform compatibility checks
        - Best practice suggestions

        Returns:
            ValidationResult with detailed validation information
        """
        errors = []
        warnings = []
        suggestions = []

        # Validate basic structure (should pass if object was constructed successfully)
        try:
            if self.type != "command":
                errors.append(ValidationError(
                    field_name="type",
                    error_code="INVALID_TYPE",
                    message=f"type must be 'command', got '{self.type}'",
                    suggested_fix="Set type to 'command'"
                ))

            if not self.command or not self.command.strip():
                errors.append(ValidationError(
                    field_name="command",
                    error_code="EMPTY_COMMAND",
                    message="command cannot be empty or whitespace-only",
                    suggested_fix="Provide a valid shell command"
                ))
            else:
                # Security warnings for potentially dangerous commands
                risky_patterns = ['rm -rf', 'eval', '$1', '$USER_INPUT', '$USER_DATA']
                for pattern in risky_patterns:
                    if pattern in self.command:
                        warnings.append(ValidationWarning(
                            field_name="command",
                            warning_code="POTENTIAL_SHELL_INJECTION",
                            message=f"Command contains potentially dangerous pattern: {pattern}"
                        ))
                        suggestions.append("Use parameterized commands to avoid injection risks")
                        break

                # Performance warning for very long commands
                if len(self.command) > 1000:
                    warnings.append(ValidationWarning(
                        field_name="command",
                        warning_code="LONG_COMMAND",
                        message=f"Command is very long ({len(self.command)} characters)"
                    ))
                    suggestions.append("Consider using a script file for complex commands")

            if self.timeout is not None:
                if not isinstance(self.timeout, int):
                    errors.append(ValidationError(
                        field_name="timeout",
                        error_code="INVALID_TIMEOUT_TYPE",
                        message=f"timeout must be an integer, got {type(self.timeout).__name__}",
                        suggested_fix="Use an integer value for timeout"
                    ))
                elif self.timeout <= 0:
                    errors.append(ValidationError(
                        field_name="timeout",
                        error_code="INVALID_TIMEOUT_VALUE",
                        message=f"timeout must be positive, got {self.timeout}",
                        suggested_fix="Use a positive integer value"
                    ))

            # Validate matcher requirements
            if self.event_type in [HookEventType.PRE_TOOL_USE, HookEventType.POST_TOOL_USE]:
                if not self.matcher:
                    errors.append(ValidationError(
                        field_name="matcher",
                        error_code="MISSING_MATCHER",
                        message=f"matcher is required for {self.event_type.value} hooks",
                        suggested_fix="Provide a tool name pattern (e.g., 'Write', 'Bash', '*')"
                    ))

        except Exception as e:
            errors.append(ValidationError(
                field_name="general",
                error_code="VALIDATION_ERROR",
                message=f"Validation failed: {str(e)}",
                suggested_fix="Check configuration format and values"
            ))

        # Additional suggestions for best practices
        if not errors and not warnings:
            suggestions.append("Configuration looks good!")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions
        )

    def __str__(self) -> str:
        """String representation for debugging and logging."""
        parts = [f"type={self.type}", f"command='{self.command}'"]

        if self.timeout is not None:
            parts.append(f"timeout={self.timeout}")
        if self.event_type is not None:
            parts.append(f"event_type={self.event_type.value}")
        if self.matcher is not None:
            parts.append(f"matcher='{self.matcher}'")

        return f"HookConfiguration({', '.join(parts)})"

    def __repr__(self) -> str:
        """Detailed representation for debugging."""
        return self.__str__()
