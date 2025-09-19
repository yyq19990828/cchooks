"""Settings Manager service for Claude Code hooks management.

This module implements the SettingsManager service that provides the core API
for managing Claude Code settings files, following the contracts/settings_file_api.yaml
specification and integrating with existing components.

The SettingsManager provides:
- Settings file discovery and loading
- Hook configuration management (add, update, remove)
- Validation and error handling
- Backup and recovery functionality
- Performance optimization for CLI operations
"""

import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..exceptions import (
    CCHooksError,
    DiskSpaceError,
    DuplicateHookError,
    HookValidationError,
    ParseError,
    ValidationError,
)
from ..models.hook_config import HookConfiguration
from ..models.settings_file import SettingsFile
from ..models.validation import (
    ModificationResult,
    SaveResult,
    ValidationResult,
    ValidationWarning,
)
from ..settings.discovery import SettingsDiscovery, discover_settings_files
from ..types.enums import HookEventType, SettingsLevel
from ..utils.backup import BackupConfig, BackupManager, BackupMetadata, BackupType
from ..utils.file_operations import get_file_info
from ..utils.json_handler import SettingsJSONHandler


class SettingsManager:
    """Core API for managing Claude Code settings files.

    This service provides the primary interface for all settings file operations,
    implementing the contract specifications and integrating with the existing
    cchooks component ecosystem.

    The service is designed for performance, with response times under 100ms
    for typical CLI operations.
    """

    def __init__(self, backup_config: Optional[BackupConfig] = None):
        """Initialize SettingsManager with discovery engine and backup manager.

        Args:
            backup_config: Optional backup configuration. If None, uses default settings.
        """
        self._discovery = SettingsDiscovery()
        self._backup_manager = BackupManager(backup_config)

    def discover_settings_files(self) -> List[SettingsFile]:
        """Find all accessible settings files in precedence order.

        Returns:
            List of SettingsFile objects ordered by precedence (project -> user)

        Raises:
            PermissionError: When settings directories are not accessible
        """
        try:
            return self._discovery.discover_settings_files()
        except Exception as e:
            if "permission" in str(e).lower():
                raise PermissionError(f"Settings directories not accessible: {e}")
            raise

    def load_settings(self, path: Path) -> SettingsFile:
        """Load and parse a settings file.

        Args:
            path: Path to settings file

        Returns:
            Parsed settings file object

        Raises:
            FileNotFoundError: When settings file doesn't exist
            ParseError: When settings file has invalid JSON
            PermissionError: When file is not readable
        """
        if not isinstance(path, Path):
            path = Path(path)

        # Create SettingsFile object based on path
        settings_file = self._create_settings_file_from_path(path)

        # Check file existence and permissions
        if not settings_file.exists:
            raise FileNotFoundError(f"Settings file not found: {path}")

        if not settings_file.readable:
            raise PermissionError(f"Settings file is not readable: {path}")

        try:
            # Load the settings file
            settings_file.load()
            return settings_file

        except CCHooksError as e:
            if "JSON" in str(e) or "parse" in str(e).lower():
                raise ParseError(f"Invalid JSON in settings file: {e}")
            raise

    def save_settings(self, settings: SettingsFile, create_backup: bool = True) -> SaveResult:
        """Save settings to file with optional backup.

        Args:
            settings: Settings object to save
            create_backup: Whether to create backup before saving

        Returns:
            Result of save operation

        Raises:
            PermissionError: When file is not writable
            DiskSpaceError: When insufficient disk space
        """
        if not settings.can_be_modified():
            raise PermissionError(f"Settings file cannot be modified: {settings.path}")

        # Get original file size
        original_size = settings.file_size

        # Check disk space if file will grow significantly
        if settings.content:
            estimated_size = len(str(settings.content)) * 2  # Rough estimate with formatting
            if estimated_size > original_size + 1024 * 1024:  # If growth > 1MB
                try:
                    disk_free = shutil.disk_usage(settings.path.parent).free
                    if disk_free < estimated_size:
                        raise DiskSpaceError(
                            "Insufficient disk space for save operation",
                            required_bytes=estimated_size,
                            available_bytes=disk_free
                        )
                except OSError:
                    # If we can't check disk space, proceed anyway
                    pass

        try:
            backup_metadata = None

            # Create backup using BackupManager if requested
            if create_backup and settings.exists:
                backup_metadata = self._backup_manager.create_backup(
                    settings.path,
                    BackupType.AUTO_PRE_MODIFY,
                    "自动备份：修改前保护"
                )

            # Save the file (without creating its own backup)
            settings.save(create_backup=False)

            # Get new file size
            settings.update_file_status()
            new_size = settings.file_size

            return SaveResult.success_result(
                backup_path=Path(backup_metadata.backup_file_path) if backup_metadata else None,
                original_size=original_size,
                new_size=new_size
            )

        except CCHooksError as e:
            if "permission" in str(e).lower():
                raise PermissionError(f"Cannot write to settings file: {e}")
            elif "space" in str(e).lower() or "disk" in str(e).lower():
                raise DiskSpaceError(f"Disk space error during save: {e}")
            raise

    def add_hook(self, settings: SettingsFile, hook: HookConfiguration) -> ModificationResult:
        """Add hook configuration to settings.

        Args:
            settings: Target settings file
            hook: Hook configuration to add

        Returns:
            Result of add operation

        Raises:
            ValidationError: When hook configuration is invalid
            DuplicateHookError: When identical hook already exists
        """
        # Validate hook configuration
        validation_result = hook.validate()
        if not validation_result.is_valid:
            error_msg = "; ".join([e.message for e in validation_result.errors])
            raise ValidationError(f"Invalid hook configuration: {error_msg}")

        # Count hooks before addition
        hook_count_before = len(settings.hooks)

        # Check for duplicate hooks
        existing_hook, existing_index = self._find_duplicate_hook(settings, hook)
        if existing_hook is not None:
            raise DuplicateHookError(
                f"Identical hook already exists at index {existing_index}",
                existing_hook=existing_hook,
                existing_index=existing_index
            )

        try:
            # Convert HookConfiguration to dict for storage
            hook_dict = hook.to_dict()

            # Add metadata for internal management
            hook_dict["_event_type"] = hook.event_type.value if hook.event_type else None
            hook_dict["_matcher"] = hook.matcher or ""

            # Add to settings
            settings.hooks.append(hook_dict)
            settings.update_hooks(settings.hooks)

            # Count hooks after addition
            hook_count_after = len(settings.hooks)

            # Collect any validation warnings
            warnings = []
            if validation_result.warnings:
                warnings = validation_result.warnings

            return ModificationResult.success_result(
                modified_hook=hook_dict,
                hook_count_before=hook_count_before,
                hook_count_after=hook_count_after,
                validation_warnings=warnings
            )

        except Exception as e:
            return ModificationResult.failure_result(hook_count_before=hook_count_before)

    def update_hook(self, settings: SettingsFile, event_type: HookEventType,
                   index: int, updates: Dict[str, Any]) -> ModificationResult:
        """Update existing hook configuration.

        Args:
            settings: Target settings file
            event_type: Event type of hook to update
            index: Index of hook within event type
            updates: Fields to update

        Returns:
            Result of update operation

        Raises:
            IndexError: When hook index doesn't exist
            ValidationError: When updated configuration is invalid
        """
        hook_count_before = len(settings.hooks)

        # Find the hook to update
        hooks_for_event = self._get_hooks_for_event_type(settings, event_type)
        if index < 0 or index >= len(hooks_for_event):
            raise IndexError(f"Hook index {index} does not exist for event type {event_type.value}")

        target_hook = hooks_for_event[index]
        original_hook = target_hook.copy()

        try:
            # Apply updates
            updated_hook = target_hook.copy()
            updated_hook.update(updates)

            # Create HookConfiguration to validate
            hook_config = HookConfiguration.from_dict(
                updated_hook,
                event_type=event_type,
                matcher=updated_hook.get("_matcher", "")
            )

            # Validate updated configuration
            validation_result = hook_config.validate()
            if not validation_result.is_valid:
                error_msg = "; ".join([e.message for e in validation_result.errors])
                raise ValidationError(f"Invalid updated hook configuration: {error_msg}")

            # Update the hook in settings
            hook_index_in_all = settings.hooks.index(target_hook)
            settings.hooks[hook_index_in_all] = updated_hook
            settings.update_hooks(settings.hooks)

            hook_count_after = len(settings.hooks)

            # Collect validation warnings
            warnings = []
            if validation_result.warnings:
                warnings = validation_result.warnings

            return ModificationResult.success_result(
                modified_hook=updated_hook,
                hook_count_before=hook_count_before,
                hook_count_after=hook_count_after,
                validation_warnings=warnings
            )

        except (ValidationError, IndexError):
            raise
        except Exception as e:
            raise ValidationError(f"Failed to update hook: {e}")

    def remove_hook(self, settings: SettingsFile, event_type: HookEventType,
                   index: int) -> ModificationResult:
        """Remove hook configuration from settings.

        Args:
            settings: Target settings file
            event_type: Event type of hook to remove
            index: Index of hook within event type

        Returns:
            Result of remove operation

        Raises:
            IndexError: When hook index doesn't exist
        """
        hook_count_before = len(settings.hooks)

        # Find the hook to remove
        hooks_for_event = self._get_hooks_for_event_type(settings, event_type)
        if index < 0 or index >= len(hooks_for_event):
            raise IndexError(f"Hook index {index} does not exist for event type {event_type.value}")

        target_hook = hooks_for_event[index]

        try:
            # Remove from all hooks list
            settings.hooks.remove(target_hook)
            settings.update_hooks(settings.hooks)

            hook_count_after = len(settings.hooks)

            return ModificationResult.success_result(
                modified_hook=target_hook,
                hook_count_before=hook_count_before,
                hook_count_after=hook_count_after
            )

        except Exception as e:
            raise IndexError(f"Failed to remove hook: {e}")

    def validate_hook(self, hook: HookConfiguration) -> ValidationResult:
        """Validate hook configuration against cchooks types.

        Args:
            hook: Hook configuration to validate

        Returns:
            Detailed validation result
        """
        return hook.validate()

    def _create_settings_file_from_path(self, path: Path) -> SettingsFile:
        """Create SettingsFile object from path, determining level automatically."""
        path = path.resolve()

        # Determine settings level based on path
        home_path = Path.home()
        if str(path).startswith(str(home_path)):
            level = SettingsLevel.USER_GLOBAL
        else:
            level = SettingsLevel.PROJECT

        return SettingsFile(path=path, level=level)

    def _find_duplicate_hook(self, settings: SettingsFile, hook: HookConfiguration) -> tuple:
        """Find if an identical hook already exists.

        Returns:
            Tuple of (existing_hook_dict, index) or (None, None) if not found
        """
        hook_dict = hook.to_dict()

        for i, existing_hook in enumerate(settings.hooks):
            # Compare the core hook fields (excluding metadata)
            existing_core = {k: v for k, v in existing_hook.items() if not k.startswith("_")}
            if existing_core == hook_dict:
                # Check event type and matcher if available
                if (existing_hook.get("_event_type") == (hook.event_type.value if hook.event_type else None) and
                    existing_hook.get("_matcher") == (hook.matcher or "")):
                    return existing_hook, i

        return None, None

    def _get_hooks_for_event_type(self, settings: SettingsFile, event_type: HookEventType) -> List[Dict[str, Any]]:
        """Get all hooks for a specific event type."""
        event_type_value = event_type.value
        return [hook for hook in settings.hooks
                if hook.get("_event_type") == event_type_value]

    # Backup management methods

    def create_manual_backup(self, settings_file: SettingsFile, reason: str = "手动备份", user_notes: str = "") -> BackupMetadata:
        """Create a manual backup of a settings file.

        Args:
            settings_file: Settings file to backup
            reason: Reason for backup
            user_notes: Additional user notes

        Returns:
            Backup metadata object

        Raises:
            FileOperationError: If backup creation fails
        """
        return self._backup_manager.create_backup(
            settings_file.path,
            BackupType.MANUAL,
            reason,
            user_notes
        )

    def list_backups_for_settings(self, settings_file: SettingsFile) -> List[BackupMetadata]:
        """List all backups for a specific settings file.

        Args:
            settings_file: Settings file to list backups for

        Returns:
            List of backup metadata objects
        """
        return self._backup_manager.list_backups(settings_file.path)

    def restore_latest_backup(self, settings_file: SettingsFile, target_path: Optional[Path] = None) -> Optional[Path]:
        """Restore the latest backup for a settings file.

        Args:
            settings_file: Settings file to restore backup for
            target_path: Optional target path (defaults to original location)

        Returns:
            Path to restored file, or None if no backups exist
        """
        return self._backup_manager.restore_latest_backup(settings_file.path, target_path)

    def get_backup_statistics(self) -> Dict[str, Any]:
        """Get backup system statistics.

        Returns:
            Dictionary containing backup statistics
        """
        return self._backup_manager.get_backup_statistics()

    def verify_backups(self) -> Dict[str, Any]:
        """Verify integrity of all backups.

        Returns:
            Dictionary containing verification results
        """
        return self._backup_manager.verify_all_backups()

    def cleanup_old_backups(self) -> int:
        """Clean up old backups according to retention policy.

        Returns:
            Number of backups cleaned up
        """
        return self._backup_manager.cleanup_all_backups()

    @property
    def backup_manager(self) -> BackupManager:
        """Get the backup manager instance for advanced operations.

        Returns:
            BackupManager instance
        """
        return self._backup_manager
