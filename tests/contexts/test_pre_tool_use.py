"""Tests for PreToolUseContext and PreToolUseOutput."""

import json
from io import StringIO
from unittest.mock import patch

import pytest

from cchooks.contexts.pre_tool_use import PreToolUseContext, PreToolUseOutput
from cchooks.exceptions import HookValidationError


class TestPreToolUseContext:
    """Test PreToolUseContext functionality."""

    def test_valid_context_creation(self):
        """Test creating context with valid data."""
        data = {
            "hook_event_name": "PreToolUse",
            "session_id": "test-session-123",
            "transcript_path": "/tmp/transcript.json",
            "tool_name": "Write",
            "tool_input": {"file_path": "/tmp/test.txt", "content": "Hello World"},
        }

        context = PreToolUseContext(data)

        assert context.hook_event_name == "PreToolUse"
        assert context.session_id == "test-session-123"
        assert context.transcript_path == "/tmp/transcript.json"
        assert context.tool_name == "Write"
        assert context.tool_input == {
            "file_path": "/tmp/test.txt",
            "content": "Hello World",
        }

    def test_context_properties(self):
        """Test that all context properties are accessible."""
        data = {
            "hook_event_name": "PreToolUse",
            "session_id": "sess_abc123def456",
            "transcript_path": "/Users/user/.claude/transcript.json",
            "tool_name": "Bash",
            "tool_input": {
                "command": "ls -la",
                "description": "List directory contents",
            },
        }

        context = PreToolUseContext(data)

        # Test that output is properly initialized
        assert isinstance(context.output, PreToolUseOutput)

    def test_context_with_different_tools(self):
        """Test context creation with different tool types."""
        tools_and_inputs = [
            ("Write", {"file_path": "/tmp/test.py", "content": "print('hello')"}),
            ("Bash", {"command": "ls -la", "description": "List files"}),
            ("Read", {"file_path": "/tmp/config.json"}),
            (
                "Edit",
                {"file_path": "/tmp/main.py", "old_text": "old", "new_text": "new"},
            ),
            ("Glob", {"pattern": "**/*.py"}),
        ]

        for tool_name, tool_input in tools_and_inputs:
            data = {
                "hook_event_name": "PreToolUse",
                "session_id": "test-123",
                "transcript_path": "/tmp/transcript.json",
                "tool_name": tool_name,
                "tool_input": tool_input,
            }

            context = PreToolUseContext(data)
            assert context.tool_name == tool_name
            assert context.tool_input == tool_input

    def test_context_validation_missing_required_fields(self):
        """Test context validation with missing required fields."""
        invalid_cases = [
            ({}, ["hook_event_name", "tool_name", "tool_input"]),
            ({"hook_event_name": "PreToolUse"}, ["tool_name", "tool_input"]),
            ({"tool_name": "Write"}, ["hook_event_name", "tool_input"]),
            ({"tool_input": {"file_path": "/test"}}, ["hook_event_name", "tool_name"]),
            ({"hook_event_name": "PreToolUse", "tool_name": "Write"}, ["tool_input"]),
        ]

        for data, missing_fields in invalid_cases:
            with pytest.raises(HookValidationError) as exc_info:
                PreToolUseContext(data)

            error_msg = str(exc_info.value)
            for field in missing_fields:
                assert f"Missing required field: {field}" in error_msg

    def test_context_with_extra_fields(self):
        """Test context creation with extra fields (should be ignored)."""
        data = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": "/tmp/test.txt"},
            "extra_field": "should_be_ignored",
            "another_extra": 123,
        }

        context = PreToolUseContext(data)

        # Should successfully create context and ignore extra fields
        assert context.hook_event_name == "PreToolUse"
        assert context.tool_name == "Write"
        assert context.tool_input == {"file_path": "/tmp/test.txt"}


