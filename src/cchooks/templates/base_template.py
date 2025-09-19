"""BaseTemplate abstract class for hook templates.

This module defines the abstract base class for all hook templates in the cchooks
system. It provides the common interface that all template implementations must
follow, along with supporting data classes and decorators.

The BaseTemplate class defines the contract for:
- Template metadata (name, description, supported events)
- Script generation from configuration
- Configuration validation with customization schemas
- Dependency management
- Default configuration provision

This serves as the foundation for both built-in and user-defined templates.
"""

from __future__ import annotations

import abc
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, Union

from ..models.validation import ValidationResult
from ..types.enums import HookEventType


@dataclass
class TemplateConfig:
    """Configuration for template script generation.

    This dataclass contains all the information needed to generate a hook script
    from a template, including the target event type, customization options,
    and output path.

    Attributes:
        template_id: Unique identifier of the template to use
        event_type: Hook event type the generated script will handle
        customization: Dictionary of template-specific customization options
        output_path: Path where the generated script will be saved
        matcher: Optional tool name pattern for PreToolUse/PostToolUse events
        timeout: Optional execution timeout in seconds for the hook
    """
    template_id: str
    event_type: HookEventType
    customization: Dict[str, Any]
    output_path: Path
    matcher: Optional[str] = None
    timeout: Optional[int] = None

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        # Validate that matcher is provided for tool events
        if self.event_type.requires_matcher() and not self.matcher:
            raise ValueError(
                f"matcher field is required for {self.event_type.value} events"
            )

        # Validate timeout if provided
        if self.timeout is not None and self.timeout <= 0:
            raise ValueError("timeout must be a positive integer")

        # Ensure output_path is a Path object
        if isinstance(self.output_path, str):
            self.output_path = Path(self.output_path)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        result = {
            "template_id": self.template_id,
            "event_type": self.event_type.value,
            "customization": self.customization.copy(),
            "output_path": str(self.output_path),
        }
        if self.matcher is not None:
            result["matcher"] = self.matcher
        if self.timeout is not None:
            result["timeout"] = self.timeout
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TemplateConfig:
        """Create TemplateConfig from dictionary data."""
        return cls(
            template_id=data["template_id"],
            event_type=HookEventType.from_string(data["event_type"]),
            customization=data["customization"],
            output_path=Path(data["output_path"]),
            matcher=data.get("matcher"),
            timeout=data.get("timeout"),
        )


class BaseTemplate(abc.ABC):
    """Abstract base class for all hook templates.

    This class defines the interface that all hook templates must implement.
    Templates are responsible for generating Python hook scripts based on
    configuration and customization options.

    Each template provides:
    - Metadata about what it does and which events it supports
    - Script generation logic from configuration
    - Validation of customization options
    - Default configuration values
    - Dependency requirements

    Subclasses must implement all abstract methods and properties.
    """

    # Abstract properties that subclasses must define
    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Human-readable name of the template.

        Returns:
            Template name for display purposes
        """
        pass

    @property
    @abc.abstractmethod
    def description(self) -> str:
        """Description of what this template does.

        Returns:
            Template description for help text and documentation
        """
        pass

    @property
    @abc.abstractmethod
    def supported_events(self) -> List[HookEventType]:
        """List of hook event types this template supports.

        Returns:
            List of HookEventType values this template can generate scripts for
        """
        pass

    @property
    @abc.abstractmethod
    def customization_schema(self) -> Dict[str, Any]:
        """JSON schema for validating customization options.

        This schema defines the structure and validation rules for the
        customization dictionary passed to generate() and validate_config().

        Returns:
            JSON schema dictionary for customization validation
        """
        pass

    # Abstract methods that subclasses must implement
    @abc.abstractmethod
    def generate(self, config: TemplateConfig) -> str:
        """Generate hook script content from configuration.

        This is the core method that generates the actual Python script content
        based on the provided configuration and customization options.

        Args:
            config: Template configuration with event type and customization

        Returns:
            Generated Python script content as a string

        Raises:
            ValueError: If configuration is invalid for this template
            RuntimeError: If script generation fails
        """
        pass

    @abc.abstractmethod
    def validate_config(self, config: Dict[str, Any]) -> ValidationResult:
        """Validate template-specific customization configuration.

        This method validates the customization options against the template's
        schema and requirements. It should check for required fields, valid
        values, and any template-specific constraints.

        Args:
            config: Customization configuration dictionary to validate

        Returns:
            ValidationResult with errors, warnings, and suggestions
        """
        pass

    @abc.abstractmethod
    def get_default_config(self) -> Dict[str, Any]:
        """Get default customization configuration for this template.

        Returns the default values for all customization options. This is used
        when no customization is provided or as a base for user customization.

        Returns:
            Dictionary of default configuration values
        """
        pass

    @abc.abstractmethod
    def get_dependencies(self) -> List[str]:
        """Get list of dependencies required by this template.

        Returns a list of Python packages, system tools, or other dependencies
        that must be available for the generated script to work properly.

        Returns:
            List of dependency names (e.g., ["requests", "git"])
        """
        pass

    # Concrete helper methods
    def get_template_id(self) -> str:
        """Get unique identifier for this template.

        By default, uses the class name converted to kebab-case.
        Subclasses can override this for custom IDs.

        Returns:
            Unique template identifier
        """
        # Convert CamelCase to kebab-case
        class_name = self.__class__.__name__
        if class_name.endswith("Template"):
            class_name = class_name[:-8]  # Remove "Template" suffix

        # Convert to kebab-case
        result = ""
        for i, char in enumerate(class_name):
            if char.isupper() and i > 0:
                result += "-"
            result += char.lower()

        return result

    def supports_event(self, event_type: HookEventType) -> bool:
        """Check if this template supports a specific event type.

        Args:
            event_type: Hook event type to check

        Returns:
            True if template supports the event type
        """
        return event_type in self.supported_events

    def validate_event_compatibility(self, event_type: HookEventType) -> None:
        """Validate that this template supports the given event type.

        Args:
            event_type: Hook event type to validate

        Raises:
            ValueError: If template doesn't support the event type
        """
        if not self.supports_event(event_type):
            supported = [event.value for event in self.supported_events]
            raise ValueError(
                f"Template '{self.name}' does not support event type "
                f"'{event_type.value}'. Supported events: {supported}"
            )

    def create_script_header(self, config: TemplateConfig) -> str:
        """Create standard header for generated scripts.

        Args:
            config: Template configuration

        Returns:
            Script header with shebang, encoding, and metadata
        """
        dependencies = self.get_dependencies()
        deps_comment = f"# Dependencies: {', '.join(dependencies)}" if dependencies else ""

        return f'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generated hook script from template: {self.name}
Event type: {config.event_type.value}
Generated for: {config.output_path.name}

{self.description}
"""

