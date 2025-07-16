"""Base classes for hook contexts and outputs."""

import json
import sys
from abc import ABC, abstractmethod
from typing import Any, Dict, NoReturn, Optional, TextIO

from ..exceptions import HookValidationError, ParseError
from ..types import BaseOutput, HookEventType


class BaseHookContext(ABC):
    """Base class for all hook contexts."""

    def __init__(self, input_data: Dict[str, Any]) -> None:
        """Initialize the context with parsed input data."""
        self._input_data = input_data
        self._validate_common_fields()

    def _validate_common_fields(self) -> None:
        """Validate fields common to all hook types."""
        required_fields = ["session_id", "transcript_path", "hook_event_name"]
        for field in required_fields:
            if field not in self._input_data:
                raise HookValidationError(f"Missing required field: {field}")

    @property
    def session_id(self) -> str:
        """Get the session ID."""
        return str(self._input_data["session_id"])

    @property
    def transcript_path(self) -> str:
        """Get the transcript file path."""
        return str(self._input_data["transcript_path"])

    @property
    def hook_event_name(self) -> HookEventType:
        """Get the hook event name."""
        return str(self._input_data["hook_event_name"])  # type: ignore

    @classmethod
    def from_stdin(cls, stdin: TextIO = sys.stdin) -> "BaseHookContext":
        """Create context from stdin JSON input."""
        try:
            input_data = json.load(stdin)
        except json.JSONDecodeError as e:
            raise ParseError(f"Invalid JSON input: {e}")

        if not isinstance(input_data, dict):
            raise ParseError("Input must be a JSON object")

        return cls(input_data)

    @property
    @abstractmethod
    def output(self) -> "BaseHookOutput":
        """Get the appropriate output handler for this hook type."""
        pass


class BaseHookOutput(ABC):
    """Base class for all hook outputs."""

    def __init__(self) -> None:
        """Initialize the output handler."""
        # self.base_json = base_json
        pass

    def continue_flow(self, suppress_output: bool = False) -> BaseOutput:
        """Construct Json with continue is true"""
        return {
            "continue": True,
            "stopReason": "stopReason",
            "suppressOutput": suppress_output,
        }

    def stop_flow(self, stop_reason: str, suppress_output: bool = False) -> BaseOutput:
        """Construct Json with continue is false"""
        return {
            "continue": False,
            "stopReason": stop_reason,
            "suppressOutput": suppress_output,
        }

    def success(self, message: Optional[str] = None) -> NoReturn:
        """Exit with success (exit code 0)."""
        if message:
            print(message, file=sys.stdout)
        sys.exit(0)

    def error(self, message: str, exit_code: int = 1) -> NoReturn:
        """Exit with error (non-blocking)."""
        print(message, file=sys.stderr)
        sys.exit(exit_code)

    def block(self, reason: str) -> NoReturn:
        """Exit with blocking error (exit code 2)."""
        print(reason, file=sys.stderr)
        sys.exit(2)