class TestPreToolUseOutput:
    """Test PreToolUseOutput functionality."""

    def test_simple_approve(self):
        """Test simple approve method."""
        data = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": "/tmp/safe.txt", "content": "safe content"},
        }

        context = PreToolUseContext(data)

        # Mock sys.exit to prevent actual exit
        with patch("sys.exit") as mock_exit:
            context.output.simple_approve("Approved for safe file")
            mock_exit.assert_called_once_with(0)

    def test_simple_block(self):
        """Test simple block method."""
        data = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": "/etc/passwd", "content": "malicious content"},
        }

        context = PreToolUseContext(data)

        with patch("sys.exit") as mock_exit:
            context.output.simple_block("Blocking write to system file")
            mock_exit.assert_called_once_with(2)

    def test_continue_approve(self):
        """Test continue approve method."""
        data = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/safe.txt"},
        }

        context = PreToolUseContext(data)

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            context.output.continue_approve("Safe read operation approved")

            output = mock_stdout.getvalue().strip()
            result = json.loads(output)

            assert result["continue"] is True
            assert result["decision"] == "approve"
            assert result["reason"] == "Safe read operation approved"

    def test_continue_block(self):
        """Test continue block method."""
        data = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf /tmp/test"},
        }

        context = PreToolUseContext(data)

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            context.output.continue_block("Potentially dangerous command blocked")

            output = mock_stdout.getvalue().strip()
            result = json.loads(output)

            assert result["continue"] is True
            assert result["decision"] == "block"
            assert result["reason"] == "Potentially dangerous command blocked"

    def test_stop_processing(self):
        """Test stop processing method."""
        data = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": "/etc/shadow", "content": "root password"},
        }

        context = PreToolUseContext(data)

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            context.output.stop_processing("Security violation detected")

            output = mock_stdout.getvalue().strip()
            result = json.loads(output)

            assert result["continue"] is False
            assert result["stopReason"] == "Security violation detected"

    def test_continue_direct(self):
        """Test continue direct method."""
        data = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/log.txt"},
        }

        context = PreToolUseContext(data)

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            context.output.continue_direct()

            output = mock_stdout.getvalue().strip()
            result = json.loads(output)

            assert result["continue"] is True
            assert (
                "decision" not in result
            )  # Should not include decision for continue_direct

    def test_output_suppression(self):
        """Test output suppression functionality."""
        data = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/test.txt"},
        }

        context = PreToolUseContext(data)

        # Test suppress_output=True
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            context.output.continue_approve("Test approval", suppress_output=True)
            assert mock_stdout.getvalue().strip() == ""

    def test_output_without_reason(self):
        """Test output methods without reason parameter."""
        data = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/test.txt"},
        }

        context = PreToolUseContext(data)

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            context.output.continue_approve()

            output = mock_stdout.getvalue().strip()
            result = json.loads(output)

            assert result["continue"] is True
            assert result["decision"] == "approve"
            assert "reason" not in result or result["reason"] == ""


class TestPreToolUseRealWorldScenarios:
    """Test real-world usage scenarios."""

    def test_block_sensitive_file_write(self):
        """Test blocking write to sensitive files."""
        sensitive_files = ["/etc/passwd", "/etc/shadow", "/etc/hosts", "~/.ssh/id_rsa"]

        for file_path in sensitive_files:
            data = {
                "hook_event_name": "PreToolUse",
                "session_id": "test-123",
                "transcript_path": "/tmp/transcript.json",
                "tool_name": "Write",
                "tool_input": {"file_path": file_path, "content": "malicious"},
            }

            context = PreToolUseContext(data)

            # Test blocking decision
            with patch("sys.exit") as mock_exit:
                context.output.simple_block(
                    f"Blocking write to sensitive file: {file_path}"
                )
                mock_exit.assert_called_with(2)

    def test_approve_safe_operations(self):
        """Test approving safe operations."""
        safe_operations = [
            ("Read", {"file_path": "/tmp/README.md"}),
            ("Write", {"file_path": "/tmp/test.txt", "content": "test"}),
            ("Bash", {"command": "pwd"}),
            ("Glob", {"pattern": "*.py"}),
        ]

        for tool_name, tool_input in safe_operations:
            data = {
                "hook_event_name": "PreToolUse",
                "session_id": "test-123",
                "transcript_path": "/tmp/transcript.json",
                "tool_name": tool_name,
                "tool_input": tool_input,
            }

            context = PreToolUseContext(data)

            # Test approval
            with patch("sys.exit") as mock_exit:
                context.output.simple_approve("Safe operation approved")
                mock_exit.assert_called_with(0)

    def test_conditional_approval_based_on_content(self):
        """Test conditional approval based on file content patterns."""
        dangerous_patterns = [
            "rm -rf /",
            "del /q /f C:\\Windows\\System32\\",
            "sudo rm -rf /",
            "format C: /q",
        ]

        for dangerous_command in dangerous_patterns:
            data = {
                "hook_event_name": "PreToolUse",
                "session_id": "test-123",
                "transcript_path": "/tmp/transcript.json",
                "tool_name": "Bash",
                "tool_input": {"command": dangerous_command},
            }

            context = PreToolUseContext(data)

            # Test blocking dangerous commands
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                context.output.continue_block("Dangerous command detected")

                output = mock_stdout.getvalue().strip()
                result = json.loads(output)
                assert result["continue"] is True
                assert result["decision"] == "block"
                assert "Dangerous command detected" in result["reason"]
