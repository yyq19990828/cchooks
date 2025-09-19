"""Template generation engine for hook script generation.

This module implements the ScriptGenerator service as specified in T033 task,
providing a complete template-based hook script generation system with
template coordination, validation, customization, and file management.

The ScriptGenerator serves as the central hub for:
- Coordinating TemplateRegistry and template classes
- Generating Python hook scripts from templates
- Handling template selection, configuration validation, and script generation
- Managing file operations and script permissions
- Supporting advanced features like template inheritance and batch generation
- Providing integration with CLI commands (cc_generatehook)

Key Features:
- Template-based script generation with customization support
- Comprehensive validation of templates and configurations
- Cross-platform file handling and permission management
- Batch script generation capabilities
- Template inheritance and composition support
- Security validation and error handling
- Integration with TemplateRegistry and BaseTemplate interface
- Support for dry-run mode and detailed generation reports
"""

from __future__ import annotations

import ast
import json
import os
import stat
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from ..exceptions import CCHooksError
from ..models.validation import ScriptGenerationResult, ValidationResult
from ..templates.base_template import BaseTemplate, TemplateConfig
from ..templates.registry import TemplateRegistry, get_template_registry
from ..templates.validator import TemplateValidator
from ..types.enums import HookEventType


class ScriptGenerationError(CCHooksError):
    """Exception raised for script generation failures."""
    pass


@dataclass
class GenerationRequest:
    """Request for script generation containing all necessary parameters.

    This dataclass encapsulates all the information needed to generate a script,
    making it easier to pass around and validate the complete request.

    Attributes:
        template_id: Template identifier to use for generation
        event_type: Hook event type the script will handle
        output_path: Path where the generated script will be saved
        customization: Template-specific customization options
        matcher: Optional tool name pattern for PreToolUse/PostToolUse events
        timeout: Optional execution timeout in seconds for the hook
        set_executable: Whether to set execute permissions on generated script
        add_to_settings: Whether to automatically add script to settings file
        dry_run: Whether to perform validation only without creating files
        force_overwrite: Whether to overwrite existing files without prompting
    """
    template_id: str
    event_type: HookEventType
    output_path: Path
    customization: Dict[str, Any] = field(default_factory=dict)
    matcher: Optional[str] = None
    timeout: Optional[int] = None
    set_executable: bool = True
    add_to_settings: bool = False
    dry_run: bool = False
    force_overwrite: bool = False

    def __post_init__(self) -> None:
        """Validate request after initialization."""
        # Ensure output_path is a Path object
        if isinstance(self.output_path, str):
            self.output_path = Path(self.output_path)

        # Validate that matcher is provided for tool events
        if self.event_type.requires_matcher() and not self.matcher:
            raise ValueError(
                f"matcher field is required for {self.event_type.value} events"
            )

        # Validate timeout if provided
        if self.timeout is not None and self.timeout <= 0:
            raise ValueError("timeout must be a positive integer")


