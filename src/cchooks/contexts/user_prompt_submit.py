"""UserPromptSubmit hook context and output."""

import json
import sys
from typing import Any, Dict, NoReturn, Optional

from ..exceptions import HookValidationError
from .base import BaseHookContext, BaseHookOutput


class UserPromptSubmitContext(BaseHookContext):
    """Context for UserPromptSubmit hooks."""

    def __init__(self, input_data: Dict[str, Any]) -> None:
        """Initialize UserPromptSubmit context."""
        super().__init__(input_data)
        self._validate_user_prompt_submit_fields()

    def _validate_user_prompt_submit_fields(self) -> None:
        """Validate UserPromptSubmit-specific fields."""
        required_fields = ["prompt", "cwd"]
        for field in required_fields:
            if field not in self._input_data:
                self._missing_fields.append(field)

        if self._missing_fields:
            raise HookValidationError(
                f"Missing required UserPromptSubmit fields: {', '.join(self._missing_fields)}"
            )

    @property
    def prompt(self) -> str:
        """Get the user prompt."""
        return str(self._input_data["prompt"])

    @property
    def cwd(self) -> str:
        """Get the current working directory."""
        return str(self._input_data["cwd"])

    @property
    def output(self) -> "UserPromptSubmitOutput":
        """Get the UserPromptSubmit-specific output handler."""
        return UserPromptSubmitOutput()


class UserPromptSubmitOutput(BaseHookOutput):
    """Output handler for UserPromptSubmit hooks."""

    def allow(
        self, suppress_output: bool = False, system_message: Optional[str] = None
    ) -> None:
        """Allow the prompt to be processed.

        Args:
            suppress_output (bool): Hide stdout from transcript mode (default: False)
            system_message (Optional[str]): Optional warning message shown to the user (default: None)
        """
        output = self._continue_flow(suppress_output, system_message)
        output = self._with_specific_output(output, "UserPromptSubmit")
        print(json.dumps(output), file=sys.stdout)

    def block(
        self,
        reason: str,
        suppress_output: bool = False,
        system_message: Optional[str] = None,
    ) -> NoReturn:
        """Block the prompt from being processed using unified SpecificOutput format.

        The submitted prompt is erased from context and the reason is shown to the user.

        Args:
            reason (str): Reason for blocking, shown to the user
            suppress_output (bool): Hide stdout from transcript mode (default: False)
            system_message (Optional[str]): Optional warning message shown to the user (default: None)
        """
        output = self._continue_flow(suppress_output, system_message)
        output.update({"decision": "block", "reason": reason})
        output = self._with_specific_output(output, "UserPromptSubmit")
        print(json.dumps(output), file=sys.stdout)
        sys.exit(0)

    def add_context(
        self,
        context: str,
        suppress_output: bool = False,
        system_message: Optional[str] = None,
    ) -> None:
        """Add additional context to the prompt using unified SpecificOutput.additionalContext.

        Args:
            context (str): Additional context to prepend to the prompt using hookSpecificOutput
            suppress_output (bool): Hide stdout from transcript mode (default: False)
            system_message (Optional[str]): Optional warning message shown to the user (default: None)
        """
        output = self._continue_flow(suppress_output, system_message)
        output = self._with_specific_output(
            output, "UserPromptSubmit", additionalContext=context
        )
        print(json.dumps(output), file=sys.stdout)

    def halt(
        self,
        stop_reason: str,
        suppress_output: bool = False,
        system_message: Optional[str] = None,
    ) -> None:
        """Stop all processing immediately.

        Args:
            stop_reason (str): Stopping reason shown to the user, not shown to Claude
            suppress_output (bool): Hide stdout from transcript mode (default: False)
            system_message (Optional[str]): Optional warning message shown to the user (default: None)
        """
        output = self._stop_flow(stop_reason, suppress_output, system_message)
        output = self._with_specific_output(output, "UserPromptSubmit")
        print(json.dumps(output), file=sys.stdout)

    def exit_success(self, message: Optional[str] = None) -> NoReturn:
        """Exit with success (exit code 0).

        Args:
            message (Optional[str]): Message shown to the user in transcript (default: None)
        """
        self._success(message)

    def exit_block(self, reason: str) -> NoReturn:
        """Exit with blocking error (exit code 2).

        Args:
            reason (str): Reason shown to the user
        """
        self._block(reason)

    def exit_non_block(self, message: str) -> NoReturn:
        """Exit with non-blocking error (exit code 1).

        Args:
            message (str): Message shown to the user
        """
        self._error(message)
