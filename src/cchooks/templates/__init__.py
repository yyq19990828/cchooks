"""Template system for hook script generation.

This module provides the template framework for generating Python hook scripts
from predefined templates. It includes the abstract base class that all templates
must implement, as well as utility functions for template registration, validation,
and script generation.

The template system supports:
- Built-in templates for common hook patterns
- User-defined custom templates
- Template registration and discovery
- Configuration validation with JSON schemas
- Dependency management
- Script generation with customization options

Templates are organized by source:
- builtin/: Built-in templates provided by cchooks
- Custom templates can be registered at runtime

Example usage:
    from cchooks.templates import BaseTemplate, TemplateConfig, template
    from cchooks.types.enums import HookEventType

    @template(template_id="my-template")
    class MyTemplate(BaseTemplate):
        @property
        def name(self) -> str:
            return "My Custom Template"

        # ... implement other abstract methods

    # Generate script
    config = TemplateConfig(
        template_id="my-template",
        event_type=HookEventType.PRE_TOOL_USE,
        customization={"option": "value"},
        output_path=Path("my_hook.py")
    )
    script = generate_script_from_template(MyTemplate, config)
"""

from .base_template import (
    BaseTemplate,
    TemplateConfig,
    check_template_dependencies,
    clear_registered_templates,
    generate_script_from_template,
    get_registered_templates,
    get_template_class,
    template,
    validate_template_config,
)
from .registry import (
    HookTemplate,
    TemplateRegistry,
    TemplateRegistryError,
    get_template_registry,
    reset_template_registry,
)

__all__ = [
    # Core template classes
    "BaseTemplate",
    "TemplateConfig",
    "HookTemplate",

    # Template registry
    "TemplateRegistry",
    "TemplateRegistryError",
    "get_template_registry",
    "reset_template_registry",

    # Registration and discovery
    "template",
    "get_registered_templates",
    "get_template_class",
    "clear_registered_templates",

    # Template utilities
    "validate_template_config",
    "generate_script_from_template",
    "check_template_dependencies",
]
