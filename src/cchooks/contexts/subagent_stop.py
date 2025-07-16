"""SubagentStop hook context and output."""

import json
import sys
from typing import Any, Dict, NoReturn, Optional

from .base import BaseHookContext, BaseHookOutput
from ..exceptions import HookValidationError


class SubagentStopContext(BaseHookContext):
    """Context for SubagentStop hooks."""

    def __init__(self, input_data: Dict[str, Any]) -> None:
        """Initialize SubagentStop context."""
        super().__init__(input_data)
        self._validate_subagent_stop_fields()

    def _validate_subagent_stop_fields(self) -> None:
        """Validate SubagentStop-specific fields."""
        if "stop_hook_active" not in self._input_data:
            self._missing_fields.append("stop_hook_active")

        if self._missing_fields:
            raise HookValidationError(
                f"Missing required subagenStop fields: {', '.join(self._missing_fields)}"
            )

    @property
    def stop_hook_active(self) -> bool:
        """stop_hook_active is true when Claude Code is already continuing as a result of a stop hook"""
        return bool(self._input_data["stop_hook_active"])

    @property
    def output(self) -> "SubagentStopOutput":
        """Get the SubagentStop-specific output handler."""
        return SubagentStopOutput()


class SubagentStopOutput(BaseHookOutput):
    """Output handler for SubagentStop hooks."""

    def stop_processing(self, stop_reason: str, suppress_output: bool = False) -> None:
        """Stop processing with JSON response.

        Args:
            stop_reason (str): Stopping reason shown to the user, not shown to Claude
            suppress_output (bool): Hide stdout from transcript mode (default: False)
        """
        output = self._stop_flow(stop_reason, suppress_output)
        print(json.dumps(output), file=sys.stdout)

    def continue_block(self, reason: str, suppress_output: bool = False) -> None:
        """Prevent Claude from Stopping and Prompt Claude with JSON response.

        Args:
            reason (str): Reason shown to Clade for further reasoning
            suppress_output (bool): Hide stdout from transcript mode (default: False)
        """
        output = self._continue_flow(suppress_output)
        output.update({"decision": "block", "reason": reason})
        print(json.dumps(output), file=sys.stdout)

    def continue_direct(self, suppress_output: bool = False) -> None:
        """Allow Claude to stop and Do nothing with JSON response.

        Args:
            suppress_output (bool): Hide stdout from transcript mode (default: False)
        """
        output = self._continue_flow(suppress_output)
        print(json.dumps(output), file=sys.stdout)

    def simple_approve(self, message: Optional[str] = None) -> NoReturn:
        """Approve with simple exit code (exit 0).

        Args:
            message (Optional[str]): Message shown to the user (default: None)
        """
        self._success(message)

    def simple_block(self, message: str) -> NoReturn:
        """Block with simple exit code (exit 2).

        Args:
            message (str): Message shown to the user
        """
        self._block(message)
