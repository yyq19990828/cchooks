"""Stop hook context and output."""

import json
import sys
from typing import Any, Dict, NoReturn, Optional

from .base import BaseHookContext, BaseHookOutput
from ..exceptions import HookValidationError


class StopContext(BaseHookContext):
    """Context for Stop hooks."""

    def __init__(self, input_data: Dict[str, Any]) -> None:
        """Initialize Stop context."""
        super().__init__(input_data)
        self._validate_stop_fields()

    def _validate_stop_fields(self) -> None:
        """Validate Stop-specific fields."""
        if "stop_hook_active" not in self._input_data:
            raise HookValidationError("Missing required Stop field: stop_hook_active")

    @property
    def stop_hook_active(self) -> bool:
        """Get whether stop hook is already active."""
        return bool(self._input_data["stop_hook_active"])

    @property
    def output(self) -> "StopOutput":
        """Get the Stop-specific output handler."""
        return StopOutput()


class StopOutput(BaseHookOutput):
    """Output handler for Stop hooks."""

    def stop_processing(self, stop_reason: str, suppress_output: bool = False) -> None:
        """Stop processing with JSON response.

        Args:
            stop_reason (str): Stopping reason shown to the user, not shown to Claude
            suppress_output (bool): Hide stdout from transcript mode (default: False)
        """
        output = self.stop_flow(stop_reason, suppress_output)
        print(json.dumps(output), file=sys.stdout)

    def continue_block(self, reason: str, suppress_output: bool = False) -> None:
        """Prevent Claude from Stopping and Prompt Claude with JSON response.

        Args:
            reason (str): Reason shown to Clade for further reasoning
            suppress_output (bool): Hide stdout from transcript mode (default: False)
        """
        output = self.continue_flow(suppress_output)
        output.update({"decision": "block", "reason": reason})
        print(json.dumps(output), file=sys.stdout)

    def continue_direct(self, suppress_output: bool = False) -> None:
        """Allow Claude to stop and Do nothing with JSON response.

        Args:
            suppress_output (bool): Hide stdout from transcript mode (default: False)
        """
        output = self.continue_flow(suppress_output)
        print(json.dumps(output), file=sys.stdout)

    def simple_approve(self, message: Optional[str] = None) -> NoReturn:
        """Approve with simple exit code (exit 0).

        Args:
            message (Optional[str]): Message shown to the user (default: None)
        """
        self.success(message)

    def simple_block(self, message: str) -> NoReturn:
        """Block with simple exit code (exit 2).

        Args:
            message (str): Message shown to the user
        """
        self.block(message)
