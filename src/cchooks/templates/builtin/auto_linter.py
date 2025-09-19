"""AutoLinterTemplate for automatic code linting with multiple tools.

This template provides automatic code quality checking using popular Python
linting tools like pylint, flake8, and ruff. It supports PostToolUse events
to analyze code changes after tool execution.

Features:
- Multiple linter support (pylint, flake8, ruff)
- Configurable severity levels and rules
- Code quality report generation
- Smart file filtering for Python files
- Error handling and graceful degradation
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List

from ...models.validation import ValidationResult
from ...types.enums import HookEventType
from ..base_template import BaseTemplate, TemplateConfig, template


@template(
    template_id="auto-linter",
    name="Auto Linter",
    description="Automatic code quality checking with multiple linting tools"
)
class AutoLinterTemplate(BaseTemplate):
    """Template for automatic code linting after tool execution.

    This template runs code quality checks on Python files that have been
    modified by tools. It supports multiple linters and provides configurable
    severity levels and reporting options.
    """

    @property
    def name(self) -> str:
        return "Auto Linter"

    @property
    def description(self) -> str:
        return "Automatic code quality checking with pylint, flake8, and ruff"

    @property
    def supported_events(self) -> List[HookEventType]:
        return [HookEventType.POST_TOOL_USE]

    @property
    def customization_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "enabled_linters": {
                    "type": "array",
                    "items": {"enum": ["pylint", "flake8", "ruff"]},
                    "default": ["ruff", "flake8"],
                    "description": "List of linters to run"
                },
                "min_severity": {
                    "type": "string",
                    "enum": ["error", "warning", "info"],
                    "default": "warning",
                    "description": "Minimum severity level to report"
                },
                "target_patterns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": ["*.py"],
                    "description": "File patterns to lint"
                },
                "exclude_patterns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": ["**/test_*.py", "**/*_test.py", "**/conftest.py"],
                    "description": "File patterns to exclude from linting"
                },
                "fail_on_errors": {
                    "type": "boolean",
                    "default": False,
                    "description": "Whether to fail the hook on linting errors"
                },
                "generate_report": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to generate a quality report"
                },
                "report_format": {
                    "type": "string",
                    "enum": ["text", "json"],
                    "default": "text",
                    "description": "Format for the quality report"
                },
                "max_issues": {
                    "type": "integer",
                    "minimum": 0,
                    "default": 50,
                    "description": "Maximum number of issues to report (0 = unlimited)"
                }
            },
            "required": ["enabled_linters", "min_severity"]
        }

    def generate(self, config: TemplateConfig) -> str:
        """Generate the auto-linter hook script."""
        # Validate event type
        self.validate_event_compatibility(config.event_type)

        # Get configuration
        custom_config = config.customization
        enabled_linters = custom_config.get("enabled_linters", ["ruff", "flake8"])
        min_severity = custom_config.get("min_severity", "warning")
        target_patterns = custom_config.get("target_patterns", ["*.py"])
        exclude_patterns = custom_config.get("exclude_patterns", ["**/test_*.py", "**/*_test.py", "**/conftest.py"])
        fail_on_errors = custom_config.get("fail_on_errors", False)
        generate_report = custom_config.get("generate_report", True)
        report_format = custom_config.get("report_format", "text")
        max_issues = custom_config.get("max_issues", 50)

        # Generate script content
        script_header = self.create_script_header(config)

        # Create linter configuration
        linter_config = f'''
# Linter configuration
ENABLED_LINTERS = {enabled_linters!r}
MIN_SEVERITY = "{min_severity}"
TARGET_PATTERNS = {target_patterns!r}
EXCLUDE_PATTERNS = {exclude_patterns!r}
FAIL_ON_ERRORS = {fail_on_errors}
GENERATE_REPORT = {generate_report}
REPORT_FORMAT = "{report_format}"
MAX_ISSUES = {max_issues}
'''

        # Create helper functions
        helper_functions = '''
import subprocess
import fnmatch
import re
from datetime import datetime


def should_lint_file(file_path: str) -> bool:
    """Check if file should be linted based on patterns."""
    file_path = str(file_path)

    # Check if file matches target patterns
    matches_target = any(fnmatch.fnmatch(file_path, pattern) for pattern in TARGET_PATTERNS)
    if not matches_target:
        return False

    # Check if file matches exclude patterns
    matches_exclude = any(fnmatch.fnmatch(file_path, pattern) for pattern in EXCLUDE_PATTERNS)
    return not matches_exclude


def run_linter(linter: str, files: List[str]) -> Dict[str, Any]:
    """Run a specific linter on files and return results."""
    if not files:
        return {"issues": [], "returncode": 0, "output": ""}

    try:
        if linter == "ruff":
            cmd = ["ruff", "check", "--output-format=json"] + files
        elif linter == "flake8":
            cmd = ["flake8", "--format=json"] + files
        elif linter == "pylint":
            cmd = ["pylint", "--output-format=json", "--score=no"] + files
        else:
            return {"issues": [], "returncode": 1, "output": f"Unknown linter: {linter}"}

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        # Parse output based on linter
        issues = parse_linter_output(linter, result.stdout, result.stderr)

        return {
            "issues": issues,
            "returncode": result.returncode,
            "output": result.stdout + result.stderr
        }

    except subprocess.TimeoutExpired:
        return {"issues": [], "returncode": 1, "output": f"{linter} timed out"}
    except FileNotFoundError:
        return {"issues": [], "returncode": 1, "output": f"{linter} not found"}
    except Exception as e:
        return {"issues": [], "returncode": 1, "output": f"{linter} error: {str(e)}"}


def parse_linter_output(linter: str, stdout: str, stderr: str) -> List[Dict[str, Any]]:
    """Parse linter output into standardized issue format."""
    issues = []

    try:
        if linter == "ruff" and stdout:
            import json
            data = json.loads(stdout)
            for issue in data:
                issues.append({
                    "file": issue.get("filename", ""),
                    "line": issue.get("location", {}).get("row", 0),
                    "column": issue.get("location", {}).get("column", 0),
                    "severity": "error" if issue.get("fix") else "warning",
                    "message": issue.get("message", ""),
                    "rule": issue.get("code", ""),
                    "linter": "ruff"
                })

        elif linter == "flake8" and stdout:
            import json
            data = json.loads(stdout)
            for issue in data:
                issues.append({
                    "file": issue.get("filename", ""),
                    "line": issue.get("line_number", 0),
                    "column": issue.get("column_number", 0),
                    "severity": "error" if issue.get("code", "").startswith("E") else "warning",
                    "message": issue.get("text", ""),
                    "rule": issue.get("code", ""),
                    "linter": "flake8"
                })

        elif linter == "pylint" and stdout:
            import json
            data = json.loads(stdout)
            for issue in data:
                severity_map = {"error": "error", "warning": "warning", "convention": "info", "refactor": "info"}
                issues.append({
                    "file": issue.get("path", ""),
                    "line": issue.get("line", 0),
                    "column": issue.get("column", 0),
                    "severity": severity_map.get(issue.get("type", ""), "info"),
                    "message": issue.get("message", ""),
                    "rule": issue.get("symbol", ""),
                    "linter": "pylint"
                })

    except Exception:
        # If JSON parsing fails, try to parse plain text output
        if stderr:
            for line in stderr.split("\\n"):
                if line.strip():
                    issues.append({
                        "file": "",
                        "line": 0,
                        "column": 0,
                        "severity": "error",
                        "message": line.strip(),
                        "rule": "",
                        "linter": linter
                    })

    return issues


def filter_issues_by_severity(issues: List[Dict[str, Any]], min_severity: str) -> List[Dict[str, Any]]:
    """Filter issues by minimum severity level."""
    severity_order = {"error": 3, "warning": 2, "info": 1}
    min_level = severity_order.get(min_severity, 1)

    return [
        issue for issue in issues
        if severity_order.get(issue.get("severity", "info"), 1) >= min_level
    ]


def generate_report(all_issues: List[Dict[str, Any]], format_type: str) -> str:
    """Generate a quality report from issues."""
    if format_type == "json":
        import json
        return json.dumps({
            "timestamp": datetime.now().isoformat(),
            "total_issues": len(all_issues),
            "issues_by_severity": {
                "error": len([i for i in all_issues if i.get("severity") == "error"]),
                "warning": len([i for i in all_issues if i.get("severity") == "warning"]),
                "info": len([i for i in all_issues if i.get("severity") == "info"])
            },
            "issues_by_linter": {
                linter: len([i for i in all_issues if i.get("linter") == linter])
                for linter in set(i.get("linter", "") for i in all_issues)
            },
            "issues": all_issues
        }, indent=2)

    else:  # text format
        report_lines = [
            f"Code Quality Report - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "=" * 60,
            f"Total issues found: {len(all_issues)}",
            ""
        ]

        # Group by severity
        by_severity = {}
        for issue in all_issues:
            severity = issue.get("severity", "info")
            if severity not in by_severity:
                by_severity[severity] = []
            by_severity[severity].append(issue)

        for severity in ["error", "warning", "info"]:
            if severity in by_severity:
                report_lines.append(f"{severity.upper()}S ({len(by_severity[severity])}):")
                for issue in by_severity[severity][:10]:  # Limit to first 10 per severity
                    file_path = issue.get("file", "unknown")
                    line = issue.get("line", 0)
                    message = issue.get("message", "")
                    rule = issue.get("rule", "")
                    linter = issue.get("linter", "")

                    report_lines.append(f"  {file_path}:{line} [{rule}] {message} ({linter})")

                if len(by_severity[severity]) > 10:
                    report_lines.append(f"  ... and {len(by_severity[severity]) - 10} more")
                report_lines.append("")

        return "\\n".join(report_lines)


def get_modified_files(context) -> List[str]:
    """Get list of files that were modified by the tool."""
    modified_files = []

    # Check if tool_use contains file information
    tool_use = getattr(context, 'tool_use', {})
    if tool_use:
        # Extract file paths from different tool types
        if 'file_path' in tool_use:
            modified_files.append(tool_use['file_path'])
        elif 'path' in tool_use:
            modified_files.append(tool_use['path'])
        elif 'files' in tool_use:
            modified_files.extend(tool_use['files'])

    # Filter for Python files that should be linted
    python_files = []
    for file_path in modified_files:
        if should_lint_file(file_path) and Path(file_path).exists():
            python_files.append(str(file_path))

    return python_files
'''

        # Create main logic
        main_logic = f'''
        # Get modified files
        modified_files = get_modified_files(context)

        if not modified_files:
            context.output.continue_flow("No Python files to lint")
            return

        # Run all enabled linters
        all_issues = []
        linter_results = {{}}

        for linter in ENABLED_LINTERS:
            result = run_linter(linter, modified_files)
            linter_results[linter] = result
            all_issues.extend(result["issues"])

        # Filter by severity
        filtered_issues = filter_issues_by_severity(all_issues, MIN_SEVERITY)

        # Limit number of issues if configured
        if MAX_ISSUES > 0 and len(filtered_issues) > MAX_ISSUES:
            filtered_issues = filtered_issues[:MAX_ISSUES]

        # Generate report if enabled
        report = ""
        if GENERATE_REPORT:
            report = generate_report(filtered_issues, REPORT_FORMAT)

        # Determine if we should fail
        has_errors = any(issue.get("severity") == "error" for issue in filtered_issues)
        should_fail = FAIL_ON_ERRORS and has_errors

        # Create response message
        issue_count = len(filtered_issues)
        if issue_count == 0:
            message = f"Code quality check passed: {{len(modified_files)}} files linted, no issues found"
            context.output.continue_flow(message)
        else:
            severity_counts = {{}}
            for issue in filtered_issues:
                sev = issue.get("severity", "info")
                severity_counts[sev] = severity_counts.get(sev, 0) + 1

            severity_summary = ", ".join(f"{{count}} {{sev}}{{'s' if count != 1 else ''}}"
                                       for sev, count in severity_counts.items())

            message = f"Code quality check: {{issue_count}} issues found ({severity_summary})"

            if report:
                message += f"\\n\\nQuality Report:\\n{{report}}"

            if should_fail:
                context.output.exit_non_block(message)
            else:
                context.output.continue_flow(message)
'''

        # Combine all parts
        return script_header + linter_config + helper_functions + self.create_main_function(
            config.event_type, main_logic
        )

    def validate_config(self, config: Dict[str, Any]) -> ValidationResult:
        """Validate the auto-linter configuration."""
        return self.validate_schema(config, self.customization_schema)

    def get_default_config(self) -> Dict[str, Any]:
        """Get default configuration for auto-linter."""
        return {
            "enabled_linters": ["ruff", "flake8"],
            "min_severity": "warning",
            "target_patterns": ["*.py"],
            "exclude_patterns": ["**/test_*.py", "**/*_test.py", "**/conftest.py"],
            "fail_on_errors": False,
            "generate_report": True,
            "report_format": "text",
            "max_issues": 50
        }

    def get_dependencies(self) -> List[str]:
        """Get dependencies for auto-linter template."""
        return ["ruff", "flake8", "pylint"]
