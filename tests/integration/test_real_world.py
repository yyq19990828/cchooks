"""Integration tests for real-world cchooks usage scenarios."""

import json
from io import StringIO
from unittest.mock import patch

from cchooks import create_context
from cchooks.contexts import (
    PreToolUseContext,
    PostToolUseContext,
    NotificationContext,
    UserPromptSubmitContext,
    StopContext,
    SubagentStopContext,
    PreCompactContext,
)


class TestRealWorldSecurityScenarios:
    """Test real-world security-focused scenarios."""

    def test_sensitive_file_protection_workflow(self):
        """Test complete workflow for protecting sensitive files."""
        # Test 1: Block write to /etc/passwd
        sensitive_write_data = {
            "hook_event_name": "PreToolUse",
            "session_id": "security-session-123",
            "transcript_path": "/tmp/transcript.json",
            "cwd": "/home/user/project",
            "tool_name": "Write",
            "tool_input": {
                "file_path": "/etc/passwd",
                "content": "malicious_user:x:0:0:root:/root:/bin/bash",
            },
        }

        test_input = StringIO(json.dumps(sensitive_write_data))
        context = create_context(test_input)
        assert isinstance(context, PreToolUseContext)

        with patch("sys.exit") as mock_exit:
            context.output.exit_block("Blocking write to system file /etc/passwd")
            mock_exit.assert_called_once_with(2)

    def test_config_file_approval_workflow(self):
        """Test config file modification approval workflow."""
        # Test 2: Approve safe config file write
        safe_config_data = {
            "hook_event_name": "PreToolUse",
            "session_id": "config-session-456",
            "transcript_path": "/tmp/transcript.json",
            "cwd": "/home/user/project",
            "tool_name": "Write",
            "tool_input": {
                "file_path": "/home/user/project/.env.example",
                "content": "API_KEY=your_api_key_here\nDEBUG=false",
            },
        }

        test_input = StringIO(json.dumps(safe_config_data))
        context = create_context(test_input)
        assert isinstance(context, PreToolUseContext)

        with patch("sys.exit") as mock_exit:
            context.output.exit_success("Safe config file write approved")
            mock_exit.assert_called_once_with(0)

    def test_bash_command_safety_check(self):
        """Test bash command safety validation."""
        dangerous_commands = [
            "rm -rf /",
            "sudo rm -rf /var/log",
            "mkfs.ext4 /dev/sda1",
            "dd if=/dev/zero of=/dev/sda",
            ":(){ :|:& };:",  # Fork bomb
        ]

        for command in dangerous_commands:
            bash_data = {
                "hook_event_name": "PreToolUse",
                "session_id": f"bash-session-{hash(command) % 1000}",
                "transcript_path": "/tmp/transcript.json",
                "cwd": "/home/user/project",
                "tool_name": "Bash",
                "tool_input": {
                    "command": command,
                    "description": "Potentially dangerous system command",
                },
            }

            test_input = StringIO(json.dumps(bash_data))
            context = create_context(test_input)
            assert isinstance(context, PreToolUseContext)

            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                context.output.block(f"Dangerous command detected: {command}")

                output = mock_stdout.getvalue().strip()
                result = json.loads(output)
                assert result["continue"] is True
                assert "Dangerous command" in result["reason"]


class TestRealWorldDevelopmentWorkflows:
    """Test real-world development workflow scenarios."""

    def test_python_auto_formatting_workflow(self):
        """Test Python file auto-formatting after write."""
        # Step 1: Write Python file
        write_data = {
            "hook_event_name": "PostToolUse",
            "session_id": "dev-session-789",
            "transcript_path": "/tmp/transcript.json",
            "cwd": "/home/user/project",
            "tool_name": "Write",
            "tool_input": {
                "file_path": "/project/src/utils.py",
                "content": "def hello():\n    print('hello')\n",
            },
            "tool_response": {
                "success": True,
                "content": "Python file written successfully",
            },
        }

        test_input = StringIO(json.dumps(write_data))
        context = create_context(test_input)
        assert isinstance(context, PostToolUseContext)

        # Check if it's a Python file
        file_path = context.tool_input["file_path"]
        assert file_path.endswith(".py")

        # Allow processing to continue (for auto-formatting)
        context.output.accept(suppress_output=True)

    def test_build_notification_workflow(self):
        """Test build completion notification workflow."""
        build_notification_data = {
            "hook_event_name": "Notification",
            "session_id": "build-session-101",
            "transcript_path": "/tmp/transcript.json",
            "cwd": "/home/user/project",
            "message": "Build completed successfully: 42 tests passed, 0 failed",
        }

        test_input = StringIO(json.dumps(build_notification_data))
        context = create_context(test_input)
        assert isinstance(context, NotificationContext)

        # Process notification
        assert "Build completed" in context.message
        assert "42 tests passed" in context.message

    def test_error_handling_workflow(self):
        """Test error handling and recovery workflow."""
        error_data = {
            "hook_event_name": "PostToolUse",
            "session_id": "error-session-202",
            "transcript_path": "/tmp/transcript.json",
            "cwd": "/home/user/project",
            "tool_name": "Write",
            "tool_input": {
                "file_path": "/protected/system.log",
                "content": "test log entry",
            },
            "tool_response": {
                "success": False,
                "error": "Permission denied: /protected/system.log",
            },
        }

        test_input = StringIO(json.dumps(error_data))
        context = create_context(test_input)
        assert isinstance(context, PostToolUseContext)

        # Handle error gracefully
        assert context.tool_response["success"] is False
        assert "Permission denied" in context.tool_response["error"]


