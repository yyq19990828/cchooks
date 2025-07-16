"""PostToolUse hook context and output."""

import json
import sys
from typing import Any, Dict, NoReturn, Optional

from .base import BaseHookContext, BaseHookOutput
from ..exceptions import HookValidationError
from ..types import ToolName


class PostToolUseContext(BaseHookContext):
    """Context for PostToolUse hooks."""

    def __init__(self, input_data: Dict[str, Any]) -> None:
        """Initialize PostToolUse context."""
        super().__init__(input_data)
        self._validate_post_tool_use_fields()

    def _validate_post_tool_use_fields(self) -> None:
        """Validate PostToolUse-specific fields."""
        required_fields = ["tool_name", "tool_input", "tool_response"]
        for field in required_fields:
            if field not in self._input_data:
                raise HookValidationError(
                    f"Missing required PostToolUse field: {field}"
                )

        if not isinstance(self._input_data["tool_input"], dict):
            raise HookValidationError("tool_input must be a JSON object")

        if not isinstance(self._input_data["tool_response"], dict):
            raise HookValidationError("tool_response must be a JSON object")

    @property
    def tool_name(self) -> ToolName:
        """Get the tool name."""
        return str(self._input_data["tool_name"])  # type: ignore

    @property
    def tool_input(self) -> Dict[str, Any]:
        """Get the tool input parameters."""
        return dict(self._input_data["tool_input"])

    @property
    def tool_response(self) -> Dict[str, Any]:
        """Get the tool response data."""
        return dict(self._input_data["tool_response"])

    @property
    def output(self) -> "PostToolUseOutput":
        """Get the PostToolUse-specific output handler."""
        return PostToolUseOutput()


class PostToolUseOutput(BaseHookOutput):
    """Output handler for PostToolUse hooks."""

    def stop_processing(self, stop_reason: str, suppress_output: bool = False) -> None:
        """Stop processing with JSON response.

        Args:
            stop_reason (str): Stopping reason shown to the user, not shown to Claude
            suppress_output (bool): Hide stdout from transcript mode (default: False)
        """
        output = self._stop_flow(stop_reason, suppress_output)
        output.update({"decision": "block", "reason": ""})
        print(json.dumps(output), file=sys.stdout)

    def continue_block(self, reason: str, suppress_output: bool = False) -> None:
        """Continue processing but Prompt Claude with JSON response.

        Args:
            reason (str): Reason shown to Clade for further reasoning
            suppress_output (bool): Hide stdout from transcript mode (default: False)
        """
        output = self._continue_flow(suppress_output)
        output.update({"decision": "block", "reason": reason})
        print(json.dumps(output), file=sys.stdout)

    def continue_direct(self, suppress_output: bool = False) -> None:
        """Continue processing and Do nothing with JSON response.

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
            message (str): shown to Clade for further reasoning
        """
        self._block(message)
