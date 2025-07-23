"""Sample test data for cchooks testing."""

# Realistic Claude Code hook input examples

SAMPLE_PRE_TOOL_USE_WRITE = {
    "hook_event_name": "PreToolUse",
    "session_id": "sess_abc123def456",
    "transcript_path": "/Users/user/.claude/transcript_20240716_143022.json",
    "cwd": "/Users/user/project",
    "tool_name": "Write",
    "tool_input": {
        "file_path": "/Users/user/project/src/main.py",
        "content": "def hello():\n    print('Hello, World!')\n",
    },
}

SAMPLE_PRE_TOOL_USE_BASH = {
    "hook_event_name": "PreToolUse",
    "session_id": "sess_abc123def456",
    "transcript_path": "/Users/user/.claude/transcript_20240716_143022.json",
    "cwd": "/Users/user/project",
    "tool_name": "Bash",
    "tool_input": {
        "command": "ls -la /tmp",
        "description": "List temporary directory contents",
    },
}

SAMPLE_PRE_TOOL_USE_DANGEROUS = {
    "hook_event_name": "PreToolUse",
    "session_id": "sess_abc123def456",
    "transcript_path": "/Users/user/.claude/transcript_20240716_143022.json",
    "cwd": "/Users/user/project",
    "tool_name": "Bash",
    "tool_input": {"command": "rm -rf /", "description": "Dangerous command"},
}

SAMPLE_POST_TOOL_USE_SUCCESS = {
    "hook_event_name": "PostToolUse",
    "session_id": "sess_abc123def456",
    "transcript_path": "/Users/user/.claude/transcript_20240716_143022.json",
    "cwd": "/Users/user/project",
    "tool_name": "Write",
    "tool_input": {
        "file_path": "/Users/user/project/src/main.py",
        "content": "def hello():\n    print('Hello, World!')\n",
    },
    "tool_response": {
        "success": True,
        "content": "File written successfully to /Users/user/project/src/main.py",
    },
}

SAMPLE_POST_TOOL_USE_ERROR = {
    "hook_event_name": "PostToolUse",
    "session_id": "sess_abc123def456",
    "transcript_path": "/Users/user/.claude/transcript_20240716_143022.json",
    "cwd": "/Users/user/project",
    "tool_name": "Write",
    "tool_input": {
        "file_path": "/etc/protected_file.txt",
        "content": "Attempting to write to protected file",
    },
    "tool_response": {
        "success": False,
        "error": "Permission denied: /etc/protected_file.txt",
    },
}

SAMPLE_NOTIFICATION_WARNING = {
    "hook_event_name": "Notification",
    "session_id": "sess_abc123def456",
    "transcript_path": "/Users/user/.claude/transcript_20240716_143022.json",
    "cwd": "/Users/user/project",
    "message": "Permission required: User needs to approve file modification in /etc/hosts",
}

SAMPLE_NOTIFICATION_INFO = {
    "hook_event_name": "Notification",
    "session_id": "sess_abc123def456",
    "transcript_path": "/Users/user/.claude/transcript_20240716_143022.json",
    "cwd": "/Users/user/project",
    "message": "Auto-formatting applied to /Users/user/project/src/utils.py",
}

SAMPLE_STOP_WITH_HOOK = {
    "hook_event_name": "Stop",
    "session_id": "sess_abc123def456",
    "transcript_path": "/Users/user/.claude/transcript_20240716_143022.json",
    "stop_hook_active": True,
}

SAMPLE_STOP_NO_HOOK = {
    "hook_event_name": "Stop",
    "session_id": "sess_abc123def456",
    "transcript_path": "/Users/user/.claude/transcript_20240716_143022.json",
    "stop_hook_active": False,
}

SAMPLE_SUBAGENT_STOP_WITH_HOOK = {
    "hook_event_name": "SubagentStop",
    "session_id": "sess_abc123def456",
    "transcript_path": "/Users/user/.claude/transcript_20240716_143022.json",
    "stop_hook_active": True,
}

SAMPLE_PRE_COMPACT_MANUAL = {
    "hook_event_name": "PreCompact",
    "session_id": "sess_abc123def456",
    "transcript_path": "/Users/user/.claude/transcript_20240716_143022.json",
    "trigger": "manual",
    "custom_instructions": "Preserve security-related decisions and tool usage patterns",
}

