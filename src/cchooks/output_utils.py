"""Standalone output utilities for graceful error handling.

This module provides standalone functions for handling errors and producing output
when context objects are not available (e.g., during `create_context()` failures).
"""

import json
import sys
from typing import Any, Dict, NoReturn, Optional, TextIO


def exit_success(message: Optional[str] = None, file: TextIO = sys.stdout) -> NoReturn:
    """Exit with success (exit code 0).

    Args:
        message: Optional success message to print
        file: Output file (defaults to stdout)
    """
    if message:
        print(message, file=file)
    sys.exit(0)


def exit_non_block(
    message: str, exit_code: int = 1, file: TextIO = sys.stderr
) -> NoReturn:
    """Exit with error (non-blocking).

    Args:
        message: Error message to print
        exit_code: Exit code (defaults to 1 for non-blocking error)
        file: Output file (defaults to stderr)
    """
    print(message, file=file)
    sys.exit(exit_code)


def exit_block(reason: str, file: TextIO = sys.stderr) -> NoReturn:
    """Exit with blocking error (exit code 2).

    Args:
        reason: Blocking reason to print
        file: Output file (defaults to stderr)
    """
    print(reason, file=file)
    sys.exit(2)


def output_json(data: Dict[str, Any], file: TextIO = sys.stdout) -> None:
    """Output JSON data to the specified file.

    Args:
        data: JSON-serializable data to output
        file: Output file (defaults to stdout)
    """
    print(json.dumps(data, ensure_ascii=False), file=file)


def handle_parse_error(error: Exception, file: TextIO = sys.stderr) -> NoReturn:
    """Handle JSON parsing errors gracefully.

    Args:
        error: The JSON parsing exception
        file: Output file for error message
    """
    exit_non_block(f"Failed to parse JSON input: {error}", exit_code=1, file=file)


def handle_validation_error(error: Exception, file: TextIO = sys.stderr) -> NoReturn:
    """Hook validation errors gracefully.

    Args:
        error: The validation exception
        file: Output file for error message
    """
    exit_non_block(f"Hook validation failed: {error}", exit_code=1, file=file)


def handle_invalid_hook_type(error: Exception, file: TextIO = sys.stderr) -> NoReturn:
    """Handle invalid hook type errors gracefully.

    Args:
        error: The invalid hook type exception
        file: Output file for error message
    """
    exit_non_block(f"Invalid hook type: {error}", exit_code=1, file=file)


def handle_context_error(error: Exception, file: TextIO = sys.stderr) -> NoReturn:
    """Unified handler for all context creation errors.

    Args:
        error: Exception from create_context()
        file: Output file for error message
    """
    from .exceptions import ParseError, InvalidHookTypeError, HookValidationError

    if isinstance(error, ParseError):
        handle_parse_error(error, file)
    elif isinstance(error, InvalidHookTypeError):
        handle_invalid_hook_type(error, file)
    elif isinstance(error, HookValidationError):
        handle_validation_error(error, file)
    else:
        # Fallback for any other exceptions
        exit_non_block(f"Unexpected error: {error}", exit_code=1, file=file)


def safe_create_context(
    stdin: TextIO = sys.stdin, error_file: TextIO = sys.stderr
) -> Any:
    """Safe wrapper around create_context() with built-in error handling.

    Args:
        stdin: Input stream (defaults to sys.stdin)
        error_file: Output file for error messages

    Returns:
        Context object on success, or exits with appropriate error code on failure
    """
    from . import create_context

    try:
        return create_context(stdin)
    except Exception as e:
        handle_context_error(e, error_file)
