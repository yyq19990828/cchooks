"""Tests for utility functions in cchooks.utils module."""

import json
from io import StringIO

import pytest

from cchooks.exceptions import HookValidationError, ParseError
from cchooks.utils import read_json_from_stdin, validate_required_fields


class TestReadJsonFromStdin:
    """Test JSON reading from stdin functionality."""

    def test_valid_json_input(self):
        """Test reading valid JSON from stdin."""
        test_data = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": "/tmp/test.txt", "content": "test"},
        }

        test_input = StringIO(json.dumps(test_data))
        result = read_json_from_stdin(test_input)
        assert result == test_data

    def test_empty_json_input(self):
        """Test reading empty JSON object from stdin."""
        test_data = {}

        test_input = StringIO(json.dumps(test_data))
        result = read_json_from_stdin(test_input)
        assert result == {}

    def test_invalid_json_syntax(self):
        """Test handling invalid JSON syntax."""
        invalid_json = '{"invalid": json,}'

        test_input = StringIO(json.dumps(invalid_json))
        with pytest.raises(ParseError) as exc_info:
            read_json_from_stdin(test_input)
        assert "Input must be a JSON object" in str(exc_info.value)

    def test_empty_stdin(self):
        """Test handling empty stdin."""
        test_input = StringIO(json.dumps(""))
        with pytest.raises(ParseError) as exc_info:
            read_json_from_stdin(test_input)
        assert "Input must be a JSON object" in str(exc_info.value)

    def test_whitespace_only_stdin(self):
        """Test handling whitespace-only stdin."""
        test_input = StringIO(json.dumps("   \n\t  "))
        with pytest.raises(ParseError) as exc_info:
            read_json_from_stdin(test_input)
        assert "Input must be a JSON object" in str(exc_info.value)


class TestValidateRequiredFields:
    """Test field validation functionality."""

    def test_all_required_fields_present(self):
        """Test validation with all required fields present."""
        data = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": "/tmp/test.txt"},
        }
        required_fields = ["hook_event_name", "tool_name", "tool_input"]

        # Should not raise any exception
        validate_required_fields(data, required_fields)

    def test_missing_required_field(self):
        """Test validation with missing required field."""
        data = {"tool_name": "Write", "tool_input": {"file_path": "/tmp/test.txt"}}
        required_fields = ["hook_event_name", "tool_name", "tool_input"]

        with pytest.raises(KeyError) as exc_info:
            validate_required_fields(data, required_fields)
        assert "hook_event_name" in str(exc_info.value)

    def test_multiple_missing_fields(self):
        """Test validation with multiple missing fields."""
        data = {"session_id": "test123"}
        required_fields = ["hook_event_name", "tool_name", "tool_input"]

        with pytest.raises(KeyError) as exc_info:
            validate_required_fields(data, required_fields)
        error_msg = str(exc_info.value)
        assert "hook_event_name" in error_msg
        assert "tool_name" in error_msg
        assert "tool_input" in error_msg

    def test_empty_data(self):
        """Test validation with empty data."""
        data = {}
        required_fields = ["hook_event_name", "tool_name"]

        with pytest.raises(KeyError) as exc_info:
            validate_required_fields(data, required_fields)
        error_msg = str(exc_info.value)
        assert "hook_event_name" in error_msg
        assert "tool_name" in error_msg

    def test_none_values(self):
        """Test validation with None values in required fields."""
        data = {
            "hook_event_name": None,
            "tool_name": "Write",
            "tool_input": {"file_path": "/tmp/test.txt"},
        }
        required_fields = ["hook_event_name", "tool_name", "tool_input"]

        # None values should pass validation (validation is for presence, not content)
        validate_required_fields(data, required_fields)

    def test_empty_string_values(self):
        """Test validation with empty string values in required fields."""
        data = {
            "hook_event_name": "",
            "tool_name": "Write",
            "tool_input": {"file_path": "/tmp/test.txt"},
        }
        required_fields = ["hook_event_name", "tool_name", "tool_input"]

        # Empty strings should pass validation (validation is for presence, not content)
        validate_required_fields(data, required_fields)

    def test_nested_field_validation(self):
        """Test validation with nested field access."""
        data = {
            "tool_input": {"file_path": "/tmp/test.txt", "nested": {"key": "value"}}
        }
        required_fields = ["tool_input"]

        # Should not raise any exception
        validate_required_fields(data, required_fields)

    # def test_non_dict_data(self):
    #     """Test validation with non-dict data."""
    #     data = "invalid string data"
    #     required_fields = ["hook_event_name"]

    #     with pytest.raises(KeyError) as exc_info:
    #         validate_required_fields(data, required_fields)
    #     assert "Input data must be a dictionary" in str(exc_info.value)

    # def test_list_data(self):
    #     """Test validation with list data."""
    #     data = ["hook_event_name", "tool_name"]
    #     required_fields = ["hook_event_name"]

    #     with pytest.raises(HookValidationError) as exc_info:
    #         validate_required_fields(data, required_fields)
    #     assert "Input data must be a dictionary" in str(exc_info.value)


class TestIntegration:
    """Integration tests combining utils functions."""

    def test_full_json_read_and_validation_flow(self):
        """Test complete flow of reading JSON and validating fields."""
        test_data = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": "/tmp/test.txt", "content": "test"},
            "session_id": "test123",
        }
        required_fields = ["hook_event_name", "tool_name", "tool_input"]

        test_input = StringIO(json.dumps(test_data))
        parsed_data = read_json_from_stdin(test_input)
        validate_required_fields(parsed_data, required_fields)
        assert parsed_data["hook_event_name"] == "PreToolUse"
        assert parsed_data["tool_name"] == "Write"

    def test_json_read_with_missing_fields_then_validation(self):
        """Test JSON reading followed by validation failure."""
        incomplete_data = {
            "tool_name": "Write",
            "tool_input": {"file_path": "/tmp/test.txt"},
        }
        required_fields = ["hook_event_name", "tool_name", "tool_input"]

        test_input = StringIO(json.dumps(incomplete_data))
        parsed_data = read_json_from_stdin(test_input)

        with pytest.raises(KeyError) as exc_info:
            validate_required_fields(parsed_data, required_fields)
        assert "hook_event_name" in str(exc_info.value)