SAMPLE_PRE_COMPACT_AUTO = {
    "hook_event_name": "PreCompact",
    "session_id": "sess_abc123def456",
    "transcript_path": "/Users/user/.claude/transcript_20240716_143022.json",
    "trigger": "auto",
    "custom_instructions": "",
}

SAMPLE_USER_PROMPT_SUBMIT_SIMPLE = {
    "hook_event_name": "UserPromptSubmit",
    "session_id": "sess_abc123def456",
    "transcript_path": "/Users/user/.claude/transcript_20240716_143022.json",
    "cwd": "/Users/user/project",
    "prompt": "Please help me write a Python function",
}

SAMPLE_USER_PROMPT_SUBMIT_COMPLEX = {
    "hook_event_name": "UserPromptSubmit",
    "session_id": "sess_abc123def456",
    "transcript_path": "/Users/user/.claude/transcript_20240716_143022.json",
    "cwd": "/Users/user/project",
    "prompt": "How do I implement authentication in Express.js with JWT tokens?",
}

SAMPLE_USER_PROMPT_SUBMIT_SENSITIVE = {
    "hook_event_name": "UserPromptSubmit",
    "session_id": "sess_abc123def456",
    "transcript_path": "/Users/user/.claude/transcript_20240716_143022.json",
    "cwd": "/Users/user/project",
    "prompt": "My password is secret123 and API key is sk-1234567890abcdef",
}

# Invalid data for testing error handling
INVALID_MISSING_HOOK_EVENT = {
    "session_id": "sess_abc123def456",
    "transcript_path": "/Users/user/.claude/transcript_20240716_143022.json",
}

INVALID_UNKNOWN_HOOK_EVENT = {
    "hook_event_name": "UnknownHook",
    "session_id": "sess_abc123def456",
    "transcript_path": "/Users/user/.claude/transcript_20240716_143022.json",
}

INVALID_PRE_TOOL_USE_MISSING_TOOL_NAME = {
    "hook_event_name": "PreToolUse",
    "session_id": "sess_abc123def456",
    "transcript_path": "/Users/user/.claude/transcript_20240716_143022.json",
    "tool_input": {"file_path": "/tmp/test.txt", "content": "test"},
}

INVALID_PRE_TOOL_USE_MISSING_TOOL_INPUT = {
    "hook_event_name": "PreToolUse",
    "session_id": "sess_abc123def456",
    "transcript_path": "/Users/user/.claude/transcript_20240716_143022.json",
    "tool_name": "Write",
}

INVALID_USER_PROMPT_SUBMIT_MISSING_PROMPT = {
    "hook_event_name": "UserPromptSubmit",
    "session_id": "sess_abc123def456",
    "transcript_path": "/Users/user/.claude/transcript_20240716_143022.json",
    "cwd": "/Users/user/project",
}

INVALID_USER_PROMPT_SUBMIT_MISSING_CWD = {
    "hook_event_name": "UserPromptSubmit",
    "session_id": "sess_abc123def456",
    "transcript_path": "/Users/user/.claude/transcript_20240716_143022.json",
    "prompt": "Test prompt",
}


def get_all_valid_samples():
    """Return all valid sample data for parameterized testing."""
    return [
        ("PreToolUse", SAMPLE_PRE_TOOL_USE_WRITE),
        ("PreToolUse", SAMPLE_PRE_TOOL_USE_BASH),
        ("PostToolUse", SAMPLE_POST_TOOL_USE_SUCCESS),
        ("Notification", SAMPLE_NOTIFICATION_WARNING),
        ("UserPromptSubmit", SAMPLE_USER_PROMPT_SUBMIT_SIMPLE),
        ("UserPromptSubmit", SAMPLE_USER_PROMPT_SUBMIT_COMPLEX),
        ("Stop", SAMPLE_STOP_WITH_HOOK),
        ("SubagentStop", SAMPLE_SUBAGENT_STOP_WITH_HOOK),
        ("PreCompact", SAMPLE_PRE_COMPACT_MANUAL),
    ]


def get_invalid_samples():
    """Return invalid sample data for error testing."""
    return [
        ("missing_hook_event", INVALID_MISSING_HOOK_EVENT),
        ("unknown_hook_event", INVALID_UNKNOWN_HOOK_EVENT),
    ]