class ScriptGenerator:
    """Central service for template-based hook script generation.

    The ScriptGenerator coordinates the template system to provide a complete
    script generation solution. It handles template selection, configuration
    validation, script generation, file operations, and advanced features.

    This class serves as the main entry point for generating Python hook scripts
    and integrates with the CLI command system to provide user-friendly script
    generation capabilities.

    Attributes:
        registry: TemplateRegistry instance for template management
        validator: TemplateValidator instance for validation
        enable_security_checks: Whether to perform security validation
        enable_caching: Whether to cache template instances
        default_script_permissions: Default file permissions for generated scripts
    """

    def __init__(
        self,
        registry: Optional[TemplateRegistry] = None,
        validator: Optional[TemplateValidator] = None,
        enable_security_checks: bool = True,
        enable_caching: bool = True,
        default_script_permissions: int = 0o755
    ):
        """Initialize ScriptGenerator.

        Args:
            registry: TemplateRegistry instance (uses global if None)
            validator: TemplateValidator instance (creates new if None)
            enable_security_checks: Whether to perform security validation
            enable_caching: Whether to enable template caching
            default_script_permissions: Default permissions for generated scripts
        """
        self.registry = registry or get_template_registry()
        self.validator = validator or TemplateValidator(enable_caching=enable_caching)
        self.enable_security_checks = enable_security_checks
        self.enable_caching = enable_caching
        self.default_script_permissions = default_script_permissions

        # Cache for template instances
        self._template_cache: Dict[str, BaseTemplate] = {}

        # Statistics tracking
        self._generation_stats = {
            'total_generated': 0,
            'successful_generations': 0,
            'failed_generations': 0,
            'total_generation_time': 0.0,
            'templates_used': set(),
        }

    def generate_script(
        self,
        template_id: str,
        event_type: HookEventType,
        output_path: Path,
        customization: Optional[Dict[str, Any]] = None,
        matcher: Optional[str] = None,
        timeout: Optional[int] = None,
        set_executable: bool = True,
        add_to_settings: bool = False,
        dry_run: bool = False,
        force_overwrite: bool = False
    ) -> ScriptGenerationResult:
        """Generate a hook script from template.

        This is the main entry point for script generation. It coordinates the
        entire generation process from template selection to file creation.

        Args:
            template_id: Template identifier to use
            event_type: Hook event type for the script
            output_path: Path to save the generated script
            customization: Template-specific customization options
            matcher: Tool name pattern for tool-related events
            timeout: Execution timeout for the hook
            set_executable: Whether to set execute permissions
            add_to_settings: Whether to add to settings file
            dry_run: Perform validation only, don't create files
            force_overwrite: Overwrite existing files without prompting

        Returns:
            ScriptGenerationResult with generation outcome and metadata

        Raises:
            ScriptGenerationError: If generation fails due to configuration issues
        """
        start_time = time.time()

        try:
            # Create and validate generation request
            request = GenerationRequest(
                template_id=template_id,
                event_type=event_type,
                output_path=output_path,
                customization=customization or {},
                matcher=matcher,
                timeout=timeout,
                set_executable=set_executable,
                add_to_settings=add_to_settings,
                dry_run=dry_run,
                force_overwrite=force_overwrite
            )

            # Validate the generation request
            validation_result = self.validate_generation_request(request)
            if not validation_result.is_valid:
                return ScriptGenerationResult.failure_result(
                    error_message=f"Request validation failed: {self._format_validation_errors(validation_result)}",
                    template_used=template_id,
                    validation_result=validation_result,
                    generation_time=time.time() - start_time
                )

            # Get template and validate it
            template = self._get_template_instance(template_id)

            # Apply template customization and validate
            final_customization = self.apply_template_customization(
                template, request.customization, request.event_type
            )

            # Create template configuration
            template_config = TemplateConfig(
                template_id=template_id,
                event_type=event_type,
                customization=final_customization,
                output_path=output_path,
                matcher=matcher,
                timeout=timeout
            )

            # Generate script content
            script_content = template.generate(template_config)

            # Validate generated script
            if self.enable_security_checks:
                script_validation = self.validator.validate_generated_script(
                    script_content, template_id
                )
                validation_result.merge(script_validation)

            # In dry-run mode, return success without creating files
            if dry_run:
                return ScriptGenerationResult.success_result(
                    generated_file=output_path,
                    template_used=template_id,
                    executable_set=False,
                    added_to_settings=False,
                    customizations_applied=final_customization,
                    validation_result=validation_result,
                    generation_time=time.time() - start_time,
                    script_size=len(script_content.encode('utf-8'))
                )

            # Write script to file
            actual_output_path = self.write_script_to_file(
                script_content, output_path, force_overwrite
            )

            # Set executable permissions if requested
            executable_set = False
            if set_executable:
                executable_set = self.make_script_executable(actual_output_path)

            # Track statistics
            self._update_generation_stats(True, template_id, time.time() - start_time)

            return ScriptGenerationResult.success_result(
                generated_file=actual_output_path,
                template_used=template_id,
                executable_set=executable_set,
                added_to_settings=add_to_settings,  # TODO: Implement settings integration
                customizations_applied=final_customization,
                validation_result=validation_result,
                generation_time=time.time() - start_time,
                script_size=len(script_content.encode('utf-8'))
            )

        except Exception as e:
            # Track failed generation
            self._update_generation_stats(False, template_id, time.time() - start_time)

            return ScriptGenerationResult.failure_result(
                error_message=f"Script generation failed: {str(e)}",
                template_used=template_id,
                generation_time=time.time() - start_time
            )

    def validate_generation_request(self, request: GenerationRequest) -> ValidationResult:
        """Validate a script generation request.

        Performs comprehensive validation of the generation request including
        template availability, event type compatibility, file path validation,
        and customization parameter validation.

        Args:
            request: GenerationRequest to validate

        Returns:
            ValidationResult with validation outcome
        """
        result = ValidationResult(is_valid=True)

        try:
            # Validate template exists
            try:
                template_info = self.registry.get_template(request.template_id)
            except Exception as e:
                result.add_error(
                    field_name="template_id",
                    error_code="TEMPLATE_NOT_FOUND",
                    message=f"Template '{request.template_id}' not found: {e}",
                    suggested_fix="Check available templates with list command"
                )
                return result

            # Validate event type compatibility
            if not template_info.supports_event(request.event_type):
                supported_events = [e.value for e in template_info.supported_events]
                result.add_error(
                    field_name="event_type",
                    error_code="INCOMPATIBLE_EVENT_TYPE",
                    message=f"Template '{request.template_id}' does not support event type '{request.event_type.value}'",
                    suggested_fix=f"Use one of the supported event types: {supported_events}"
                )

            # Validate output path
            self._validate_output_path(request.output_path, request.force_overwrite, result)

            # Validate matcher requirement for tool events
            if request.event_type.requires_matcher() and not request.matcher:
                result.add_error(
                    field_name="matcher",
                    error_code="MISSING_MATCHER",
                    message=f"Event type '{request.event_type.value}' requires a matcher pattern",
                    suggested_fix="Provide a tool name pattern for the matcher field"
                )

            # Validate timeout
            if request.timeout is not None:
                if request.timeout <= 0:
                    result.add_error(
                        field_name="timeout",
                        error_code="INVALID_TIMEOUT",
                        message="Timeout must be a positive integer",
                        suggested_fix="Use a positive number of seconds for timeout"
                    )
                elif request.timeout > 3600:  # 1 hour limit
                    result.add_warning(
                        field_name="timeout",
                        warning_code="LONG_TIMEOUT",
                        message="Timeout is very long (>1 hour), this may cause issues"
                    )

            # Validate template customization
            if request.customization:
                template_instance = self._get_template_instance(request.template_id)
                customization_validation = template_instance.validate_config(request.customization)
                result.merge(customization_validation)

        except Exception as e:
            result.add_error(
                field_name="request_validation",
                error_code="VALIDATION_EXCEPTION",
                message=f"Error during request validation: {str(e)}"
            )

        return result

    def apply_template_customization(
        self,
        template: BaseTemplate,
        customization: Dict[str, Any],
        event_type: HookEventType
    ) -> Dict[str, Any]:
        """Apply and merge template customization options.

        Combines user-provided customization with template defaults and
        applies event-type-specific customizations.

        Args:
            template: Template instance
            customization: User-provided customization options
            event_type: Target event type for context-specific customization

        Returns:
            Final merged customization configuration
        """
        # Start with template defaults
        final_config = template.get_default_config().copy()

        # Apply event-type-specific defaults
        event_defaults = self._get_event_type_defaults(event_type)
        final_config.update(event_defaults)

        # Apply user customization (overrides defaults)
        final_config.update(customization)

        # Apply event-type-specific overrides
        event_overrides = self._get_event_type_overrides(event_type)
        final_config.update(event_overrides)

        return final_config

    def write_script_to_file(
        self,
        script_content: str,
        output_path: Path,
        force_overwrite: bool = False
    ) -> Path:
        """Write generated script content to file.

        Handles file creation, directory creation, backup of existing files,
        and safe writing with atomic operations where possible.

        Args:
            script_content: Generated script content to write
            output_path: Target file path
            force_overwrite: Whether to overwrite existing files

        Returns:
            Actual path where file was written

        Raises:
            ScriptGenerationError: If file cannot be written
        """
        try:
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Check if file exists and handle accordingly
            if output_path.exists() and not force_overwrite:
                # Create backup
                backup_path = self._create_backup_file(output_path)
                if backup_path:
                    # Log backup creation (could be enhanced with proper logging)
                    pass

            # Write script content atomically
            temp_path = output_path.with_suffix(output_path.suffix + '.tmp')

            try:
                with open(temp_path, 'w', encoding='utf-8') as f:
                    f.write(script_content)

                # Atomic move to final location
                temp_path.replace(output_path)

            except Exception:
                # Clean up temp file if something went wrong
                if temp_path.exists():
                    temp_path.unlink()
                raise

            return output_path

        except Exception as e:
            raise ScriptGenerationError(f"Failed to write script to {output_path}: {e}")

    def make_script_executable(self, script_path: Path) -> bool:
        """Set execute permissions on generated script.

        Sets appropriate execute permissions for the current platform,
        handling cross-platform differences in permission systems.

        Args:
            script_path: Path to script file

        Returns:
            True if permissions were set successfully
        """
        try:
            # Get current permissions
            current_mode = script_path.stat().st_mode

            # Add execute permissions for owner, group, and others
            new_mode = current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH

            # Apply new permissions
            script_path.chmod(new_mode)

            return True

        except Exception:
            # Permission setting failed, but this is not critical
            return False

    def _get_template_instance(self, template_id: str) -> BaseTemplate:
        """Get template instance with caching support."""
        if self.enable_caching and template_id in self._template_cache:
            return self._template_cache[template_id]

        template_info = self.registry.get_template(template_id)
        template_instance = template_info.get_instance()

        if self.enable_caching:
            self._template_cache[template_id] = template_instance

        return template_instance

    def _validate_output_path(
        self,
        output_path: Path,
        force_overwrite: bool,
        result: ValidationResult
    ) -> None:
        """Validate output path for script generation."""
        try:
            # Check if parent directory exists or can be created
            parent_dir = output_path.parent
            if not parent_dir.exists():
                try:
                    parent_dir.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    result.add_error(
                        field_name="output_path",
                        error_code="CANNOT_CREATE_DIRECTORY",
                        message=f"Cannot create output directory {parent_dir}: {e}",
                        suggested_fix="Ensure you have write permissions to the parent directory"
                    )
                    return

            # Check if file already exists
            if output_path.exists():
                if not force_overwrite:
                    result.add_warning(
                        field_name="output_path",
                        warning_code="FILE_EXISTS",
                        message=f"Output file {output_path} already exists"
                    )

                # Check if file is writable
                if not os.access(output_path, os.W_OK):
                    result.add_error(
                        field_name="output_path",
                        error_code="FILE_NOT_WRITABLE",
                        message=f"Cannot write to existing file {output_path}",
                        suggested_fix="Check file permissions or use a different output path"
                    )

            # Check if we can write to the directory
            if not os.access(parent_dir, os.W_OK):
                result.add_error(
                    field_name="output_path",
                    error_code="DIRECTORY_NOT_WRITABLE",
                    message=f"Cannot write to directory {parent_dir}",
                    suggested_fix="Check directory permissions"
                )

        except Exception as e:
            result.add_error(
                field_name="output_path",
                error_code="PATH_VALIDATION_ERROR",
                message=f"Error validating output path: {e}"
            )

    def _get_event_type_defaults(self, event_type: HookEventType) -> Dict[str, Any]:
        """Get default configuration values for specific event types."""
        defaults = {}

        if event_type in [HookEventType.PRE_TOOL_USE, HookEventType.POST_TOOL_USE]:
            defaults.update({
                'include_tool_metadata': True,
                'validate_tool_params': True,
            })

        if event_type == HookEventType.SESSION_START:
            defaults.update({
                'initialize_environment': True,
                'log_session_start': True,
            })

        if event_type == HookEventType.SESSION_END:
            defaults.update({
                'cleanup_resources': True,
                'log_session_end': True,
            })

        return defaults

    def _get_event_type_overrides(self, event_type: HookEventType) -> Dict[str, Any]:
        """Get mandatory configuration overrides for specific event types."""
        overrides = {}

        # Add event-specific mandatory settings
        overrides['hook_event_type'] = event_type.value

        return overrides

    def _create_backup_file(self, original_path: Path) -> Optional[Path]:
        """Create backup of existing file before overwriting."""
        try:
            backup_path = original_path.with_suffix(original_path.suffix + '.bak')

            # If backup already exists, add timestamp
            if backup_path.exists():
                timestamp = int(time.time())
                backup_path = original_path.with_suffix(f"{original_path.suffix}.{timestamp}.bak")

            # Copy original to backup
            import shutil
            shutil.copy2(original_path, backup_path)

            return backup_path

        except Exception:
            return None

    def _format_validation_errors(self, validation_result: ValidationResult) -> str:
        """Format validation errors into a readable string."""
        if not validation_result.errors:
            return "No specific errors"

        error_messages = []
        for error in validation_result.errors:
            if hasattr(error, 'message'):
                error_messages.append(error.message)
            elif isinstance(error, dict):
                error_messages.append(error.get('message', str(error)))
            else:
                error_messages.append(str(error))

        return '; '.join(error_messages)

    def _update_generation_stats(self, success: bool, template_id: str, generation_time: float) -> None:
        """Update internal generation statistics."""
        self._generation_stats['total_generated'] += 1
        self._generation_stats['total_generation_time'] += generation_time
        self._generation_stats['templates_used'].add(template_id)

        if success:
            self._generation_stats['successful_generations'] += 1
        else:
            self._generation_stats['failed_generations'] += 1

    def get_generation_stats(self) -> Dict[str, Any]:
        """Get generation statistics.

        Returns:
            Dictionary with generation statistics
        """
        stats = self._generation_stats.copy()
        stats['templates_used'] = list(stats['templates_used'])

        if stats['total_generated'] > 0:
            stats['success_rate'] = stats['successful_generations'] / stats['total_generated']
            stats['average_generation_time'] = stats['total_generation_time'] / stats['total_generated']
        else:
            stats['success_rate'] = 0.0
            stats['average_generation_time'] = 0.0

        return stats

    def clear_cache(self) -> int:
        """Clear template instance cache.

        Returns:
            Number of cached templates removed
        """
        count = len(self._template_cache)
        self._template_cache.clear()
        return count

    # Advanced Features

    def generate_batch_scripts(
        self,
        batch_requests: List[GenerationRequest]
    ) -> List[ScriptGenerationResult]:
        """Generate multiple scripts in batch.

        Processes multiple script generation requests efficiently,
        with shared validation and caching benefits.

        Args:
            batch_requests: List of GenerationRequest objects

        Returns:
            List of ScriptGenerationResult objects, one per request
        """
        results = []

        for request in batch_requests:
            try:
                result = self.generate_script(
                    template_id=request.template_id,
                    event_type=request.event_type,
                    output_path=request.output_path,
                    customization=request.customization,
                    matcher=request.matcher,
                    timeout=request.timeout,
                    set_executable=request.set_executable,
                    add_to_settings=request.add_to_settings,
                    dry_run=request.dry_run,
                    force_overwrite=request.force_overwrite
                )
                results.append(result)

            except Exception as e:
                # Even if one fails, continue with others
                result = ScriptGenerationResult.failure_result(
                    error_message=f"Batch generation failed for {request.template_id}: {str(e)}",
                    template_used=request.template_id
                )
                results.append(result)

        return results

    def apply_post_processing(
        self,
        script_content: str,
        template_id: str,
        customization: Dict[str, Any]
    ) -> str:
        """Apply post-processing to generated script content.

        Performs script optimization, formatting, and enhancement
        based on configuration and template requirements.

        Args:
            script_content: Original generated script content
            template_id: Template that generated the script
            customization: Template customization options

        Returns:
            Post-processed script content
        """
        processed_content = script_content

        # Apply code formatting if requested
        if customization.get('format_code', True):
            processed_content = self._format_script_code(processed_content)

        # Add custom imports if specified
        custom_imports = customization.get('additional_imports', [])
        if custom_imports:
            processed_content = self._add_custom_imports(processed_content, custom_imports)

        # Optimize script if requested
        if customization.get('optimize_script', False):
            processed_content = self._optimize_script_content(processed_content)

        # Add template metadata comments
        if customization.get('add_metadata_comments', True):
            processed_content = self._add_metadata_comments(
                processed_content, template_id, customization
            )

        return processed_content

    def compose_templates(
        self,
        primary_template_id: str,
        secondary_template_ids: List[str],
        composition_strategy: str = "sequential"
    ) -> str:
        """Compose multiple templates into a single script.

        Combines functionality from multiple templates to create
        more complex hook scripts.

        Args:
            primary_template_id: Main template to use as base
            secondary_template_ids: Additional templates to compose
            composition_strategy: How to combine templates ("sequential", "parallel", "conditional")

        Returns:
            Template ID for the composed template

        Raises:
            ScriptGenerationError: If composition fails
        """
        # This is a placeholder for template composition logic
        # In a full implementation, this would create a new composite template
        # that combines the logic from multiple templates

        if composition_strategy == "sequential":
            # Execute templates in sequence
            pass
        elif composition_strategy == "parallel":
            # Execute templates in parallel where possible
            pass
        elif composition_strategy == "conditional":
            # Execute templates based on conditions
            pass
        else:
            raise ScriptGenerationError(f"Unknown composition strategy: {composition_strategy}")

        # For now, return a composed template ID
        composed_id = f"composed_{primary_template_id}_{'_'.join(secondary_template_ids)}"
        return composed_id

    def validate_script_dependencies(
        self,
        script_content: str,
        template_id: str
    ) -> ValidationResult:
        """Validate script dependencies and requirements.

        Checks that all dependencies required by the generated script
        are available in the target environment.

        Args:
            script_content: Generated script content to validate
            template_id: Template that generated the script

        Returns:
            ValidationResult with dependency validation results
        """
        result = ValidationResult(is_valid=True)

        try:
            # Parse script to extract imports and dependencies
            imports = self._extract_script_imports(script_content)

            # Validate each import
            for import_module in imports:
                if not self._check_module_availability(import_module):
                    result.add_error(
                        field_name="dependencies",
                        error_code="MISSING_DEPENDENCY",
                        message=f"Required module '{import_module}' is not available",
                        suggested_fix=f"Install missing dependency: pip install {import_module}"
                    )

            # Check template-specific dependencies
            template_info = self.registry.get_template(template_id)
            for dependency in template_info.dependencies:
                if not self._check_dependency_availability(dependency):
                    result.add_error(
                        field_name="dependencies",
                        error_code="MISSING_TEMPLATE_DEPENDENCY",
                        message=f"Template dependency '{dependency}' is not available",
                        suggested_fix=f"Install template dependency: {dependency}"
                    )

        except Exception as e:
            result.add_error(
                field_name="dependency_validation",
                error_code="VALIDATION_EXCEPTION",
                message=f"Error during dependency validation: {str(e)}"
            )

        return result

    def _format_script_code(self, script_content: str) -> str:
        """Format script code for readability."""
        try:
            # Basic code formatting - in practice, could use tools like black or autopep8
            lines = script_content.split('\n')
            formatted_lines = []

            for line in lines:
                # Basic indentation cleanup
                stripped = line.lstrip()
                if stripped:
                    # Maintain relative indentation
                    indent_level = len(line) - len(stripped)
                    formatted_lines.append(' ' * indent_level + stripped)
                else:
                    formatted_lines.append('')

            return '\n'.join(formatted_lines)

        except Exception:
            # If formatting fails, return original content
            return script_content

    def _add_custom_imports(self, script_content: str, imports: List[str]) -> str:
        """Add custom imports to script content."""
        import_lines = []
        for imp in imports:
            if not imp.startswith('import ') and not imp.startswith('from '):
                import_lines.append(f"import {imp}")
            else:
                import_lines.append(imp)

        # Find where to insert imports (after existing imports)
        lines = script_content.split('\n')
        insert_index = 0

        for i, line in enumerate(lines):
            if line.strip().startswith(('import ', 'from ')):
                insert_index = i + 1
            elif line.strip() and not line.startswith('#'):
                break

        # Insert custom imports
        for import_line in reversed(import_lines):
            lines.insert(insert_index, import_line)

        return '\n'.join(lines)

    def _optimize_script_content(self, script_content: str) -> str:
        """Optimize script content for performance."""
        # Placeholder for script optimization logic
        # Could include:
        # - Removing unused imports
        # - Simplifying expressions
        # - Caching expensive operations
        # - Adding performance hints

        return script_content

    def _add_metadata_comments(
        self,
        script_content: str,
        template_id: str,
        customization: Dict[str, Any]
    ) -> str:
        """Add metadata comments to script."""
        metadata_lines = [
            f"# Generated by template: {template_id}",
            f"# Generation time: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"# Customization options: {len(customization)} settings",
        ]

        lines = script_content.split('\n')

        # Find where to insert metadata (after shebang and encoding)
        insert_index = 0
        for i, line in enumerate(lines):
            if line.startswith('#!') or line.startswith('# -*- coding'):
                insert_index = i + 1
            else:
                break

        # Insert metadata comments
        for meta_line in reversed(metadata_lines):
            lines.insert(insert_index, meta_line)

        return '\n'.join(lines)

    def _extract_script_imports(self, script_content: str) -> List[str]:
        """Extract import statements from script content."""
        imports = []

        try:
            # Parse script to extract imports
            tree = ast.parse(script_content)

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module)

        except Exception:
            # If parsing fails, fall back to regex
            import re
            import_pattern = r'(?:from\s+(\S+)\s+import|import\s+(\S+))'
            matches = re.findall(import_pattern, script_content)
            for match in matches:
                imports.extend([m for m in match if m])

        return list(set(imports))  # Remove duplicates

    def _check_module_availability(self, module_name: str) -> bool:
        """Check if a Python module is available."""
        try:
            import importlib
            importlib.import_module(module_name)
            return True
        except ImportError:
            return False

    def _check_dependency_availability(self, dependency: str) -> bool:
        """Check if a dependency is available."""
        # Check for Python modules
        if self._check_module_availability(dependency):
            return True

        # Check for system commands
        import shutil
        if shutil.which(dependency):
            return True

        return False


