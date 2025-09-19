"""Validation models for hook configuration validation.

This module contains the ValidationResult, ValidationError, and ValidationWarning
models used throughout the CLI API system for hook configuration validation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


@dataclass
class ValidationError:
    """Represents a field-specific validation error.

    ValidationError is used when a hook configuration field contains invalid
    data that would prevent the hook from functioning correctly.

    Attributes:
        field_name: Name of the field with the error
        error_code: Standardized error code for programmatic handling
        message: Human-readable error description
        suggested_fix: Optional suggestion for fixing the error
    """
    field_name: str
    error_code: str
    message: str
    suggested_fix: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        result = {
            "field_name": self.field_name,
            "error_code": self.error_code,
            "message": self.message,
        }
        if self.suggested_fix is not None:
            result["suggested_fix"] = self.suggested_fix
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ValidationError:
        """Create ValidationError from dictionary data."""
        return cls(
            field_name=data["field_name"],
            error_code=data["error_code"],
            message=data["message"],
            suggested_fix=data.get("suggested_fix"),
        )


@dataclass
class ValidationWarning:
    """Represents a non-blocking validation warning.

    ValidationWarning is used for potential issues that don't prevent
    hook functionality but may indicate suboptimal configuration.

    Attributes:
        field_name: Name of the field with the warning
        warning_code: Standardized warning code for programmatic handling
        message: Human-readable warning description
    """
    field_name: str
    warning_code: str
    message: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "field_name": self.field_name,
            "warning_code": self.warning_code,
            "message": self.message,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ValidationWarning:
        """Create ValidationWarning from dictionary data."""
        return cls(
            field_name=data["field_name"],
            warning_code=data["warning_code"],
            message=data["message"],
        )


@dataclass
class ValidationResult:
    """Result of hook configuration validation.

    ValidationResult provides a comprehensive outcome of validating hook
    configurations, including errors, warnings, and suggestions for improvement.

    Attributes:
        is_valid: Overall validation result (True if no errors)
        errors: List of field-specific validation errors (ValidationError objects or dicts)
        warnings: List of non-blocking validation warnings (ValidationWarning objects or dicts)
        suggestions: List of improvement suggestions for the configuration
    """
    is_valid: bool
    errors: List[Union[ValidationError, Dict[str, Any]]] = field(default_factory=list)
    warnings: List[Union[ValidationWarning, Dict[str, Any]]] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

    def add_error(
        self,
        field_name: str,
        error_code: str,
        message: str,
        suggested_fix: Optional[str] = None
    ) -> None:
        """Add a validation error and mark result as invalid.

        Args:
            field_name: Name of the field with error
            error_code: Standardized error code
            message: Human-readable error description
            suggested_fix: Optional suggestion for fixing the error
        """
        self.errors.append(ValidationError(
            field_name=field_name,
            error_code=error_code,
            message=message,
            suggested_fix=suggested_fix
        ))
        self.is_valid = False

    def add_warning(
        self,
        field_name: str,
        warning_code: str,
        message: str
    ) -> None:
        """Add a validation warning.

        Args:
            field_name: Name of the field with warning
            warning_code: Standardized warning code
            message: Human-readable warning description
        """
        self.warnings.append(ValidationWarning(
            field_name=field_name,
            warning_code=warning_code,
            message=message
        ))

    def add_suggestion(self, suggestion: str) -> None:
        """Add an improvement suggestion.

        Args:
            suggestion: Improvement suggestion text
        """
        self.suggestions.append(suggestion)

    def has_errors(self) -> bool:
        """Check if result contains any errors.

        Returns:
            True if there are validation errors
        """
        return len(self.errors) > 0

    def has_warnings(self) -> bool:
        """Check if result contains any warnings.

        Returns:
            True if there are validation warnings
        """
        return len(self.warnings) > 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation.

        Returns:
            Dictionary representation compatible with API contracts
        """
        # Convert errors to dict format
        errors_list = []
        for error in self.errors:
            if isinstance(error, ValidationError):
                errors_list.append(error.to_dict())
            else:
                errors_list.append(error)

        # Convert warnings to dict format
        warnings_list = []
        for warning in self.warnings:
            if isinstance(warning, ValidationWarning):
                warnings_list.append(warning.to_dict())
            else:
                warnings_list.append(warning)

        return {
            "is_valid": self.is_valid,
            "errors": errors_list,
            "warnings": warnings_list,
            "suggestions": self.suggestions.copy(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ValidationResult:
        """Create ValidationResult from dictionary data.

        Args:
            data: Dictionary containing validation result data

        Returns:
            ValidationResult instance
        """
        # Process errors - can be either dicts or ValidationError objects
        errors = []
        for error_data in data.get("errors", []):
            if isinstance(error_data, dict):
                # Try to create ValidationError from dict, fall back to keeping as dict
                if all(key in error_data for key in ["field_name", "error_code", "message"]):
                    errors.append(ValidationError.from_dict(error_data))
                else:
                    errors.append(error_data)
            else:
                errors.append(error_data)

        # Process warnings - can be either dicts or ValidationWarning objects
        warnings = []
        for warning_data in data.get("warnings", []):
            if isinstance(warning_data, dict):
                # Try to create ValidationWarning from dict, fall back to keeping as dict
                if all(key in warning_data for key in ["field_name", "warning_code", "message"]):
                    warnings.append(ValidationWarning.from_dict(warning_data))
                else:
                    warnings.append(warning_data)
            else:
                warnings.append(warning_data)

        return cls(
            is_valid=data["is_valid"],
            errors=errors,
            warnings=warnings,
            suggestions=data.get("suggestions", []).copy(),
        )

    @classmethod
    def success(cls, suggestions: Optional[List[str]] = None) -> ValidationResult:
        """Create a successful validation result.

        Args:
            suggestions: Optional list of improvement suggestions

        Returns:
            ValidationResult indicating successful validation
        """
        return cls(
            is_valid=True,
            suggestions=suggestions or [],
        )

    @classmethod
    def failure(
        cls,
        errors: Optional[List[ValidationError]] = None,
        warnings: Optional[List[ValidationWarning]] = None,
        suggestions: Optional[List[str]] = None
    ) -> ValidationResult:
        """Create a failed validation result.

        Args:
            errors: List of validation errors
            warnings: List of validation warnings
            suggestions: List of improvement suggestions

        Returns:
            ValidationResult indicating failed validation
        """
        return cls(
            is_valid=False,
            errors=errors or [],
            warnings=warnings or [],
            suggestions=suggestions or [],
        )

    def merge(self, other: ValidationResult) -> None:
        """Merge another validation result into this one.

        Args:
            other: Another ValidationResult to merge
        """
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        self.suggestions.extend(other.suggestions)

        # Update validity status
        if other.has_errors():
            self.is_valid = False


@dataclass
class SaveResult:
    """Result of settings file save operation.

    Properties:
        success: Whether the save operation succeeded
        backup_path: Path to backup file if created
        original_size: Size of original file in bytes
        new_size: Size of new file in bytes
    """
    success: bool
    backup_path: Optional[Path] = None
    original_size: int = 0
    new_size: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "success": self.success,
            "backup_path": str(self.backup_path) if self.backup_path else None,
            "original_size": self.original_size,
            "new_size": self.new_size,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SaveResult:
        """Create SaveResult from dictionary data."""
        backup_path = None
        if data.get("backup_path"):
            backup_path = Path(data["backup_path"])

        return cls(
            success=data["success"],
            backup_path=backup_path,
            original_size=data.get("original_size", 0),
            new_size=data.get("new_size", 0),
        )

    @classmethod
    def success_result(cls, backup_path: Optional[Path] = None,
                      original_size: int = 0, new_size: int = 0) -> SaveResult:
        """Create a successful save result."""
        return cls(
            success=True,
            backup_path=backup_path,
            original_size=original_size,
            new_size=new_size,
        )

    @classmethod
    def failure_result(cls) -> SaveResult:
        """Create a failed save result."""
        return cls(success=False)


@dataclass
class ModificationResult:
    """Result of hook modification operation.

    Properties:
        success: Whether the modification succeeded
        modified_hook: The hook configuration that was modified
        hook_count_before: Number of hooks before modification
        hook_count_after: Number of hooks after modification
        validation_warnings: Any validation warnings for the modified hook
    """
    success: bool
    modified_hook: Dict[str, Any] = field(default_factory=dict)
    hook_count_before: int = 0
    hook_count_after: int = 0
    validation_warnings: List[Union[ValidationWarning, Dict[str, Any]]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        # Convert warnings to dict format
        warnings_list = []
        for warning in self.validation_warnings:
            if isinstance(warning, ValidationWarning):
                warnings_list.append(warning.to_dict())
            else:
                warnings_list.append(warning)

        return {
            "success": self.success,
            "modified_hook": self.modified_hook.copy(),
            "hook_count_before": self.hook_count_before,
            "hook_count_after": self.hook_count_after,
            "validation_warnings": warnings_list,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ModificationResult:
        """Create ModificationResult from dictionary data."""
        # Process warnings
        warnings = []
        for warning_data in data.get("validation_warnings", []):
            if isinstance(warning_data, dict):
                if all(key in warning_data for key in ["field_name", "warning_code", "message"]):
                    warnings.append(ValidationWarning.from_dict(warning_data))
                else:
                    warnings.append(warning_data)
            else:
                warnings.append(warning_data)

        return cls(
            success=data["success"],
            modified_hook=data.get("modified_hook", {}).copy(),
            hook_count_before=data.get("hook_count_before", 0),
            hook_count_after=data.get("hook_count_after", 0),
            validation_warnings=warnings,
        )

    @classmethod
    def success_result(cls, modified_hook: Dict[str, Any],
                      hook_count_before: int, hook_count_after: int,
                      validation_warnings: Optional[List[ValidationWarning]] = None) -> ModificationResult:
        """Create a successful modification result."""
        return cls(
            success=True,
            modified_hook=modified_hook.copy(),
            hook_count_before=hook_count_before,
            hook_count_after=hook_count_after,
            validation_warnings=validation_warnings or [],
        )

    @classmethod
    def failure_result(cls, hook_count_before: int = 0) -> ModificationResult:
        """Create a failed modification result."""
        return cls(
            success=False,
            hook_count_before=hook_count_before,
            hook_count_after=hook_count_before,
        )


@dataclass
class ScriptGenerationResult:
    """Result of script generation from template.

    This dataclass contains all information about the script generation process,
    including success status, generated file information, template metadata,
    and applied customizations.

    Attributes:
        success: Whether script generation succeeded
        generated_file: Path to the generated script file (if successful)
        template_used: Template ID/name that was used for generation
        executable_set: Whether execute permissions were set on the script
        added_to_settings: Whether the script was automatically added to settings
        customizations_applied: Dictionary of customization options that were applied
        validation_result: Template and script validation results
        generation_time: Time taken for script generation in seconds
        script_size: Size of generated script in bytes
        error_message: Error message if generation failed
    """
    success: bool
    generated_file: Optional[Path] = None
    template_used: str = ""
    executable_set: bool = False
    added_to_settings: bool = False
    customizations_applied: Dict[str, Any] = field(default_factory=dict)
    validation_result: Optional[ValidationResult] = None
    generation_time: float = 0.0
    script_size: int = 0
    error_message: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate result data after initialization."""
        if self.success and not self.generated_file:
            raise ValueError("successful generation must have a generated_file")
        if not self.success and not self.error_message:
            raise ValueError("failed generation must have an error_message")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        result = {
            "success": self.success,
            "generated_file": str(self.generated_file) if self.generated_file else None,
            "template_used": self.template_used,
            "executable_set": self.executable_set,
            "added_to_settings": self.added_to_settings,
            "customizations_applied": self.customizations_applied.copy(),
            "generation_time": self.generation_time,
            "script_size": self.script_size,
        }

        if self.validation_result:
            result["validation_result"] = self.validation_result.to_dict()

        if self.error_message:
            result["error_message"] = self.error_message

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ScriptGenerationResult:
        """Create ScriptGenerationResult from dictionary data."""
        generated_file = None
        if data.get("generated_file"):
            generated_file = Path(data["generated_file"])

        validation_result = None
        if data.get("validation_result"):
            validation_result = ValidationResult.from_dict(data["validation_result"])

        return cls(
            success=data["success"],
            generated_file=generated_file,
            template_used=data.get("template_used", ""),
            executable_set=data.get("executable_set", False),
            added_to_settings=data.get("added_to_settings", False),
            customizations_applied=data.get("customizations_applied", {}).copy(),
            validation_result=validation_result,
            generation_time=data.get("generation_time", 0.0),
            script_size=data.get("script_size", 0),
            error_message=data.get("error_message"),
        )

    @classmethod
    def success_result(
        cls,
        generated_file: Path,
        template_used: str,
        executable_set: bool = False,
        added_to_settings: bool = False,
        customizations_applied: Optional[Dict[str, Any]] = None,
        validation_result: Optional[ValidationResult] = None,
        generation_time: float = 0.0,
        script_size: int = 0
    ) -> ScriptGenerationResult:
        """Create a successful script generation result."""
        return cls(
            success=True,
            generated_file=generated_file,
            template_used=template_used,
            executable_set=executable_set,
            added_to_settings=added_to_settings,
            customizations_applied=customizations_applied or {},
            validation_result=validation_result,
            generation_time=generation_time,
            script_size=script_size,
        )

    @classmethod
    def failure_result(
        cls,
        error_message: str,
        template_used: str = "",
        validation_result: Optional[ValidationResult] = None,
        generation_time: float = 0.0
    ) -> ScriptGenerationResult:
        """Create a failed script generation result."""
        return cls(
            success=False,
            template_used=template_used,
            validation_result=validation_result,
            generation_time=generation_time,
            error_message=error_message,
        )
