"""DesktopNotifierTemplate for cross-platform desktop notifications.

This template provides cross-platform desktop notification support for Claude Code
events. It supports Notification events to display system notifications with
configurable styles, sounds, and priority levels.

Features:
- Cross-platform desktop notification support (Windows, macOS, Linux)
- Configurable notification styles and icons
- Sound support with custom audio files
- Priority-based notification filtering
- Notification history and logging
- Rich notification content with formatting
"""

from __future__ import annotations

import platform
import subprocess
from pathlib import Path
from typing import Any, Dict, List

from ...models.validation import ValidationResult
from ...types.enums import HookEventType
from ..base_template import BaseTemplate, TemplateConfig, template


@template(
    template_id="desktop-notifier",
    name="Desktop Notifier",
    description="Cross-platform desktop notifications with rich formatting"
)
class DesktopNotifierTemplate(BaseTemplate):
    """Template for cross-platform desktop notifications.

    This template displays desktop notifications for Claude Code events,
    supporting multiple platforms and rich notification formatting with
    priority levels, sounds, and custom styling.
    """

    @property
    def name(self) -> str:
        return "Desktop Notifier"

    @property
    def description(self) -> str:
        return "Cross-platform desktop notifications with rich formatting"

    @property
    def supported_events(self) -> List[HookEventType]:
        return [HookEventType.NOTIFICATION]

    @property
    def customization_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "enabled": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether notifications are enabled"
                },
                "min_priority": {
                    "type": "string",
                    "enum": ["low", "normal", "high", "urgent"],
                    "default": "normal",
                    "description": "Minimum priority level to show notifications"
                },
                "notification_timeout": {
                    "type": "integer",
                    "minimum": 1000,
                    "maximum": 30000,
                    "default": 5000,
                    "description": "Notification display timeout in milliseconds"
                },
                "enable_sound": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to play notification sounds"
                },
                "sound_file": {
                    "type": "string",
                    "default": "",
                    "description": "Custom sound file path (empty = system default)"
                },
                "icon_path": {
                    "type": "string",
                    "default": "",
                    "description": "Custom notification icon path"
                },
                "app_name": {
                    "type": "string",
                    "default": "Claude Code",
                    "description": "Application name for notifications"
                },
                "max_title_length": {
                    "type": "integer",
                    "minimum": 10,
                    "maximum": 200,
                    "default": 80,
                    "description": "Maximum notification title length"
                },
                "max_message_length": {
                    "type": "integer",
                    "minimum": 50,
                    "maximum": 1000,
                    "default": 300,
                    "description": "Maximum notification message length"
                },
                "include_timestamp": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to include timestamp in notifications"
                },
                "notification_position": {
                    "type": "string",
                    "enum": ["top-right", "top-left", "bottom-right", "bottom-left", "center"],
                    "default": "top-right",
                    "description": "Notification position on screen"
                },
                "enable_history": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to maintain notification history"
                },
                "history_file": {
                    "type": "string",
                    "default": "~/.claude/logs/notification_history.json",
                    "description": "Path to notification history file"
                },
                "max_history_size": {
                    "type": "integer",
                    "minimum": 10,
                    "default": 100,
                    "description": "Maximum number of notifications to keep in history"
                },
                "quiet_hours": {
                    "type": "object",
                    "properties": {
                        "enabled": {"type": "boolean", "default": False},
                        "start_time": {"type": "string", "default": "22:00"},
                        "end_time": {"type": "string", "default": "08:00"}
                    },
                    "default": {"enabled": False, "start_time": "22:00", "end_time": "08:00"},
                    "description": "Quiet hours configuration"
                },
                "priority_settings": {
                    "type": "object",
                    "properties": {
                        "low": {
                            "type": "object",
                            "properties": {
                                "timeout": {"type": "integer", "default": 3000},
                                "sound": {"type": "boolean", "default": False}
                            },
                            "default": {"timeout": 3000, "sound": False}
                        },
                        "normal": {
                            "type": "object",
                            "properties": {
                                "timeout": {"type": "integer", "default": 5000},
                                "sound": {"type": "boolean", "default": True}
                            },
                            "default": {"timeout": 5000, "sound": True}
                        },
                        "high": {
                            "type": "object",
                            "properties": {
                                "timeout": {"type": "integer", "default": 8000},
                                "sound": {"type": "boolean", "default": True}
                            },
                            "default": {"timeout": 8000, "sound": True}
                        },
                        "urgent": {
                            "type": "object",
                            "properties": {
                                "timeout": {"type": "integer", "default": 0},
                                "sound": {"type": "boolean", "default": True}
                            },
                            "default": {"timeout": 0, "sound": True}
                        }
                    },
                    "default": {
                        "low": {"timeout": 3000, "sound": False},
                        "normal": {"timeout": 5000, "sound": True},
                        "high": {"timeout": 8000, "sound": True},
                        "urgent": {"timeout": 0, "sound": True}
                    },
                    "description": "Priority-specific notification settings"
                }
            },
            "required": ["enabled", "min_priority"]
        }

    def generate(self, config: TemplateConfig) -> str:
        """Generate the desktop notifier hook script."""
        # Validate event type
        self.validate_event_compatibility(config.event_type)

        # Get configuration
        custom_config = config.customization
        enabled = custom_config.get("enabled", True)
        min_priority = custom_config.get("min_priority", "normal")
        notification_timeout = custom_config.get("notification_timeout", 5000)
        enable_sound = custom_config.get("enable_sound", True)
        sound_file = custom_config.get("sound_file", "")
        icon_path = custom_config.get("icon_path", "")
        app_name = custom_config.get("app_name", "Claude Code")
        max_title_length = custom_config.get("max_title_length", 80)
        max_message_length = custom_config.get("max_message_length", 300)
        include_timestamp = custom_config.get("include_timestamp", True)
        notification_position = custom_config.get("notification_position", "top-right")
        enable_history = custom_config.get("enable_history", True)
        history_file = custom_config.get("history_file", "~/.claude/logs/notification_history.json")
        max_history_size = custom_config.get("max_history_size", 100)
        quiet_hours = custom_config.get("quiet_hours", {"enabled": False, "start_time": "22:00", "end_time": "08:00"})
        priority_settings = custom_config.get("priority_settings", {
            "low": {"timeout": 3000, "sound": False},
            "normal": {"timeout": 5000, "sound": True},
            "high": {"timeout": 8000, "sound": True},
            "urgent": {"timeout": 0, "sound": True}
        })

        # Generate script content
        script_header = self.create_script_header(config)

        # Create notifier configuration
        notifier_config = f'''
# Desktop notifier configuration
ENABLED = {enabled}
MIN_PRIORITY = "{min_priority}"
NOTIFICATION_TIMEOUT = {notification_timeout}
ENABLE_SOUND = {enable_sound}
SOUND_FILE = "{sound_file}"
ICON_PATH = "{icon_path}"
APP_NAME = "{app_name}"
MAX_TITLE_LENGTH = {max_title_length}
MAX_MESSAGE_LENGTH = {max_message_length}
INCLUDE_TIMESTAMP = {include_timestamp}
NOTIFICATION_POSITION = "{notification_position}"
ENABLE_HISTORY = {enable_history}
HISTORY_FILE = "{history_file}"
MAX_HISTORY_SIZE = {max_history_size}
QUIET_HOURS = {quiet_hours!r}
PRIORITY_SETTINGS = {priority_settings!r}
'''

        # Create helper functions
        helper_functions = '''
import json
import platform
import subprocess
import time
from datetime import datetime, time as dt_time
from pathlib import Path


def get_platform() -> str:
    """Get normalized platform name."""
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    elif system == "linux":
        return "linux"
    elif system == "windows":
        return "windows"
    else:
        return "unknown"


def expand_path(path_str: str) -> Path:
    """Expand user path and create parent directories."""
    if not path_str:
        return None
    path = Path(path_str).expanduser().resolve()
    if path_str.endswith(('.json', '.log', '.txt')):  # File paths
        path.parent.mkdir(parents=True, exist_ok=True)
    return path


def get_priority_value(priority: str) -> int:
    """Get numeric value for priority level."""
    priorities = {"low": 1, "normal": 2, "high": 3, "urgent": 4}
    return priorities.get(priority.lower(), 2)


def should_show_notification(priority: str) -> bool:
    """Check if notification should be shown based on priority."""
    return get_priority_value(priority) >= get_priority_value(MIN_PRIORITY)


def is_quiet_hours() -> bool:
    """Check if current time is within quiet hours."""
    if not QUIET_HOURS.get("enabled", False):
        return False

    now = datetime.now().time()
    start_time = dt_time.fromisoformat(QUIET_HOURS.get("start_time", "22:00"))
    end_time = dt_time.fromisoformat(QUIET_HOURS.get("end_time", "08:00"))

    if start_time <= end_time:
        # Same day range (e.g., 10:00 to 18:00)
        return start_time <= now <= end_time
    else:
        # Overnight range (e.g., 22:00 to 08:00)
        return now >= start_time or now <= end_time


def truncate_text(text: str, max_length: int) -> str:
    """Truncate text to maximum length with ellipsis."""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def format_notification_content(title: str, message: str, priority: str) -> tuple[str, str]:
    """Format notification title and message."""
    # Add priority indicator to title
    priority_indicators = {
        "low": "ⓘ",
        "normal": "🔔",
        "high": "⚠️",
        "urgent": "🚨"
    }

    indicator = priority_indicators.get(priority, "🔔")
    formatted_title = f"{indicator} {title}"

    # Add timestamp if enabled
    if INCLUDE_TIMESTAMP:
        timestamp = datetime.now().strftime("%H:%M")
        formatted_title = f"[{timestamp}] {formatted_title}"

    # Truncate to limits
    formatted_title = truncate_text(formatted_title, MAX_TITLE_LENGTH)
    formatted_message = truncate_text(message, MAX_MESSAGE_LENGTH)

    return formatted_title, formatted_message


def show_notification_windows(title: str, message: str, timeout: int, sound: bool) -> bool:
    """Show notification on Windows using PowerShell."""
    try:
        # Use Windows 10+ toast notifications
        ps_script = f"""
Add-Type -AssemblyName System.Windows.Forms
$notification = New-Object System.Windows.Forms.NotifyIcon
$notification.Icon = [System.Drawing.SystemIcons]::Information
$notification.BalloonTipIcon = "Info"
$notification.BalloonTipText = "{message.replace('"', "'")}"
$notification.BalloonTipTitle = "{title.replace('"', "'")}"
$notification.Visible = $true
$notification.ShowBalloonTip({timeout})
Start-Sleep -Milliseconds {timeout + 1000}
$notification.Dispose()
"""

        result = subprocess.run(
            ["powershell", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.returncode == 0

    except Exception:
        # Fallback to simple message box
        try:
            subprocess.run([
                "powershell", "-Command",
                f'[System.Windows.Forms.MessageBox]::Show("{message}", "{title}")'
            ], timeout=5)
            return True
        except Exception:
            return False


def show_notification_macos(title: str, message: str, timeout: int, sound: bool) -> bool:
    """Show notification on macOS using osascript."""
    try:
        cmd = [
            "osascript", "-e",
            f'display notification "{message}" with title "{title}"'
        ]

        if sound and SOUND_FILE:
            cmd.extend(["-e", f'set sound "{SOUND_FILE}"'])
        elif sound:
            cmd.extend(["-e", 'set sound "default"'])

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return result.returncode == 0

    except Exception:
        return False


def show_notification_linux(title: str, message: str, timeout: int, sound: bool) -> bool:
    """Show notification on Linux using notify-send."""
    try:
        cmd = ["notify-send"]

        # Add timeout
        if timeout > 0:
            cmd.extend(["-t", str(timeout)])

        # Add icon if specified
        if ICON_PATH:
            icon_path = expand_path(ICON_PATH)
            if icon_path and icon_path.exists():
                cmd.extend(["-i", str(icon_path)])

        # Add urgency based on priority
        urgency_map = {"low": "low", "normal": "normal", "high": "normal", "urgent": "critical"}
        priority = "normal"  # Default, will be overridden by caller
        cmd.extend(["-u", urgency_map.get(priority, "normal")])

        # Add title and message
        cmd.extend([title, message])

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

        # Play sound if enabled and notification succeeded
        if result.returncode == 0 and sound:
            try:
                if SOUND_FILE:
                    sound_path = expand_path(SOUND_FILE)
                    if sound_path and sound_path.exists():
                        subprocess.run(["paplay", str(sound_path)],
                                     capture_output=True, timeout=5)
                else:
                    # System default sound
                    subprocess.run(["paplay", "/usr/share/sounds/alsa/Front_Left.wav"],
                                 capture_output=True, timeout=5)
            except Exception:
                pass  # Ignore sound errors

        return result.returncode == 0

    except Exception:
        return False


def show_notification(title: str, message: str, priority: str) -> bool:
    """Show notification using platform-appropriate method."""
    if not ENABLED or is_quiet_hours():
        return True

    # Get priority-specific settings
    priority_config = PRIORITY_SETTINGS.get(priority, PRIORITY_SETTINGS["normal"])
    timeout = priority_config.get("timeout", NOTIFICATION_TIMEOUT)
    sound = ENABLE_SOUND and priority_config.get("sound", True)

    # Format content
    formatted_title, formatted_message = format_notification_content(title, message, priority)

    # Show notification based on platform
    platform_name = get_platform()
    success = False

    if platform_name == "windows":
        success = show_notification_windows(formatted_title, formatted_message, timeout, sound)
    elif platform_name == "macos":
        success = show_notification_macos(formatted_title, formatted_message, timeout, sound)
    elif platform_name == "linux":
        success = show_notification_linux(formatted_title, formatted_message, timeout, sound)

    return success


def save_to_history(title: str, message: str, priority: str, success: bool) -> None:
    """Save notification to history file."""
    if not ENABLE_HISTORY:
        return

    history_path = expand_path(HISTORY_FILE)
    if not history_path:
        return

    # Load existing history
    history = []
    if history_path.exists():
        try:
            with open(history_path, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = []

    # Add new entry
    entry = {
        "timestamp": datetime.now().isoformat(),
        "title": title,
        "message": message,
        "priority": priority,
        "success": success,
        "platform": get_platform()
    }

    history.append(entry)

    # Limit history size
    if len(history) > MAX_HISTORY_SIZE:
        history = history[-MAX_HISTORY_SIZE:]

    # Save history
    try:
        with open(history_path, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)
    except Exception:
        pass  # Ignore history save errors


def extract_notification_info(context) -> tuple[str, str, str]:
    """Extract notification information from context."""
    # Default values
    title = "Claude Code Notification"
    message = "A notification was triggered"
    priority = "normal"

    # Try to extract from notification context
    if hasattr(context, 'notification'):
        notification = context.notification
        title = notification.get('title', title)
        message = notification.get('message', message)
        priority = notification.get('priority', priority)

    # Fallback: extract from other context fields
    if title == "Claude Code Notification":
        if hasattr(context, 'tool_name'):
            title = f"Tool: {context.tool_name}"
        elif hasattr(context, 'hook_event_name'):
            title = f"Hook: {context.hook_event_name}"

    if message == "A notification was triggered":
        if hasattr(context, 'message'):
            message = context.message
        elif hasattr(context, 'description'):
            message = context.description

    return title, message, priority
'''

        # Create main logic
        main_logic = f'''
        # Extract notification information
        title, message, priority = extract_notification_info(context)

        # Check if notification should be shown
        if not should_show_notification(priority):
            context.output.continue_flow(f"Notification skipped (priority {priority} below threshold)")
            return

        # Show the notification
        success = show_notification(title, message, priority)

        # Save to history
        save_to_history(title, message, priority, success)

        # Respond based on success
        if success:
            context.output.continue_flow(f"Desktop notification sent: {title}")
        else:
            context.output.continue_flow(f"Failed to send desktop notification: {title}")
'''

        # Combine all parts
        return script_header + notifier_config + helper_functions + self.create_main_function(
            config.event_type, main_logic
        )

    def validate_config(self, config: Dict[str, Any]) -> ValidationResult:
        """Validate the desktop notifier configuration."""
        result = self.validate_schema(config, self.customization_schema)

        # Additional validation for file paths
        for path_field in ["sound_file", "icon_path", "history_file"]:
            path_value = config.get(path_field, "")
            if path_value:
                try:
                    expanded_path = Path(path_value).expanduser()
                    if path_field in ["sound_file", "icon_path"] and not expanded_path.exists():
                        result.add_warning(
                            field_name=path_field,
                            warning_code="FILE_NOT_FOUND",
                            message=f"File {expanded_path} does not exist"
                        )
                except Exception:
                    result.add_error(
                        field_name=path_field,
                        error_code="INVALID_PATH",
                        message=f"Invalid path for {path_field}",
                        suggested_fix="Use a valid file path"
                    )

        # Validate quiet hours time format
        quiet_hours = config.get("quiet_hours", {})
        if quiet_hours.get("enabled", False):
            for time_field in ["start_time", "end_time"]:
                time_value = quiet_hours.get(time_field, "")
                if time_value:
                    try:
                        from datetime import time
                        time.fromisoformat(time_value)
                    except ValueError:
                        result.add_error(
                            field_name=f"quiet_hours.{time_field}",
                            error_code="INVALID_TIME_FORMAT",
                            message=f"Invalid time format for {time_field}: {time_value}",
                            suggested_fix="Use HH:MM format (e.g., '22:00')"
                        )

        return result

    def get_default_config(self) -> Dict[str, Any]:
        """Get default configuration for desktop notifier."""
        return {
            "enabled": True,
            "min_priority": "normal",
            "notification_timeout": 5000,
            "enable_sound": True,
            "sound_file": "",
            "icon_path": "",
            "app_name": "Claude Code",
            "max_title_length": 80,
            "max_message_length": 300,
            "include_timestamp": True,
            "notification_position": "top-right",
            "enable_history": True,
            "history_file": "~/.claude/logs/notification_history.json",
            "max_history_size": 100,
            "quiet_hours": {
                "enabled": False,
                "start_time": "22:00",
                "end_time": "08:00"
            },
            "priority_settings": {
                "low": {"timeout": 3000, "sound": False},
                "normal": {"timeout": 5000, "sound": True},
                "high": {"timeout": 8000, "sound": True},
                "urgent": {"timeout": 0, "sound": True}
            }
        }

    def get_dependencies(self) -> List[str]:
        """Get dependencies for desktop notifier template."""
        # Platform-specific dependencies that should be available
        platform_name = platform.system().lower()
        if platform_name == "linux":
            return ["notify-send", "paplay"]
        elif platform_name == "darwin":
            return ["osascript"]
        elif platform_name == "windows":
            return ["powershell"]
        else:
            return []