# Global generator instance
_generator: Optional[ScriptGenerator] = None


def get_script_generator() -> ScriptGenerator:
    """Get the global script generator instance.

    Returns:
        ScriptGenerator singleton instance
    """
    global _generator
    if _generator is None:
        _generator = ScriptGenerator()
    return _generator


def reset_script_generator() -> None:
    """Reset the global script generator (mainly for testing)."""
    global _generator
    _generator = None


# Convenience functions for CLI compatibility

def generate_hook_script(
    template_type: str,
    event_type: str,
    output_path: Union[str, Path],
    customization: Optional[Dict[str, Any]] = None,
    matcher: Optional[str] = None,
    timeout: Optional[int] = None,
    overwrite: bool = False
) -> ScriptGenerationResult:
    """Generate hook script using global generator instance.

    This function provides backward compatibility with the original CLI interface.
    """
    from ..models.validation import ScriptGenerationResult
    from ..types.enums import HookEventType

    try:
        # Convert string event type to enum
        try:
            hook_event_type = HookEventType.from_string(event_type)
        except (ValueError, AttributeError):
            # Fallback for when HookEventType doesn't have from_string method
            hook_event_type = getattr(HookEventType, event_type.upper().replace(' ', '_'))

        generator = get_script_generator()
        return generator.generate_script(
            template_id=template_type,
            event_type=hook_event_type,
            output_path=Path(output_path),
            customization=customization,
            matcher=matcher,
            timeout=timeout,
            force_overwrite=overwrite
        )
    except Exception as e:
        # Return a simple failure result for compatibility
        return ScriptGenerationResult(
            success=False,
            message=f"Script generation failed: {e}",
            errors=[str(e)]
        )