{deps_comment}

import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from cchooks import create_context

'''

    def create_main_function(self, event_type: HookEventType, custom_logic: str) -> str:
        """Create main function with event-specific context handling.

        Args:
            event_type: Hook event type
            custom_logic: Template-specific logic to insert

        Returns:
            Main function code
        """
        return f'''
def main() -> None:
    """Main hook entry point."""
    try:
        # Create context from stdin
        context = create_context()

        # Validate event type
        if context.hook_event_name != "{event_type.value}":
            context.output.exit_non_block(
                f"Expected {event_type.value} event, got {{context.hook_event_name}}"
            )
            return

        # Template-specific logic
{self._indent_code(custom_logic, 8)}

    except Exception as e:
        # Handle unexpected errors
        print(json.dumps({{
            "continue": False,
            "stopReason": f"Hook error: {{str(e)}}",
            "suppressOutput": False
        }}))
        sys.exit(1)


if __name__ == "__main__":
    main()
'''

    def _indent_code(self, code: str, spaces: int) -> str:
        """Indent code by specified number of spaces.

        Args:
            code: Code to indent
            spaces: Number of spaces to indent

        Returns:
            Indented code
        """
        indent = " " * spaces
        lines = code.strip().split("\n")
        return "\n".join(indent + line if line.strip() else line for line in lines)

    def validate_schema(
        self,
        config: Dict[str, Any],
        schema: Dict[str, Any]
    ) -> ValidationResult:
        """Basic JSON schema validation helper.

        Args:
            config: Configuration to validate
            schema: JSON schema to validate against

        Returns:
            ValidationResult with validation errors
        """
        result = ValidationResult(is_valid=True)

        # Check required fields
        required = schema.get("required", [])
        for field in required:
            if field not in config:
                result.add_error(
                    field_name=field,
                    error_code="MISSING_REQUIRED_FIELD",
                    message=f"Required field '{field}' is missing",
                    suggested_fix=f"Add '{field}' field to configuration"
                )

        # Check field types and constraints
        properties = schema.get("properties", {})
        for field, value in config.items():
            if field in properties:
                field_schema = properties[field]
                field_type = field_schema.get("type")

                # Type validation
                if field_type and not self._validate_type(value, field_type):
                    result.add_error(
                        field_name=field,
                        error_code="INVALID_TYPE",
                        message=f"Field '{field}' must be of type {field_type}",
                        suggested_fix=f"Change '{field}' to {field_type} type"
                    )

                # Enum validation
                enum_values = field_schema.get("enum")
                if enum_values and value not in enum_values:
                    result.add_error(
                        field_name=field,
                        error_code="INVALID_ENUM_VALUE",
                        message=f"Field '{field}' must be one of: {enum_values}",
                        suggested_fix=f"Use one of the valid values: {enum_values}"
                    )

        return result

    def _validate_type(self, value: Any, expected_type: str) -> bool:
        """Validate that value matches expected JSON schema type.

        Args:
            value: Value to validate
            expected_type: JSON schema type name

        Returns:
            True if value matches type
        """
        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
        }

        expected_python_type = type_map.get(expected_type)
        if expected_python_type is None:
            return True  # Unknown type, assume valid

        return isinstance(value, expected_python_type)


# Template registration decorator
_REGISTERED_TEMPLATES: Dict[str, Type[BaseTemplate]] = {}


def template(
    template_id: Optional[str] = None,
    name: Optional[str] = None,
    description: Optional[str] = None,
    supported_events: Optional[List[HookEventType]] = None
) -> Any:
    """Decorator for registering template classes.

    This decorator can be used to register template classes and optionally
    override their metadata. The decorator extracts metadata from the class
    and makes it available for template discovery.

    Args:
        template_id: Override template ID (default: derived from class name)
        name: Override template name (default: class.name property)
        description: Override description (default: class.description property)
        supported_events: Override supported events (default: class.supported_events)

    Returns:
        Decorated class with registration metadata

    Example:
        @template(
            template_id="security-guard",
            name="Security Guard",
            description="Multi-tool security validation"
        )
        class SecurityGuardTemplate(BaseTemplate):
            # Implementation...
    """
    def decorator(cls: Type[BaseTemplate]) -> Type[BaseTemplate]:
        # Validate that class inherits from BaseTemplate
        if not issubclass(cls, BaseTemplate):
            raise TypeError(f"Template class {cls.__name__} must inherit from BaseTemplate")

        # Create instance to extract metadata
        try:
            instance = cls()
            actual_template_id = template_id or instance.get_template_id()

            # Store metadata as class attributes
            cls._template_id = actual_template_id
            cls._template_name = name or instance.name
            cls._template_description = description or instance.description
            cls._supported_events = supported_events or instance.supported_events

            # Register template
            _REGISTERED_TEMPLATES[actual_template_id] = cls

        except Exception as e:
            raise RuntimeError(f"Failed to register template {cls.__name__}: {e}")

        return cls

    return decorator


def get_registered_templates() -> Dict[str, Type[BaseTemplate]]:
    """Get all registered template classes.

    Returns:
        Dictionary mapping template IDs to template classes
    """
    return _REGISTERED_TEMPLATES.copy()


def get_template_class(template_id: str) -> Optional[Type[BaseTemplate]]:
    """Get template class by ID.

    Args:
        template_id: Template identifier

    Returns:
        Template class or None if not found
    """
    return _REGISTERED_TEMPLATES.get(template_id)


def clear_registered_templates() -> None:
    """Clear all registered templates (mainly for testing)."""
    _REGISTERED_TEMPLATES.clear()


# Utility functions for template validation and script generation

def validate_template_config(
    template_class: Type[BaseTemplate],
    config: Dict[str, Any]
) -> ValidationResult:
    """Validate configuration for a specific template class.

    Args:
        template_class: Template class to validate against
        config: Configuration to validate

    Returns:
        ValidationResult with validation outcome
    """
    try:
        instance = template_class()
        return instance.validate_config(config)
    except Exception as e:
        result = ValidationResult(is_valid=False)
        result.add_error(
            field_name="template",
            error_code="TEMPLATE_ERROR",
            message=f"Template validation failed: {str(e)}",
            suggested_fix="Check template implementation"
        )
        return result


def generate_script_from_template(
    template_class: Type[BaseTemplate],
    config: TemplateConfig
) -> str:
    """Generate script from template class and configuration.

    Args:
        template_class: Template class to use
        config: Template configuration

    Returns:
        Generated script content

    Raises:
        ValueError: If configuration is invalid
        RuntimeError: If script generation fails
    """
    instance = template_class()

    # Validate event compatibility
    instance.validate_event_compatibility(config.event_type)

    # Validate customization config
    validation_result = instance.validate_config(config.customization)
    if not validation_result.is_valid:
        errors = [f"{err.field_name}: {err.message}" for err in validation_result.errors]
        raise ValueError(f"Invalid template configuration: {'; '.join(errors)}")

    # Generate script
    return instance.generate(config)


def check_template_dependencies(
    template_class: Type[BaseTemplate]
) -> List[str]:
    """Check which dependencies are missing for a template.

    Args:
        template_class: Template class to check

    Returns:
        List of missing dependency names
    """
    instance = template_class()
    dependencies = instance.get_dependencies()
    missing = []

    for dependency in dependencies:
        try:
            # Try to import Python packages
            if "." not in dependency and dependency.isidentifier():
                __import__(dependency)
            # For system tools, you might want to check PATH
            # This is a basic implementation
        except ImportError:
            missing.append(dependency)

    return missing
