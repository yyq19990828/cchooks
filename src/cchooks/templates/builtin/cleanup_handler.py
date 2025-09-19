"""CleanupHandlerTemplate for session end cleanup operations.

This template provides comprehensive cleanup operations when Claude sessions end,
including temporary file cleanup, cache management, session log preservation,
and system resource cleanup. It supports SessionEnd events.

Features:
- Temporary file and cache cleanup
- Session log preservation and archival
- System resource cleanup and optimization
- Configurable cleanup policies and retention
- Performance metrics and reporting
- Safe cleanup with backup options
"""

from __future__ import annotations

import os
import shutil
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

from ...models.validation import ValidationResult
from ...types.enums import HookEventType
from ..base_template import BaseTemplate, TemplateConfig, template


@template(
    template_id="cleanup-handler",
    name="Cleanup Handler",
    description="Comprehensive session cleanup and resource management"
)
class CleanupHandlerTemplate(BaseTemplate):
    """Template for session end cleanup and resource management.

    This template handles cleanup operations when Claude sessions end,
    including temporary files, caches, logs, and system resource optimization.
    """

    @property
    def name(self) -> str:
        return "Cleanup Handler"

    @property
    def description(self) -> str:
        return "Comprehensive session cleanup and resource management"

    @property
    def supported_events(self) -> List[HookEventType]:
        return [HookEventType.SESSION_END]

    @property
    def customization_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "cleanup_enabled": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to enable session cleanup"
                },
                "cleanup_scope": {
                    "type": "array",
                    "items": {"enum": ["temp_files", "cache", "logs", "downloads", "backups"]},
                    "default": ["temp_files", "cache"],
                    "description": "Types of cleanup to perform"
                },
                "temp_file_patterns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": ["*.tmp", "*.temp", "claude_*", ".claude_session_*"],
                    "description": "Temporary file patterns to clean"
                },
                "temp_directories": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": ["~/.cache/claude", "/tmp/claude", "~/.local/tmp/claude"],
                    "description": "Temporary directories to clean"
                },
                "cache_directories": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": ["~/.cache/claude", "~/.claude/cache"],
                    "description": "Cache directories to clean"
                },
                "log_retention_days": {
                    "type": "integer",
                    "minimum": 0,
                    "default": 30,
                    "description": "Number of days to retain log files (0 = keep all)"
                },
                "backup_retention_days": {
                    "type": "integer",
                    "minimum": 0,
                    "default": 7,
                    "description": "Number of days to retain backup files (0 = keep all)"
                },
                "max_cache_size": {
                    "type": "integer",
                    "minimum": 0,
                    "default": 104857600,
                    "description": "Maximum cache size in bytes (100MB default, 0 = unlimited)"
                },
                "preserve_session_logs": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to preserve current session logs"
                },
                "session_log_archive": {
                    "type": "string",
                    "default": "~/.claude/logs/archive",
                    "description": "Directory to archive session logs"
                },
                "compress_archives": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to compress archived files"
                },
                "safe_cleanup": {
                    "type": "boolean",
                    "default": True,
                    "description": "Enable safe cleanup mode (backup before delete)"
                },
                "cleanup_timeout": {
                    "type": "integer",
                    "minimum": 5,
                    "maximum": 300,
                    "default": 60,
                    "description": "Maximum time in seconds for cleanup operations"
                },
                "parallel_cleanup": {
                    "type": "boolean",
                    "default": False,
                    "description": "Enable parallel cleanup operations"
                },
                "verify_cleanup": {
                    "type": "boolean",
                    "default": True,
                    "description": "Verify cleanup operations completed successfully"
                },
                "generate_report": {
                    "type": "boolean",
                    "default": True,
                    "description": "Generate cleanup report"
                },
                "report_file": {
                    "type": "string",
                    "default": "~/.claude/logs/cleanup_report.log",
                    "description": "Path to cleanup report file"
                },
                "cleanup_on_error": {
                    "type": "boolean",
                    "default": False,
                    "description": "Perform cleanup even if session ended with error"
                },
                "system_optimization": {
                    "type": "object",
                    "properties": {
                        "clear_memory": {"type": "boolean", "default": False},
                        "sync_filesystem": {"type": "boolean", "default": False},
                        "optimize_database": {"type": "boolean", "default": False}
                    },
                    "default": {"clear_memory": False, "sync_filesystem": False, "optimize_database": False},
                    "description": "System optimization options"
                },
                "notification_settings": {
                    "type": "object",
                    "properties": {
                        "notify_on_completion": {"type": "boolean", "default": False},
                        "notify_on_errors": {"type": "boolean", "default": True},
                        "notification_threshold": {"type": "integer", "default": 10}
                    },
                    "default": {"notify_on_completion": False, "notify_on_errors": True, "notification_threshold": 10},
                    "description": "Notification settings for cleanup events"
                }
            },
            "required": ["cleanup_enabled"]
        }

    def generate(self, config: TemplateConfig) -> str:
        """Generate the cleanup handler hook script."""
        # Validate event type
        self.validate_event_compatibility(config.event_type)

        # Get configuration
        custom_config = config.customization
        cleanup_enabled = custom_config.get("cleanup_enabled", True)
        cleanup_scope = custom_config.get("cleanup_scope", ["temp_files", "cache"])
        temp_file_patterns = custom_config.get("temp_file_patterns", ["*.tmp", "*.temp", "claude_*", ".claude_session_*"])
        temp_directories = custom_config.get("temp_directories", ["~/.cache/claude", "/tmp/claude", "~/.local/tmp/claude"])
        cache_directories = custom_config.get("cache_directories", ["~/.cache/claude", "~/.claude/cache"])
        log_retention_days = custom_config.get("log_retention_days", 30)
        backup_retention_days = custom_config.get("backup_retention_days", 7)
        max_cache_size = custom_config.get("max_cache_size", 104857600)
        preserve_session_logs = custom_config.get("preserve_session_logs", True)
        session_log_archive = custom_config.get("session_log_archive", "~/.claude/logs/archive")
        compress_archives = custom_config.get("compress_archives", True)
        safe_cleanup = custom_config.get("safe_cleanup", True)
        cleanup_timeout = custom_config.get("cleanup_timeout", 60)
        parallel_cleanup = custom_config.get("parallel_cleanup", False)
        verify_cleanup = custom_config.get("verify_cleanup", True)
        generate_report = custom_config.get("generate_report", True)
        report_file = custom_config.get("report_file", "~/.claude/logs/cleanup_report.log")
        cleanup_on_error = custom_config.get("cleanup_on_error", False)
        system_optimization = custom_config.get("system_optimization", {"clear_memory": False, "sync_filesystem": False, "optimize_database": False})
        notification_settings = custom_config.get("notification_settings", {"notify_on_completion": False, "notify_on_errors": True, "notification_threshold": 10})

        # Generate script content
        script_header = self.create_script_header(config)

        # Create cleanup configuration
        cleanup_config = f'''
# Cleanup handler configuration
CLEANUP_ENABLED = {cleanup_enabled}
CLEANUP_SCOPE = {cleanup_scope!r}
TEMP_FILE_PATTERNS = {temp_file_patterns!r}
TEMP_DIRECTORIES = {temp_directories!r}
CACHE_DIRECTORIES = {cache_directories!r}
LOG_RETENTION_DAYS = {log_retention_days}
BACKUP_RETENTION_DAYS = {backup_retention_days}
MAX_CACHE_SIZE = {max_cache_size}
PRESERVE_SESSION_LOGS = {preserve_session_logs}
SESSION_LOG_ARCHIVE = "{session_log_archive}"
COMPRESS_ARCHIVES = {compress_archives}
SAFE_CLEANUP = {safe_cleanup}
CLEANUP_TIMEOUT = {cleanup_timeout}
PARALLEL_CLEANUP = {parallel_cleanup}
VERIFY_CLEANUP = {verify_cleanup}
GENERATE_REPORT = {generate_report}
REPORT_FILE = "{report_file}"
CLEANUP_ON_ERROR = {cleanup_on_error}
SYSTEM_OPTIMIZATION = {system_optimization!r}
NOTIFICATION_SETTINGS = {notification_settings!r}
'''

        # Create helper functions
        helper_functions = '''
import os
import shutil
import time
import glob
import gzip
import signal
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Tuple, Any


def expand_path(path_str: str) -> Path:
    """Expand user path and resolve."""
    return Path(path_str).expanduser().resolve()


def ensure_directory(path: Path) -> bool:
    """Ensure directory exists, create if needed."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        return True
    except Exception:
        return False


def get_directory_size(path: Path) -> int:
    """Get total size of directory in bytes."""
    if not path.exists() or not path.is_dir():
        return 0

    total_size = 0
    try:
        for item in path.rglob('*'):
            if item.is_file():
                total_size += item.stat().st_size
    except Exception:
        pass

    return total_size


def is_file_older_than(file_path: Path, days: int) -> bool:
    """Check if file is older than specified days."""
    if days <= 0 or not file_path.exists():
        return False

    try:
        file_age = datetime.now() - datetime.fromtimestamp(file_path.stat().st_mtime)
        return file_age.days > days
    except Exception:
        return False


def safe_delete_file(file_path: Path, backup_dir: Path = None) -> bool:
    """Safely delete file with optional backup."""
    try:
        if SAFE_CLEANUP and backup_dir:
            ensure_directory(backup_dir)
            backup_name = f"{file_path.name}_{int(time.time())}"
            backup_path = backup_dir / backup_name
            shutil.copy2(file_path, backup_path)

        file_path.unlink()
        return True
    except Exception:
        return False


def safe_delete_directory(dir_path: Path, backup_dir: Path = None) -> bool:
    """Safely delete directory with optional backup."""
    try:
        if SAFE_CLEANUP and backup_dir and dir_path.exists():
            ensure_directory(backup_dir)
            backup_name = f"{dir_path.name}_{int(time.time())}"
            backup_path = backup_dir / backup_name
            shutil.copytree(dir_path, backup_path)

        shutil.rmtree(dir_path)
        return True
    except Exception:
        return False


def compress_file(file_path: Path) -> bool:
    """Compress file using gzip."""
    try:
        compressed_path = file_path.with_suffix(file_path.suffix + '.gz')
        with open(file_path, 'rb') as f_in:
            with gzip.open(compressed_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        file_path.unlink()  # Remove original
        return True
    except Exception:
        return False


class CleanupStats:
    """Track cleanup statistics."""

    def __init__(self):
        self.files_deleted = 0
        self.directories_deleted = 0
        self.bytes_freed = 0
        self.files_backed_up = 0
        self.files_compressed = 0
        self.errors = []
        self.start_time = time.time()
        self.operations = []

    def add_file_deleted(self, file_path: Path, size: int = 0):
        """Record file deletion."""
        self.files_deleted += 1
        self.bytes_freed += size
        self.operations.append(f"Deleted file: {file_path}")

    def add_directory_deleted(self, dir_path: Path, size: int = 0):
        """Record directory deletion."""
        self.directories_deleted += 1
        self.bytes_freed += size
        self.operations.append(f"Deleted directory: {dir_path}")

    def add_file_backed_up(self, file_path: Path):
        """Record file backup."""
        self.files_backed_up += 1
        self.operations.append(f"Backed up file: {file_path}")

    def add_file_compressed(self, file_path: Path):
        """Record file compression."""
        self.files_compressed += 1
        self.operations.append(f"Compressed file: {file_path}")

    def add_error(self, error: str):
        """Record error."""
        self.errors.append(error)

    def get_duration(self) -> float:
        """Get cleanup duration in seconds."""
        return time.time() - self.start_time

    def to_dict(self) -> Dict[str, Any]:
        """Convert stats to dictionary."""
        return {
            "files_deleted": self.files_deleted,
            "directories_deleted": self.directories_deleted,
            "bytes_freed": self.bytes_freed,
            "files_backed_up": self.files_backed_up,
            "files_compressed": self.files_compressed,
            "errors": len(self.errors),
            "error_details": self.errors[:10],  # Limit to first 10 errors
            "duration": self.get_duration(),
            "operations": len(self.operations)
        }


def cleanup_temp_files(stats: CleanupStats) -> None:
    """Clean up temporary files."""
    backup_dir = expand_path("~/.claude/backups/temp") if SAFE_CLEANUP else None

    # Clean temporary directories
    for temp_dir_str in TEMP_DIRECTORIES:
        try:
            temp_dir = expand_path(temp_dir_str)
            if not temp_dir.exists():
                continue

            dir_size = get_directory_size(temp_dir)
            if safe_delete_directory(temp_dir, backup_dir):
                stats.add_directory_deleted(temp_dir, dir_size)
            else:
                stats.add_error(f"Failed to delete temp directory: {temp_dir}")

        except Exception as e:
            stats.add_error(f"Error processing temp directory {temp_dir_str}: {e}")

    # Clean temporary files by pattern
    for pattern in TEMP_FILE_PATTERNS:
        try:
            # Search in common temp locations
            search_paths = [Path.cwd(), expand_path("~"), Path(tempfile.gettempdir())]

            for search_path in search_paths:
                if not search_path.exists():
                    continue

                for file_path in search_path.glob(pattern):
                    if file_path.is_file():
                        try:
                            file_size = file_path.stat().st_size
                            if safe_delete_file(file_path, backup_dir):
                                stats.add_file_deleted(file_path, file_size)
                            else:
                                stats.add_error(f"Failed to delete temp file: {file_path}")
                        except Exception as e:
                            stats.add_error(f"Error deleting temp file {file_path}: {e}")

        except Exception as e:
            stats.add_error(f"Error processing temp pattern {pattern}: {e}")


def cleanup_cache(stats: CleanupStats) -> None:
    """Clean up cache directories."""
    backup_dir = expand_path("~/.claude/backups/cache") if SAFE_CLEANUP else None

    for cache_dir_str in CACHE_DIRECTORIES:
        try:
            cache_dir = expand_path(cache_dir_str)
            if not cache_dir.exists():
                continue

            current_size = get_directory_size(cache_dir)

            # If cache size is within limits, skip
            if MAX_CACHE_SIZE > 0 and current_size <= MAX_CACHE_SIZE:
                continue

            # Clean old cache files first
            cleaned_size = 0
            for file_path in cache_dir.rglob('*'):
                if file_path.is_file() and is_file_older_than(file_path, 1):  # Files older than 1 day
                    try:
                        file_size = file_path.stat().st_size
                        if safe_delete_file(file_path, backup_dir):
                            stats.add_file_deleted(file_path, file_size)
                            cleaned_size += file_size

                            # Check if we've freed enough space
                            if MAX_CACHE_SIZE > 0 and (current_size - cleaned_size) <= MAX_CACHE_SIZE:
                                break
                    except Exception as e:
                        stats.add_error(f"Error deleting cache file {file_path}: {e}")

        except Exception as e:
            stats.add_error(f"Error processing cache directory {cache_dir_str}: {e}")


def cleanup_logs(stats: CleanupStats) -> None:
    """Clean up old log files."""
    if LOG_RETENTION_DAYS <= 0:
        return

    log_dirs = [expand_path("~/.claude/logs"), Path.cwd() / "logs"]
    backup_dir = expand_path("~/.claude/backups/logs") if SAFE_CLEANUP else None

    for log_dir in log_dirs:
        if not log_dir.exists():
            continue

        try:
            for log_file in log_dir.rglob('*.log'):
                if is_file_older_than(log_file, LOG_RETENTION_DAYS):
                    try:
                        file_size = log_file.stat().st_size
                        if safe_delete_file(log_file, backup_dir):
                            stats.add_file_deleted(log_file, file_size)
                        else:
                            stats.add_error(f"Failed to delete log file: {log_file}")
                    except Exception as e:
                        stats.add_error(f"Error deleting log file {log_file}: {e}")

        except Exception as e:
            stats.add_error(f"Error processing log directory {log_dir}: {e}")


def cleanup_downloads(stats: CleanupStats) -> None:
    """Clean up old download files."""
    downloads_dir = expand_path("~/Downloads")
    if not downloads_dir.exists():
        return

    backup_dir = expand_path("~/.claude/backups/downloads") if SAFE_CLEANUP else None

    try:
        # Clean files with claude-related names that are older than 1 day
        for file_path in downloads_dir.glob("*claude*"):
            if file_path.is_file() and is_file_older_than(file_path, 1):
                try:
                    file_size = file_path.stat().st_size
                    if safe_delete_file(file_path, backup_dir):
                        stats.add_file_deleted(file_path, file_size)
                    else:
                        stats.add_error(f"Failed to delete download file: {file_path}")
                except Exception as e:
                    stats.add_error(f"Error deleting download file {file_path}: {e}")

    except Exception as e:
        stats.add_error(f"Error processing downloads directory: {e}")


def cleanup_backups(stats: CleanupStats) -> None:
    """Clean up old backup files."""
    if BACKUP_RETENTION_DAYS <= 0:
        return

    backup_dirs = [
        expand_path("~/.claude/backups"),
        expand_path("~/.claude/archive")
    ]

    for backup_dir in backup_dirs:
        if not backup_dir.exists():
            continue

        try:
            for backup_file in backup_dir.rglob('*'):
                if backup_file.is_file() and is_file_older_than(backup_file, BACKUP_RETENTION_DAYS):
                    try:
                        file_size = backup_file.stat().st_size
                        backup_file.unlink()  # Don't backup backups
                        stats.add_file_deleted(backup_file, file_size)
                    except Exception as e:
                        stats.add_error(f"Error deleting backup file {backup_file}: {e}")

        except Exception as e:
            stats.add_error(f"Error processing backup directory {backup_dir}: {e}")


def archive_session_logs(context, stats: CleanupStats) -> None:
    """Archive current session logs."""
    if not PRESERVE_SESSION_LOGS:
        return

    try:
        archive_dir = expand_path(SESSION_LOG_ARCHIVE)
        ensure_directory(archive_dir)

        # Get session ID and transcript path
        session_id = getattr(context, 'session_id', 'unknown')
        transcript_path = getattr(context, 'transcript_path', '')

        if transcript_path and Path(transcript_path).exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_name = f"session_{session_id}_{timestamp}.log"
            archive_path = archive_dir / archive_name

            # Copy transcript to archive
            shutil.copy2(transcript_path, archive_path)
            stats.add_file_backed_up(Path(transcript_path))

            # Compress if enabled
            if COMPRESS_ARCHIVES:
                if compress_file(archive_path):
                    stats.add_file_compressed(archive_path)

    except Exception as e:
        stats.add_error(f"Error archiving session logs: {e}")


def perform_system_optimization(stats: CleanupStats) -> None:
    """Perform system optimization tasks."""
    if not any(SYSTEM_OPTIMIZATION.values()):
        return

    try:
        if SYSTEM_OPTIMIZATION.get("sync_filesystem", False):
            # Sync filesystem
            try:
                os.sync()
                stats.operations.append("Synchronized filesystem")
            except Exception as e:
                stats.add_error(f"Failed to sync filesystem: {e}")

        if SYSTEM_OPTIMIZATION.get("clear_memory", False):
            # Clear Python memory (limited effect)
            try:
                import gc
                gc.collect()
                stats.operations.append("Cleared Python memory")
            except Exception as e:
                stats.add_error(f"Failed to clear memory: {e}")

    except Exception as e:
        stats.add_error(f"Error during system optimization: {e}")


def generate_cleanup_report(stats: CleanupStats, context) -> bool:
    """Generate cleanup report."""
    if not GENERATE_REPORT:
        return True

    try:
        report_path = expand_path(REPORT_FILE)
        ensure_directory(report_path.parent)

        # Create report content
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        session_id = getattr(context, 'session_id', 'unknown')

        report_data = {
            "timestamp": timestamp,
            "session_id": session_id,
            "cleanup_scope": CLEANUP_SCOPE,
            "statistics": stats.to_dict(),
            "duration_seconds": stats.get_duration(),
            "cleanup_successful": len(stats.errors) == 0
        }

        # Format report
        report_lines = [
            f"Session Cleanup Report - {timestamp}",
            "=" * 60,
            f"Session ID: {session_id}",
            f"Cleanup Scope: {', '.join(CLEANUP_SCOPE)}",
            f"Duration: {stats.get_duration():.2f} seconds",
            "",
            "Statistics:",
            f"  Files deleted: {stats.files_deleted}",
            f"  Directories deleted: {stats.directories_deleted}",
            f"  Bytes freed: {stats.bytes_freed:,} ({stats.bytes_freed / 1024 / 1024:.2f} MB)",
            f"  Files backed up: {stats.files_backed_up}",
            f"  Files compressed: {stats.files_compressed}",
            f"  Total operations: {len(stats.operations)}",
            f"  Errors: {len(stats.errors)}",
            ""
        ]

        if stats.errors:
            report_lines.extend([
                "Errors encountered:",
                *[f"  - {error}" for error in stats.errors[:10]],
            ])
            if len(stats.errors) > 10:
                report_lines.append(f"  ... and {len(stats.errors) - 10} more errors")

        report_lines.extend(["", "=" * 60, ""])

        # Append to report file
        with open(report_path, 'a', encoding='utf-8') as f:
            f.write("\\n".join(report_lines))

        return True

    except Exception as e:
        print(f"Warning: Failed to generate cleanup report: {e}")
        return False


def run_cleanup_operation(operation_name: str, operation_func, *args) -> None:
    """Run a cleanup operation with timeout handling."""
    def timeout_handler(signum, frame):
        raise TimeoutError(f"Cleanup operation '{operation_name}' timed out")

    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(CLEANUP_TIMEOUT // len(CLEANUP_SCOPE))  # Divide timeout among operations

    try:
        operation_func(*args)
    finally:
        signal.alarm(0)  # Clear timeout
'''

        # Create main logic
        main_logic = f'''
        if not CLEANUP_ENABLED:
            context.output.continue_flow("Session cleanup disabled")
            return

        # Check if we should cleanup on error
        session_error = getattr(context, 'error', None) or getattr(context, 'stop_reason', '').lower() == 'error'
        if session_error and not CLEANUP_ON_ERROR:
            context.output.continue_flow("Session ended with error, cleanup skipped")
            return

        # Initialize cleanup statistics
        stats = CleanupStats()

        try:
            # Archive session logs first
            archive_session_logs(context, stats)

            # Perform cleanup operations based on scope
            cleanup_operations = []

            if "temp_files" in CLEANUP_SCOPE:
                cleanup_operations.append(("temp_files", cleanup_temp_files, stats))

            if "cache" in CLEANUP_SCOPE:
                cleanup_operations.append(("cache", cleanup_cache, stats))

            if "logs" in CLEANUP_SCOPE:
                cleanup_operations.append(("logs", cleanup_logs, stats))

            if "downloads" in CLEANUP_SCOPE:
                cleanup_operations.append(("downloads", cleanup_downloads, stats))

            if "backups" in CLEANUP_SCOPE:
                cleanup_operations.append(("backups", cleanup_backups, stats))

            # Run cleanup operations
            if PARALLEL_CLEANUP and len(cleanup_operations) > 1:
                # Run operations in parallel
                import threading

                threads = []
                for op_name, op_func, op_args in cleanup_operations:
                    thread = threading.Thread(target=op_func, args=(op_args,))
                    thread.start()
                    threads.append(thread)

                # Wait for all threads to complete
                for thread in threads:
                    thread.join(timeout=CLEANUP_TIMEOUT // len(cleanup_operations))

            else:
                # Run operations sequentially
                for op_name, op_func, op_args in cleanup_operations:
                    try:
                        run_cleanup_operation(op_name, op_func, op_args)
                    except TimeoutError as e:
                        stats.add_error(str(e))
                    except Exception as e:
                        stats.add_error(f"Error in {op_name} cleanup: {e}")

            # Perform system optimization
            perform_system_optimization(stats)

            # Verify cleanup if enabled
            if VERIFY_CLEANUP:
                verification_errors = 0
                # Add verification logic here if needed
                if verification_errors > 0:
                    stats.add_error(f"Cleanup verification found {verification_errors} issues")

        except Exception as e:
            stats.add_error(f"Unexpected error during cleanup: {e}")

        # Generate cleanup report
        report_generated = generate_cleanup_report(stats, context)

        # Create summary message
        duration = stats.get_duration()
        bytes_freed_mb = stats.bytes_freed / 1024 / 1024

        summary_parts = []
        if stats.files_deleted > 0:
            summary_parts.append(f"deleted {stats.files_deleted} files")
        if stats.directories_deleted > 0:
            summary_parts.append(f"removed {stats.directories_deleted} directories")
        if bytes_freed_mb > 0.1:
            summary_parts.append(f"freed {bytes_freed_mb:.1f} MB")
        if stats.files_backed_up > 0:
            summary_parts.append(f"backed up {stats.files_backed_up} files")

        if not summary_parts:
            summary = "Session cleanup completed - no files processed"
        else:
            summary = f"Session cleanup completed: {', '.join(summary_parts)}"

        summary += f" ({duration:.1f}s)"

        # Add error summary
        if stats.errors:
            summary += f" with {len(stats.errors)} error{'s' if len(stats.errors) != 1 else ''}"

        # Handle notifications
        notify_completion = NOTIFICATION_SETTINGS.get("notify_on_completion", False)
        notify_errors = NOTIFICATION_SETTINGS.get("notify_on_errors", True)
        threshold = NOTIFICATION_SETTINGS.get("notification_threshold", 10)

        should_notify = (
            (notify_completion and len(stats.operations) >= threshold) or
            (notify_errors and len(stats.errors) > 0)
        )

        if should_notify:
            summary += "\\n[Cleanup notification triggered]"

        context.output.continue_flow(summary)
'''

        # Combine all parts
        return script_header + cleanup_config + helper_functions + self.create_main_function(
            config.event_type, main_logic
        )

    def validate_config(self, config: Dict[str, Any]) -> ValidationResult:
        """Validate the cleanup handler configuration."""
        result = self.validate_schema(config, self.customization_schema)

        # Additional validation for paths
        for path_field in ["session_log_archive", "report_file"]:
            path_value = config.get(path_field, "")
            if path_value:
                try:
                    expanded_path = Path(path_value).expanduser()
                    if not expanded_path.parent.exists():
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

        # Validate retention settings
        log_retention = config.get("log_retention_days", 30)
        backup_retention = config.get("backup_retention_days", 7)

        if log_retention > 0 and log_retention < 7:
            result.add_warning(
                field_name="log_retention_days",
                warning_code="SHORT_RETENTION",
                message="Log retention period is very short (less than 7 days)"
            )

        if backup_retention > 0 and backup_retention < 3:
            result.add_warning(
                field_name="backup_retention_days",
                warning_code="SHORT_RETENTION",
                message="Backup retention period is very short (less than 3 days)"
            )

        # Validate cleanup timeout
        timeout = config.get("cleanup_timeout", 60)
        cleanup_scope = config.get("cleanup_scope", ["temp_files", "cache"])

        if timeout < len(cleanup_scope) * 5:
            result.add_warning(
                field_name="cleanup_timeout",
                warning_code="SHORT_TIMEOUT",
                message="Cleanup timeout may be too short for selected cleanup scope"
            )

        # Warn about system optimization
        sys_opt = config.get("system_optimization", {})
        if any(sys_opt.values()):
            result.add_warning(
                field_name="system_optimization",
                warning_code="SYSTEM_CHANGES",
                message="System optimization options may affect system performance"
            )

        return result

    def get_default_config(self) -> Dict[str, Any]:
        """Get default configuration for cleanup handler."""
        return {
            "cleanup_enabled": True,
            "cleanup_scope": ["temp_files", "cache"],
            "temp_file_patterns": ["*.tmp", "*.temp", "claude_*", ".claude_session_*"],
            "temp_directories": ["~/.cache/claude", "/tmp/claude", "~/.local/tmp/claude"],
            "cache_directories": ["~/.cache/claude", "~/.claude/cache"],
            "log_retention_days": 30,
            "backup_retention_days": 7,
            "max_cache_size": 104857600,
            "preserve_session_logs": True,
            "session_log_archive": "~/.claude/logs/archive",
            "compress_archives": True,
            "safe_cleanup": True,
            "cleanup_timeout": 60,
            "parallel_cleanup": False,
            "verify_cleanup": True,
            "generate_report": True,
            "report_file": "~/.claude/logs/cleanup_report.log",
            "cleanup_on_error": False,
            "system_optimization": {
                "clear_memory": False,
                "sync_filesystem": False,
                "optimize_database": False
            },
            "notification_settings": {
                "notify_on_completion": False,
                "notify_on_errors": True,
                "notification_threshold": 10
            }
        }

    def get_dependencies(self) -> List[str]:
        """Get dependencies for cleanup handler template."""
        return []  # Uses only Python standard library
