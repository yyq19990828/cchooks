"""SecurityGuardTemplate for generating security validation hook scripts.

This template creates Python hook scripts that monitor and protect against
dangerous operations across multiple tools. It's designed for PreToolUse events
to block potentially harmful commands before they execute.

The security guard provides:
- Dangerous command pattern detection
- System directory protection
- Network operation monitoring
- File system operation validation
- Configurable blocking and warning policies

Template Features:
- Multi-tool support (Bash, Write, Edit, etc.)
- Customizable danger patterns and protected paths
- Allow-list for exceptions
- Comprehensive logging
- Warning-only or blocking modes
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from ...models.validation import ValidationResult
from ...types.enums import HookEventType
from ..base_template import BaseTemplate, TemplateConfig, template


@template(
    template_id="security-guard",
    name="Security Guard",
    description="Multi-tool security protection with configurable danger detection",
    supported_events=[HookEventType.PRE_TOOL_USE]
)
class SecurityGuardTemplate(BaseTemplate):
    """Template for generating security guard hook scripts.

    This template creates comprehensive security validation scripts that can
    monitor tool usage and block or warn about potentially dangerous operations.
    It supports customizable danger patterns, protected paths, and flexible
    warning/blocking policies.
    """

    @property
    def name(self) -> str:
        """Human-readable name of the template."""
        return "Security Guard"

    @property
    def description(self) -> str:
        """Description of what this template does."""
        return (
            "Multi-tool security protection that monitors and validates tool usage, "
            "blocking dangerous commands, protecting system directories, and logging "
            "security events with configurable policies."
        )

    @property
    def supported_events(self) -> List[HookEventType]:
        """List of hook event types this template supports."""
        return [HookEventType.PRE_TOOL_USE]

    @property
    def customization_schema(self) -> Dict[str, Any]:
        """JSON schema for validating customization options."""
        return {
            "type": "object",
            "properties": {
                "blocked_patterns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of regex patterns for dangerous commands",
                    "default": []
                },
                "protected_paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of protected file/directory paths",
                    "default": []
                },
                "allow_list": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of commands/patterns that bypass security checks",
                    "default": []
                },
                "warning_only": {
                    "type": "boolean",
                    "description": "If true, only warn about dangers but don't block",
                    "default": False
                },
                "log_file": {
                    "type": "string",
                    "description": "Path to security log file",
                    "default": ""
                },
                "monitored_tools": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of tool names to monitor (empty = all tools)",
                    "default": []
                },
                "block_network": {
                    "type": "boolean",
                    "description": "Block network operations like curl, wget",
                    "default": True
                },
                "block_system_changes": {
                    "type": "boolean",
                    "description": "Block system-level changes (users, permissions, etc.)",
                    "default": True
                },
                "severity_threshold": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "critical"],
                    "description": "Minimum severity level to trigger action",
                    "default": "medium"
                }
            },
            "additionalProperties": False
        }

    def get_default_config(self) -> Dict[str, Any]:
        """Get default customization configuration for this template."""
        return {
            "blocked_patterns": [
                r"rm\s+-rf\s+/",  # Dangerous recursive delete
                r"sudo\s+rm\s+-rf",  # Sudo dangerous delete
                r"chmod\s+777",  # Overpermissive permissions
                r"mkfs\.",  # Format filesystem
                r"dd\s+.*of=/dev/",  # Direct device writes
                r">/dev/sd[a-z]",  # Write to disk devices
                r"fdisk|parted",  # Disk partitioning
                r"userdel|usermod.*-G.*root",  # User management
                r"passwd.*root",  # Root password changes
                r"chown.*root:",  # Change ownership to root
                r"systemctl.*stop.*ssh",  # Stop SSH service
                r"iptables.*-F",  # Flush firewall rules
            ],
            "protected_paths": [
                "/",
                "/boot",
                "/etc",
                "/usr",
                "/var",
                "/sys",
                "/proc",
                "/dev",
                "/home",
                "~/.ssh",
                "~/.aws",
                "~/.docker",
            ],
            "allow_list": [
                r"ls\s+",  # Safe listing commands
                r"cat\s+.*\.txt",  # Reading text files
                r"echo\s+",  # Safe echo commands
                r"mkdir\s+.*tmp",  # Creating temp directories
            ],
            "warning_only": False,
            "log_file": "~/.claude/security.log",
            "monitored_tools": [],  # Monitor all tools by default
            "block_network": True,
            "block_system_changes": True,
            "severity_threshold": "medium"
        }

    def get_dependencies(self) -> List[str]:
        """Get list of dependencies required by this template."""
        return ["re", "pathlib", "json", "datetime"]  # All standard library

    def validate_config(self, config: Dict[str, Any]) -> ValidationResult:
        """Validate template-specific customization configuration."""
        result = self.validate_schema(config, self.customization_schema)

        # Additional validation for regex patterns
        blocked_patterns = config.get("blocked_patterns", [])
        for pattern in blocked_patterns:
            try:
                re.compile(pattern)
            except re.error as e:
                result.add_error(
                    field_name="blocked_patterns",
                    error_code="INVALID_REGEX",
                    message=f"Invalid regex pattern '{pattern}': {str(e)}",
                    suggested_fix="Fix the regex pattern syntax"
                )

        # Validate allow_list patterns
        allow_list = config.get("allow_list", [])
        for pattern in allow_list:
            try:
                re.compile(pattern)
            except re.error as e:
                result.add_error(
                    field_name="allow_list",
                    error_code="INVALID_REGEX",
                    message=f"Invalid regex pattern '{pattern}': {str(e)}",
                    suggested_fix="Fix the regex pattern syntax"
                )

        # Validate log file path if provided
        log_file = config.get("log_file", "")
        if log_file:
            try:
                Path(log_file).expanduser().parent
            except Exception as e:
                result.add_warning(
                    field_name="log_file",
                    warning_code="INVALID_LOG_PATH",
                    message=f"Log file path may be invalid: {str(e)}"
                )

        return result

    def generate(self, config: TemplateConfig) -> str:
        """Generate hook script content from configuration."""
        # Validate event type compatibility
        self.validate_event_compatibility(config.event_type)

        # Get merged configuration
        default_config = self.get_default_config()
        custom_config = config.customization
        merged_config = {**default_config, **custom_config}

        # Generate script content
        header = self.create_script_header(config)
        imports = self._generate_imports()
        config_section = self._generate_config_section(merged_config)
        security_functions = self._generate_security_functions()
        main_logic = self._generate_main_logic(config.event_type, merged_config)
        main_function_logic = self._generate_main_function_logic(config.event_type)
        main_function = self.create_main_function(config.event_type, main_function_logic)

        return f"""{header}
{imports}

