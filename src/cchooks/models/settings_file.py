"""Settings file data model.

This module defines the SettingsFile data model for representing Claude Code
settings files and their manipulation state.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..exceptions import CCHooksError, HookValidationError
from ..types.enums import SettingsLevel
from ..utils.file_operations import (
    create_backup,
    get_file_info,
    read_json_file,
    write_json_file,
)
from ..utils.json_handler import SettingsJSONHandler


class SettingsFileState(str, Enum):
    """Settings file state tracking for lifecycle management."""
    NOT_FOUND = "not_found"    # File doesn't exist
    EXISTS = "exists"          # File exists but not loaded
    LOADED = "loaded"          # File loaded into memory
    MODIFIED = "modified"      # File content modified
    SAVED = "saved"           # Modifications saved to disk


@dataclass
class SettingsFile:
    """Represents a Claude Code settings file and its manipulation state.

    This class encapsulates all information about a settings file,
    including its location, level, content, and state transitions.

    Attributes:
        path: Absolute path to the settings file
        level: Settings level (project, user-global)
        content: Parsed JSON content from the file
        hooks: Extracted hook configurations (if any)
        backup_path: Path to backup file if created
        state: Current state of the file
        exists: Whether the file exists on disk
        readable: Whether the file can be read
        writable: Whether the file can be written
    """

    path: Path
    level: SettingsLevel
    content: Dict[str, Any] = field(default_factory=dict)
    hooks: List[Dict[str, Any]] = field(default_factory=list)
    backup_path: Optional[Path] = None
    last_modified: Optional[datetime] = None
    file_size: int = 0
    state: SettingsFileState = SettingsFileState.NOT_FOUND
    exists: bool = False
    readable: bool = False
    writable: bool = False

    def __post_init__(self) -> None:
        """Post-initialization validation and state setup."""
        # Ensure path is absolute
        self.path = self.path.resolve()

        # Update existence and permission flags
        self.update_file_status()

    def update_file_status(self) -> None:
        """Update file existence and permission status."""
        self.exists = self.path.exists()

        if self.exists:
            self.readable = self.path.is_file() and self._check_readable()
            self.writable = self._check_writable()
            self._update_file_metadata()
            if self.state == SettingsFileState.NOT_FOUND:
                self.state = SettingsFileState.EXISTS
        else:
            self.readable = False
            # File might be writable if parent directory is writable
            self.writable = self._check_parent_writable()
            self.last_modified = None
            self.file_size = 0
            self.state = SettingsFileState.NOT_FOUND

    def _check_readable(self) -> bool:
        """Check if file is readable."""
        try:
            with open(self.path, encoding='utf-8'):
                pass
            return True
        except (OSError, PermissionError):
            return False

    def _check_writable(self) -> bool:
        """Check if file is writable."""
        if not self.exists:
            return self._check_parent_writable()

        try:
            # Try to open in append mode (least destructive)
            with open(self.path, 'a', encoding='utf-8'):
                pass
            return True
        except (OSError, PermissionError):
            return False

    def _check_parent_writable(self) -> bool:
        """Check if parent directory is writable."""
        parent = self.path.parent
        if not parent.exists():
            # Check if we can create the parent directory
            return self._check_can_create_parent()

        try:
            # Check if we can write to the parent directory
            test_file = parent / '.test_write_permission'
            test_file.touch()
            test_file.unlink()
            return True
        except (OSError, PermissionError):
            return False

    def _check_can_create_parent(self) -> bool:
        """Check if we can create parent directories."""
        parent = self.path.parent
        # Walk up the directory tree to find an existing parent
        while not parent.exists() and parent != parent.parent:
            parent = parent.parent

        # Check if the existing parent is writable
        try:
            test_dir = parent / '.test_mkdir_permission'
            test_dir.mkdir(exist_ok=True)
            test_dir.rmdir()
            return True
        except (OSError, PermissionError):
            return False

    def _update_file_metadata(self) -> None:
        """Update file metadata (size, modification time)."""
        if not self.exists:
            self.last_modified = None
            self.file_size = 0
            return

        try:
            stat_info = self.path.stat()
            self.last_modified = datetime.fromtimestamp(stat_info.st_mtime)
            self.file_size = stat_info.st_size
        except OSError:
            self.last_modified = None
            self.file_size = 0

    @property
    def directory(self) -> Path:
        """Get the .claude directory path."""
        return self.path.parent

    @property
    def is_project_level(self) -> bool:
        """Check if this is a project-level settings file."""
        return self.level == SettingsLevel.PROJECT

    @property
    def is_user_level(self) -> bool:
        """Check if this is a user-level settings file."""
        return self.level == SettingsLevel.USER_GLOBAL

    def get_hooks_section(self) -> Dict[str, Any]:
        """Extract the hooks section from settings content.

        Returns:
            Dictionary containing the hooks configuration, or empty dict if not found.
        """
        return self.content.get('hooks', {})

    def set_hooks_section(self, hooks_section: Dict[str, Any]) -> None:
        """Update the hooks section in settings content.

        Args:
            hooks_section: New hooks section to set (raw JSON structure)
        """
        self.content['hooks'] = hooks_section
        # Re-extract hooks list from the new section
        self.hooks = self.extract_hooks()
        if self.state == SettingsFileState.LOADED:
            self.state = SettingsFileState.MODIFIED

    def mark_loaded(self, content: Dict[str, Any]) -> None:
        """Mark file as loaded with the given content.

        Args:
            content: Parsed JSON content from the file
        """
        self.content = content
        self.hooks = self.extract_hooks()
        self.state = SettingsFileState.LOADED

        # Update file metadata when loading content
        self._update_file_metadata()

    def mark_saved(self) -> None:
        """Mark file as saved to disk."""
        self.state = SettingsFileState.SAVED
        # Update file metadata after saving
        self._update_file_metadata()

    def needs_backup(self) -> bool:
        """Check if file needs backup before modification.

        Returns:
            True if file exists and has content that should be backed up
        """
        return (self.exists and
                self.state in [SettingsFileState.LOADED, SettingsFileState.EXISTS] and
                self.backup_path is None)

    def can_be_modified(self) -> bool:
        """Check if file can be safely modified.

        Returns:
            True if file can be written to (exists and writable, or parent is writable)
        """
        return self.writable

    def load(self) -> None:
        """Load and parse the settings file from the filesystem.

        Raises:
            CCHooksError: If file cannot be read or parsed
            HookValidationError: If settings structure is invalid
        """
        if not self.exists:
            raise CCHooksError(f"Settings file does not exist: {self.path}")

        if not self.readable:
            raise CCHooksError(f"Settings file is not readable: {self.path}")

        try:
            # Use json_handler for consistent parsing
            handler = SettingsJSONHandler(self.path)
            self.content = handler.load(create_if_missing=False)

            # Extract hooks from content
            self.hooks = self.extract_hooks()

            # Update metadata
            self._update_file_metadata()

            # Update state
            self.state = SettingsFileState.LOADED

        except Exception as e:
            raise CCHooksError(f"Failed to load settings file {self.path}: {e}")

    def save(self, create_backup: bool = True) -> Optional[Path]:
        """Save the settings file to the filesystem.

        Args:
            create_backup: Whether to create a backup before saving

        Returns:
            Path to backup file if created, None otherwise

        Raises:
            CCHooksError: If file cannot be saved
        """
        if not self.can_be_modified():
            raise CCHooksError(f"Settings file cannot be modified: {self.path}")

        backup_path = None
        was_existing = self.exists

        try:
            # Create backup if requested and file exists
            if create_backup and self.exists:
                backup_path = self.create_backup()

            # Ensure parent directory exists
            self.path.parent.mkdir(parents=True, exist_ok=True)

            # Use json_handler for consistent formatting
            handler = SettingsJSONHandler(self.path)
            handler.save(self.content, create_dirs=True)

            # Update metadata and state
            self.update_file_status()

            # Handle state transitions: NotFound -> Created, Modified -> Saved
            if not was_existing:
                self.state = SettingsFileState.SAVED  # NotFound -> Created -> Saved
            else:
                self.state = SettingsFileState.SAVED  # Modified -> Saved

            return backup_path

        except Exception as e:
            raise CCHooksError(f"Failed to save settings file {self.path}: {e}")

    def extract_hooks(self) -> List[Dict[str, Any]]:
        """Extract hook configurations from content.

        Returns:
            List of all hook configurations found in the content
        """
        if not self.content:
            return []

        hooks_section = self.content.get("hooks", {})
        if not isinstance(hooks_section, dict):
            return []

        all_hooks = []
        for event_type, event_configs in hooks_section.items():
            if not isinstance(event_configs, list):
                continue

            for config in event_configs:
                if not isinstance(config, dict) or "hooks" not in config:
                    continue

                matcher = config.get("matcher", "")
                hooks_list = config["hooks"]

                if isinstance(hooks_list, list):
                    for hook in hooks_list:
                        if isinstance(hook, dict):
                            # Add metadata for easier management
                            hook_with_meta = hook.copy()
                            hook_with_meta["_event_type"] = event_type
                            hook_with_meta["_matcher"] = matcher
                            all_hooks.append(hook_with_meta)

        return all_hooks

    def update_hooks(self, hooks: List[Dict[str, Any]]) -> None:
        """Update the hooks section in content.

        Args:
            hooks: List of hook configurations to set
        """
        # Reconstruct hooks section from the provided list
        hooks_section = {}

        for hook in hooks:
            if not isinstance(hook, dict):
                continue

            event_type = hook.get("_event_type")
            matcher = hook.get("_matcher", "")

            if not event_type:
                continue

            # Remove metadata fields for storage
            clean_hook = {k: v for k, v in hook.items()
                         if not k.startswith("_")}

            # Ensure hooks section structure exists
            if event_type not in hooks_section:
                hooks_section[event_type] = []

            # Find or create matcher configuration
            target_config = None
            for config in hooks_section[event_type]:
                if config.get("matcher") == matcher:
                    target_config = config
                    break

            if target_config is None:
                target_config = {"matcher": matcher, "hooks": []}
                hooks_section[event_type].append(target_config)

            # Add hook to the configuration
            target_config["hooks"].append(clean_hook)

        # Update content and mark as modified
        self.content["hooks"] = hooks_section
        self.hooks = hooks

        if self.state == SettingsFileState.LOADED:
            self.state = SettingsFileState.MODIFIED

    def create_backup(self, suffix: Optional[str] = None) -> Path:
        """Create a timestamped backup of the settings file.

        Args:
            suffix: Custom suffix for backup file, defaults to timestamp

        Returns:
            Path to the created backup file

        Raises:
            CCHooksError: If backup creation fails
        """
        if not self.exists:
            raise CCHooksError(f"Cannot backup non-existent file: {self.path}")

        try:
            if suffix is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                suffix = f"bak_{timestamp}"

            backup_path = self.path.with_suffix(f".{suffix}")

            # Use file_operations for consistent backup creation
            import shutil
            shutil.copy2(self.path, backup_path)

            self.backup_path = backup_path
            return backup_path

        except Exception as e:
            raise CCHooksError(f"Failed to create backup for {self.path}: {e}")

    def __str__(self) -> str:
        """String representation of settings file."""
        return f"SettingsFile(path={self.path}, level={self.level.value}, state={self.state.value})"

    def __repr__(self) -> str:
        """Detailed representation of settings file."""
        return (f"SettingsFile(path={self.path!r}, level={self.level!r}, "
                f"state={self.state!r}, exists={self.exists}, "
                f"readable={self.readable}, writable={self.writable}, "
                f"size={self.file_size}, modified={self.last_modified})")
