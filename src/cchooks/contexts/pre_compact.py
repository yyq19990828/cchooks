"""PreCompact hook context and output."""

from typing import Any, Dict, NoReturn, Optional

from .base import BaseHookContext, BaseHookOutput
from ..exceptions import HookValidationError
from ..types import PreCompactTrigger


class PreCompactContext(BaseHookContext):
    """Context for PreCompact hooks."""

    def __init__(self, input_data: Dict[str, Any]) -> None:
        """Initialize PreCompact context."""
        super().__init__(input_data)
        self._validate_pre_compact_fields()

    def _validate_pre_compact_fields(self) -> None:
        """Validate PreCompact-specific fields."""
        required_fields = ["trigger", "custom_instructions"]
        for field in required_fields:
            if field not in self._input_data:
                self._missing_fields.append(field)

        if self._missing_fields:
            raise HookValidationError(
                f"Missing required PreCompact fields: {', '.join(self._missing_fields)}"
            )

    @property
    def trigger(self) -> PreCompactTrigger:
        """Get the compact trigger type.

        "manual" means explicitly triggered by user, with @custom_instructions
        "auto" means triggered by Claude itself, while @custom_instructions is empty
        """
        return str(self._input_data["trigger"])  # type: ignore

    @property
    def custom_instructions(self) -> str:
        """Get custom instructions for compaction."""
        return str(self._input_data["custom_instructions"])

    @property
    def output(self) -> "PreCompactOutput":
        """Get the PreCompact-specific output handler."""
        return PreCompactOutput()


class PreCompactOutput(BaseHookOutput):
    """Output handler for PreCompact hooks.

    Note: PreCompact hooks cannot make decisions, they can only process.
    """

    def simple_success(self, message: Optional[str]) -> NoReturn:  # type: ignore
        """Approve with simple exit code (exit 0).

        Args:
            message(Optional[str]): Message shown to the user(default: None)
        """
        self.success(message)

    def simple_block(self, reason: str) -> NoReturn:
        """Block with simple exit code (exit 2).

        Args:
            reason(str): Blocking reason shown to the user, not to Claude
        """
        self.block(reason)

    def simple_error(self, message: str) -> NoReturn:
        """Report error and Block with simple exit code (exit 1).

        Args:
            message(str): Message shown to the user
        """
        self.error(message)
