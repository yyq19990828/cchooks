#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generated hook script from template: Context Loader
Event type: SessionStart
Generated for: demo_context_hook.py

Automatically loads project-specific context when Claude Code starts, including project files, git status, and development environment information
"""

# Dependencies: git, pathlib, subprocess

import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional


import datetime
import subprocess
from pathlib import Path

from cchooks import create_context


def main() -> None:
    """Main hook entry point."""
    try:
        # Create context from stdin
        context = create_context()

        # Validate event type
        if context.hook_event_name != "SessionStart":
            context.output.fail(
                f"Expected SessionStart event, got {context.hook_event_name}"
            )
            return

        # Template-specific logic
        # Initialize context sections
        context_sections = []
        project_root = Path.cwd()

        # Project Information Section
        context_sections.append("# Project Context")
        context_sections.append(f"**Project Path**: {project_root}")
        context_sections.append(f"**Loaded at**: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        context_sections.append("")

        # Load context files
        # Load specified context files
        context_files = ['.claude-context', 'README.md']
        for file_path in context_files:
            try:
                file_path_obj = project_root / file_path
                if file_path_obj.exists() and file_path_obj.is_file():
                    # Check file size
                    file_size_kb = file_path_obj.stat().st_size / 1024
                    if file_size_kb > 1024:
                        context_sections.append(f"⚠️ **{file_path}**: File too large ({file_size_kb:.1f}KB > 1024KB)")
                        continue

                    # Read file content
                    try:
                        content = file_path_obj.read_text(encoding="utf-8")
                        context_sections.append(f"## {file_path}")
                        context_sections.append("```")
                        context_sections.append(content.strip())
                        context_sections.append("```")
                        context_sections.append("")
                    except UnicodeDecodeError:
                        context_sections.append(f"⚠️ **{file_path}**: Unable to decode as utf-8")
                else:
                    context_sections.append(f"ℹ️ **{file_path}**: Not found")
            except Exception as e:
                context_sections.append(f"❌ **{file_path}**: Error reading file - {str(e)}")

        context_sections.append("")


        # Git information
        # Git Information
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


        # Development environment
        # Development Environment
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
                            lines = content.strip().split('\n')
                            if len(lines) > 20:
                                context_sections.append("\n".join(f"  {{line}}" for line in lines[:20]))
                                context_sections.append(f"  ... (and {{len(lines) - 20}} more lines)")
                            else:
                                context_sections.append("\n".join(f"  {{line}}" for line in lines))
                            context_sections.append("  ```")
                except Exception as e:
                    context_sections.append(f"- {{dep_file}}: Error reading file - {{str(e)}}")
        else:
            context_sections.append("**Dependency Files**: None found")

        context_sections.append("")


        # Documentation files
        # Documentation Files
        docs_dir = project_root / "docs"
        if docs_dir.exists() and docs_dir.is_dir():
            context_sections.append("## Documentation")

            doc_files = []
            extensions = ['.md', '.txt']

            try:
                # Find documentation files
                for ext in extensions:
                    doc_files.extend(docs_dir.glob(f"*{ext}"))
                    doc_files.extend(docs_dir.glob(f"**/*{ext}"))

                # Remove duplicates and sort
                doc_files = sorted(set(doc_files))

                if doc_files:
                    context_sections.append("**Documentation Files Found**:")
                    for doc_file in doc_files[:10]:  # Limit to first 10 files
                        relative_path = doc_file.relative_to(project_root)
                        file_size_kb = doc_file.stat().st_size / 1024
                        if file_size_kb > 100:  # Don't load very large files
                            context_sections.append(f"- {relative_path} ({file_size_kb:.1f}KB - too large to load)")
                        else:
                            context_sections.append(f"- {relative_path}")

                    if len(doc_files) > 10:
                        context_sections.append(f"- ... and {len(doc_files) - 10} more files")
                else:
                    context_sections.append("**Documentation Files**: None found with supported extensions")

            except Exception as e:
                context_sections.append(f"**Documentation Files**: Error scanning docs directory - {str(e)}")
        else:
            context_sections.append("## Documentation")
            context_sections.append("**Documentation Directory**: Not found")

        context_sections.append("")


        # Combine all context sections
        full_context = "\n".join(context_sections)

        # Output context to Claude
        context.output.append_message(
            "🔍 **Project Context Loaded**\n\n" + full_context,
            message_type="system"
        )

        # Exit successfully
        context.output.continue_flow("Context loaded successfully")

    except Exception as e:
        # Handle unexpected errors
        print(json.dumps({
            "continue": False,
            "stopReason": f"Hook error: {str(e)}",
            "suppressOutput": False
        }))
        sys.exit(1)


if __name__ == "__main__":
    main()
