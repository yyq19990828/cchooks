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
            self._missing_fields.append("message")

        if self._missing_fields:
            raise HookValidationError(
                f"Missing required fields: {', '.join(self._missing_fields)}"
            )

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

    def acknowledge(self, message: Optional[str]) -> NoReturn:  # type: ignore
        """Acknowledge the notification (exit 0).

        Args:
            message(Optional[str]): Message shown to the user(default: None)
        """
        self._success(message)

    def exit_block(self, reason: str) -> NoReturn:
        """Exit with blocking error (exit 2).

        Args:
            reason(str): Blocking reason shown to the user, not to Claude
        """
        self._block(reason)

    def exit_error(self, message: str) -> NoReturn:
        """Report error and Exit with blocking error (exit 1).

        Args:
            message(str): Message shown to the user
        """
        self._error(message)
