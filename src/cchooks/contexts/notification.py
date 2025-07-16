"""Notification hook context and output."""

from typing import Any, Dict, NoReturn, Optional

from .base import BaseHookContext, BaseHookOutput
from ..exceptions import HookValidationError


class NotificationContext(BaseHookContext):
    """Context for Notification hooks."""

    def __init__(self, input_data: Dict[str, Any]) -> None:
        """Initialize Notification context."""
        super().__init__(input_data)
        self._validate_notification_fields()

    def _validate_notification_fields(self) -> None:
        """Validate Notification-specific fields."""
        if "message" not in self._input_data:
            raise HookValidationError("Missing required Notification field: message")

    @property
    def message(self) -> str:
        """Get the notification message."""
        return str(self._input_data["message"])

    @property
    def output(self) -> "NotificationOutput":
        """Get the Notification-specific output handler."""
        return NotificationOutput()


class NotificationOutput(BaseHookOutput):
    """Output handler for Notification hooks.

    Note: Notification hooks cannot make decisions, they can only process.
    """

    def simple_success(self, message: Optional[str]) -> NoReturn:  # type: ignore
        """Approve with simple exit code (exit 0).

        Args:
            message(Optional[str]): Message shown to the user(default: None)
        """
        self._success(message)

    def simple_block(self, reason: str) -> NoReturn:
        """Block with simple exit code (exit 2).

        Args:
            reason(str): Blocking reason shown to the user, not to Claude
        """
        self._block(reason)

    def simple_error(self, message: str) -> NoReturn:
        """Report error and Block with simple exit code (exit 1).

        Args:
            message(str): Message shown to the user
        """
        self._error(message)
