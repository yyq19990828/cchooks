"""PreToolUse hook context and output."""

import json
import sys
from typing import Any, Dict, NoReturn, Optional

from .base import BaseHookContext, BaseHookOutput
from ..exceptions import HookValidationError
from ..types import ToolName


class PreToolUseContext(BaseHookContext):
    """Context for PreToolUse hooks."""

    def __init__(self, input_data: Dict[str, Any]) -> None:
        """Initialize PreToolUse context."""
        super().__init__(input_data)
        self._validate_pre_tool_use_fields()

    def _validate_pre_tool_use_fields(self) -> None:
        """Validate PreToolUse-specific fields."""
        required_fields = ["tool_name", "tool_input"]
        for field in required_fields:
            if field not in self._input_data:
                raise HookValidationError(f"Missing required PreToolUse field: {field}")

        if not isinstance(self._input_data["tool_input"], dict):
            raise HookValidationError("tool_input must be a JSON object")

    @property
    def tool_name(self) -> ToolName:
        """Get the tool name."""
        return str(self._input_data["tool_name"])  # type: ignore

    @property
    def tool_input(self) -> Dict[str, Any]:
        """Get the tool input parameters."""
        return dict(self._input_data["tool_input"])

    @property
    def output(self) -> "PreToolUseOutput":
        """Get the PreToolUse-specific output handler."""
        return PreToolUseOutput()


class PreToolUseOutput(BaseHookOutput):
    """Output handler for PreToolUse hooks."""

    def stop_processing(self, stop_reason: str, suppress_output: bool = False) -> None:
        """Stop processing and Prevent the tool execution with JSON response.

        Args:
            stop_reason (str): Stopping reason shown to the user, not shown to Claude
            suppress_output (bool): Hide stdout from transcript mode (default: False)
        """
        output = self.stop_flow(stop_reason, suppress_output)
        output.update({"decision": "block", "reason": ""})
        print(json.dumps(output), file=sys.stdout)

    def continue_approve(self, reason: str, suppress_output: bool = False) -> None:
        """Continue processing and Approve the tool execution with JSON response.

        Args:
            reason (str): Reason shown to the user, not shown to Clade
            suppress_output (bool): Hide stdout from transcript mode (default: False)
        """
        output = self.continue_flow(suppress_output)
        output.update({"decision": "approve", "reason": reason})
        print(json.dumps(output), file=sys.stdout)

    def continue_block(self, reason: str, suppress_output: bool = False) -> None:
        """Continue processing but Prevent the tool execution with JSON response.

        Args:
            reason (str): Reason shown to Clade for further reasoning
            suppress_output (bool): Hide stdout from transcript mode (default: False)
        """
        output = self.continue_flow(suppress_output)
        output.update({"decision": "block", "reason": reason})
        print(json.dumps(output), file=sys.stdout)

    def continue_direct(self, suppress_output: bool = False) -> None:
        """Continue processing and Do nothing with JSON response.

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
            message (str): shown to Clade for further reasoning
        """
        self.block(message)