class TestRealWorldConversationManagement:
    """Test real-world conversation management scenarios."""

    def test_stop_with_pending_tasks(self):
        """Test stopping behavior with pending tasks."""
        stop_data = {
            "hook_event_name": "Stop",
            "session_id": "conversation-303",
            "transcript_path": "/tmp/transcript.json",
            "cwd": "/home/user/project",
            "stop_hook_active": False,  # Indicates pending tasks
        }

        test_input = StringIO(json.dumps(stop_data))
        context = create_context(test_input)
        assert isinstance(context, StopContext)
        assert context.stop_hook_active is False

        # Prevent stop due to pending tasks
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            context.output.prevent("Pending deployment tasks not completed")

            output = mock_stdout.getvalue().strip()
            result = json.loads(output)
            assert result["continue"] is True
            assert "Pending deployment tasks" in result["reason"]

    def test_subagent_workflow_completion(self):
        """Test subagent workflow completion management."""
        subagent_stop_data = {
            "hook_event_name": "SubagentStop",
            "session_id": "subagent-404",
            "transcript_path": "/tmp/transcript.json",
            "cwd": "/home/user/project",
            "stop_hook_active": True,  # Indicates completion
        }

        test_input = StringIO(json.dumps(subagent_stop_data))
        context = create_context(test_input)
        assert isinstance(context, SubagentStopContext)
        assert context.stop_hook_active is True

        # Allow subagent to stop
        with patch("sys.exit") as mock_exit:
            context.output.exit_success("Code analysis subagent completed successfully")
            mock_exit.assert_called_once_with(0)

    def test_transcript_compaction_workflow(self):
        """Test transcript compaction workflow."""
        compaction_data = {
            "hook_event_name": "PreCompact",
            "session_id": "compaction-505",
            "transcript_path": "/tmp/transcript.json",
            "cwd": "/home/user/project",
            "trigger": "auto",
            "custom_instructions": "Preserve security decisions and error messages",
        }

        test_input = StringIO(json.dumps(compaction_data))
        context = create_context(test_input)
        assert isinstance(context, PreCompactContext)
        assert context.trigger == "auto"
        assert "security decisions" in context.custom_instructions

        # Approve compaction with custom rules
        with patch("sys.exit") as mock_exit:
            context.output.acknowledge("Auto-compaction with security preservation")
            mock_exit.assert_called_once_with(0)


