"""PermissionLoggerTemplate for logging tool usage permissions.

This template provides comprehensive logging of all tool usage requests with
detailed information about permissions, tool types, and usage patterns. It supports
PreToolUse events to log requests before tool execution.

Features:
- Comprehensive tool usage logging
- Sensitive operation detection and marking
- Usage statistics and reporting
- Configurable log levels and formats
- Log rotation and archival
- Security audit trail generation
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from ...models.validation import ValidationResult
from ...types.enums import HookEventType
from ..base_template import BaseTemplate, TemplateConfig, template


@template(
    template_id="permission-logger",
    name="Permission Logger",
    description="Comprehensive logging of tool usage requests and permissions"
)
class PermissionLoggerTemplate(BaseTemplate):
    """Template for logging tool usage permissions and requests.

    This template logs all tool usage requests before execution, providing
    an audit trail of permissions, sensitive operations, and usage patterns.
    It's designed for security monitoring and compliance purposes.
    """

    @property
    def name(self) -> str:
        return "Permission Logger"

    @property
    def description(self) -> str:
        return "Comprehensive logging of tool usage requests and permissions"

    @property
    def supported_events(self) -> List[HookEventType]:
        return [HookEventType.PRE_TOOL_USE]

    @property
    def customization_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "log_file": {
                    "type": "string",
                    "default": "~/.claude/logs/permission_log.jsonl",
                    "description": "Path to the permission log file"
                },
                "log_format": {
                    "type": "string",
                    "enum": ["json", "text", "csv"],
                    "default": "json",
                    "description": "Format for log entries"
                },
                "log_level": {
                    "type": "string",
                    "enum": ["debug", "info", "warning", "error"],
                    "default": "info",
                    "description": "Minimum log level to record"
                },
                "sensitive_tools": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": ["Bash", "Write", "Edit", "MultiEdit"],
                    "description": "Tools considered sensitive for special marking"
                },
                "sensitive_patterns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": ["rm ", "sudo ", "chmod ", "password", "secret", "key"],
                    "description": "Patterns in tool arguments that indicate sensitive operations"
                },
                "include_content": {
                    "type": "boolean",
                    "default": False,
                    "description": "Whether to include tool content in logs (security risk)"
                },
                "max_content_length": {
                    "type": "integer",
                    "minimum": 0,
                    "default": 1000,
                    "description": "Maximum length of content to log (0 = unlimited)"
                },
                "enable_statistics": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to maintain usage statistics"
                },
                "stats_file": {
                    "type": "string",
                    "default": "~/.claude/logs/usage_stats.json",
                    "description": "Path to the usage statistics file"
                },
                "log_rotation": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to rotate log files"
                },
                "max_log_size": {
                    "type": "integer",
                    "minimum": 1,
                    "default": 10485760,
                    "description": "Maximum log file size in bytes (10MB default)"
                },
                "backup_count": {
                    "type": "integer",
                    "minimum": 0,
                    "default": 5,
                    "description": "Number of backup log files to keep"
                },
                "alert_on_sensitive": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to generate alerts for sensitive operations"
                },
                "block_sensitive": {
                    "type": "boolean",
                    "default": False,
                    "description": "Whether to block sensitive operations"
                }
            },
            "required": ["log_file", "log_format"]
        }

    def generate(self, config: TemplateConfig) -> str:
        """Generate the permission logger hook script."""
        # Validate event type
        self.validate_event_compatibility(config.event_type)

        # Get configuration
        custom_config = config.customization
        log_file = custom_config.get("log_file", "~/.claude/logs/permission_log.jsonl")
        log_format = custom_config.get("log_format", "json")
        log_level = custom_config.get("log_level", "info")
        sensitive_tools = custom_config.get("sensitive_tools", ["Bash", "Write", "Edit", "MultiEdit"])
        sensitive_patterns = custom_config.get("sensitive_patterns", ["rm ", "sudo ", "chmod ", "password", "secret", "key"])
        include_content = custom_config.get("include_content", False)
        max_content_length = custom_config.get("max_content_length", 1000)
        enable_statistics = custom_config.get("enable_statistics", True)
        stats_file = custom_config.get("stats_file", "~/.claude/logs/usage_stats.json")
        log_rotation = custom_config.get("log_rotation", True)
        max_log_size = custom_config.get("max_log_size", 10485760)
        backup_count = custom_config.get("backup_count", 5)
        alert_on_sensitive = custom_config.get("alert_on_sensitive", True)
        block_sensitive = custom_config.get("block_sensitive", False)

        # Generate script content
        script_header = self.create_script_header(config)

        # Create logger configuration
        logger_config = f'''
# Permission logger configuration
LOG_FILE = "{log_file}"
LOG_FORMAT = "{log_format}"
LOG_LEVEL = "{log_level}"
SENSITIVE_TOOLS = {sensitive_tools!r}
SENSITIVE_PATTERNS = {sensitive_patterns!r}
INCLUDE_CONTENT = {include_content}
MAX_CONTENT_LENGTH = {max_content_length}
ENABLE_STATISTICS = {enable_statistics}
STATS_FILE = "{stats_file}"
LOG_ROTATION = {log_rotation}
MAX_LOG_SIZE = {max_log_size}
BACKUP_COUNT = {backup_count}
ALERT_ON_SENSITIVE = {alert_on_sensitive}
BLOCK_SENSITIVE = {block_sensitive}
'''

        # Create helper functions
        helper_functions = '''
import json
import os
import time
import hashlib
from datetime import datetime
from pathlib import Path


def expand_path(path_str: str) -> Path:
    """Expand user path and create parent directories."""
    path = Path(path_str).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def get_log_level_value(level: str) -> int:
    """Get numeric value for log level."""
    levels = {"debug": 10, "info": 20, "warning": 30, "error": 40}
    return levels.get(level.lower(), 20)


def should_log(entry_level: str) -> bool:
    """Check if entry should be logged based on level."""
    return get_log_level_value(entry_level) >= get_log_level_value(LOG_LEVEL)


def detect_sensitive_operation(tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
    """Detect if operation is sensitive and return analysis."""
    sensitivity = {
        "is_sensitive": False,
        "reasons": [],
        "risk_level": "low",
        "detected_patterns": []
    }

    # Check if tool is inherently sensitive
    if tool_name in SENSITIVE_TOOLS:
        sensitivity["is_sensitive"] = True
        sensitivity["reasons"].append(f"Tool '{tool_name}' is marked as sensitive")
        sensitivity["risk_level"] = "medium"

    # Check for sensitive patterns in arguments
    args_text = json.dumps(tool_args).lower()
    for pattern in SENSITIVE_PATTERNS:
        if pattern.lower() in args_text:
            sensitivity["is_sensitive"] = True
            sensitivity["detected_patterns"].append(pattern)
            sensitivity["reasons"].append(f"Detected sensitive pattern: '{pattern}'")

    # Upgrade risk level based on patterns
    dangerous_patterns = ["rm ", "sudo ", "chmod "]
    if any(pattern.lower() in args_text for pattern in dangerous_patterns):
        sensitivity["risk_level"] = "high"
    elif sensitivity["detected_patterns"]:
        sensitivity["risk_level"] = "medium"

    # Special analysis for specific tools
    if tool_name == "Bash":
        command = tool_args.get("command", "")
        if any(dangerous in command.lower() for dangerous in ["rm -rf", "sudo rm", "format", "dd if="]):
            sensitivity["risk_level"] = "critical"
            sensitivity["reasons"].append("Potentially destructive bash command detected")

    elif tool_name in ["Write", "Edit", "MultiEdit"]:
        file_path = tool_args.get("file_path", "")
        if any(sensitive in file_path.lower() for sensitive in ["/etc/", "passwd", "shadow", ".ssh/"]):
            sensitivity["risk_level"] = "high"
            sensitivity["reasons"].append("Access to sensitive system file")

    return sensitivity


def truncate_content(content: str, max_length: int) -> str:
    """Truncate content to maximum length with indicator."""
    if max_length <= 0 or len(content) <= max_length:
        return content
    return content[:max_length] + f"... [truncated, original length: {len(content)}]"


def create_log_entry(context, sensitivity: Dict[str, Any]) -> Dict[str, Any]:
    """Create structured log entry."""
    tool_use = getattr(context, 'tool_use', {})
    tool_name = tool_use.get('tool_name', 'Unknown')

    entry = {
        "timestamp": datetime.now().isoformat(),
        "session_id": getattr(context, 'session_id', 'unknown'),
        "tool_name": tool_name,
        "user_id": os.getenv('USER', 'unknown'),
        "hostname": os.getenv('HOSTNAME', 'unknown'),
        "pid": os.getpid(),
        "sensitivity": sensitivity,
        "log_level": "warning" if sensitivity["is_sensitive"] else "info"
    }

    # Add tool parameters (with content filtering)
    if tool_use:
        filtered_args = tool_use.copy()

        # Remove or truncate sensitive content
        if not INCLUDE_CONTENT:
            # Remove content fields
            for field in ["content", "new_string", "code", "command"]:
                if field in filtered_args:
                    filtered_args[field] = "[CONTENT REMOVED FOR SECURITY]"
        elif MAX_CONTENT_LENGTH > 0:
            # Truncate content fields
            for field in ["content", "new_string", "code", "command"]:
                if field in filtered_args and isinstance(filtered_args[field], str):
                    filtered_args[field] = truncate_content(filtered_args[field], MAX_CONTENT_LENGTH)

        entry["tool_parameters"] = filtered_args

    # Add execution context
    entry["context"] = {
        "transcript_path": getattr(context, 'transcript_path', ''),
        "hook_event_name": getattr(context, 'hook_event_name', ''),
        "working_directory": os.getcwd()
    }

    return entry


def rotate_log_file(log_path: Path) -> None:
    """Rotate log file if it exceeds maximum size."""
    if not LOG_ROTATION or not log_path.exists():
        return

    if log_path.stat().st_size <= MAX_LOG_SIZE:
        return

    # Create backup files
    for i in range(BACKUP_COUNT - 1, 0, -1):
        old_backup = log_path.with_suffix(f"{log_path.suffix}.{i}")
        new_backup = log_path.with_suffix(f"{log_path.suffix}.{i + 1}")
        if old_backup.exists():
            if new_backup.exists():
                new_backup.unlink()
            old_backup.rename(new_backup)

    # Move current log to .1
    backup_path = log_path.with_suffix(f"{log_path.suffix}.1")
    if backup_path.exists():
        backup_path.unlink()
    log_path.rename(backup_path)


def write_log_entry(entry: Dict[str, Any]) -> None:
    """Write log entry to file."""
    if not should_log(entry["log_level"]):
        return

    log_path = expand_path(LOG_FILE)

    # Rotate log if needed
    rotate_log_file(log_path)

    # Write entry based on format
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            if LOG_FORMAT == "json":
                f.write(json.dumps(entry) + "\\n")
            elif LOG_FORMAT == "csv":
                # Simple CSV format
                timestamp = entry["timestamp"]
                tool_name = entry["tool_name"]
                sensitive = entry["sensitivity"]["is_sensitive"]
                risk_level = entry["sensitivity"]["risk_level"]
                f.write(f'"{timestamp}","{tool_name}",{sensitive},"{risk_level}"\\n')
            else:  # text format
                timestamp = entry["timestamp"]
                tool_name = entry["tool_name"]
                sensitive = " [SENSITIVE]" if entry["sensitivity"]["is_sensitive"] else ""
                f.write(f"{timestamp} - {tool_name}{sensitive}\\n")

    except Exception as e:
        # Fallback: write to stderr if logging fails
        print(f"Permission logger error: {e}", file=sys.stderr)


def update_statistics(tool_name: str, sensitivity: Dict[str, Any]) -> None:
    """Update usage statistics."""
    if not ENABLE_STATISTICS:
        return

    stats_path = expand_path(STATS_FILE)

    # Load existing statistics
    stats = {"total_requests": 0, "sensitive_requests": 0, "tools": {}, "risk_levels": {}}
    if stats_path.exists():
        try:
            with open(stats_path, "r", encoding="utf-8") as f:
                stats = json.load(f)
        except Exception:
            pass  # Use default stats if loading fails

    # Update statistics
    stats["total_requests"] = stats.get("total_requests", 0) + 1
    if sensitivity["is_sensitive"]:
        stats["sensitive_requests"] = stats.get("sensitive_requests", 0) + 1

    # Tool statistics
    if "tools" not in stats:
        stats["tools"] = {}
    if tool_name not in stats["tools"]:
        stats["tools"][tool_name] = {"count": 0, "sensitive_count": 0}

    stats["tools"][tool_name]["count"] += 1
    if sensitivity["is_sensitive"]:
        stats["tools"][tool_name]["sensitive_count"] += 1

    # Risk level statistics
    if "risk_levels" not in stats:
        stats["risk_levels"] = {}
    risk_level = sensitivity["risk_level"]
    stats["risk_levels"][risk_level] = stats["risk_levels"].get(risk_level, 0) + 1

    # Add timestamp
    stats["last_updated"] = datetime.now().isoformat()

    # Save statistics
    try:
        with open(stats_path, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2)
    except Exception:
        pass  # Ignore statistics save errors


def generate_alert(sensitivity: Dict[str, Any], tool_name: str) -> str:
    """Generate alert message for sensitive operations."""
    if not sensitivity["is_sensitive"]:
        return ""

    risk_level = sensitivity["risk_level"]
    reasons = "; ".join(sensitivity["reasons"])

    alert = f"SECURITY ALERT: {risk_level.upper()} risk operation detected\\n"
    alert += f"Tool: {tool_name}\\n"
    alert += f"Reasons: {reasons}\\n"
    alert += f"Timestamp: {datetime.now().isoformat()}\\n"

    if sensitivity["detected_patterns"]:
        alert += f"Patterns: {', '.join(sensitivity['detected_patterns'])}\\n"

    return alert
'''

        # Create main logic
        main_logic = f'''
        # Analyze the tool usage request
        tool_use = getattr(context, 'tool_use', {{}})
        tool_name = tool_use.get('tool_name', 'Unknown')

        # Detect sensitive operations
        sensitivity = detect_sensitive_operation(tool_name, tool_use)

        # Create and write log entry
        log_entry = create_log_entry(context, sensitivity)
        write_log_entry(log_entry)

        # Update statistics
        update_statistics(tool_name, sensitivity)

        # Handle sensitive operations
        if sensitivity["is_sensitive"]:
            alert_message = ""

            if ALERT_ON_SENSITIVE:
                alert_message = generate_alert(sensitivity, tool_name)

            if BLOCK_SENSITIVE:
                message = f"BLOCKED: Sensitive operation detected ({sensitivity['risk_level']} risk)"
                if alert_message:
                    message += f"\\n\\n{alert_message}"
                context.output.deny(message)
                return

            # Allow but warn
            message = f"CAUTION: {sensitivity['risk_level'].upper()} risk operation logged"
            if alert_message:
                message += f"\\n\\n{alert_message}"
            context.output.ask(message)
        else:
            # Log normal operation and allow
            context.output.allow(f"Tool usage logged: {tool_name}")
'''

        # Combine all parts
        return script_header + logger_config + helper_functions + self.create_main_function(
            config.event_type, main_logic
        )

    def validate_config(self, config: Dict[str, Any]) -> ValidationResult:
        """Validate the permission logger configuration."""
        result = self.validate_schema(config, self.customization_schema)

        # Additional validation for file paths
        log_file = config.get("log_file", "")
        if log_file:
            try:
                expanded_path = Path(log_file).expanduser()
                if not expanded_path.parent.exists():
                    result.add_warning(
                        field_name="log_file",
                        warning_code="DIRECTORY_MISSING",
                        message=f"Log directory {expanded_path.parent} does not exist (will be created)"
                    )
            except Exception:
                result.add_error(
                    field_name="log_file",
                    error_code="INVALID_PATH",
                    message="Invalid log file path",
                    suggested_fix="Use a valid file path"
                )

        # Validate content inclusion security
        if config.get("include_content", False):
            result.add_warning(
                field_name="include_content",
                warning_code="SECURITY_RISK",
                message="Including content in logs may expose sensitive information"
            )

        return result

    def get_default_config(self) -> Dict[str, Any]:
        """Get default configuration for permission logger."""
        return {
            "log_file": "~/.claude/logs/permission_log.jsonl",
            "log_format": "json",
            "log_level": "info",
            "sensitive_tools": ["Bash", "Write", "Edit", "MultiEdit"],
            "sensitive_patterns": ["rm ", "sudo ", "chmod ", "password", "secret", "key"],
            "include_content": False,
            "max_content_length": 1000,
            "enable_statistics": True,
            "stats_file": "~/.claude/logs/usage_stats.json",
            "log_rotation": True,
            "max_log_size": 10485760,
            "backup_count": 5,
            "alert_on_sensitive": True,
            "block_sensitive": False
        }

    def get_dependencies(self) -> List[str]:
        """Get dependencies for permission logger template."""
        return []  # Uses only Python standard library
