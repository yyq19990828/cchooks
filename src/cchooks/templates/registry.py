"""TemplateRegistry service for hook template management.

This module implements the central registry for managing hook templates in the cchooks
system. It provides template registration, discovery, loading, and management capabilities
as specified in the T027 task and data-model.md specifications.

The TemplateRegistry serves as the central hub for:
- Built-in template management
- User-registered template tracking
- Template discovery and search
- Template persistence and caching
- Integration with BaseTemplate interface
- Support for template CLI commands (T034-T037)

Key Features:
- Multi-source template support (builtin, user, file, plugin)
- Template conflict detection and resolution
- Persistent registry with file-based storage
- Template validation and dependency checking
- Event-based filtering and compatibility checks
- Version control and compatibility tracking
"""

from __future__ import annotations

import importlib
import inspect
import json
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Type, Union

from ..exceptions import CCHooksError
from ..models.validation import ValidationResult
from ..types.enums import HookEventType, TemplateSource
from .base_template import BaseTemplate, TemplateConfig, get_registered_templates


@dataclass
class HookTemplate:
    """Represents a hook template with its metadata and implementation.

    This dataclass contains all information about a template, including its
    metadata, capabilities, dependencies, and implementation class reference.

    Attributes:
        template_id: Unique template identifier (kebab-case)
        name: Human-readable template name
        supported_events: List of compatible hook event types
        description: Template description for help and documentation
        customization_options: Available customization parameters with schemas
        dependencies: Required Python packages or system tools
        source: Template source (builtin/user/file/plugin)
        template_class: Template implementation class
        version: Template version for compatibility tracking
    """
    template_id: str
    name: str
    supported_events: List[HookEventType]
    description: str
    customization_options: Dict[str, Any]
    dependencies: List[str]
    source: TemplateSource
    template_class: Type[BaseTemplate]
    version: str = "1.0.0"

    def __post_init__(self) -> None:
        """Validate template data after initialization."""
        if not self.template_id:
            raise ValueError("template_id cannot be empty")
        if not self.name:
            raise ValueError("name cannot be empty")
        if not self.supported_events:
            raise ValueError("supported_events cannot be empty")
        if not issubclass(self.template_class, BaseTemplate):
            raise ValueError("template_class must be a BaseTemplate subclass")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation for serialization."""
        return {
            "template_id": self.template_id,
            "name": self.name,
            "supported_events": [event.value for event in self.supported_events],
            "description": self.description,
            "customization_options": self.customization_options.copy(),
            "dependencies": self.dependencies.copy(),
            "source": self.source.value,
            "template_class": f"{self.template_class.__module__}.{self.template_class.__name__}",
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], template_class: Type[BaseTemplate]) -> HookTemplate:
        """Create HookTemplate from dictionary data.

        Args:
            data: Dictionary containing template metadata
            template_class: Template implementation class

        Returns:
            HookTemplate instance
        """
        return cls(
            template_id=data["template_id"],
            name=data["name"],
            supported_events=[HookEventType.from_string(event) for event in data["supported_events"]],
            description=data["description"],
            customization_options=data.get("customization_options", {}),
            dependencies=data.get("dependencies", []),
            source=TemplateSource.from_string(data["source"]),
            template_class=template_class,
            version=data.get("version", "1.0.0"),
        )

    @classmethod
    def from_template_class(cls, template_class: Type[BaseTemplate],
                          source: TemplateSource = TemplateSource.USER) -> HookTemplate:
        """Create HookTemplate from a BaseTemplate class.

        Args:
            template_class: Template implementation class
            source: Template source type

        Returns:
            HookTemplate instance
        """
        # Create instance to extract metadata
        instance = template_class()

        return cls(
            template_id=instance.get_template_id(),
            name=instance.name,
            supported_events=instance.supported_events.copy(),
            description=instance.description,
            customization_options=instance.customization_schema.copy(),
            dependencies=instance.get_dependencies().copy(),
            source=source,
            template_class=template_class,
            version=getattr(template_class, '_template_version', '1.0.0'),
        )

    def supports_event(self, event_type: HookEventType) -> bool:
        """Check if this template supports a specific event type.

        Args:
            event_type: Hook event type to check

        Returns:
            True if template supports the event type
        """
        return event_type in self.supported_events

    def get_instance(self) -> BaseTemplate:
        """Get a new instance of the template class.

        Returns:
            New template instance

        Raises:
            CCHooksError: If template instantiation fails
        """
        try:
            return self.template_class()
        except Exception as e:
            raise CCHooksError(f"Failed to instantiate template '{self.template_id}': {e}")

    def validate_config(self, config: Dict[str, Any]) -> ValidationResult:
        """Validate configuration for this template.

        Args:
            config: Configuration to validate

        Returns:
            ValidationResult with validation outcome
        """
        try:
            instance = self.get_instance()
            return instance.validate_config(config)
        except Exception as e:
            result = ValidationResult(is_valid=False)
            result.add_error(
                field_name="template",
                error_code="VALIDATION_ERROR",
                message=f"Template validation failed: {str(e)}",
                suggested_fix="Check template implementation and configuration"
            )
            return result

    def generate_script(self, config: TemplateConfig) -> str:
        """Generate script using this template.

        Args:
            config: Template configuration

        Returns:
            Generated script content

        Raises:
            CCHooksError: If script generation fails
        """
        try:
            instance = self.get_instance()

            # Validate event compatibility
            if not self.supports_event(config.event_type):
                raise CCHooksError(
                    f"Template '{self.template_id}' does not support event type '{config.event_type.value}'"
                )

            return instance.generate(config)
        except Exception as e:
            raise CCHooksError(f"Failed to generate script with template '{self.template_id}': {e}")


class TemplateRegistryError(CCHooksError):
    """Template registry specific errors."""
    pass


class TemplateRegistry:
    """Central registry for managing hook templates.

    The TemplateRegistry manages all aspects of template lifecycle including
    registration, discovery, persistence, and validation. It supports multiple
    template sources and provides integration with the BaseTemplate interface.

    Features:
    - Multi-source template management (builtin, user, file, plugin)
    - Template conflict detection and resolution
    - Persistent registry with JSON storage
    - Template search and filtering
    - Dependency validation
    - Version compatibility checking

    Attributes:
        builtin_templates: Dictionary of built-in templates
        user_templates: Dictionary of user-registered templates
        template_paths: List of template search paths
        registry_file: Path to template registry file
    """

    def __init__(self, registry_file: Optional[Path] = None,
                 template_paths: Optional[List[Path]] = None):
        """Initialize TemplateRegistry.

        Args:
            registry_file: Path to registry persistence file
            template_paths: List of template search paths
        """
        self.builtin_templates: Dict[str, HookTemplate] = {}
        self.user_templates: Dict[str, HookTemplate] = {}
        self.template_paths: List[Path] = template_paths or []
        self.registry_file: Path = registry_file or self._get_default_registry_file()

        # Template cache and state
        self._cache: Dict[str, HookTemplate] = {}
        self._last_scan_time: float = 0
        self._scan_interval: float = 300  # 5 minutes

        # Initialize registry
        self._discover_builtin_templates()
        self._load_registry()

    def _get_default_registry_file(self) -> Path:
        """Get default registry file path."""
        # Use ~/.claude/ directory for template registry
        user_home = Path.home()
        claude_dir = user_home / ".claude"
        return claude_dir / "template_registry.json"

    def _discover_builtin_templates(self) -> None:
        """Discover and load built-in templates."""
        # Load templates from decorator registry
        registered_templates = get_registered_templates()

        for template_id, template_class in registered_templates.items():
            try:
                template = HookTemplate.from_template_class(
                    template_class,
                    source=TemplateSource.BUILTIN
                )
                self.builtin_templates[template_id] = template
            except Exception as e:
                # Log error but continue with other templates
                print(f"Warning: Failed to load builtin template '{template_id}': {e}")

        # Discover templates in builtin directory
        builtin_dir = Path(__file__).parent / "builtin"
        if builtin_dir.exists():
            self._scan_directory_for_templates(builtin_dir, TemplateSource.BUILTIN)

    def _scan_directory_for_templates(self, directory: Path, source: TemplateSource) -> None:
        """Scan directory for template modules.

        Args:
            directory: Directory to scan
            source: Template source type
        """
        for python_file in directory.glob("*.py"):
            if python_file.name.startswith("__"):
                continue

            try:
                # Import module and look for BaseTemplate subclasses
                module_name = f"cchooks.templates.builtin.{python_file.stem}"
                module = importlib.import_module(module_name)

                for name in dir(module):
                    obj = getattr(module, name)
                    if (inspect.isclass(obj) and
                        issubclass(obj, BaseTemplate) and
                        obj != BaseTemplate):

                        try:
                            template = HookTemplate.from_template_class(obj, source)
                            if source == TemplateSource.BUILTIN:
                                self.builtin_templates[template.template_id] = template
                            else:
                                self.user_templates[template.template_id] = template
                        except Exception as e:
                            print(f"Warning: Failed to load template from {python_file}: {e}")

            except Exception as e:
                print(f"Warning: Failed to import template module {python_file}: {e}")

    def _load_registry(self) -> None:
        """Load registry from persistent storage."""
        if not self.registry_file.exists():
            return

        try:
            with open(self.registry_file, encoding='utf-8') as f:
                data = json.load(f)

            # Load user templates (builtin templates are discovered automatically)
            user_templates_data = data.get("user_templates", {})
            for template_id, template_data in user_templates_data.items():
                try:
                    # Import template class
                    class_path = template_data["template_class"]
                    module_name, class_name = class_path.rsplit(".", 1)
                    module = importlib.import_module(module_name)
                    template_class = getattr(module, class_name)

                    template = HookTemplate.from_dict(template_data, template_class)
                    self.user_templates[template_id] = template

                except Exception as e:
                    print(f"Warning: Failed to load user template '{template_id}': {e}")

        except Exception as e:
            print(f"Warning: Failed to load template registry: {e}")

    def _save_registry(self) -> None:
        """Save registry to persistent storage."""
        try:
            # Ensure registry directory exists
            self.registry_file.parent.mkdir(parents=True, exist_ok=True)

            # Prepare data for serialization
            data = {
                "version": "1.0.0",
                "last_updated": time.time(),
                "user_templates": {
                    template_id: template.to_dict()
                    for template_id, template in self.user_templates.items()
                },
                "template_paths": [str(path) for path in self.template_paths],
            }

            # Write to file with backup
            backup_file = self.registry_file.with_suffix(".json.bak")
            if self.registry_file.exists():
                shutil.copy2(self.registry_file, backup_file)

            with open(self.registry_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            raise TemplateRegistryError(f"Failed to save template registry: {e}")

    def register_template(self, template_id: str, template_class: Type[BaseTemplate]) -> None:
        """Register a new template.

        Args:
            template_id: Unique template identifier
            template_class: Template implementation class

        Raises:
            TemplateRegistryError: If registration fails or template already exists
        """
        if not template_id:
            raise TemplateRegistryError("Template ID cannot be empty")

        if not issubclass(template_class, BaseTemplate):
            raise TemplateRegistryError("Template class must inherit from BaseTemplate")

        # Check for conflicts
        if template_id in self.builtin_templates:
            raise TemplateRegistryError(
                f"Cannot register template '{template_id}': conflicts with builtin template"
            )

        if template_id in self.user_templates:
            raise TemplateRegistryError(
                f"Template '{template_id}' is already registered"
            )

        try:
            # Create template metadata
            template = HookTemplate.from_template_class(template_class, TemplateSource.USER)

            # Validate template
            validation_result = self._validate_template(template)
            if not validation_result.is_valid:
                errors = [f"{err.field_name}: {err.message}" for err in validation_result.errors]
                raise TemplateRegistryError(f"Template validation failed: {'; '.join(errors)}")

            # Register template
            self.user_templates[template_id] = template
            self._cache[template_id] = template

            # Persist registry
            self._save_registry()

        except Exception as e:
            if isinstance(e, TemplateRegistryError):
                raise
            raise TemplateRegistryError(f"Failed to register template '{template_id}': {e}")

    def unregister_template(self, template_id: str) -> None:
        """Remove a template from the registry.

        Args:
            template_id: Template identifier to remove

        Raises:
            TemplateRegistryError: If template cannot be removed
        """
        if template_id in self.builtin_templates:
            raise TemplateRegistryError(
                f"Cannot unregister builtin template '{template_id}'"
            )

        if template_id not in self.user_templates:
            raise TemplateRegistryError(
                f"Template '{template_id}' is not registered"
            )

        # Remove template
        del self.user_templates[template_id]
        self._cache.pop(template_id, None)

        # Persist registry
        self._save_registry()

    def get_template(self, template_id: str) -> HookTemplate:
        """Get template by ID.

        Args:
            template_id: Template identifier

        Returns:
            HookTemplate instance

        Raises:
            TemplateRegistryError: If template not found
        """
        # Check cache first
        if template_id in self._cache:
            return self._cache[template_id]

        # Check builtin templates
        if template_id in self.builtin_templates:
            template = self.builtin_templates[template_id]
            self._cache[template_id] = template
            return template

        # Check user templates
        if template_id in self.user_templates:
            template = self.user_templates[template_id]
            self._cache[template_id] = template
            return template

        raise TemplateRegistryError(f"Template '{template_id}' not found")

    def list_templates(self, event_filter: Optional[HookEventType] = None,
                      source_filter: Optional[TemplateSource] = None) -> List[HookTemplate]:
        """List available templates with optional filtering.

        Args:
            event_filter: Filter by supported event type
            source_filter: Filter by template source

        Returns:
            List of matching templates
        """
        # Collect all templates
        all_templates = {}

        # Add builtin templates (higher priority)
        all_templates.update(self.builtin_templates)

        # Add user templates (may override builtin with same ID)
        all_templates.update(self.user_templates)

        # Apply filters
        templates = list(all_templates.values())

        if event_filter:
            templates = [t for t in templates if t.supports_event(event_filter)]

        if source_filter:
            templates = [t for t in templates if t.source == source_filter]

        # Sort by name for consistent ordering
        templates.sort(key=lambda t: t.name)

        return templates

    def reload_templates(self) -> None:
        """Reload templates from all sources."""
        # Clear caches
        self._cache.clear()
        self.builtin_templates.clear()
        self.user_templates.clear()

        # Rediscover templates
        self._discover_builtin_templates()
        self._load_registry()

        # Scan additional paths
        for path in self.template_paths:
            if path.exists() and path.is_dir():
                self._scan_directory_for_templates(path, TemplateSource.FILE)

        self._last_scan_time = time.time()

    def search_templates(self, query: str,
                        event_filter: Optional[HookEventType] = None) -> List[HookTemplate]:
        """Search templates by name, description, or ID.

        Args:
            query: Search query string
            event_filter: Optional event type filter

        Returns:
            List of matching templates
        """
        query_lower = query.lower()
        templates = self.list_templates(event_filter=event_filter)

        matches = []
        for template in templates:
            # Search in template ID, name, and description
            if (query_lower in template.template_id.lower() or
                query_lower in template.name.lower() or
                query_lower in template.description.lower()):
                matches.append(template)

        return matches

    def get_templates_by_source(self, source: TemplateSource) -> List[HookTemplate]:
        """Get all templates from a specific source.

        Args:
            source: Template source

        Returns:
            List of templates from the source
        """
        return self.list_templates(source_filter=source)

    def validate_template_dependencies(self, template_id: str) -> ValidationResult:
        """Validate dependencies for a specific template.

        Args:
            template_id: Template identifier

        Returns:
            ValidationResult with dependency validation
        """
        try:
            template = self.get_template(template_id)
            result = ValidationResult(is_valid=True)

            # Check each dependency
            missing_deps = []
            for dependency in template.dependencies:
                if not self._check_dependency_available(dependency):
                    missing_deps.append(dependency)

            if missing_deps:
                result.is_valid = False
                result.add_error(
                    field_name="dependencies",
                    error_code="MISSING_DEPENDENCIES",
                    message=f"Missing dependencies: {', '.join(missing_deps)}",
                    suggested_fix=f"Install missing dependencies: {', '.join(missing_deps)}"
                )

            return result

        except TemplateRegistryError as e:
            result = ValidationResult(is_valid=False)
            result.add_error(
                field_name="template",
                error_code="TEMPLATE_NOT_FOUND",
                message=str(e)
            )
            return result

    def _check_dependency_available(self, dependency: str) -> bool:
        """Check if a dependency is available.

        Args:
            dependency: Dependency name

        Returns:
            True if dependency is available
        """
        try:
            # Try to import as Python package
            if dependency.replace("-", "_").isidentifier():
                importlib.import_module(dependency.replace("-", "_"))
                return True
        except ImportError:
            pass

        # Try to find as system command
        if shutil.which(dependency):
            return True

        return False

    def _validate_template(self, template: HookTemplate) -> ValidationResult:
        """Validate a template for registration.

        Args:
            template: Template to validate

        Returns:
            ValidationResult with validation outcome
        """
        result = ValidationResult(is_valid=True)

        # Validate template ID format
        if not template.template_id.replace("-", "").replace("_", "").isalnum():
            result.add_error(
                field_name="template_id",
                error_code="INVALID_TEMPLATE_ID",
                message="Template ID must contain only alphanumeric characters, hyphens, and underscores"
            )

        # Validate template class
        try:
            instance = template.get_instance()

            # Test basic functionality
            default_config = instance.get_default_config()
            validation_result = instance.validate_config(default_config)
            if not validation_result.is_valid:
                result.add_warning(
                    field_name="template_class",
                    warning_code="DEFAULT_CONFIG_INVALID",
                    message="Template's default configuration is invalid"
                )

        except Exception as e:
            result.add_error(
                field_name="template_class",
                error_code="TEMPLATE_INSTANTIATION_FAILED",
                message=f"Failed to instantiate template: {e}"
            )

        # Validate supported events
        if not template.supported_events:
            result.add_error(
                field_name="supported_events",
                error_code="NO_SUPPORTED_EVENTS",
                message="Template must support at least one event type"
            )

        return result

    def get_registry_stats(self) -> Dict[str, Any]:
        """Get registry statistics.

        Returns:
            Dictionary with registry statistics
        """
        builtin_count = len(self.builtin_templates)
        user_count = len(self.user_templates)

        # Count templates by event type
        event_counts = {}
        for template in self.list_templates():
            for event in template.supported_events:
                event_counts[event.value] = event_counts.get(event.value, 0) + 1

        # Count templates by source
        source_counts = {}
        for template in self.list_templates():
            source_counts[template.source.value] = source_counts.get(template.source.value, 0) + 1

        return {
            "total_templates": builtin_count + user_count,
            "builtin_templates": builtin_count,
            "user_templates": user_count,
            "templates_by_event": event_counts,
            "templates_by_source": source_counts,
            "registry_file": str(self.registry_file),
            "template_paths": [str(path) for path in self.template_paths],
            "last_scan_time": self._last_scan_time,
        }

    def cleanup_invalid_templates(self) -> Dict[str, List[str]]:
        """Remove invalid templates from registry.

        Returns:
            Dictionary with lists of removed template IDs by reason
        """
        removed = {
            "invalid_class": [],
            "missing_dependencies": [],
            "validation_failed": [],
        }

        # Check user templates (don't touch builtin)
        to_remove = []

        for template_id, template in self.user_templates.items():
            try:
                # Test instantiation
                instance = template.get_instance()

                # Test configuration validation
                default_config = instance.get_default_config()
                validation_result = instance.validate_config(default_config)

                if not validation_result.is_valid:
                    to_remove.append((template_id, "validation_failed"))

            except Exception:
                to_remove.append((template_id, "invalid_class"))

        # Remove invalid templates
        for template_id, reason in to_remove:
            del self.user_templates[template_id]
            self._cache.pop(template_id, None)
            removed[reason].append(template_id)

        # Save if any changes
        if any(removed.values()):
            self._save_registry()

        return removed


# Singleton registry instance
_registry: Optional[TemplateRegistry] = None


def get_template_registry() -> TemplateRegistry:
    """Get the global template registry instance.

    Returns:
        TemplateRegistry singleton instance
    """
    global _registry
    if _registry is None:
        _registry = TemplateRegistry()
    return _registry


def reset_template_registry() -> None:
    """Reset the global template registry (mainly for testing)."""
    global _registry
    _registry = None
