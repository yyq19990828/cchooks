"""AutoFormatterTemplate for automatic code formatting.

This template generates hook scripts that automatically format code files after
they are written or modified by Claude Code tools. It supports multiple Python
formatters with configurable priority and options.

The template is designed for PostToolUse events and detects file operations
(Write, Edit, MultiEdit, etc.) to automatically format Python files according
to configured formatters and settings.

Supported formatters:
- black: The uncompromising Python code formatter
- isort: Python import sorting utility
- autopep8: PEP 8 compliance formatter
- ruff: Modern Python linter and formatter

Features:
- Multi-formatter support with priority ordering
- Configurable file patterns and exclusions
- Smart file type detection
- Backup creation before formatting
- Check-only mode for validation
- Detailed formatting reports
- Error handling and rollback
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

from ...models.validation import ValidationResult
from ...types.enums import HookEventType
from ..base_template import BaseTemplate, TemplateConfig, template


@template(
    template_id="auto-formatter",
    name="Auto Formatter",
    description="Automatically formats Python files after tool operations",
    supported_events=[HookEventType.POST_TOOL_USE]
)
class AutoFormatterTemplate(BaseTemplate):
    """Template for automatic code formatting after file operations.

    This template creates hook scripts that monitor PostToolUse events and
    automatically format Python files when they are created or modified by
    Claude Code tools like Write, Edit, MultiEdit, etc.

    The generated scripts:
    1. Detect file operations from tool_name and tool_input
    2. Extract file paths from tool_input
    3. Check file extensions against configured patterns
    4. Run formatters in priority order
    5. Report formatting results and any errors
    6. Handle backups and rollback on failures
    """

    @property
    def name(self) -> str:
        """Human-readable name of the template."""
        return "Auto Formatter"

    @property
    def description(self) -> str:
        """Description of what this template does."""
        return "Automatically formats Python files after tool operations"

    @property
    def supported_events(self) -> List[HookEventType]:
        """List of hook event types this template supports."""
        return [HookEventType.POST_TOOL_USE]

    @property
    def customization_schema(self) -> Dict[str, Any]:
        """JSON schema for validating customization options."""
        return {
            "type": "object",
            "properties": {
                "formatters": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["black", "isort", "autopep8", "ruff"]
                    },
                    "minItems": 1,
                    "description": "List of formatters to run in order"
                },
                "max_line_length": {
                    "type": "integer",
                    "minimum": 50,
                    "maximum": 200,
                    "description": "Maximum line length for formatting"
                },
                "file_patterns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "File patterns to format (e.g., '*.py')"
                },
                "exclude_patterns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "File patterns to exclude from formatting"
                },
                "check_only": {
                    "type": "boolean",
                    "description": "Only check formatting without modifying files"
                },
                "create_backup": {
                    "type": "boolean",
                    "description": "Create backup files before formatting"
                },
                "tool_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tool names to monitor (Write, Edit, etc.)"
                },
                "timeout": {
                    "type": "integer",
                    "minimum": 5,
                    "maximum": 300,
                    "description": "Timeout in seconds for each formatter"
                }
            },
            "required": ["formatters"],
            "additionalProperties": False
        }

    def generate(self, config: TemplateConfig) -> str:
        """Generate hook script content from configuration."""
        # Validate event type
        self.validate_event_compatibility(config.event_type)

        # Get configuration with defaults
        customization = {**self.get_default_config(), **config.customization}

        # Create script header
        header = self.create_script_header(config)

        # Generate formatter-specific logic
        formatter_logic = self._generate_formatter_logic(customization)

        # Create main function
        main_function = self.create_main_function(
            config.event_type,
            formatter_logic
        )

        # Generate the complete main function logic with formatter integration
        main_logic = self._generate_main_logic(customization)

        return header + formatter_logic + main_logic

    def validate_config(self, config: Dict[str, Any]) -> ValidationResult:
        """Validate template-specific customization configuration."""
        result = self.validate_schema(config, self.customization_schema)

        # Additional validation for formatters
        formatters = config.get("formatters", [])
        if formatters:
            # Check for duplicate formatters
            if len(formatters) != len(set(formatters)):
                result.add_error(
                    field_name="formatters",
                    error_code="DUPLICATE_FORMATTERS",
                    message="Duplicate formatters specified",
                    suggested_fix="Remove duplicate entries from formatters list"
                )

            # Warn about formatter availability
            for formatter in formatters:
                if formatter not in ["black", "isort", "autopep8", "ruff"]:
                    result.add_error(
                        field_name="formatters",
                        error_code="UNSUPPORTED_FORMATTER",
                        message=f"Unsupported formatter: {formatter}",
                        suggested_fix="Use one of: black, isort, autopep8, ruff"
                    )

        # Validate file patterns
        file_patterns = config.get("file_patterns", [])
        if file_patterns:
            for pattern in file_patterns:
                if not isinstance(pattern, str) or not pattern.strip():
                    result.add_error(
                        field_name="file_patterns",
                        error_code="INVALID_PATTERN",
                        message=f"Invalid file pattern: {pattern}",
                        suggested_fix="Use valid glob patterns like '*.py'"
                    )

        # Validate exclude patterns
        exclude_patterns = config.get("exclude_patterns", [])
        if exclude_patterns:
            for pattern in exclude_patterns:
                if not isinstance(pattern, str) or not pattern.strip():
                    result.add_error(
                        field_name="exclude_patterns",
                        error_code="INVALID_EXCLUDE_PATTERN",
                        message=f"Invalid exclude pattern: {pattern}",
                        suggested_fix="Use valid glob patterns"
                    )

        # Add suggestions
        if not result.has_errors():
            result.add_suggestion("Consider using 'black' formatter for consistent style")
            result.add_suggestion("Use 'isort' with 'black' for complete formatting")
            if config.get("max_line_length", 88) != 88:
                result.add_suggestion("Line length 88 is recommended for black formatter")

        return result

    def get_default_config(self) -> Dict[str, Any]:
        """Get default customization configuration for this template."""
        return {
            "formatters": ["black", "isort"],
            "max_line_length": 88,
            "file_patterns": ["*.py"],
            "exclude_patterns": ["*_pb2.py", "*/migrations/*", "*/.venv/*"],
            "check_only": False,
            "create_backup": True,
            "tool_names": ["Write", "Edit", "MultiEdit", "NotebookEdit"],
            "timeout": 30
        }

    def get_dependencies(self) -> List[str]:
        """Get list of dependencies required by this template."""
        return ["subprocess", "pathlib", "fnmatch", "json"]

    def _generate_main_logic(self, customization: Dict[str, Any]) -> str:
        """Generate the main function logic for the auto-formatter script."""
        return '''

def main() -> None:
    """Main hook entry point."""
    try:
        # Create context from stdin
        context = create_context()

        # Validate event type
        if not isinstance(context, PostToolUseContext):
            context.output.fail(
                f"Expected PostToolUse event, got {context.hook_event_name}"
            )
            return

        # Run auto-formatting
        format_and_report(context)

    except Exception as e:
        # Handle unexpected errors
        print(json.dumps({
            "continue": False,
            "stopReason": f"Auto-formatter error: {str(e)}",
            "suppressOutput": False
        }))
        sys.exit(1)


if __name__ == "__main__":
    main()
'''

    def _generate_formatter_logic(self, customization: Dict[str, Any]) -> str:
        """Generate formatter-specific logic for the script."""
        # Use simple string replacement instead of f-strings to avoid brace issues
        template = '''
import fnmatch
import shutil
import subprocess
import time
from pathlib import Path
from typing import List, Dict, Tuple, Optional


def check_formatter_available(formatter: str) -> bool:
    """Check if a formatter is available in the system."""
    try:
        result = subprocess.run([formatter, "--version"],
                              capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError):
        return False


def should_format_file(file_path: Path, patterns: List[str], exclude_patterns: List[str]) -> bool:
    """Check if file should be formatted based on patterns."""
    file_str = str(file_path)

    # Check exclude patterns first
    for exclude_pattern in exclude_patterns:
        if fnmatch.fnmatch(file_str, exclude_pattern):
            return False

    # Check include patterns
    for pattern in patterns:
        if fnmatch.fnmatch(file_str, pattern):
            return True

    return False


def create_backup(file_path: Path) -> Optional[Path]:
    """Create backup of file before formatting."""
    if not file_path.exists():
        return None

    backup_path = file_path.with_suffix(file_path.suffix + ".backup")
    counter = 1
    while backup_path.exists():
        backup_path = file_path.with_suffix(f"{file_path.suffix}.backup.{counter}")
        counter += 1

    try:
        shutil.copy2(file_path, backup_path)
        return backup_path
    except Exception as e:
        print(f"Warning: Could not create backup for {file_path}: {e}")
        return None


def run_formatter(formatter: str, file_path: Path, check_only: bool, max_line_length: int, timeout: int) -> Tuple[bool, str, str]:
    """Run a specific formatter on a file."""
    if not check_formatter_available(formatter):
        return False, "", f"Formatter '{formatter}' is not available"

    # Build formatter command
    if formatter == "black":
        cmd = ["black", "--line-length", str(max_line_length)]
        if check_only:
            cmd.append("--check")
        cmd.append(str(file_path))

    elif formatter == "isort":
        cmd = ["isort", "--profile", "black", "--line-length", str(max_line_length)]
        if check_only:
            cmd.append("--check-only")
        cmd.append(str(file_path))

    elif formatter == "autopep8":
        cmd = ["autopep8", "--max-line-length", str(max_line_length)]
        if not check_only:
            cmd.append("--in-place")
        cmd.append(str(file_path))

    elif formatter == "ruff":
        if check_only:
            cmd = ["ruff", "check", str(file_path)]
        else:
            cmd = ["ruff", "check", "--fix", str(file_path)]

    else:
        return False, "", f"Unknown formatter: {formatter}"

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        success = result.returncode == 0
        return success, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", f"Formatter '{formatter}' timed out after {timeout} seconds"
    except Exception as e:
        return False, "", f"Error running {formatter}: {str(e)}"


def extract_file_paths(tool_name: str, tool_input: Dict[str, Any]) -> List[Path]:
    """Extract file paths from tool input based on tool name."""
    file_paths = []

    if tool_name in ["Write", "Edit", "MultiEdit"]:
        if "file_path" in tool_input:
            file_paths.append(Path(tool_input["file_path"]))

    elif tool_name == "NotebookEdit":
        if "notebook_path" in tool_input:
            file_paths.append(Path(tool_input["notebook_path"]))

    elif tool_name == "MultiEdit" and "edits" in tool_input:
        # MultiEdit might have multiple file edits
        seen_files = set()
        for edit in tool_input.get("edits", []):
            if isinstance(edit, dict) and "file_path" in edit:
                file_path = Path(edit["file_path"])
                if file_path not in seen_files:
                    file_paths.append(file_path)
                    seen_files.add(file_path)

    return file_paths


def format_files(context, file_paths: List[Path]) -> Dict[str, Any]:
    """Format multiple files and return results."""
    formatters = FORMATTERS_PLACEHOLDER
    max_line_length = MAX_LINE_LENGTH_PLACEHOLDER
    file_patterns = FILE_PATTERNS_PLACEHOLDER
    exclude_patterns = EXCLUDE_PATTERNS_PLACEHOLDER
    check_only = CHECK_ONLY_PLACEHOLDER
    create_backup_flag = CREATE_BACKUP_PLACEHOLDER
    timeout = TIMEOUT_PLACEHOLDER

    results = {
        "formatted_files": [],
        "skipped_files": [],
        "errors": [],
        "warnings": []
    }

    for file_path in file_paths:
        if not file_path.exists():
            results["warnings"].append(f"File does not exist: {file_path}")
            continue

        if not should_format_file(file_path, file_patterns, exclude_patterns):
            results["skipped_files"].append({
                "path": str(file_path),
                "reason": "Pattern mismatch"
            })
            continue

        file_result = {
            "path": str(file_path),
            "formatters_run": [],
            "backup_path": None,
            "success": True,
            "errors": []
        }

        # Create backup if requested
        backup_path = None
        if create_backup_flag and not check_only:
            backup_path = create_backup(file_path)
            if backup_path:
                file_result["backup_path"] = str(backup_path)

        # Run formatters in order
        for formatter in formatters:
            success, stdout, stderr = run_formatter(
                formatter, file_path, check_only, max_line_length, timeout
            )

            formatter_result = {
                "formatter": formatter,
                "success": success,
                "stdout": stdout.strip() if stdout else "",
                "stderr": stderr.strip() if stderr else ""
            }

            file_result["formatters_run"].append(formatter_result)

            if not success:
                file_result["success"] = False
                file_result["errors"].append(f"{formatter}: {stderr or 'Unknown error'}")

                # If backup was created and formatting failed, consider restoring
                if backup_path and backup_path.exists():
                    results["warnings"].append(
                        f"Formatting failed for {file_path}. Backup available at {backup_path}"
                    )

        if file_result["success"]:
            results["formatted_files"].append(file_result)
        else:
            results["errors"].append(file_result)

    return results


def format_and_report(context: PostToolUseContext) -> None:
    """Main formatting logic with reporting."""
    tool_names = TOOL_NAMES_PLACEHOLDER

    # Check if this tool operation should trigger formatting
    if context.tool_name not in tool_names:
        context.output.continue_flow(f"Skipping formatting - tool {context.tool_name} not in monitored tools")
        return

    # Extract file paths from tool input
    file_paths = extract_file_paths(context.tool_name, context.tool_input)

    if not file_paths:
        context.output.continue_flow("No files to format")
        return

    # Format the files
    try:
        results = format_files(context, file_paths)

        # Generate report
        report = generate_formatting_report(results)

        # Report results
        if results["errors"]:
            context.output.append_message(f"Formatting completed with errors:\\n{report}")
        else:
            context.output.append_message(f"Formatting completed successfully:\\n{report}")

        context.output.continue_flow("Auto-formatting completed")

    except Exception as e:
        context.output.exit_error(f"Auto-formatting failed: {str(e)}")


def generate_formatting_report(results: Dict[str, Any]) -> str:
    """Generate a human-readable formatting report."""
    lines = []

    # Summary
    total_files = len(results["formatted_files"]) + len(results["skipped_files"]) + len(results["errors"])
    lines.append(f"Auto-Formatter Report")
    lines.append(f"==================")
    lines.append(f"Total files processed: {total_files}")
    lines.append(f"Successfully formatted: {len(results['formatted_files'])}")
    lines.append(f"Skipped: {len(results['skipped_files'])}")
    lines.append(f"Errors: {len(results['errors'])}")
    lines.append("")

    # Formatted files details
    if results["formatted_files"]:
        lines.append("✅ Successfully formatted files:")
        for file_result in results["formatted_files"]:
            lines.append(f"  - {file_result['path']}")
            for formatter_result in file_result["formatters_run"]:
                status = "✅" if formatter_result["success"] else "❌"
                lines.append(f"    {status} {formatter_result['formatter']}")
            if file_result.get("backup_path"):
                lines.append(f"    💾 Backup: {file_result['backup_path']}")
        lines.append("")

    # Skipped files
    if results["skipped_files"]:
        lines.append("⏭️  Skipped files:")
        for skipped in results["skipped_files"]:
            lines.append(f"  - {skipped['path']} ({skipped['reason']})")
        lines.append("")

    # Errors
    if results["errors"]:
        lines.append("❌ Files with errors:")
        for error_result in results["errors"]:
            lines.append(f"  - {error_result['path']}")
            for error in error_result.get("errors", []):
                lines.append(f"    💥 {error}")
        lines.append("")

    # Warnings
    if results["warnings"]:
        lines.append("⚠️  Warnings:")
        for warning in results["warnings"]:
            lines.append(f"  - {warning}")
        lines.append("")

    return "\\n".join(lines)
'''

        # Replace placeholders with actual values
        replacements = {
            "FORMATTERS_PLACEHOLDER": json.dumps(customization["formatters"]),
            "MAX_LINE_LENGTH_PLACEHOLDER": str(customization["max_line_length"]),
            "FILE_PATTERNS_PLACEHOLDER": json.dumps(customization["file_patterns"]),
            "EXCLUDE_PATTERNS_PLACEHOLDER": json.dumps(customization["exclude_patterns"]),
            "CHECK_ONLY_PLACEHOLDER": str(customization["check_only"]),
            "CREATE_BACKUP_PLACEHOLDER": str(customization["create_backup"]),
            "TOOL_NAMES_PLACEHOLDER": json.dumps(customization["tool_names"]),
            "TIMEOUT_PLACEHOLDER": str(customization["timeout"])
        }

        for placeholder, value in replacements.items():
            template = template.replace(placeholder, value)

        return template

    def create_script_header(self, config: TemplateConfig) -> str:
        """Create standard header for generated scripts."""
        dependencies = self.get_dependencies()
        deps_comment = f"# Dependencies: {', '.join(dependencies)}" if dependencies else ""

        # Add formatter-specific dependency information
        formatters = config.customization.get("formatters", ["black", "isort"])
        formatter_deps = f"# Required formatters: {', '.join(formatters)}"

        return f'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generated auto-formatter hook script
Event type: {config.event_type.value}
Generated for: {config.output_path.name}

{self.description}

This script automatically formats Python files after they are written or
modified by Claude Code tools. It supports multiple formatters and provides
detailed reporting of formatting operations.
"""

{deps_comment}
{formatter_deps}

import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from cchooks import create_context
from cchooks.contexts.post_tool_use import PostToolUseContext

'''