class TestRealWorldIntegrationScenarios:
    """Test complete real-world integration scenarios."""

    def test_complete_deployment_workflow(self):
        """Test complete deployment workflow with multiple hooks."""
        workflow_steps = [
            # Step 1: Check deployment script safety
            {
                "type": "PreToolUse",
                "data": {
                    "hook_event_name": "PreToolUse",
                    "session_id": "deploy-workflow-1",
                    "transcript_path": "/tmp/transcript.json",
                    "cwd": "/home/user/project",
                    "tool_name": "Bash",
                    "tool_input": {
                        "command": "./deploy.sh production",
                        "description": "Deploy to production environment",
                    },
                },
                "expected": "approve",
            },
            # Step 2: Log deployment success
            {
                "type": "PostToolUse",
                "data": {
                    "hook_event_name": "PostToolUse",
                    "session_id": "deploy-workflow-2",
                    "transcript_path": "/tmp/transcript.json",
                    "cwd": "/home/user/project",
                    "tool_name": "Bash",
                    "tool_input": {
                        "command": "./deploy.sh production",
                        "description": "Deploy to production environment",
                    },
                    "tool_response": {
                        "success": True,
                        "content": "Deployment completed successfully",
                    },
                },
                "expected": "continue",
            },
            # Step 3: Notify completion
            {
                "type": "Notification",
                "data": {
                    "hook_event_name": "Notification",
                    "session_id": "deploy-workflow-3",
                    "transcript_path": "/tmp/transcript.json",
                    "cwd": "/home/user/project",
                    "message": "Production deployment v2.1.0 completed successfully",
                },
                "expected": "process",
            },
        ]

        for step in workflow_steps:
            test_input = StringIO(json.dumps(step["data"]))
            context = create_context(test_input)

            # Verify context type
            expected_type = step["type"]
            if expected_type == "PreToolUse":
                assert isinstance(context, PreToolUseContext)
            elif expected_type == "PostToolUse":
                assert isinstance(context, PostToolUseContext)
            elif expected_type == "Notification":
                assert isinstance(context, NotificationContext)
            elif expected_type == "UserPromptSubmit":
                assert isinstance(context, UserPromptSubmitContext)

    def test_security_audit_workflow(self):
        """Test security audit workflow."""
        audit_scenarios = [
            {
                "description": "Block sensitive file access",
                "file_path": "/etc/shadow",
                "action": "read",
                "expected": "block",
            },
            {
                "description": "Allow safe config read",
                "file_path": "/home/user/project/config.json",
                "action": "read",
                "expected": "approve",
            },
            {
                "description": "Block dangerous command",
                "command": "sudo cat /etc/shadow",
                "action": "write",
                "expected": "block",
            },
        ]

        for scenario in audit_scenarios:
            if scenario["action"] == "read":
                data = {
                    "hook_event_name": "PreToolUse",
                    "session_id": "audit-session",
                    "transcript_path": "/tmp/transcript.json",
                    "cwd": "/home/user/project",
                    "tool_name": "Read",
                    "tool_input": {"file_path": scenario["file_path"]},
                }
            else:  # bash command
                data = {
                    "hook_event_name": "PreToolUse",
                    "session_id": "audit-session",
                    "transcript_path": "/tmp/transcript.json",
                    "cwd": "/home/user/project",
                    "tool_name": "Bash",
                    "tool_input": {
                        "command": scenario["command"],
                        "description": "Security audit command",
                    },
                }

            test_input = StringIO(json.dumps(data))
            context = create_context(test_input)
            assert isinstance(context, PreToolUseContext)

            if scenario["expected"] == "block":
                with patch("sys.exit") as mock_exit:
                    context.output.exit_block(
                        f"Security policy: {scenario['description']}"
                    )
                    mock_exit.assert_called_once_with(2)
            else:
                with patch("sys.exit") as mock_exit:
                    context.output.exit_success("Security audit approved")
                    mock_exit.assert_called_once_with(0)

    def test_development_cycle_workflow(self):
        """Test complete development cycle workflow."""
        dev_cycle = [
            # 1. User submits prompt
            {
                "hook": "UserPromptSubmit",
                "prompt": "Please help me write a Python function to calculate fibonacci numbers",
                "expected": "allow",
            },
            # 2. Write code
            {
                "hook": "PreToolUse",
                "tool": "Write",
                "input": {
                    "file_path": "/project/src/main.py",
                    "content": "def fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)",
                },
                "expected": "approve",
            },
            # 3. Auto-format Python file
            {
                "hook": "PostToolUse",
                "tool": "Write",
                "input": {
                    "file_path": "/project/src/main.py",
                    "content": "def fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)",
                },
                "response": {"success": True, "content": "File written"},
                "expected": "continue",
            },
            # 4. Run tests
            {
                "hook": "PreToolUse",
                "tool": "Bash",
                "input": {"command": "pytest tests/", "description": "Run test suite"},
                "expected": "approve",
            },
            # 5. Test results notification
            {
                "hook": "Notification",
                "message": "Test suite passed: 15/15 tests successful",
                "expected": "process",
            },
            # 6. Stop conversation
            {"hook": "Stop", "stop_hook_active": True, "expected": "allow"},
        ]

        for step in dev_cycle:
            if step["hook"] == "PreToolUse":
                data = {
                    "hook_event_name": "PreToolUse",
                    "session_id": "dev-cycle",
                    "transcript_path": "/tmp/transcript.json",
                    "cwd": "/home/user/project",
                    "tool_name": step["tool"],
                    "tool_input": step["input"],
                }
            elif step["hook"] == "PostToolUse":
                data = {
                    "hook_event_name": "PostToolUse",
                    "session_id": "dev-cycle",
                    "transcript_path": "/tmp/transcript.json",
                    "cwd": "/home/user/project",
                    "tool_name": step["tool"],
                    "tool_input": step["input"],
                    "tool_response": step["response"],
                }
            elif step["hook"] == "Notification":
                data = {
                    "hook_event_name": "Notification",
                    "session_id": "dev-cycle",
                    "transcript_path": "/tmp/transcript.json",
                    "cwd": "/home/user/project",
                    "message": step["message"],
                }
            elif step["hook"] == "UserPromptSubmit":
                data = {
                    "hook_event_name": "UserPromptSubmit",
                    "session_id": "dev-cycle",
                    "transcript_path": "/tmp/transcript.json",
                    "cwd": "/home/user/project",
                    "prompt": step["prompt"],
                }
            else:
                data = {
                    "hook_event_name": "Stop",
                    "session_id": "dev-cycle",
                    "transcript_path": "/tmp/transcript.json",
                    "cwd": "/home/user/project",
                    "stop_hook_active": step["stop_hook_active"],
                }

            test_input = StringIO(json.dumps(data))
            context = create_context(test_input)

            # Basic validation that context was created
            assert context is not None
            assert hasattr(context, "hook_event_name")
