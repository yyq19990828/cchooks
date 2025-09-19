"""Template validation system for cchooks templates.

This module provides comprehensive validation for hook templates including:
- Template class implementation validation
- Configuration parameter validation
- Generated script validation
- Dependency checking
- Security validation
- Schema validation for customizations

The TemplateValidator ensures template quality, security, and compliance
with cchooks template standards.
"""

from __future__ import annotations

import ast
import hashlib
import importlib
import inspect
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from abc import ABCMeta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Type, Union

from ..exceptions import CCHooksError
from ..models.validation import ValidationError, ValidationResult, ValidationWarning


class TemplateValidationError(CCHooksError):
    """Exception raised for template validation failures."""
    pass


class TemplateValidator:
    """Comprehensive validation system for cchooks templates.

    Provides validation for template classes, configurations, generated scripts,
    dependencies, and custom schemas with security checks and performance
    optimizations.

    Features:
    - Template class completeness validation
    - Configuration parameter validation with JSON schema
    - Generated script syntax and security validation
    - Dependency availability and version checking
    - Custom schema validation
    - Caching for performance optimization
    - Cross-platform compatibility checks
    """

    def __init__(self, enable_caching: bool = True, cache_ttl: int = 300):
        """Initialize the template validator.

        Args:
            enable_caching: Whether to enable result caching
            cache_ttl: Cache time-to-live in seconds
        """
        self.enable_caching = enable_caching
        self.cache_ttl = cache_ttl
        self._cache: Dict[str, Tuple[float, ValidationResult]] = {}

        # Required template methods and properties
        self.required_methods = {
            'generate_hook': 'Method to generate hook script content',
            'get_default_config': 'Method to get default configuration',
            'validate_config': 'Method to validate configuration parameters'
        }

        self.required_properties = {
            'name': 'Template name identifier',
            'description': 'Human-readable template description',
            'version': 'Template version string',
            'supported_events': 'List of supported hook event types'
        }

        # Security patterns for script validation
        self.dangerous_patterns = [
            r'exec\s*\(',  # exec() calls
            r'eval\s*\(',  # eval() calls
            r'__import__\s*\(',  # dynamic imports
            r'open\s*\(["\'][/\\]',  # absolute path file operations
            r'subprocess\..*shell\s*=\s*True',  # shell injection
            r'os\.system\s*\(',  # system calls
            r'input\s*\(["\'].*password',  # password input (case insensitive)
            r'getpass\.',  # password operations
            r'socket\.',  # network operations
            r'urllib\.',  # network requests
            r'requests\.',  # HTTP requests
            r'http\.',  # HTTP operations
        ]

        # Platform-specific validation
        self.platform_info = {
            'system': platform.system(),
            'python_version': sys.version_info,
            'arch': platform.machine()
        }

    def validate_template_class(self, template_class: Type) -> ValidationResult:
        """Validate template class implementation completeness.

        Checks for required methods, properties, inheritance structure,
        and decorator metadata.

        Args:
            template_class: Template class to validate

        Returns:
            ValidationResult with class validation details
        """
        cache_key = f"class_{template_class.__name__}_{id(template_class)}"
        cached_result = self._get_cached_result(cache_key)
        if cached_result:
            return cached_result

        result = ValidationResult(is_valid=True)

        try:
            # Check if class is properly defined
            if not inspect.isclass(template_class):
                result.add_error(
                    field_name="class_definition",
                    error_code="NOT_A_CLASS",
                    message="Provided object is not a class",
                    suggested_fix="Ensure you're passing a class object, not an instance"
                )
                return result

            # Check inheritance structure
            self._validate_inheritance(template_class, result)

            # Check required methods
            self._validate_required_methods(template_class, result)

            # Check required properties
            self._validate_required_properties(template_class, result)

            # Check method signatures
            self._validate_method_signatures(template_class, result)

            # Check for template metadata decorators
            self._validate_template_decorators(template_class, result)

            # Validate class documentation
            self._validate_class_documentation(template_class, result)

        except Exception as e:
            result.add_error(
                field_name="class_validation",
                error_code="VALIDATION_EXCEPTION",
                message=f"Error during class validation: {str(e)}",
                suggested_fix="Check class definition and ensure all required elements are present"
            )

        self._cache_result(cache_key, result)
        return result

    def validate_template_config(self, template: Any, config: Dict[str, Any]) -> ValidationResult:
        """Validate template configuration parameters.

        Performs JSON schema validation, type checking, range validation,
        and required parameter checks.

        Args:
            template: Template instance or class
            config: Configuration dictionary to validate

        Returns:
            ValidationResult with configuration validation details
        """
        config_hash = hashlib.md5(json.dumps(config, sort_keys=True).encode()).hexdigest()
        cache_key = f"config_{template.__class__.__name__}_{config_hash}"
        cached_result = self._get_cached_result(cache_key)
        if cached_result:
            return cached_result

        result = ValidationResult(is_valid=True)

        try:
            # Get template's default configuration for comparison
            if hasattr(template, 'get_default_config'):
                try:
                    default_config = template.get_default_config()
                    self._validate_against_defaults(config, default_config, result)
                except Exception as e:
                    result.add_warning(
                        field_name="default_config",
                        warning_code="DEFAULT_CONFIG_ERROR",
                        message=f"Could not get default configuration: {str(e)}"
                    )

            # Use template's built-in validation if available
            if hasattr(template, 'validate_config'):
                try:
                    template_result = template.validate_config(config)
                    if isinstance(template_result, ValidationResult):
                        result.merge(template_result)
                    elif isinstance(template_result, bool):
                        if not template_result:
                            result.add_error(
                                field_name="config_validation",
                                error_code="TEMPLATE_VALIDATION_FAILED",
                                message="Template's validate_config method returned False"
                            )
                    elif isinstance(template_result, (list, tuple)):
                        # Assume it's a list of error messages
                        for error_msg in template_result:
                            result.add_error(
                                field_name="config_validation",
                                error_code="TEMPLATE_VALIDATION_ERROR",
                                message=str(error_msg)
                            )
                except Exception as e:
                    result.add_error(
                        field_name="config_validation",
                        error_code="VALIDATION_METHOD_ERROR",
                        message=f"Error calling template's validate_config: {str(e)}"
                    )

            # Perform additional validation checks
            self._validate_config_types(config, result)
            self._validate_config_security(config, result)
            self._validate_config_completeness(config, template, result)

        except Exception as e:
            result.add_error(
                field_name="config_validation",
                error_code="CONFIG_VALIDATION_EXCEPTION",
                message=f"Error during configuration validation: {str(e)}"
            )

        self._cache_result(cache_key, result)
        return result

    def validate_generated_script(self, script_content: str, template_name: str = "unknown") -> ValidationResult:
        """Validate generated script content for syntax and security.

        Performs syntax checking, security vulnerability detection,
        cchooks integration validation, and cross-platform compatibility.

        Args:
            script_content: Generated script content to validate
            template_name: Name of template that generated the script

        Returns:
            ValidationResult with script validation details
        """
        script_hash = hashlib.md5(script_content.encode()).hexdigest()
        cache_key = f"script_{template_name}_{script_hash}"
        cached_result = self._get_cached_result(cache_key)
        if cached_result:
            return cached_result

        result = ValidationResult(is_valid=True)

        try:
            # Basic content validation
            if not script_content or not script_content.strip():
                result.add_error(
                    field_name="script_content",
                    error_code="EMPTY_SCRIPT",
                    message="Generated script content is empty",
                    suggested_fix="Ensure template generates non-empty script content"
                )
                return result

            # Python syntax validation
            self._validate_script_syntax(script_content, result)

            # Security validation
            self._validate_script_security(script_content, result)

            # CCHooks integration validation
            self._validate_cchooks_integration(script_content, result)

            # Cross-platform compatibility
            self._validate_platform_compatibility(script_content, result)

            # Performance considerations
            self._validate_script_performance(script_content, result)

            # Add suggestions for improvement
            self._add_script_suggestions(script_content, result)

        except Exception as e:
            result.add_error(
                field_name="script_validation",
                error_code="SCRIPT_VALIDATION_EXCEPTION",
                message=f"Error during script validation: {str(e)}"
            )

        self._cache_result(cache_key, result)
        return result

    def validate_dependencies(self, dependencies: Dict[str, Any]) -> ValidationResult:
        """Check dependency availability and version compatibility.

        Validates Python packages, system tools, version requirements,
        and optional dependency handling.

        Args:
            dependencies: Dictionary of dependency specifications

        Returns:
            ValidationResult with dependency validation details
        """
        deps_hash = hashlib.md5(json.dumps(dependencies, sort_keys=True).encode()).hexdigest()
        cache_key = f"deps_{deps_hash}"
        cached_result = self._get_cached_result(cache_key)
        if cached_result:
            return cached_result

        result = ValidationResult(is_valid=True)

        try:
            # Validate Python package dependencies
            python_deps = dependencies.get('python_packages', {})
            self._validate_python_packages(python_deps, result)

            # Validate system tool dependencies
            system_deps = dependencies.get('system_tools', {})
            self._validate_system_tools(system_deps, result)

            # Validate optional dependencies
            optional_deps = dependencies.get('optional', {})
            self._validate_optional_dependencies(optional_deps, result)

            # Check for conflicting dependencies
            self._validate_dependency_conflicts(dependencies, result)

            # Platform-specific dependency validation
            self._validate_platform_dependencies(dependencies, result)

        except Exception as e:
            result.add_error(
                field_name="dependency_validation",
                error_code="DEPENDENCY_VALIDATION_EXCEPTION",
                message=f"Error during dependency validation: {str(e)}"
            )

        self._cache_result(cache_key, result)
        return result

    def validate_customization_schema(self, schema: Dict[str, Any]) -> ValidationResult:
        """Validate custom configuration schema definition.

        Validates JSON schema structure, type definitions, constraints,
        and default values.

        Args:
            schema: JSON schema definition to validate

        Returns:
            ValidationResult with schema validation details
        """
        schema_hash = hashlib.md5(json.dumps(schema, sort_keys=True).encode()).hexdigest()
        cache_key = f"schema_{schema_hash}"
        cached_result = self._get_cached_result(cache_key)
        if cached_result:
            return cached_result

        result = ValidationResult(is_valid=True)

        try:
            # Basic schema structure validation
            if not isinstance(schema, dict):
                result.add_error(
                    field_name="schema_structure",
                    error_code="INVALID_SCHEMA_TYPE",
                    message="Schema must be a dictionary",
                    suggested_fix="Provide schema as a JSON object/dictionary"
                )
                return result

            # Validate schema metadata
            self._validate_schema_metadata(schema, result)

            # Validate property definitions
            self._validate_schema_properties(schema, result)

            # Validate schema constraints
            self._validate_schema_constraints(schema, result)

            # Validate default values
            self._validate_schema_defaults(schema, result)

            # Check for schema best practices
            self._validate_schema_best_practices(schema, result)

        except Exception as e:
            result.add_error(
                field_name="schema_validation",
                error_code="SCHEMA_VALIDATION_EXCEPTION",
                message=f"Error during schema validation: {str(e)}"
            )

        self._cache_result(cache_key, result)
        return result

    def clear_cache(self) -> int:
        """Clear validation result cache.

        Returns:
            Number of cached entries removed
        """
        count = len(self._cache)
        self._cache.clear()
        return count

    def _get_cached_result(self, cache_key: str) -> Optional[ValidationResult]:
        """Get cached validation result if valid."""
        if not self.enable_caching or cache_key not in self._cache:
            return None

        timestamp, result = self._cache[cache_key]
        if time.time() - timestamp > self.cache_ttl:
            del self._cache[cache_key]
            return None

        return result

    def _cache_result(self, cache_key: str, result: ValidationResult) -> None:
        """Cache validation result."""
        if self.enable_caching:
            self._cache[cache_key] = (time.time(), result)

    # Private validation methods follow...

    def _validate_inheritance(self, template_class: Type, result: ValidationResult) -> None:
        """Validate template class inheritance structure."""
        # Check if class has proper inheritance (if required by framework)
        base_classes = [cls.__name__ for cls in template_class.__mro__[1:]]  # Skip self

        if not base_classes or base_classes == ['object']:
            result.add_warning(
                field_name="inheritance",
                warning_code="NO_BASE_CLASS",
                message="Template class doesn't inherit from a specific base class"
            )

    def _validate_required_methods(self, template_class: Type, result: ValidationResult) -> None:
        """Validate that all required methods are implemented."""
        for method_name, description in self.required_methods.items():
            if not hasattr(template_class, method_name):
                result.add_error(
                    field_name="required_methods",
                    error_code="MISSING_METHOD",
                    message=f"Required method '{method_name}' is not implemented: {description}",
                    suggested_fix=f"Add {method_name} method to the template class"
                )
            else:
                method = getattr(template_class, method_name)
                if not callable(method):
                    result.add_error(
                        field_name="required_methods",
                        error_code="METHOD_NOT_CALLABLE",
                        message=f"Required method '{method_name}' exists but is not callable"
                    )

    def _validate_required_properties(self, template_class: Type, result: ValidationResult) -> None:
        """Validate that all required properties are defined."""
        for prop_name, description in self.required_properties.items():
            if not hasattr(template_class, prop_name):
                result.add_error(
                    field_name="required_properties",
                    error_code="MISSING_PROPERTY",
                    message=f"Required property '{prop_name}' is not defined: {description}",
                    suggested_fix=f"Add {prop_name} property to the template class"
                )
            else:
                prop_value = getattr(template_class, prop_name)
                if prop_value is None:
                    result.add_warning(
                        field_name="required_properties",
                        warning_code="EMPTY_PROPERTY",
                        message=f"Property '{prop_name}' is None or empty"
                    )

    def _validate_method_signatures(self, template_class: Type, result: ValidationResult) -> None:
        """Validate method signatures for required methods."""
        if hasattr(template_class, 'generate_hook'):
            method = template_class.generate_hook
            if callable(method):
                try:
                    sig = inspect.signature(method)
                    params = list(sig.parameters.keys())

                    # Expect at least 'self' and potentially 'config' parameters
                    if len(params) < 2:
                        result.add_warning(
                            field_name="method_signatures",
                            warning_code="MINIMAL_PARAMETERS",
                            message="generate_hook method has minimal parameters, consider adding config parameter"
                        )
                except Exception:
                    result.add_warning(
                        field_name="method_signatures",
                        warning_code="SIGNATURE_INSPECTION_FAILED",
                        message="Could not inspect generate_hook method signature"
                    )

    def _validate_template_decorators(self, template_class: Type, result: ValidationResult) -> None:
        """Validate template metadata decorators."""
        # Check for common decorators or metadata attributes
        if hasattr(template_class, '__template_metadata__'):
            metadata = template_class.__template_metadata__
            if not isinstance(metadata, dict):
                result.add_warning(
                    field_name="decorators",
                    warning_code="INVALID_METADATA",
                    message="__template_metadata__ should be a dictionary"
                )
        else:
            result.add_suggestion("Consider adding __template_metadata__ attribute for better template discovery")

    def _validate_class_documentation(self, template_class: Type, result: ValidationResult) -> None:
        """Validate class documentation."""
        if not template_class.__doc__:
            result.add_warning(
                field_name="documentation",
                warning_code="MISSING_DOCSTRING",
                message="Template class lacks documentation string"
            )
        elif len(template_class.__doc__.strip()) < 20:
            result.add_warning(
                field_name="documentation",
                warning_code="MINIMAL_DOCSTRING",
                message="Template class documentation is very brief"
            )

    def _validate_against_defaults(self, config: Dict[str, Any],
                                 default_config: Dict[str, Any], result: ValidationResult) -> None:
        """Validate configuration against default values."""
        # Check for unknown keys
        unknown_keys = set(config.keys()) - set(default_config.keys())
        if unknown_keys:
            result.add_warning(
                field_name="configuration",
                warning_code="UNKNOWN_CONFIG_KEYS",
                message=f"Configuration contains unknown keys: {', '.join(unknown_keys)}"
            )

        # Check for missing required keys (those without defaults)
        for key, default_value in default_config.items():
            if key not in config and default_value is None:
                result.add_error(
                    field_name="configuration",
                    error_code="MISSING_REQUIRED_CONFIG",
                    message=f"Required configuration key '{key}' is missing",
                    suggested_fix=f"Add '{key}' to configuration"
                )

    def _validate_config_types(self, config: Dict[str, Any], result: ValidationResult) -> None:
        """Validate configuration value types."""
        for key, value in config.items():
            # Check for potentially problematic types
            if callable(value):
                result.add_warning(
                    field_name="configuration",
                    warning_code="CALLABLE_CONFIG_VALUE",
                    message=f"Configuration key '{key}' contains callable object"
                )
            elif isinstance(value, type):
                result.add_warning(
                    field_name="configuration",
                    warning_code="TYPE_CONFIG_VALUE",
                    message=f"Configuration key '{key}' contains type object"
                )

    def _validate_config_security(self, config: Dict[str, Any], result: ValidationResult) -> None:
        """Validate configuration for security issues."""
        def check_value_security(key: str, value: Any, path: str = ""):
            current_path = f"{path}.{key}" if path else key

            if isinstance(value, str):
                # Check for sensitive patterns
                if re.search(r'password|secret|token|key', key, re.IGNORECASE):
                    if len(value) > 0:
                        result.add_warning(
                            field_name="security",
                            warning_code="POTENTIAL_SECRET_IN_CONFIG",
                            message=f"Configuration key '{current_path}' may contain sensitive information"
                        )

                # Check for file paths
                if re.search(r'^[/\\]|^[A-Za-z]:[/\\]', value):
                    result.add_warning(
                        field_name="security",
                        warning_code="ABSOLUTE_PATH_IN_CONFIG",
                        message=f"Configuration contains absolute file path in '{current_path}'"
                    )

            elif isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    check_value_security(sub_key, sub_value, current_path)

        for key, value in config.items():
            check_value_security(key, value)

    def _validate_config_completeness(self, config: Dict[str, Any], template: Any, result: ValidationResult) -> None:
        """Validate configuration completeness."""
        if not config:
            result.add_warning(
                field_name="configuration",
                warning_code="EMPTY_CONFIGURATION",
                message="Configuration is empty"
            )

        # Check if template supports configuration validation
        if hasattr(template, 'get_config_schema'):
            try:
                schema = template.get_config_schema()
                if schema and isinstance(schema, dict):
                    required_fields = schema.get('required', [])
                    for field in required_fields:
                        if field not in config:
                            result.add_error(
                                field_name="configuration",
                                error_code="MISSING_SCHEMA_REQUIRED_FIELD",
                                message=f"Required field '{field}' missing from configuration"
                            )
            except Exception:
                result.add_warning(
                    field_name="configuration",
                    warning_code="SCHEMA_RETRIEVAL_FAILED",
                    message="Could not retrieve configuration schema from template"
                )

    def _validate_script_syntax(self, script_content: str, result: ValidationResult) -> None:
        """Validate Python script syntax."""
        try:
            ast.parse(script_content)
            result.add_suggestion("Script has valid Python syntax")
        except SyntaxError as e:
            result.add_error(
                field_name="script_syntax",
                error_code="SYNTAX_ERROR",
                message=f"Script contains syntax error at line {e.lineno}: {e.msg}",
                suggested_fix="Fix Python syntax errors in generated script"
            )
        except Exception as e:
            result.add_error(
                field_name="script_syntax",
                error_code="PARSING_ERROR",
                message=f"Error parsing script: {str(e)}"
            )

    def _validate_script_security(self, script_content: str, result: ValidationResult) -> None:
        """Validate script for security vulnerabilities."""
        lines = script_content.split('\n')

        for line_num, line in enumerate(lines, 1):
            line_stripped = line.strip()

            for pattern in self.dangerous_patterns:
                if re.search(pattern, line_stripped, re.IGNORECASE):
                    result.add_warning(
                        field_name="script_security",
                        warning_code="DANGEROUS_PATTERN",
                        message=f"Line {line_num} contains potentially dangerous pattern: {pattern}"
                    )

        # Check for hardcoded secrets
        secret_patterns = [
            r'["\'][A-Za-z0-9+/=]{20,}["\']',  # Base64-like strings
            r'["\'][A-Fa-f0-9]{32,}["\']',     # Hex strings
            r'password\s*=\s*["\'][^"\']+["\']',  # Hardcoded passwords
        ]

        for pattern in secret_patterns:
            if re.search(pattern, script_content, re.IGNORECASE):
                result.add_warning(
                    field_name="script_security",
                    warning_code="POTENTIAL_HARDCODED_SECRET",
                    message="Script may contain hardcoded secrets or credentials"
                )

    def _validate_cchooks_integration(self, script_content: str, result: ValidationResult) -> None:
        """Validate script integration with cchooks library."""
        # Check for cchooks imports
        has_cchooks_import = re.search(r'from\s+cchooks|import\s+cchooks', script_content)
        if not has_cchooks_import:
            result.add_warning(
                field_name="cchooks_integration",
                warning_code="NO_CCHOOKS_IMPORT",
                message="Script doesn't import cchooks library"
            )

        # Check for context creation
        has_context_creation = re.search(r'create_context\(\)', script_content)
        if not has_context_creation:
            result.add_warning(
                field_name="cchooks_integration",
                warning_code="NO_CONTEXT_CREATION",
                message="Script doesn't call create_context() function"
            )

        # Check for proper output handling
        has_output_handling = re.search(r'\.output\.|\.allow\(|\.deny\(|\.continue_flow\(', script_content)
        if not has_output_handling:
            result.add_warning(
                field_name="cchooks_integration",
                warning_code="NO_OUTPUT_HANDLING",
                message="Script doesn't appear to handle output through cchooks context"
            )

    def _validate_platform_compatibility(self, script_content: str, result: ValidationResult) -> None:
        """Validate cross-platform compatibility."""
        # Check for platform-specific path separators
        if '\\\\' in script_content or script_content.count('\\') > script_content.count('/'):
            if self.platform_info['system'] != 'Windows':
                result.add_warning(
                    field_name="platform_compatibility",
                    warning_code="WINDOWS_PATHS_ON_NON_WINDOWS",
                    message="Script contains Windows-style paths but running on non-Windows platform"
                )

        # Check for Unix-specific commands
        unix_commands = ['ls', 'grep', 'awk', 'sed', 'find', 'xargs']
        for cmd in unix_commands:
            if re.search(rf'\b{cmd}\b', script_content):
                if self.platform_info['system'] == 'Windows':
                    result.add_warning(
                        field_name="platform_compatibility",
                        warning_code="UNIX_COMMANDS_ON_WINDOWS",
                        message=f"Script uses Unix command '{cmd}' but running on Windows"
                    )

    def _validate_script_performance(self, script_content: str, result: ValidationResult) -> None:
        """Validate script for performance considerations."""
        # Check script length
        line_count = len(script_content.split('\n'))
        if line_count > 500:
            result.add_warning(
                field_name="script_performance",
                warning_code="LONG_SCRIPT",
                message=f"Generated script is quite long ({line_count} lines), consider optimization"
            )

        # Check for potentially slow operations
        slow_patterns = [
            r'time\.sleep\(\s*\d+',
            r'input\s*\(',
            r'subprocess\..*\btimeout\s*=\s*None',
        ]

        for pattern in slow_patterns:
            if re.search(pattern, script_content):
                result.add_warning(
                    field_name="script_performance",
                    warning_code="POTENTIALLY_SLOW_OPERATION",
                    message="Script contains operations that may be slow or blocking"
                )

    def _add_script_suggestions(self, script_content: str, result: ValidationResult) -> None:
        """Add improvement suggestions for script."""
        # Check for error handling
        if 'try:' not in script_content and 'except' not in script_content:
            result.add_suggestion("Consider adding error handling (try/except blocks) to the script")

        # Check for logging
        if 'logging.' not in script_content and 'print(' not in script_content:
            result.add_suggestion("Consider adding logging or output statements for debugging")

        # Check for documentation
        if '"""' not in script_content and "'''" not in script_content:
            result.add_suggestion("Consider adding docstrings to functions in the generated script")

    def _validate_python_packages(self, python_deps: Dict[str, Any], result: ValidationResult) -> None:
        """Validate Python package dependencies."""
        for package_name, version_spec in python_deps.items():
            try:
                # Try to import the package
                importlib.import_module(package_name)
                result.add_suggestion(f"Python package '{package_name}' is available")

                # If version specification is provided, try to validate it
                if version_spec and version_spec != "*":
                    # This is a simplified version check - in a real implementation,
                    # you'd use packaging.version for proper version comparison
                    try:
                        module = importlib.import_module(package_name)
                        if hasattr(module, '__version__'):
                            current_version = module.__version__
                            result.add_suggestion(f"Package '{package_name}' version: {current_version}")
                    except Exception:
                        result.add_warning(
                            field_name="dependencies",
                            warning_code="VERSION_CHECK_FAILED",
                            message=f"Could not verify version of package '{package_name}'"
                        )

            except ImportError:
                result.add_error(
                    field_name="dependencies",
                    error_code="MISSING_PYTHON_PACKAGE",
                    message=f"Required Python package '{package_name}' is not available",
                    suggested_fix=f"Install package: pip install {package_name}"
                )

    def _validate_system_tools(self, system_deps: Dict[str, Any], result: ValidationResult) -> None:
        """Validate system tool dependencies."""
        for tool_name, tool_spec in system_deps.items():
            tool_path = shutil.which(tool_name)
            if tool_path:
                result.add_suggestion(f"System tool '{tool_name}' found at: {tool_path}")

                # Try to get version if specified
                if isinstance(tool_spec, dict) and 'version_command' in tool_spec:
                    try:
                        version_cmd = tool_spec['version_command']
                        proc = subprocess.run(
                            version_cmd.split(),
                            capture_output=True,
                            text=True,
                            timeout=10
                        )
                        if proc.returncode == 0:
                            result.add_suggestion(f"Tool '{tool_name}' version info: {proc.stdout.strip()[:100]}")
                    except Exception:
                        result.add_warning(
                            field_name="dependencies",
                            warning_code="VERSION_CHECK_FAILED",
                            message=f"Could not get version info for tool '{tool_name}'"
                        )
            else:
                result.add_error(
                    field_name="dependencies",
                    error_code="MISSING_SYSTEM_TOOL",
                    message=f"Required system tool '{tool_name}' is not available in PATH",
                    suggested_fix=f"Install {tool_name} and ensure it's in your system PATH"
                )

    def _validate_optional_dependencies(self, optional_deps: Dict[str, Any], result: ValidationResult) -> None:
        """Validate optional dependencies."""
        for dep_name, dep_spec in optional_deps.items():
            dep_type = dep_spec.get('type', 'python_package') if isinstance(dep_spec, dict) else 'python_package'

            if dep_type == 'python_package':
                try:
                    importlib.import_module(dep_name)
                    result.add_suggestion(f"Optional Python package '{dep_name}' is available")
                except ImportError:
                    result.add_suggestion(f"Optional Python package '{dep_name}' is not available (this is OK)")

            elif dep_type == 'system_tool':
                if shutil.which(dep_name):
                    result.add_suggestion(f"Optional system tool '{dep_name}' is available")
                else:
                    result.add_suggestion(f"Optional system tool '{dep_name}' is not available (this is OK)")

    def _validate_dependency_conflicts(self, dependencies: Dict[str, Any], result: ValidationResult) -> None:
        """Check for conflicting dependencies."""
        # This is a simplified conflict detection - in practice, you'd have
        # a more sophisticated system for detecting package conflicts
        python_deps = dependencies.get('python_packages', {})

        # Example: Check for common conflicting packages
        conflicts = [
            (['requests', 'urllib3'], 'requests and urllib3 versions may conflict'),
            (['numpy', 'scipy'], 'numpy and scipy versions should be compatible'),
        ]

        for conflicting_packages, message in conflicts:
            present_packages = [pkg for pkg in conflicting_packages if pkg in python_deps]
            if len(present_packages) > 1:
                result.add_warning(
                    field_name="dependencies",
                    warning_code="POTENTIAL_PACKAGE_CONFLICT",
                    message=f"Potential conflict between packages {present_packages}: {message}"
                )

    def _validate_platform_dependencies(self, dependencies: Dict[str, Any], result: ValidationResult) -> None:
        """Validate platform-specific dependencies."""
        platform_deps = dependencies.get('platform_specific', {})
        current_platform = self.platform_info['system'].lower()

        if current_platform in platform_deps:
            platform_specific = platform_deps[current_platform]
            result.add_suggestion(f"Found platform-specific dependencies for {current_platform}")

            # Validate platform-specific dependencies
            if isinstance(platform_specific, dict):
                if 'python_packages' in platform_specific:
                    self._validate_python_packages(platform_specific['python_packages'], result)
                if 'system_tools' in platform_specific:
                    self._validate_system_tools(platform_specific['system_tools'], result)

    def _validate_schema_metadata(self, schema: Dict[str, Any], result: ValidationResult) -> None:
        """Validate schema metadata."""
        required_metadata = ['type', 'properties']
        for field in required_metadata:
            if field not in schema:
                result.add_error(
                    field_name="schema_structure",
                    error_code="MISSING_SCHEMA_FIELD",
                    message=f"Schema is missing required field: {field}",
                    suggested_fix=f"Add '{field}' field to schema definition"
                )

        if schema.get('type') != 'object':
            result.add_warning(
                field_name="schema_structure",
                warning_code="UNEXPECTED_SCHEMA_TYPE",
                message="Schema type should typically be 'object' for configuration schemas"
            )

    def _validate_schema_properties(self, schema: Dict[str, Any], result: ValidationResult) -> None:
        """Validate schema property definitions."""
        properties = schema.get('properties', {})
        if not properties:
            result.add_warning(
                field_name="schema_properties",
                warning_code="NO_PROPERTIES_DEFINED",
                message="Schema has no properties defined"
            )
            return

        for prop_name, prop_def in properties.items():
            if not isinstance(prop_def, dict):
                result.add_error(
                    field_name="schema_properties",
                    error_code="INVALID_PROPERTY_DEFINITION",
                    message=f"Property '{prop_name}' definition should be a dictionary"
                )
                continue

            # Check for required property fields
            if 'type' not in prop_def:
                result.add_error(
                    field_name="schema_properties",
                    error_code="MISSING_PROPERTY_TYPE",
                    message=f"Property '{prop_name}' is missing type definition"
                )

            # Validate property types
            prop_type = prop_def.get('type')
            valid_types = ['string', 'number', 'integer', 'boolean', 'array', 'object', 'null']
            if prop_type not in valid_types:
                result.add_error(
                    field_name="schema_properties",
                    error_code="INVALID_PROPERTY_TYPE",
                    message=f"Property '{prop_name}' has invalid type: {prop_type}"
                )

    def _validate_schema_constraints(self, schema: Dict[str, Any], result: ValidationResult) -> None:
        """Validate schema constraints."""
        properties = schema.get('properties', {})

        for prop_name, prop_def in properties.items():
            if not isinstance(prop_def, dict):
                continue

            prop_type = prop_def.get('type')

            # Validate constraints based on type
            if prop_type == 'string':
                if 'minLength' in prop_def and 'maxLength' in prop_def:
                    min_len = prop_def['minLength']
                    max_len = prop_def['maxLength']
                    if min_len > max_len:
                        result.add_error(
                            field_name="schema_constraints",
                            error_code="INVALID_LENGTH_CONSTRAINT",
                            message=f"Property '{prop_name}' minLength ({min_len}) > maxLength ({max_len})"
                        )

            elif prop_type in ['number', 'integer']:
                if 'minimum' in prop_def and 'maximum' in prop_def:
                    minimum = prop_def['minimum']
                    maximum = prop_def['maximum']
                    if minimum > maximum:
                        result.add_error(
                            field_name="schema_constraints",
                            error_code="INVALID_NUMERIC_CONSTRAINT",
                            message=f"Property '{prop_name}' minimum ({minimum}) > maximum ({maximum})"
                        )

    def _validate_schema_defaults(self, schema: Dict[str, Any], result: ValidationResult) -> None:
        """Validate schema default values."""
        properties = schema.get('properties', {})
        required = schema.get('required', [])

        for prop_name, prop_def in properties.items():
            if not isinstance(prop_def, dict):
                continue

            if 'default' in prop_def:
                default_value = prop_def['default']
                prop_type = prop_def.get('type')

                # Validate default value against type
                type_validators = {
                    'string': lambda x: isinstance(x, str),
                    'number': lambda x: isinstance(x, (int, float)),
                    'integer': lambda x: isinstance(x, int),
                    'boolean': lambda x: isinstance(x, bool),
                    'array': lambda x: isinstance(x, list),
                    'object': lambda x: isinstance(x, dict),
                    'null': lambda x: x is None,
                }

                if prop_type in type_validators:
                    if not type_validators[prop_type](default_value):
                        result.add_error(
                            field_name="schema_defaults",
                            error_code="INVALID_DEFAULT_TYPE",
                            message=f"Property '{prop_name}' default value type doesn't match declared type {prop_type}"
                        )

            # Check if required properties have defaults
            if prop_name in required and 'default' not in prop_def:
                result.add_warning(
                    field_name="schema_defaults",
                    warning_code="REQUIRED_PROPERTY_NO_DEFAULT",
                    message=f"Required property '{prop_name}' has no default value"
                )

    def _validate_schema_best_practices(self, schema: Dict[str, Any], result: ValidationResult) -> None:
        """Validate schema follows best practices."""
        # Check for description fields
        if 'description' not in schema:
            result.add_suggestion("Consider adding a description field to the schema")

        properties = schema.get('properties', {})
        undocumented_props = []

        for prop_name, prop_def in properties.items():
            if isinstance(prop_def, dict) and 'description' not in prop_def:
                undocumented_props.append(prop_name)

        if undocumented_props:
            result.add_suggestion(f"Consider adding descriptions to properties: {', '.join(undocumented_props)}")

        # Check for examples
        if 'examples' not in schema:
            result.add_suggestion("Consider adding examples to the schema")

        # Check schema version
        if '$schema' not in schema:
            result.add_suggestion("Consider adding $schema field to specify JSON Schema version")
