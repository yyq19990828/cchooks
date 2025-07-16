"""Utility functions for Claude Code hooks."""

import json
import sys
from typing import Any, Dict, TextIO

from .exceptions import ParseError


def read_json_from_stdin(stdin: TextIO = sys.stdin) -> Dict[str, Any]:
    """Read and parse JSON from stdin.

    Args:
        stdin: Input stream to read from (defaults to sys.stdin)

    Returns:
        Parsed JSON data as a dictionary

    Raises:
        ParseError: If JSON is invalid or not an object
    """
    try:
        input_data = json.load(stdin)
    except json.JSONDecodeError as e:
        raise ParseError(f"Invalid JSON input: {e}")

    if not isinstance(input_data, dict):
        raise ParseError("Input must be a JSON object")

    return input_data


def validate_required_fields(data: Dict[str, Any], required_fields: list[str]) -> None:
    """Validate that required fields are present in the data.

    Args:
        data: Dictionary to validate
        required_fields: List of required field names

    Raises:
        KeyError: If any required field is missing
    """
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        raise KeyError(f"Missing required fields: {', '.join(missing_fields)}")


def safe_get_str(data: Dict[str, Any], key: str, default: str = "") -> str:
    """Safely get a string value from dictionary.

    Args:
        data: Dictionary to get value from
        key: Key to look up
        default: Default value if key missing or not string

    Returns:
        String value or default
    """
    value = data.get(key, default)
    return str(value) if value is not None else default


def safe_get_bool(data: Dict[str, Any], key: str, default: bool = False) -> bool:
    """Safely get a boolean value from dictionary.

    Args:
        data: Dictionary to get value from
        key: Key to look up
        default: Default value if key missing or not boolean

    Returns:
        Boolean value or default
    """
    value = data.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes", "on")
    return default


def safe_get_dict(
    data: Dict[str, Any], key: str, default: Dict[str, Any] | None = None
) -> Dict[str, Any]:
    """Safely get a dictionary value from dictionary.

    Args:
        data: Dictionary to get value from
        key: Key to look up
        default: Default value if key missing or not dict

    Returns:
        Dictionary value or default empty dict
    """
    default = default or {}
    value = data.get(key, default)
    return dict(value) if isinstance(value, dict) else default
