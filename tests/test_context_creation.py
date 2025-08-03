"""Tests for the main create_context() function."""

import json
from io import StringIO

import pytest

from cchooks import create_context
from cchooks.contexts import (
    PreToolUseContext,
    PostToolUseContext,
    NotificationContext,
    UserPromptSubmitContext,
    StopContext,
    SubagentStopContext,
    PreCompactContext,
    SessionStartContext,
)
from cchooks.exceptions import InvalidHookTypeError, ParseError
from tests.fixtures.sample_data import (
    SAMPLE_PRE_TOOL_USE_WRITE,
    SAMPLE_POST_TOOL_USE_SUCCESS,
    SAMPLE_NOTIFICATION_WARNING,
    SAMPLE_STOP_WITH_HOOK,
    SAMPLE_SUBAGENT_STOP_WITH_HOOK,
    SAMPLE_PRE_COMPACT_MANUAL,
    SAMPLE_USER_PROMPT_SUBMIT_SIMPLE,
    SAMPLE_SESSION_START_STARTUP,
    INVALID_MISSING_HOOK_EVENT,
    INVALID_UNKNOWN_HOOK_EVENT,
)


class TestCreateContextValidInput:
    """Test create_context() with valid inputs."""

    def test_create_pre_tool_use_context(self):
        """Test creating PreToolUseContext from valid input."""
        test_input = StringIO(json.dumps(SAMPLE_PRE_TOOL_USE_WRITE))
        context = create_context(test_input)

        assert isinstance(context, PreToolUseContext)
        assert context.hook_event_name == "PreToolUse"
        assert context.tool_name == "Write"
        assert context.tool_input == SAMPLE_PRE_TOOL_USE_WRITE["tool_input"]

    def test_create_post_tool_use_context(self):
        """Test creating PostToolUseContext from valid input."""
        test_input = StringIO(json.dumps(SAMPLE_POST_TOOL_USE_SUCCESS))
        context = create_context(test_input)
        assert isinstance(context, PostToolUseContext)
        assert context.hook_event_name == "PostToolUse"
        assert context.tool_name == "Write"
        assert context.tool_input == SAMPLE_POST_TOOL_USE_SUCCESS["tool_input"]
        assert context.tool_response == SAMPLE_POST_TOOL_USE_SUCCESS["tool_response"]

    def test_create_notification_context(self):
        """Test creating NotificationContext from valid input."""
        test_input = StringIO(json.dumps(SAMPLE_NOTIFICATION_WARNING))
        context = create_context(test_input)
        assert isinstance(context, NotificationContext)
        assert context.hook_event_name == "Notification"
        assert context.message == SAMPLE_NOTIFICATION_WARNING["message"]

    def test_create_stop_context(self):
        """Test creating StopContext from valid input."""
        test_input = StringIO(json.dumps(SAMPLE_STOP_WITH_HOOK))
        context = create_context(test_input)
        assert isinstance(context, StopContext)
        assert context.hook_event_name == "Stop"
        assert context.stop_hook_active == SAMPLE_STOP_WITH_HOOK["stop_hook_active"]

    def test_create_subagent_stop_context(self):
        """Test creating SubagentStopContext from valid input."""
        test_input = StringIO(json.dumps(SAMPLE_SUBAGENT_STOP_WITH_HOOK))
        context = create_context(test_input)
        assert isinstance(context, SubagentStopContext)
        assert context.hook_event_name == "SubagentStop"
        assert (
            context.stop_hook_active
            == SAMPLE_SUBAGENT_STOP_WITH_HOOK["stop_hook_active"]
        )

    def test_create_pre_compact_context(self):
        """Test creating PreCompactContext from valid input."""
        test_input = StringIO(json.dumps(SAMPLE_PRE_COMPACT_MANUAL))
        context = create_context(test_input)
        assert isinstance(context, PreCompactContext)
        assert context.hook_event_name == "PreCompact"
        assert context.trigger == SAMPLE_PRE_COMPACT_MANUAL["trigger"]
        assert (
            context.custom_instructions
            == SAMPLE_PRE_COMPACT_MANUAL["custom_instructions"]
        )

    def test_create_user_prompt_submit_context(self):
        """Test creating UserPromptSubmitContext from valid input."""
        test_input = StringIO(json.dumps(SAMPLE_USER_PROMPT_SUBMIT_SIMPLE))
        context = create_context(test_input)
        assert isinstance(context, UserPromptSubmitContext)
        assert context.hook_event_name == "UserPromptSubmit"
        assert context.prompt == SAMPLE_USER_PROMPT_SUBMIT_SIMPLE["prompt"]
        assert context.cwd == SAMPLE_USER_PROMPT_SUBMIT_SIMPLE["cwd"]

    def test_create_session_start_context(self):
        """Test creating SessionStartContext from valid input."""
        test_input = StringIO(json.dumps(SAMPLE_SESSION_START_STARTUP))
        context = create_context(test_input)
        assert isinstance(context, SessionStartContext)
        assert context.hook_event_name == "SessionStart"
        assert context.source == SAMPLE_SESSION_START_STARTUP["source"]


