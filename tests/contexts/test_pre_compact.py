"""Tests for PreCompactContext and PreCompactOutput."""

import json
from io import StringIO
from unittest.mock import patch

import pytest

from cchooks.contexts.pre_compact import PreCompactContext
from cchooks.exceptions import HookValidationError


class TestPreCompactContext:
    """Test PreCompactContext functionality."""

    def test_valid_context_creation_manual(self):
        """Test creating context with valid manual trigger data."""
        data = {
            "hook_event_name": "PreCompact",
            "session_id": "test-session-123",
            "transcript_path": "/tmp/transcript.json",
            "trigger": "manual",
            "custom_instructions": "Preserve important decisions and security warnings",
        }

        context = PreCompactContext(data)

        assert context.hook_event_name == "PreCompact"
        assert context.session_id == "test-session-123"
        assert context.transcript_path == "/tmp/transcript.json"
        assert context.trigger == "manual"
        assert (
            context.custom_instructions
            == "Preserve important decisions and security warnings"
        )

    def test_valid_context_creation_auto(self):
        """Test creating context with valid auto trigger data."""
        data = {
            "hook_event_name": "PreCompact",
            "session_id": "test-123",
            "transcript_path": "/tmp/transcript.json",
            "trigger": "auto",
            "custom_instructions": "",
        }

        context = PreCompactContext(data)
        assert context.trigger == "auto"
        assert context.custom_instructions == ""

    def test_context_without_custom_instructions(self):
        """Test context creation without custom_instructions field."""
        data = {
            "hook_event_name": "PreCompact",
            "session_id": "test-123",
            "transcript_path": "/tmp/transcript.json",
            "trigger": "auto",
            "custom_instructions": "",
        }

        context = PreCompactContext(data)
        assert context.trigger == "auto"
        assert context.custom_instructions == ""

    def test_context_validation_missing_required_fields(self):
        """Test context validation with missing required fields."""
        invalid_cases = [
            (
                {},
                [
                    "session_id",
                    "transcript_path",
                    "hook_event_name",
                    "trigger",
                    "custom_instructions",
                ],
            ),
            (
                {"hook_event_name": "PostToolUse"},
                [
                    "session_id",
                    "transcript_path",
                    "trigger",
                    "custom_instructions",
                ],
            ),
            (
                {"trigger": "manual"},
                [
                    "session_id",
                    "transcript_path",
                    "hook_event_name",
                    "custom_instructions",
                ],
            ),
            (
                {"custom_instructions": "Please compact"},
                [
                    "session_id",
                    "transcript_path",
                    "hook_event_name",
                    "trigger",
                ],
            ),
        ]

        for data, missing_fields in invalid_cases:
            with pytest.raises(HookValidationError) as exc_info:
                PreCompactContext(data)

            error_msg = str(exc_info.value)
            for field in missing_fields:
                assert field in error_msg

    def test_context_with_invalid_trigger(self):
        """Test context with invalid trigger value."""
        data = {
            "hook_event_name": "PreCompact",
            "session_id": "test-123",
            "transcript_path": "/tmp/transcript.json",
            "trigger": "invalid",
            "custom_instructions": "test",
        }

        # Should still create context - validation is for presence, not value
        context = PreCompactContext(data)
        assert context.trigger == "invalid"

    def test_context_with_extra_fields(self):
        """Test context creation with extra fields."""
        data = {
            "hook_event_name": "PreCompact",
            "session_id": "test-123",
            "transcript_path": "/tmp/transcript.json",
            "trigger": "manual",
            "custom_instructions": "Preserve security logs",
            "extra_field": "should_be_ignored",
            "retention_days": 30,
        }

        context = PreCompactContext(data)
        assert context.trigger == "manual"
        assert context.custom_instructions == "Preserve security logs"


class TestPreCompactOutput:
    """Test PreCompactOutput functionality."""

    def test_acknowledge(self):
        """Test simple approve method."""
        data = {
            "hook_event_name": "PreCompact",
            "session_id": "test-123",
            "transcript_path": "/tmp/transcript.json",
            "trigger": "manual",
            "custom_instructions": "Preserve important content",
        }

        context = PreCompactContext(data)

        with patch("sys.exit") as mock_exit:
            context.output.acknowledge("Compaction approved")
            mock_exit.assert_called_once_with(0)

    def test_exit_block(self):
        """Test simple block method."""
        data = {
            "hook_event_name": "PreCompact",
            "session_id": "test-123",
            "transcript_path": "/tmp/transcript.json",
            "trigger": "auto",
            "custom_instructions": "",
        }

        context = PreCompactContext(data)

        with patch("sys.exit") as mock_exit:
            context.output.exit_block("Prevent compaction")
            mock_exit.assert_called_once_with(2)

    def test_acknowledge(self):
        """Test simple block method."""
        data = {
            "hook_event_name": "PreCompact",
            "session_id": "test-123",
            "transcript_path": "/tmp/transcript.json",
            "trigger": "auto",
            "custom_instructions": "",
        }

        context = PreCompactContext(data)

        with patch("sys.exit") as mock_exit:
            context.output.acknowledge("Compaction success")
            mock_exit.assert_called_once_with(0)

    def test_exit_error(self):
        """Test simple block method."""
        data = {
            "hook_event_name": "PreCompact",
            "session_id": "test-123",
            "transcript_path": "/tmp/transcript.json",
            "trigger": "auto",
            "custom_instructions": "",
        }

        context = PreCompactContext(data)

        with patch("sys.exit") as mock_exit:
            context.output.exit_error("No need for compaction")
            mock_exit.assert_called_once_with(1)


