"""Custom exceptions for Claude Code hooks."""


class CCHooksError(Exception):
    """Base exception for all cchooks errors."""

    pass


class HookValidationError(CCHooksError):
    """Raised when hook input validation fails."""

    pass


class ParseError(CCHooksError):
    """Raised when JSON parsing fails."""

    pass


class InvalidHookTypeError(CCHooksError):
    """Raised when an invalid hook type is encountered."""

    pass