class TestCreateContextInvalidInput:
    """Test create_context() with invalid inputs."""

    def test_missing_hook_event_name(self):
        """Test creating context with missing hook_event_name."""
        test_input = StringIO(json.dumps(INVALID_MISSING_HOOK_EVENT))
        with pytest.raises(InvalidHookTypeError) as exc_info:
            create_context(test_input)
        assert "Missing hook_event_name in input" in str(exc_info.value)

    def test_unknown_hook_event_type(self):
        """Test creating context with unknown hook event type."""
        test_input = StringIO(json.dumps(INVALID_UNKNOWN_HOOK_EVENT))
        with pytest.raises(InvalidHookTypeError) as exc_info:
            create_context(test_input)
        assert "Unknown hook event type: UnknownHook" in str(exc_info.value)

    def test_invalid_json_syntax(self):
        """Test creating context with invalid JSON syntax."""
        invalid_json = '{"invalid": json,}'
        test_input = StringIO(json.dumps(invalid_json))
        with pytest.raises(ParseError) as exc_info:
            create_context(test_input)
        assert "Input must be a JSON object" in str(exc_info.value)

    def test_empty_json_object(self):
        """Test creating context with empty JSON object."""
        test_input = StringIO(json.dumps({}))
        with pytest.raises(InvalidHookTypeError) as exc_info:
            create_context(test_input)
        assert "Missing hook_event_name in input" in str(exc_info.value)

    def test_empty_stdin(self):
        """Test creating context with empty stdin."""
        test_input = StringIO("")
        with pytest.raises(ParseError) as exc_info:
            create_context(test_input)
        assert "Invalid JSON input" in str(exc_info.value)


class TestCreateContextEdgeCases:
    """Test create_context() with edge cases."""

    def test_case_sensitive_hook_event_name(self):
        """Test that hook event names are case-sensitive."""
        data = SAMPLE_PRE_TOOL_USE_WRITE.copy()
        data["hook_event_name"] = "pretooluse"  # lowercase

        test_input = StringIO(json.dumps(data))
        with pytest.raises(InvalidHookTypeError) as exc_info:
            create_context(test_input)
        assert "Unknown hook event type: pretooluse" in str(exc_info.value)

    def test_whitespace_in_hook_event_name(self):
        """Test handling of whitespace in hook event name."""
        data = SAMPLE_PRE_TOOL_USE_WRITE.copy()
        data["hook_event_name"] = " PreToolUse "  # with spaces

        test_input = StringIO(json.dumps(data))
        with pytest.raises(InvalidHookTypeError) as exc_info:
            create_context(test_input)
        assert "Unknown hook event type:  PreToolUse " in str(exc_info.value)

    def test_none_hook_event_name(self):
        """Test handling of None as hook event name."""
        data = SAMPLE_PRE_TOOL_USE_WRITE.copy()
        data["hook_event_name"] = None

        test_input = StringIO(json.dumps(data))
        with pytest.raises(InvalidHookTypeError) as exc_info:
            create_context(test_input)
        assert "Missing hook_event_name in input" in str(exc_info.value)

    def test_empty_string_hook_event_name(self):
        """Test handling of empty string as hook event name."""
        data = SAMPLE_PRE_TOOL_USE_WRITE.copy()
        data["hook_event_name"] = ""

        test_input = StringIO(json.dumps(data))
        with pytest.raises(InvalidHookTypeError) as exc_info:
            create_context(test_input)
        assert "Missing hook_event_name in input" in str(exc_info.value)


class TestCreateContextIntegration:
    """Integration tests for create_context()."""

    @pytest.mark.parametrize(
        "hook_type,sample_data",
        [
            ("PreToolUse", SAMPLE_PRE_TOOL_USE_WRITE),
            ("PostToolUse", SAMPLE_POST_TOOL_USE_SUCCESS),
            ("Notification", SAMPLE_NOTIFICATION_WARNING),
            ("Stop", SAMPLE_STOP_WITH_HOOK),
            ("SubagentStop", SAMPLE_SUBAGENT_STOP_WITH_HOOK),
            ("PreCompact", SAMPLE_PRE_COMPACT_MANUAL),
        ],
    )
    def test_all_hook_types_integration(self, hook_type, sample_data):
        """Test all hook types can be created successfully."""
        test_input = StringIO(json.dumps(sample_data))
        context = create_context(test_input)
        assert context.hook_event_name == hook_type

    def test_context_properties_access(self):
        """Test that context properties are correctly accessible."""
        test_data = SAMPLE_PRE_TOOL_USE_WRITE.copy()
        test_data["extra_field"] = "should_be_ignored"

        test_input = StringIO(json.dumps(test_data))
        context = create_context(test_input)

        assert isinstance(context, PreToolUseContext)

        # Test standard properties
        assert context.hook_event_name == "PreToolUse"
        assert context.session_id == "sess_abc123def456"
        assert (
            context.transcript_path
            == "/Users/user/.claude/transcript_20240716_143022.json"
        )
        assert context.tool_name == "Write"
        assert context.tool_input["file_path"] == "/Users/user/project/src/main.py"

    def test_context_output_methods_exist(self):
        """Test that context output methods are available."""
        test_input = StringIO(json.dumps(SAMPLE_PRE_TOOL_USE_WRITE))
        context = create_context(test_input)

        # Test that output methods exist
        assert hasattr(context, "output")
        assert hasattr(context.output, "exit_success")
        assert hasattr(context.output, "exit_block")
        assert hasattr(context.output, "allow")
        assert hasattr(context.output, "deny")
        assert hasattr(context.output, "ask")
        assert hasattr(context.output, "halt")