class TestPreCompactRealWorldScenarios:
    """Test real-world pre-compact scenarios."""

    def test_manual_compaction_with_custom_instructions(self):
        """Test manual compaction with detailed custom instructions."""
        instructions = (
            "Preserve all security-related decisions, tool usage patterns, "
            "file modification logs, and error messages. Remove temporary "
            "files and debug output. Keep user confirmations and approvals."
        )

        data = {
            "hook_event_name": "PreCompact",
            "session_id": "manual-compact-123",
            "transcript_path": "/tmp/transcript.json",
            "trigger": "manual",
            "custom_instructions": instructions,
        }

        context = PreCompactContext(data)

        assert context.trigger == "manual"
        assert len(context.custom_instructions) > 50
        assert "security" in context.custom_instructions.lower()

    def test_auto_compaction_default_behavior(self):
        """Test automatic compaction with default behavior."""
        data = {
            "hook_event_name": "PreCompact",
            "session_id": "auto-compact-456",
            "transcript_path": "/tmp/transcript.json",
            "trigger": "auto",
            "custom_instructions": "",
        }

        context = PreCompactContext(data)

        # Test standard auto-compaction
        with patch("sys.exit") as mock_exit:
            context.output.acknowledge("Auto-compaction approved")
            mock_exit.assert_called_once_with(0)

    def test_prevent_compaction_during_critical_operations(self):
        """Test preventing compaction during critical operations."""
        data = {
            "hook_event_name": "PreCompact",
            "session_id": "critical-session-789",
            "transcript_path": "/tmp/transcript.json",
            "trigger": "auto",
            "custom_instructions": "Critical deployment in progress",
        }

        context = PreCompactContext(data)

        # Test preventing compaction
        with patch("sys.exit") as mock_exit:
            context.output.exit_block("Critical deployment active")
            mock_exit.assert_called_once_with(2)

    def test_compaction_with_conditional_logic(self):
        """Test compaction with conditional logic based on trigger type."""
        scenarios = [
            {
                "trigger": "manual",
                "should_compact": True,
                "reason": "User explicitly requested compaction",
            },
            {
                "trigger": "auto",
                "should_compact": True,
                "reason": "Automatic compaction threshold reached",
            },
        ]

        for scenario in scenarios:
            data = {
                "hook_event_name": "PreCompact",
                "session_id": f"{scenario['trigger']}-session",
                "transcript_path": "/tmp/transcript.json",
                "trigger": scenario["trigger"],
                "custom_instructions": "Standard compaction rules",
            }

            context = PreCompactContext(data)

            if scenario["should_compact"]:
                with patch("sys.exit") as mock_exit:
                    context.output.acknowledge(scenario["reason"])
                    mock_exit.assert_called_once_with(0)

    def test_compaction_with_security_focus(self):
        """Test compaction with security-focused instructions."""
        security_instructions = (
            "RETAIN: All security decisions, permission denials, file access logs, "
            "network requests, environment variable reads/writes, sensitive file modifications. "
            "REMOVE: Debug output, progress indicators, temporary file operations, "
            "standard library usage, successful operations without security implications."
        )

        data = {
            "hook_event_name": "PreCompact",
            "session_id": "security-session-111",
            "transcript_path": "/tmp/transcript.json",
            "trigger": "manual",
            "custom_instructions": security_instructions,
        }

        context = PreCompactContext(data)

        assert "security" in context.custom_instructions.lower()
        assert "permission" in context.custom_instructions.lower()
        assert "sensitive" in context.custom_instructions.lower()

    def test_compaction_with_size_optimization(self):
        """Test compaction focused on size optimization."""
        size_instructions = (
            "COMPACT: Remove all debug logs, progress messages, standard output, "
            "successful operations, and non-critical information. "
            "RETAIN: Error messages, warnings, security events, and user decisions."
        )

        data = {
            "hook_event_name": "PreCompact",
            "session_id": "optimization-session-222",
            "transcript_path": "/tmp/transcript.json",
            "trigger": "auto",
            "custom_instructions": size_instructions,
        }

        context = PreCompactContext(data)

        assert "COMPACT" in context.custom_instructions
        assert "RETAIN" in context.custom_instructions

    def test_compaction_workflow_integration(self):
        """Test compaction workflow integration scenarios."""
        workflows = [
            {
                "name": "Development Session",
                "trigger": "auto",
                "instructions": "Keep code changes and test results",
                "expected_action": "approve",
            },
            {
                "name": "Security Audit",
                "trigger": "manual",
                "instructions": "Preserve all security-related content",
                "expected_action": "approve",
            },
            {
                "name": "Active Debugging",
                "trigger": "auto",
                "instructions": "Preserve debug session - prevent compaction",
                "expected_action": "block",
            },
        ]

        for workflow in workflows:
            data = {
                "hook_event_name": "PreCompact",
                "session_id": f"{workflow['name'].lower().replace(' ', '-')}-session",
                "transcript_path": "/tmp/transcript.json",
                "trigger": workflow["trigger"],
                "custom_instructions": workflow["instructions"],
            }

            context = PreCompactContext(data)

            if workflow["expected_action"] == "approve":
                with patch("sys.exit") as mock_exit:
                    context.output.acknowledge(f"Approved for {workflow['name']}")
                    mock_exit.assert_called_once_with(0)
            else:
                with patch("sys.exit") as mock_exit:
                    context.output.exit_block(f"Blocked for {workflow['name']}")
                    mock_exit.assert_called_once_with(2)
