"""ContextLoaderTemplate for loading project context at session start.

This template generates hooks that automatically load project-specific context
when Claude Code starts, including project files, git information, development
environment details, and other relevant project data.

The generated script provides Claude with comprehensive project context to
improve its understanding and provide better assistance.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from ...models.validation import ValidationResult
from ...types.enums import HookEventType
from ..base_template import BaseTemplate, TemplateConfig


class ContextLoaderTemplate(BaseTemplate):
    """Template for generating context loader hooks.

    This template creates hooks that automatically load project context when
    Claude Code starts a new session. It supports various context sources:

    - Project files: README.md, .claude-context, documentation files
    - Git information: current branch, status, recent commits, remote info
    - Development environment: package.json, pyproject.toml, requirements.txt
    - Documentation files: docs/ directory contents

    The generated script provides structured, formatted context to Claude.
    """

    @property
    def name(self) -> str:
        """Human-readable name of the template."""
        return "Context Loader"

    @property
    def description(self) -> str:
        """Description of what this template does."""
        return ("Automatically loads project-specific context when Claude Code starts, "
                "including project files, git status, and development environment information")

    @property
    def supported_events(self) -> List[HookEventType]:
        """List of hook event types this template supports."""
        return [HookEventType.SESSION_START]

    @property
    def customization_schema(self) -> Dict[str, Any]:
        """JSON schema for validating customization options."""
        return {
            "type": "object",
            "properties": {
                "context_files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": [".claude-context", "README.md"],
                    "description": "List of context files to load"
                },
                "include_git_status": {
                    "type": "boolean",
                    "default": True,
                    "description": "Include git status and branch information"
                },
                "include_dependencies": {
                    "type": "boolean",
                    "default": True,
                    "description": "Include development dependencies information"
                },
                "max_file_size": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10240,
                    "default": 1024,
                    "description": "Maximum file size to load in KB"
                },
                "encoding": {
                    "type": "string",
                    "default": "utf-8",
                    "description": "File encoding to use when reading files"
                },
                "include_docs": {
                    "type": "boolean",
                    "default": True,
                    "description": "Include documentation files from docs/ directory"
                },
                "docs_extensions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": [".md", ".txt", ".rst"],
                    "description": "File extensions to include from docs directory"
                }
            },
            "additionalProperties": False
        }

    def generate(self, config: TemplateConfig) -> str:
        """Generate context loader hook script."""
        self.validate_event_compatibility(config.event_type)

        # Get customization options with defaults
        customization = config.customization
        context_files = customization.get("context_files", [".claude-context", "README.md"])
        include_git_status = customization.get("include_git_status", True)
        include_dependencies = customization.get("include_dependencies", True)
        max_file_size = customization.get("max_file_size", 1024)
        encoding = customization.get("encoding", "utf-8")
        include_docs = customization.get("include_docs", True)
        docs_extensions = customization.get("docs_extensions", [".md", ".txt", ".rst"])

        # Generate script header
        header = self.create_script_header(config)

        # Generate main script logic
        main_logic = self._generate_context_loader_logic(
            context_files, include_git_status, include_dependencies,
            max_file_size, encoding, include_docs, docs_extensions
        )

        # Create complete script
        main_function = self.create_main_function(config.event_type, main_logic)

        return header + main_function

    def validate_config(self, config: Dict[str, Any]) -> ValidationResult:
        """Validate template-specific customization configuration."""
        result = self.validate_schema(config, self.customization_schema)

        # Additional validation for context files
        context_files = config.get("context_files", [])
        if not context_files:
            result.add_warning(
                field_name="context_files",
                warning_code="EMPTY_CONTEXT_FILES",
                message="No context files specified - hook will only include system context"
            )

        # Validate file extensions
        docs_extensions = config.get("docs_extensions", [])
        for ext in docs_extensions:
            if not ext.startswith('.'):
                result.add_error(
                    field_name="docs_extensions",
                    error_code="INVALID_EXTENSION",
                    message=f"File extension '{ext}' must start with '.'",
                    suggested_fix=f"Change '{ext}' to '.{ext}'"
                )

        return result

    def get_default_config(self) -> Dict[str, Any]:
        """Get default customization configuration for this template."""
        return {
            "context_files": [".claude-context", "README.md"],
            "include_git_status": True,
            "include_dependencies": True,
            "max_file_size": 1024,
            "encoding": "utf-8",
            "include_docs": True,
            "docs_extensions": [".md", ".txt", ".rst"]
        }

    def get_dependencies(self) -> List[str]:
        """Get list of dependencies required by this template."""
        return ["git", "pathlib", "subprocess"]

    def create_script_header(self, config: TemplateConfig) -> str:
        """Create enhanced script header with additional imports."""
        base_header = super().create_script_header(config)

        # Additional imports needed for the context loader
        additional_imports = '''
import datetime
import subprocess
from pathlib import Path
'''

        # Insert additional imports after the standard imports
        import_insertion_point = base_header.find("from cchooks import create_context")
        if import_insertion_point != -1:
            before_imports = base_header[:import_insertion_point]
            after_imports = base_header[import_insertion_point:]
            return before_imports + additional_imports + "\n" + after_imports
        else:
            return base_header + additional_imports

    def _generate_context_loader_logic(
        self,
        context_files: List[str],
        include_git_status: bool,
        include_dependencies: bool,
        max_file_size: int,
        encoding: str,
        include_docs: bool,
        docs_extensions: List[str]
    ) -> str:
        """Generate the main context loading logic."""
        return f'''# Initialize context sections
context_sections = []
project_root = Path.cwd()

# Project Information Section
context_sections.append("# Project Context")
context_sections.append(f"**Project Path**: {{project_root}}")
context_sections.append(f"**Loaded at**: {{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}}")
context_sections.append("")

# Load context files
{self._generate_file_loading_logic(context_files, max_file_size, encoding)}

# Git information
{self._generate_git_logic() if include_git_status else "# Git status disabled"}

# Development environment
{self._generate_dependencies_logic() if include_dependencies else "# Dependencies scanning disabled"}

# Documentation files
{self._generate_docs_logic(docs_extensions) if include_docs else "# Documentation scanning disabled"}

# Combine all context sections
full_context = "\\n".join(context_sections)

# Output context to Claude
context.output.append_message(
    "🔍 **Project Context Loaded**\\n\\n" + full_context,
    message_type="system"
)

# Exit successfully
context.output.continue_flow("Context loaded successfully")
'''

    def _generate_file_loading_logic(
        self,
        context_files: List[str],
        max_file_size: int,
        encoding: str
    ) -> str:
        """Generate logic for loading context files."""
        context_files_str = repr(context_files)
        return f'''# Load specified context files
context_files = {context_files_str}
for file_path in context_files:
    try:
        file_path_obj = project_root / file_path
        if file_path_obj.exists() and file_path_obj.is_file():
            # Check file size
            file_size_kb = file_path_obj.stat().st_size / 1024
            if file_size_kb > {max_file_size}:
                context_sections.append(f"⚠️ **{{file_path}}**: File too large ({{file_size_kb:.1f}}KB > {max_file_size}KB)")
                continue

            # Read file content
            try:
                content = file_path_obj.read_text(encoding="{encoding}")
                context_sections.append(f"## {{file_path}}")
                context_sections.append("```")
                context_sections.append(content.strip())
                context_sections.append("```")
                context_sections.append("")
            except UnicodeDecodeError:
                context_sections.append(f"⚠️ **{{file_path}}**: Unable to decode as {encoding}")
        else:
            context_sections.append(f"ℹ️ **{{file_path}}**: Not found")
    except Exception as e:
        context_sections.append(f"❌ **{{file_path}}**: Error reading file - {{str(e)}}")

context_sections.append("")
'''

    def _generate_git_logic(self) -> str:
        """Generate logic for git information."""
        return '''# Git Information
try:
    import subprocess

    context_sections.append("## Git Information")

    # Current branch
    try:
        branch_result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, cwd=project_root, timeout=5
        )
        if branch_result.returncode == 0:
            current_branch = branch_result.stdout.strip()
            context_sections.append(f"**Current Branch**: {{current_branch}}")
        else:
            context_sections.append("**Current Branch**: Unable to determine")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        context_sections.append("**Current Branch**: Git not available")

    # Git status
    try:
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, cwd=project_root, timeout=5
        )
        if status_result.returncode == 0:
            status_output = status_result.stdout.strip()
            if status_output:
                context_sections.append("**Working Directory Status**:")
                context_sections.append("```")
                context_sections.append(status_output)
                context_sections.append("```")
            else:
                context_sections.append("**Working Directory Status**: Clean")
        else:
            context_sections.append("**Working Directory Status**: Unable to determine")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Recent commits
    try:
        log_result = subprocess.run(
            ["git", "log", "--oneline", "-5"],
            capture_output=True, text=True, cwd=project_root, timeout=5
        )
        if log_result.returncode == 0:
            log_output = log_result.stdout.strip()
            if log_output:
                context_sections.append("**Recent Commits**:")
                context_sections.append("```")
                context_sections.append(log_output)
                context_sections.append("```")
        else:
            context_sections.append("**Recent Commits**: Unable to retrieve")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Remote information
    try:
        remote_result = subprocess.run(
            ["git", "remote", "-v"],
            capture_output=True, text=True, cwd=project_root, timeout=5
        )
        if remote_result.returncode == 0:
            remote_output = remote_result.stdout.strip()
            if remote_output:
                context_sections.append("**Remote Repositories**:")
                context_sections.append("```")
                context_sections.append(remote_output)
                context_sections.append("```")
        else:
            context_sections.append("**Remote Repositories**: None configured")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    context_sections.append("")

except ImportError:
    context_sections.append("## Git Information")
    context_sections.append("⚠️ subprocess module not available")
    context_sections.append("")
'''

    def _generate_dependencies_logic(self) -> str:
        """Generate logic for development environment detection."""
        return '''# Development Environment
context_sections.append("## Development Environment")

# Detect project type and dependencies
project_type = "Unknown"
dependency_files = []

# Python projects
if (project_root / "pyproject.toml").exists():
    project_type = "Python (pyproject.toml)"
    dependency_files.append("pyproject.toml")
elif (project_root / "requirements.txt").exists():
    project_type = "Python (requirements.txt)"
    dependency_files.append("requirements.txt")
elif (project_root / "setup.py").exists():
    project_type = "Python (setup.py)"
    dependency_files.append("setup.py")
elif (project_root / "Pipfile").exists():
    project_type = "Python (Pipfile)"
    dependency_files.append("Pipfile")

# Node.js projects
if (project_root / "package.json").exists():
    if project_type == "Unknown":
        project_type = "Node.js"
    else:
        project_type += " + Node.js"
    dependency_files.append("package.json")

# Rust projects
if (project_root / "Cargo.toml").exists():
    if project_type == "Unknown":
        project_type = "Rust"
    else:
        project_type += " + Rust"
    dependency_files.append("Cargo.toml")

# Go projects
if (project_root / "go.mod").exists():
    if project_type == "Unknown":
        project_type = "Go"
    else:
        project_type += " + Go"
    dependency_files.append("go.mod")

# Java/Kotlin projects
if (project_root / "pom.xml").exists():
    if project_type == "Unknown":
        project_type = "Java (Maven)"
    else:
        project_type += " + Java (Maven)"
    dependency_files.append("pom.xml")
elif (project_root / "build.gradle").exists() or (project_root / "build.gradle.kts").exists():
    if project_type == "Unknown":
        project_type = "Java/Kotlin (Gradle)"
    else:
        project_type += " + Java/Kotlin (Gradle)"
    dependency_files.extend([f for f in ["build.gradle", "build.gradle.kts"]
                           if (project_root / f).exists()])

context_sections.append(f"**Project Type**: {{project_type}}")

# Load dependency files
if dependency_files:
    context_sections.append("**Dependency Files**:")
    for dep_file in dependency_files:
        try:
            dep_path = project_root / dep_file
            if dep_path.exists():
                # For large files, just show existence
                file_size_kb = dep_path.stat().st_size / 1024
                if file_size_kb > 50:  # Limit for dependency files
                    context_sections.append(f"- {{dep_file}} (exists, {{file_size_kb:.1f}}KB)")
                else:
                    content = dep_path.read_text(encoding="utf-8")
                    context_sections.append(f"- **{{dep_file}}**:")
                    context_sections.append("  ```")
                    # Show only first 20 lines for brevity
                    lines = content.strip().split('\\n')
                    if len(lines) > 20:
                        context_sections.append("\\n".join(f"  {{line}}" for line in lines[:20]))
                        context_sections.append(f"  ... (and {{len(lines) - 20}} more lines)")
                    else:
                        context_sections.append("\\n".join(f"  {{line}}" for line in lines))
                    context_sections.append("  ```")
        except Exception as e:
            context_sections.append(f"- {{dep_file}}: Error reading file - {{str(e)}}")
else:
    context_sections.append("**Dependency Files**: None found")

context_sections.append("")
'''

    def _generate_docs_logic(self, docs_extensions: List[str]) -> str:
        """Generate logic for documentation files."""
        extensions_str = repr(docs_extensions)
        return f'''# Documentation Files
docs_dir = project_root / "docs"
if docs_dir.exists() and docs_dir.is_dir():
    context_sections.append("## Documentation")

    doc_files = []
    extensions = {extensions_str}

    try:
        # Find documentation files
        for ext in extensions:
            doc_files.extend(docs_dir.glob(f"*{{ext}}"))
            doc_files.extend(docs_dir.glob(f"**/*{{ext}}"))

        # Remove duplicates and sort
        doc_files = sorted(set(doc_files))

        if doc_files:
            context_sections.append("**Documentation Files Found**:")
            for doc_file in doc_files[:10]:  # Limit to first 10 files
                relative_path = doc_file.relative_to(project_root)
                file_size_kb = doc_file.stat().st_size / 1024
                if file_size_kb > 100:  # Don't load very large files
                    context_sections.append(f"- {{relative_path}} ({{file_size_kb:.1f}}KB - too large to load)")
                else:
                    context_sections.append(f"- {{relative_path}}")

            if len(doc_files) > 10:
                context_sections.append(f"- ... and {{len(doc_files) - 10}} more files")
        else:
            context_sections.append("**Documentation Files**: None found with supported extensions")

    except Exception as e:
        context_sections.append(f"**Documentation Files**: Error scanning docs directory - {{str(e)}}")
else:
    context_sections.append("## Documentation")
    context_sections.append("**Documentation Directory**: Not found")

context_sections.append("")
'''