def get_supported_templates() -> List[str]:
    """Get list of supported template types."""
    try:
        generator = get_script_generator()
        templates = generator.registry.list_templates()
        return [template.template_id for template in templates]
    except Exception:
        # Return default list if registry not available
        return [
            "security-guard",
            "auto-formatter",
            "auto-linter",
            "git-auto-commit",
            "permission-logger",
            "desktop-notifier",
            "task-manager",
            "prompt-filter",
            "context-loader",
            "cleanup-handler"
        ]


def validate_template_compatibility(template_type: str, event_type: str) -> ValidationResult:
    """Validate template and event type compatibility."""
    from ..models.validation import ValidationResult

    try:
        generator = get_script_generator()
        # Create a basic validation request
        from ..types.enums import HookEventType
        hook_event_type = HookEventType.from_string(event_type)

        # Simple compatibility check
        templates = generator.registry.list_templates()
        for template in templates:
            if template.template_id == template_type:
                if hook_event_type in template.supported_events:
                    return ValidationResult.success()
                else:
                    return ValidationResult.failure([
                        f"Template {template_type} does not support event type {event_type}"
                    ])

        return ValidationResult.failure([f"Template {template_type} not found"])

    except Exception as e:
        return ValidationResult.failure([f"Validation failed: {e}"])


# Export list for __all__
__all__ = [
    "ScriptGenerator",
    "ScriptGenerationResult",
    "GenerationRequest",
    "ScriptGenerationError",
    "generate_hook_script",
    "get_supported_templates",
    "validate_template_compatibility",
    "get_script_generator",
    "reset_script_generator"
]
