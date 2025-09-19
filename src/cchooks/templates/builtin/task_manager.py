"""TaskManagerTemplate for Claude stop event handling and resource management.

This template provides comprehensive task management when Claude stops execution,
including temporary file cleanup, resource management, work state preservation,
and task completion reporting. It supports Stop events to handle graceful shutdown.

Features:
- Temporary file and resource cleanup
- Work state preservation and recovery
- Task completion reporting and logging
- Process management and cleanup
- Configurable cleanup policies
- Backup and recovery mechanisms
"""

from __future__ import annotations

import os
import shutil
import signal
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import psutil

from ...models.validation import ValidationResult
from ...types.enums import HookEventType
from ..base_template import BaseTemplate, TemplateConfig, template


@template(
    template_id="task-manager",
    name="Task Manager",
    description="Resource cleanup and state management for Claude stop events"
)
class TaskManagerTemplate(BaseTemplate):
    """Template for managing resources and state when Claude stops.

    This template handles cleanup operations when Claude execution stops,
    including temporary file cleanup, resource management, state preservation,
    and task completion reporting.
    """

    @property
    def name(self) -> str:
        return "Task Manager"

    @property
    def description(self) -> str:
        return "Resource cleanup and state management for Claude stop events"

    @property
    def supported_events(self) -> List[HookEventType]:
        return [HookEventType.STOP]

    @property
    def customization_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "cleanup_enabled": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to perform cleanup operations"
                },
                "temp_directories": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": ["/tmp/claude_*", "~/.cache/claude", "~/.local/tmp/claude_*"],
                    "description": "Temporary directories to clean up"
                },
                "file_patterns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": ["*.tmp", "*.temp", "*.bak~", "*.swp", ".DS_Store"],
                    "description": "File patterns to remove from working directory"
                },
                "max_file_age": {
                    "type": "integer",
                    "minimum": 0,
                    "default": 3600,
                    "description": "Maximum age in seconds for files to keep (0 = keep all)"
                },
                "preserve_patterns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": ["*.log", "*.backup", "*.save"],
                    "description": "File patterns to preserve during cleanup"
                },
                "kill_processes": {
                    "type": "boolean",
                    "default": False,
                    "description": "Whether to kill spawned processes"
                },
                "process_patterns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": ["claude_subprocess_*", "temp_process_*"],
                    "description": "Process name patterns to terminate"
                },
                "save_state": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to save current work state"
                },
                "state_file": {
                    "type": "string",
                    "default": "~/.claude/state/task_state.json",
                    "description": "Path to save work state"
                },
                "include_environment": {
                    "type": "boolean",
                    "default": False,
                    "description": "Whether to save environment variables in state"
                },
                "generate_report": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to generate completion report"
                },
                "report_file": {
                    "type": "string",
                    "default": "~/.claude/logs/task_completion.log",
                    "description": "Path to save completion report"
                },
                "backup_important_files": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to backup important files before cleanup"
                },
                "backup_directory": {
                    "type": "string",
                    "default": "~/.claude/backups",
                    "description": "Directory to store backups"
                },
                "important_patterns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": ["*.py", "*.json", "*.md", "*.txt", "*.yaml", "*.yml"],
                    "description": "Patterns for files to backup before cleanup"
                },
                "cleanup_timeout": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 300,
                    "default": 30,
                    "description": "Maximum time in seconds for cleanup operations"
                },
                "force_cleanup": {
                    "type": "boolean",
                    "default": False,
                    "description": "Whether to force cleanup even if operations fail"
                },
                "log_cleanup_details": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to log detailed cleanup information"
                }
            },
            "required": ["cleanup_enabled"]
        }

    def generate(self, config: TemplateConfig) -> str:
        """Generate the task manager hook script."""
        # Validate event type
        self.validate_event_compatibility(config.event_type)

        # Get configuration
        custom_config = config.customization
        cleanup_enabled = custom_config.get("cleanup_enabled", True)
        temp_directories = custom_config.get("temp_directories", ["/tmp/claude_*", "~/.cache/claude", "~/.local/tmp/claude_*"])
        file_patterns = custom_config.get("file_patterns", ["*.tmp", "*.temp", "*.bak~", "*.swp", ".DS_Store"])
        max_file_age = custom_config.get("max_file_age", 3600)
        preserve_patterns = custom_config.get("preserve_patterns", ["*.log", "*.backup", "*.save"])
        kill_processes = custom_config.get("kill_processes", False)
        process_patterns = custom_config.get("process_patterns", ["claude_subprocess_*", "temp_process_*"])
        save_state = custom_config.get("save_state", True)
        state_file = custom_config.get("state_file", "~/.claude/state/task_state.json")
        include_environment = custom_config.get("include_environment", False)
        generate_report = custom_config.get("generate_report", True)
        report_file = custom_config.get("report_file", "~/.claude/logs/task_completion.log")
        backup_important_files = custom_config.get("backup_important_files", True)
        backup_directory = custom_config.get("backup_directory", "~/.claude/backups")
        important_patterns = custom_config.get("important_patterns", ["*.py", "*.json", "*.md", "*.txt", "*.yaml", "*.yml"])
        cleanup_timeout = custom_config.get("cleanup_timeout", 30)
        force_cleanup = custom_config.get("force_cleanup", False)
        log_cleanup_details = custom_config.get("log_cleanup_details", True)

        # Generate script content
        script_header = self.create_script_header(config)

        # Create task manager configuration
        task_config = f'''
# Task manager configuration
CLEANUP_ENABLED = {cleanup_enabled}
TEMP_DIRECTORIES = {temp_directories!r}
FILE_PATTERNS = {file_patterns!r}
MAX_FILE_AGE = {max_file_age}
PRESERVE_PATTERNS = {preserve_patterns!r}
KILL_PROCESSES = {kill_processes}
PROCESS_PATTERNS = {process_patterns!r}
SAVE_STATE = {save_state}
STATE_FILE = "{state_file}"
INCLUDE_ENVIRONMENT = {include_environment}
GENERATE_REPORT = {generate_report}
REPORT_FILE = "{report_file}"
BACKUP_IMPORTANT_FILES = {backup_important_files}
BACKUP_DIRECTORY = "{backup_directory}"
IMPORTANT_PATTERNS = {important_patterns!r}
CLEANUP_TIMEOUT = {cleanup_timeout}
FORCE_CLEANUP = {force_cleanup}
LOG_CLEANUP_DETAILS = {log_cleanup_details}
'''

        # Create helper functions
        helper_functions = '''
import os
import signal
import shutil
import time
import glob
import fnmatch
import json
import psutil
from datetime import datetime, timedelta
from pathlib import Path


def expand_path(path_str: str) -> Path:
    """Expand user path and create parent directories."""
    path = Path(path_str).expanduser().resolve()
    if not path.exists() and str(path_str).endswith(('.json', '.log', '.txt')):
        path.parent.mkdir(parents=True, exist_ok=True)
    return path


def log_action(message: str, details: str = "") -> None:
    """Log cleanup action if detailed logging is enabled."""
    if LOG_CLEANUP_DETAILS:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] {message}"
        if details:
            log_message += f": {details}"
        print(log_message)


def should_preserve_file(file_path: Path) -> bool:
    """Check if file should be preserved based on preserve patterns."""
    file_name = file_path.name
    return any(fnmatch.fnmatch(file_name, pattern) for pattern in PRESERVE_PATTERNS)


def is_file_too_old(file_path: Path, max_age: int) -> bool:
    """Check if file is older than maximum age in seconds."""
    if max_age <= 0:
        return False

    try:
        file_age = time.time() - file_path.stat().st_mtime
        return file_age > max_age
    except Exception:
        return False


def backup_file(file_path: Path, backup_dir: Path) -> bool:
    """Backup a file to the backup directory."""
    try:
        backup_dir.mkdir(parents=True, exist_ok=True)

        # Create unique backup name with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{file_path.name}_{timestamp}"
        backup_path = backup_dir / backup_name

        shutil.copy2(file_path, backup_path)
        log_action(f"Backed up file", f"{file_path} -> {backup_path}")
        return True

    except Exception as e:
        log_action(f"Failed to backup file {file_path}", str(e))
        return False


def cleanup_files_in_directory(directory: Path, patterns: List[str]) -> Dict[str, Any]:
    """Clean up files matching patterns in a directory."""
    cleanup_stats = {
        "files_removed": 0,
        "files_backed_up": 0,
        "files_preserved": 0,
        "errors": []
    }

    if not directory.exists() or not directory.is_dir():
        return cleanup_stats

    backup_dir = expand_path(BACKUP_DIRECTORY) if BACKUP_IMPORTANT_FILES else None

    try:
        for pattern in patterns:
            for file_path in directory.glob(pattern):
                if not file_path.is_file():
                    continue

                # Check if file should be preserved
                if should_preserve_file(file_path):
                    cleanup_stats["files_preserved"] += 1
                    continue

                # Check file age
                if not is_file_too_old(file_path, MAX_FILE_AGE):
                    cleanup_stats["files_preserved"] += 1
                    continue

                try:
                    # Backup important files
                    backed_up = False
                    if BACKUP_IMPORTANT_FILES and backup_dir:
                        file_name = file_path.name
                        if any(fnmatch.fnmatch(file_name, pattern) for pattern in IMPORTANT_PATTERNS):
                            backed_up = backup_file(file_path, backup_dir)
                            if backed_up:
                                cleanup_stats["files_backed_up"] += 1

                    # Remove the file
                    file_path.unlink()
                    cleanup_stats["files_removed"] += 1
                    log_action(f"Removed file", str(file_path))

                except Exception as e:
                    cleanup_stats["errors"].append(f"Failed to remove {file_path}: {e}")
                    if not FORCE_CLEANUP:
                        break

    except Exception as e:
        cleanup_stats["errors"].append(f"Failed to process directory {directory}: {e}")

    return cleanup_stats


def cleanup_temp_directories() -> Dict[str, Any]:
    """Clean up temporary directories."""
    cleanup_stats = {
        "directories_processed": 0,
        "total_files_removed": 0,
        "total_files_backed_up": 0,
        "total_files_preserved": 0,
        "errors": []
    }

    for temp_dir_pattern in TEMP_DIRECTORIES:
        expanded_pattern = str(expand_path(temp_dir_pattern))

        # Handle glob patterns
        if '*' in expanded_pattern:
            for temp_dir_path in glob.glob(expanded_pattern):
                temp_dir = Path(temp_dir_path)
                if temp_dir.exists() and temp_dir.is_dir():
                    try:
                        shutil.rmtree(temp_dir)
                        cleanup_stats["directories_processed"] += 1
                        log_action(f"Removed temp directory", str(temp_dir))
                    except Exception as e:
                        cleanup_stats["errors"].append(f"Failed to remove {temp_dir}: {e}")
        else:
            temp_dir = Path(expanded_pattern)
            if temp_dir.exists() and temp_dir.is_dir():
                try:
                    shutil.rmtree(temp_dir)
                    cleanup_stats["directories_processed"] += 1
                    log_action(f"Removed temp directory", str(temp_dir))
                except Exception as e:
                    cleanup_stats["errors"].append(f"Failed to remove {temp_dir}: {e}")

    return cleanup_stats


def cleanup_working_directory() -> Dict[str, Any]:
    """Clean up files in current working directory."""
    working_dir = Path.cwd()
    return cleanup_files_in_directory(working_dir, FILE_PATTERNS)


def kill_spawned_processes() -> Dict[str, Any]:
    """Kill processes matching specified patterns."""
    process_stats = {
        "processes_found": 0,
        "processes_killed": 0,
        "errors": []
    }

    if not KILL_PROCESSES:
        return process_stats

    try:
        current_pid = os.getpid()

        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                proc_info = proc.info
                proc_name = proc_info.get('name', '')
                proc_cmdline = ' '.join(proc_info.get('cmdline', []))

                # Skip current process
                if proc_info['pid'] == current_pid:
                    continue

                # Check if process matches patterns
                should_kill = any(
                    fnmatch.fnmatch(proc_name, pattern) or
                    fnmatch.fnmatch(proc_cmdline, pattern)
                    for pattern in PROCESS_PATTERNS
                )

                if should_kill:
                    process_stats["processes_found"] += 1
                    try:
                        proc.terminate()
                        # Give process time to terminate gracefully
                        proc.wait(timeout=5)
                        process_stats["processes_killed"] += 1
                        log_action(f"Terminated process", f"{proc_name} (PID: {proc_info['pid']})")
                    except psutil.TimeoutExpired:
                        # Force kill if it doesn't terminate gracefully
                        try:
                            proc.kill()
                            process_stats["processes_killed"] += 1
                            log_action(f"Force killed process", f"{proc_name} (PID: {proc_info['pid']})")
                        except Exception as e:
                            process_stats["errors"].append(f"Failed to kill {proc_name}: {e}")
                    except Exception as e:
                        process_stats["errors"].append(f"Failed to terminate {proc_name}: {e}")

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

    except Exception as e:
        process_stats["errors"].append(f"Failed to enumerate processes: {e}")

    return process_stats


def save_work_state(context) -> bool:
    """Save current work state to file."""
    if not SAVE_STATE:
        return True

    try:
        state_path = expand_path(STATE_FILE)

        # Collect state information
        state = {
            "timestamp": datetime.now().isoformat(),
            "session_id": getattr(context, 'session_id', 'unknown'),
            "working_directory": str(Path.cwd()),
            "hook_event": getattr(context, 'hook_event_name', 'Stop'),
            "transcript_path": getattr(context, 'transcript_path', ''),
        }

        # Add environment variables if requested
        if INCLUDE_ENVIRONMENT:
            state["environment"] = dict(os.environ)

        # Add context-specific information
        if hasattr(context, 'stop_reason'):
            state["stop_reason"] = context.stop_reason

        # Save state to file
        with open(state_path, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2)

        log_action(f"Saved work state", str(state_path))
        return True

    except Exception as e:
        log_action(f"Failed to save work state", str(e))
        return False


def generate_completion_report(cleanup_stats: Dict[str, Any], process_stats: Dict[str, Any]) -> bool:
    """Generate task completion report."""
    if not GENERATE_REPORT:
        return True

    try:
        report_path = expand_path(REPORT_FILE)

        # Create report content
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        report_lines = [
            f"Task Completion Report - {timestamp}",
            "=" * 50,
            "",
            "Cleanup Summary:",
            f"  Temp directories processed: {cleanup_stats.get('directories_processed', 0)}",
            f"  Files removed: {cleanup_stats.get('total_files_removed', 0)}",
            f"  Files backed up: {cleanup_stats.get('total_files_backed_up', 0)}",
            f"  Files preserved: {cleanup_stats.get('total_files_preserved', 0)}",
            "",
            "Process Management:",
            f"  Processes found: {process_stats.get('processes_found', 0)}",
            f"  Processes killed: {process_stats.get('processes_killed', 0)}",
            "",
        ]

        # Add error summary
        all_errors = cleanup_stats.get('errors', []) + process_stats.get('errors', [])
        if all_errors:
            report_lines.extend([
                "Errors:",
                *[f"  - {error}" for error in all_errors[:10]],  # Limit to first 10 errors
            ])
            if len(all_errors) > 10:
                report_lines.append(f"  ... and {len(all_errors) - 10} more errors")
        else:
            report_lines.append("No errors encountered")

        report_lines.extend(["", "=" * 50, ""])

        # Append to report file
        with open(report_path, 'a', encoding='utf-8') as f:
            f.write("\\n".join(report_lines))

        log_action(f"Generated completion report", str(report_path))
        return True

    except Exception as e:
        log_action(f"Failed to generate completion report", str(e))
        return False
'''

        # Create main logic
        main_logic = '''
        start_time = time.time()
        log_action("Task manager starting cleanup operations")

        # Initialize statistics
        total_cleanup_stats = {
            "directories_processed": 0,
            "total_files_removed": 0,
            "total_files_backed_up": 0,
            "total_files_preserved": 0,
            "errors": []
        }

        process_stats = {
            "processes_found": 0,
            "processes_killed": 0,
            "errors": []
        }

        # Save work state first
        state_saved = save_work_state(context)

        # Perform cleanup operations if enabled
        if CLEANUP_ENABLED:
            try:
                # Set cleanup timeout
                def timeout_handler(signum, frame):
                    raise TimeoutError("Cleanup timeout exceeded")

                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(CLEANUP_TIMEOUT)

                # Clean up temporary directories
                temp_stats = cleanup_temp_directories()
                total_cleanup_stats["directories_processed"] += temp_stats["directories_processed"]
                total_cleanup_stats["errors"].extend(temp_stats["errors"])

                # Clean up working directory
                work_stats = cleanup_working_directory()
                total_cleanup_stats["total_files_removed"] += work_stats["files_removed"]
                total_cleanup_stats["total_files_backed_up"] += work_stats["files_backed_up"]
                total_cleanup_stats["total_files_preserved"] += work_stats["files_preserved"]
                total_cleanup_stats["errors"].extend(work_stats["errors"])

                # Kill spawned processes
                process_stats = kill_spawned_processes()

                # Clear timeout
                signal.alarm(0)

            except TimeoutError:
                log_action("Cleanup timeout exceeded", "Stopping cleanup operations")
                if not FORCE_CLEANUP:
                    total_cleanup_stats["errors"].append("Cleanup timeout exceeded")
            except Exception as e:
                log_action("Unexpected error during cleanup", str(e))
                total_cleanup_stats["errors"].append(f"Unexpected error: {e}")

        # Generate completion report
        report_generated = generate_completion_report(total_cleanup_stats, process_stats)

        # Calculate execution time
        execution_time = time.time() - start_time

        # Create summary message
        files_processed = (total_cleanup_stats["total_files_removed"] +
                          total_cleanup_stats["total_files_backed_up"] +
                          total_cleanup_stats["total_files_preserved"])

        summary_parts = []

        if CLEANUP_ENABLED:
            summary_parts.append(f"Processed {files_processed} files")
            summary_parts.append(f"removed {total_cleanup_stats['total_files_removed']}")

            if total_cleanup_stats["total_files_backed_up"] > 0:
                summary_parts.append(f"backed up {total_cleanup_stats['total_files_backed_up']}")

            if process_stats["processes_killed"] > 0:
                summary_parts.append(f"killed {process_stats['processes_killed']} processes")

        if SAVE_STATE and state_saved:
            summary_parts.append("saved work state")

        if GENERATE_REPORT and report_generated:
            summary_parts.append("generated report")

        summary = "Task cleanup completed: " + ", ".join(summary_parts) if summary_parts else "Task cleanup completed"
        summary += f" ({execution_time:.2f}s)"

        # Add error summary if there were errors
        total_errors = len(total_cleanup_stats["errors"]) + len(process_stats["errors"])
        if total_errors > 0:
            summary += f" with {total_errors} error{'s' if total_errors != 1 else ''}"

        # Respond with summary
        context.output.continue_flow(summary)
'''

        # Combine all parts
        return script_header + task_config + helper_functions + self.create_main_function(
            config.event_type, main_logic
        )

    def validate_config(self, config: Dict[str, Any]) -> ValidationResult:
        """Validate the task manager configuration."""
        result = self.validate_schema(config, self.customization_schema)

        # Additional validation for file paths
        for path_field in ["state_file", "report_file", "backup_directory"]:
            path_value = config.get(path_field, "")
            if path_value:
                try:
                    expanded_path = Path(path_value).expanduser()
                    if path_field == "backup_directory" and not expanded_path.parent.exists():
                        result.add_warning(
                            field_name=path_field,
                            warning_code="DIRECTORY_MISSING",
                            message=f"Parent directory for {path_field} does not exist (will be created)"
                        )
                except Exception:
                    result.add_error(
                        field_name=path_field,
                        error_code="INVALID_PATH",
                        message=f"Invalid path for {path_field}",
                        suggested_fix="Use a valid file path"
                    )

        # Validate cleanup timeout
        timeout = config.get("cleanup_timeout", 30)
        if timeout < 5:
            result.add_warning(
                field_name="cleanup_timeout",
                warning_code="SHORT_TIMEOUT",
                message="Cleanup timeout is very short, may not complete operations"
            )

        # Warn about process killing
        if config.get("kill_processes", False):
            result.add_warning(
                field_name="kill_processes",
                warning_code="DESTRUCTIVE_OPERATION",
                message="Process killing is enabled - ensure process patterns are correct"
            )

        return result

    def get_default_config(self) -> Dict[str, Any]:
        """Get default configuration for task manager."""
        return {
            "cleanup_enabled": True,
            "temp_directories": ["/tmp/claude_*", "~/.cache/claude", "~/.local/tmp/claude_*"],
            "file_patterns": ["*.tmp", "*.temp", "*.bak~", "*.swp", ".DS_Store"],
            "max_file_age": 3600,
            "preserve_patterns": ["*.log", "*.backup", "*.save"],
            "kill_processes": False,
            "process_patterns": ["claude_subprocess_*", "temp_process_*"],
            "save_state": True,
            "state_file": "~/.claude/state/task_state.json",
            "include_environment": False,
            "generate_report": True,
            "report_file": "~/.claude/logs/task_completion.log",
            "backup_important_files": True,
            "backup_directory": "~/.claude/backups",
            "important_patterns": ["*.py", "*.json", "*.md", "*.txt", "*.yaml", "*.yml"],
            "cleanup_timeout": 30,
            "force_cleanup": False,
            "log_cleanup_details": True
        }

    def get_dependencies(self) -> List[str]:
        """Get dependencies for task manager template."""
        return ["psutil"]