{config_section}

{security_functions}

{main_logic}

{main_function}
"""

    def _generate_imports(self) -> str:
        """Generate import statements for the security guard script."""
        return """
import datetime
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Import cchooks context types
from cchooks import PreToolUseContext
"""

    def _generate_config_section(self, config: Dict[str, Any]) -> str:
        """Generate configuration section with user settings."""
        # Convert config to Python dict representation
        config_repr = self._dict_to_python_repr(config)

        return f"""
# Security Guard Configuration
SECURITY_CONFIG = {config_repr}

# Severity levels mapping
SEVERITY_LEVELS = {{
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4
}}

# Built-in network operation patterns
NETWORK_PATTERNS = [
    r"curl\\s+",
    r"wget\\s+",
    r"nc\\s+.*-l",  # netcat listen
    r"python.*-m\\s+http\\.server",
    r"python.*SimpleHTTPServer",
    r"ssh\\s+.*@",
    r"scp\\s+",
    r"rsync\\s+.*:",
    r"git\\s+.*https?://",
    r"pip\\s+install.*-i\\s+http",
]

# Built-in system change patterns
SYSTEM_CHANGE_PATTERNS = [
    r"sudo\\s+",
    r"su\\s+",
    r"passwd\\s+",
    r"adduser\\s+",
    r"useradd\\s+",
    r"usermod\\s+",
    r"userdel\\s+",
    r"groupadd\\s+",
    r"groupdel\\s+",
    r"crontab\\s+-e",
    r"systemctl\\s+",
    r"service\\s+.*start|stop|restart",
    r"mount\\s+",
    r"umount\\s+",
]
"""

    def _generate_security_functions(self) -> str:
        """Generate security validation helper functions."""
        return '''
def log_security_event(event_type: str, tool_name: str, details: str, severity: str = "medium") -> None:
    """Log security event to file if logging is enabled."""
    log_file = SECURITY_CONFIG.get("log_file", "")
    if not log_file:
        return

    try:
        log_path = Path(log_file).expanduser()
        log_path.parent.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.datetime.now().isoformat()
        log_entry = f"[{timestamp}] {severity.upper()} - {event_type} - {tool_name}: {details}\\n"

        with open(log_path, "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception:
        # Don't fail the hook if logging fails
        pass


def check_allow_list(command: str) -> bool:
    """Check if command matches any allow-list pattern."""
    allow_list = SECURITY_CONFIG.get("allow_list", [])
    for pattern in allow_list:
        try:
            if re.search(pattern, command, re.IGNORECASE):
                return True
        except re.error:
            continue
    return False


def check_blocked_patterns(command: str) -> Tuple[bool, str, str]:
    """Check if command matches blocked patterns.

    Returns:
        (is_blocked, pattern_matched, severity)
    """
    blocked_patterns = SECURITY_CONFIG.get("blocked_patterns", [])

    for pattern in blocked_patterns:
        try:
            if re.search(pattern, command, re.IGNORECASE):
                return True, pattern, "high"
        except re.error:
            continue

    return False, "", "low"


def check_network_operations(command: str) -> Tuple[bool, str]:
    """Check for potentially dangerous network operations."""
    if not SECURITY_CONFIG.get("block_network", True):
        return False, ""

    for pattern in NETWORK_PATTERNS:
        try:
            if re.search(pattern, command, re.IGNORECASE):
                return True, f"Network operation detected: {pattern}"
        except re.error:
            continue

    return False, ""


def check_system_changes(command: str) -> Tuple[bool, str]:
    """Check for system-level changes."""
    if not SECURITY_CONFIG.get("block_system_changes", True):
        return False, ""

    for pattern in SYSTEM_CHANGE_PATTERNS:
        try:
            if re.search(pattern, command, re.IGNORECASE):
                return True, f"System change detected: {pattern}"
        except re.error:
            continue

    return False, ""


def check_protected_paths(tool_input: Dict[str, Any]) -> Tuple[bool, str]:
    """Check if operation affects protected paths."""
    protected_paths = SECURITY_CONFIG.get("protected_paths", [])

    # Check different ways paths might be specified
    path_fields = ["file_path", "path", "directory", "target", "destination"]

    for field in path_fields:
        if field in tool_input:
            target_path = str(tool_input[field])
            target_path = Path(target_path).expanduser().resolve()

            for protected in protected_paths:
                try:
                    protected_path = Path(protected).expanduser().resolve()
                    if target_path == protected_path or protected_path in target_path.parents:
                        return True, f"Protected path access: {target_path}"
                except Exception:
                    continue

    return False, ""


def should_monitor_tool(tool_name: str) -> bool:
    """Check if tool should be monitored."""
    monitored_tools = SECURITY_CONFIG.get("monitored_tools", [])

    # Empty list means monitor all tools
    if not monitored_tools:
        return True

    return tool_name in monitored_tools


def meets_severity_threshold(severity: str) -> bool:
    """Check if severity meets the configured threshold."""
    threshold = SECURITY_CONFIG.get("severity_threshold", "medium")
    threshold_level = SEVERITY_LEVELS.get(threshold, 2)
    severity_level = SEVERITY_LEVELS.get(severity, 1)

    return severity_level >= threshold_level


def validate_tool_security(context: PreToolUseContext) -> Tuple[bool, str, str]:
    """Main security validation function.

    Returns:
        (should_block, reason, severity)
    """
    tool_name = context.tool_name
    tool_input = context.tool_input

    # Skip monitoring if tool not in monitored list
    if not should_monitor_tool(tool_name):
        return False, "", "low"

    # Extract command for analysis
    command = ""
    if tool_name == "Bash":
        command = tool_input.get("command", "")
    elif tool_name in ["Write", "Edit"]:
        # For file operations, analyze the file path and content
        file_path = tool_input.get("file_path", "")
        content = tool_input.get("content", "") or tool_input.get("new_string", "")
        command = f"{tool_name.lower()} {file_path} {content}"
    elif tool_name == "MultiEdit":
        # Check all edit operations
        edits = tool_input.get("edits", [])
        for edit in edits:
            content = edit.get("new_string", "")
            if content:
                command += f" {content}"
    else:
        # For other tools, convert tool_input to string for pattern matching
        command = str(tool_input)

    # Check allow-list first (highest priority)
    if check_allow_list(command):
        return False, "Allowed by allow-list", "low"

    # Check blocked patterns
    is_blocked, pattern, severity = check_blocked_patterns(command)
    if is_blocked and meets_severity_threshold(severity):
        reason = f"Matches blocked pattern: {pattern}"
        log_security_event("BLOCKED_PATTERN", tool_name, f"{reason} - Command: {command}", severity)
        return True, reason, severity

    # Check network operations
    is_network, reason = check_network_operations(command)
    if is_network and meets_severity_threshold("medium"):
        log_security_event("NETWORK_BLOCK", tool_name, f"{reason} - Command: {command}", "medium")
        return True, reason, "medium"

    # Check system changes
    is_system, reason = check_system_changes(command)
    if is_system and meets_severity_threshold("high"):
        log_security_event("SYSTEM_BLOCK", tool_name, f"{reason} - Command: {command}", "high")
        return True, reason, "high"

    # Check protected paths
    is_protected, reason = check_protected_paths(tool_input)
    if is_protected and meets_severity_threshold("high"):
        log_security_event("PROTECTED_PATH", tool_name, f"{reason}", "high")
        return True, reason, "high"

    # Log safe operations for audit trail
    log_security_event("ALLOWED", tool_name, f"Safe operation - Command: {command}", "low")
    return False, "", "low"
'''

    def _generate_main_logic(self, event_type: HookEventType, config: Dict[str, Any]) -> str:
        """Generate main hook logic."""
        warning_only = config.get("warning_only", False)

        if warning_only:
            action_logic = '''# Warning-only mode: log but don't block
if should_block:
    log_security_event("WARNING", context.tool_name, f"Security warning: {reason}", severity)
    context.output.ask(
        reason=f"Security Warning: {reason}. Continue?",
        system_message=f"Security guard detected potential risk: {reason}"
    )
else:
    context.output.allow(reason="Security validation passed")'''
        else:
            action_logic = '''# Blocking mode: actually block dangerous operations
if should_block:
    context.output.deny(
        reason=f"Security Guard: {reason}",
        system_message=f"Operation blocked by security guard: {reason}"
    )
else:
    context.output.allow(reason="Security validation passed")'''

        return f'''
def handle_security_validation(context: PreToolUseContext) -> None:
    """Handle security validation for PreToolUse events."""
    try:
        # Perform security validation
        should_block, reason, severity = validate_tool_security(context)

{self._indent_code(action_logic, 8)}

    except Exception as e:
        # If security check fails, err on the side of caution
        log_security_event("ERROR", context.tool_name, f"Security check failed: {{str(e)}}", "critical")
        context.output.deny(
            reason="Security validation failed",
            system_message=f"Security guard encountered an error: {{str(e)}}"
        )
'''

    def _dict_to_python_repr(self, obj: Any, parent_key: str = "") -> str:
        """Convert dictionary to valid Python representation."""
        if isinstance(obj, dict):
            items = []
            for key, value in obj.items():
                key_repr = repr(key)
                value_repr = self._dict_to_python_repr(value, key)
                items.append(f"{key_repr}: {value_repr}")
            return "{" + ", ".join(items) + "}"
        elif isinstance(obj, list):
            items = []
            for item in obj:
                if parent_key in ["blocked_patterns", "allow_list", "protected_paths"]:
                    # These should be raw strings to preserve regex patterns
                    if isinstance(item, str):
                        items.append(f"r'{item}'")
                    else:
                        items.append(self._dict_to_python_repr(item, parent_key))
                else:
                    items.append(self._dict_to_python_repr(item, parent_key))
            return "[" + ", ".join(items) + "]"
        elif isinstance(obj, str):
            # Use raw strings only for regex patterns and paths
            if parent_key in ["blocked_patterns", "allow_list", "protected_paths", "log_file"]:
                return f"r'{obj}'"
            else:
                return repr(obj)
        else:
            return repr(obj)

    def _generate_main_function_logic(self, event_type: HookEventType) -> str:
        """Generate the main function logic specific to the event type."""
        return """# Cast to specific context type for type safety
if not isinstance(context, PreToolUseContext):
    context.output.exit_non_block("Invalid context type for security guard")
    return

# Run security validation
handle_security_validation(context)"""
