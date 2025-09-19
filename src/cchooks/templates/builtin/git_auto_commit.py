"""GitAutoCommitTemplate for automatic git operations.

This template provides automatic git operations including adding modified files,
generating intelligent commit messages, and optionally pushing changes. It supports
PostToolUse events to automatically commit changes after tool execution.

Features:
- Automatic git add for modified files
- Intelligent commit message generation
- Support for custom commit message templates
- Optional automatic push
- Git status checking and validation
- Error handling and graceful degradation
"""

from __future__ import annotations

import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from ...models.validation import ValidationResult
from ...types.enums import HookEventType
from ..base_template import BaseTemplate, TemplateConfig, template


@template(
    template_id="git-auto-commit",
    name="Git Auto Commit",
    description="Automatic git operations with intelligent commit messages"
)
class GitAutoCommitTemplate(BaseTemplate):
    """Template for automatic git operations after tool execution.

    This template automatically adds modified files to git, generates intelligent
    commit messages based on the tool execution context, and optionally pushes
    changes to remote repositories.
    """

    @property
    def name(self) -> str:
        return "Git Auto Commit"

    @property
    def description(self) -> str:
        return "Automatic git operations with intelligent commit messages"

    @property
    def supported_events(self) -> List[HookEventType]:
        return [HookEventType.POST_TOOL_USE]

    @property
    def customization_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "auto_add": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to automatically add modified files"
                },
                "auto_push": {
                    "type": "boolean",
                    "default": False,
                    "description": "Whether to automatically push commits"
                },
                "commit_message_template": {
                    "type": "string",
                    "default": "{tool_name}: {summary}",
                    "description": "Template for commit messages with placeholders"
                },
                "include_patterns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": ["*"],
                    "description": "File patterns to include in commits"
                },
                "exclude_patterns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": [".git/*", "*.tmp", "*.log"],
                    "description": "File patterns to exclude from commits"
                },
                "max_files": {
                    "type": "integer",
                    "minimum": 1,
                    "default": 50,
                    "description": "Maximum number of files to commit at once"
                },
                "require_clean_working_tree": {
                    "type": "boolean",
                    "default": False,
                    "description": "Whether to require a clean working tree before commit"
                },
                "author_name": {
                    "type": "string",
                    "default": "",
                    "description": "Override git author name (empty = use git config)"
                },
                "author_email": {
                    "type": "string",
                    "default": "",
                    "description": "Override git author email (empty = use git config)"
                },
                "branch_restrictions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": [],
                    "description": "Branches where auto-commit is allowed (empty = all branches)"
                },
                "commit_prefix": {
                    "type": "string",
                    "default": "",
                    "description": "Prefix to add to all commit messages"
                },
                "detailed_messages": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to generate detailed commit messages"
                }
            },
            "required": ["auto_add", "commit_message_template"]
        }

    def generate(self, config: TemplateConfig) -> str:
        """Generate the git auto-commit hook script."""
        # Validate event type
        self.validate_event_compatibility(config.event_type)

        # Get configuration
        custom_config = config.customization
        auto_add = custom_config.get("auto_add", True)
        auto_push = custom_config.get("auto_push", False)
        commit_template = custom_config.get("commit_message_template", "{tool_name}: {summary}")
        include_patterns = custom_config.get("include_patterns", ["*"])
        exclude_patterns = custom_config.get("exclude_patterns", [".git/*", "*.tmp", "*.log"])
        max_files = custom_config.get("max_files", 50)
        require_clean = custom_config.get("require_clean_working_tree", False)
        author_name = custom_config.get("author_name", "")
        author_email = custom_config.get("author_email", "")
        branch_restrictions = custom_config.get("branch_restrictions", [])
        commit_prefix = custom_config.get("commit_prefix", "")
        detailed_messages = custom_config.get("detailed_messages", True)

        # Generate script content
        script_header = self.create_script_header(config)

        # Create git configuration
        git_config = f'''
# Git auto-commit configuration
AUTO_ADD = {auto_add}
AUTO_PUSH = {auto_push}
COMMIT_MESSAGE_TEMPLATE = "{commit_template}"
INCLUDE_PATTERNS = {include_patterns!r}
EXCLUDE_PATTERNS = {exclude_patterns!r}
MAX_FILES = {max_files}
REQUIRE_CLEAN_WORKING_TREE = {require_clean}
AUTHOR_NAME = "{author_name}"
AUTHOR_EMAIL = "{author_email}"
BRANCH_RESTRICTIONS = {branch_restrictions!r}
COMMIT_PREFIX = "{commit_prefix}"
DETAILED_MESSAGES = {detailed_messages}
'''

        # Create helper functions
        helper_functions = '''
import subprocess
import fnmatch
import re
from datetime import datetime


def run_git_command(cmd: List[str], cwd: str = None) -> Dict[str, Any]:
    """Run a git command and return results."""
    try:
        result = subprocess.run(
            ["git"] + cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "returncode": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "stdout": "", "stderr": "Command timed out", "returncode": 1}
    except Exception as e:
        return {"success": False, "stdout": "", "stderr": str(e), "returncode": 1}


def is_git_repository(path: str = ".") -> bool:
    """Check if current directory is a git repository."""
    result = run_git_command(["status", "--porcelain"], cwd=path)
    return result["success"]


def get_current_branch() -> str:
    """Get the current git branch name."""
    result = run_git_command(["branch", "--show-current"])
    return result["stdout"] if result["success"] else ""


def is_working_tree_clean() -> bool:
    """Check if working tree is clean."""
    result = run_git_command(["status", "--porcelain"])
    return result["success"] and not result["stdout"]


def get_git_status() -> Dict[str, List[str]]:
    """Get git status categorized by change type."""
    result = run_git_command(["status", "--porcelain"])
    if not result["success"]:
        return {"modified": [], "added": [], "deleted": [], "untracked": []}

    status = {"modified": [], "added": [], "deleted": [], "untracked": []}
    for line in result["stdout"].split("\\n"):
        if not line.strip():
            continue

        status_code = line[:2]
        file_path = line[3:]

        if status_code.startswith("M") or status_code.startswith(" M"):
            status["modified"].append(file_path)
        elif status_code.startswith("A") or status_code.startswith(" A"):
            status["added"].append(file_path)
        elif status_code.startswith("D") or status_code.startswith(" D"):
            status["deleted"].append(file_path)
        elif status_code.startswith("??"):
            status["untracked"].append(file_path)

    return status


def should_include_file(file_path: str) -> bool:
    """Check if file should be included based on patterns."""
    # Check include patterns
    matches_include = any(fnmatch.fnmatch(file_path, pattern) for pattern in INCLUDE_PATTERNS)
    if not matches_include:
        return False

    # Check exclude patterns
    matches_exclude = any(fnmatch.fnmatch(file_path, pattern) for pattern in EXCLUDE_PATTERNS)
    return not matches_exclude


def get_files_to_commit(git_status: Dict[str, List[str]]) -> List[str]:
    """Get list of files to commit based on patterns and limits."""
    all_files = []
    all_files.extend(git_status["modified"])
    all_files.extend(git_status["added"])
    all_files.extend(git_status["deleted"])
    if AUTO_ADD:
        all_files.extend(git_status["untracked"])

    # Filter by patterns
    filtered_files = [f for f in all_files if should_include_file(f)]

    # Limit number of files
    if MAX_FILES > 0 and len(filtered_files) > MAX_FILES:
        filtered_files = filtered_files[:MAX_FILES]

    return filtered_files


def generate_commit_message(context, files: List[str]) -> str:
    """Generate intelligent commit message based on context and files."""
    # Extract tool information
    tool_name = getattr(context, 'tool_name', 'Unknown')

    # Analyze file changes
    file_types = {}
    for file_path in files:
        ext = Path(file_path).suffix.lower()
        file_types[ext] = file_types.get(ext, 0) + 1

    # Generate summary based on file types and count
    if len(files) == 1:
        summary = f"Update {files[0]}"
    elif len(files) <= 5:
        summary = f"Update {len(files)} files"
    else:
        # Describe by file types
        type_descriptions = []
        for ext, count in sorted(file_types.items(), key=lambda x: x[1], reverse=True)[:3]:
            if ext:
                type_descriptions.append(f"{count} {ext[1:]} file{'s' if count != 1 else ''}")
            else:
                type_descriptions.append(f"{count} file{'s' if count != 1 else ''}")
        summary = f"Update {', '.join(type_descriptions)}"

    # Create commit message from template
    message = COMMIT_MESSAGE_TEMPLATE.format(
        tool_name=tool_name,
        summary=summary,
        file_count=len(files),
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M")
    )

    # Add prefix if configured
    if COMMIT_PREFIX:
        message = f"{COMMIT_PREFIX} {message}"

    # Add detailed information if enabled
    if DETAILED_MESSAGES and len(files) <= 10:
        message += "\\n\\nFiles changed:"
        for file_path in sorted(files):
            message += f"\\n- {file_path}"

    return message


def add_files_to_git(files: List[str]) -> bool:
    """Add files to git staging area."""
    if not files:
        return True

    result = run_git_command(["add"] + files)
    return result["success"]


def commit_changes(message: str) -> bool:
    """Commit staged changes with the given message."""
    cmd = ["commit", "-m", message]

    # Add author information if configured
    if AUTHOR_NAME and AUTHOR_EMAIL:
        cmd.extend(["--author", f"{AUTHOR_NAME} <{AUTHOR_EMAIL}>"])

    result = run_git_command(cmd)
    return result["success"]


def push_changes() -> bool:
    """Push changes to remote repository."""
    result = run_git_command(["push"])
    return result["success"]


def check_branch_restrictions() -> bool:
    """Check if current branch is allowed for auto-commit."""
    if not BRANCH_RESTRICTIONS:
        return True

    current_branch = get_current_branch()
    return current_branch in BRANCH_RESTRICTIONS
'''

        # Create main logic
        main_logic = '''
        # Check if we're in a git repository
        if not is_git_repository():
            context.output.continue_flow("Not in a git repository, skipping auto-commit")
            return

        # Check branch restrictions
        if not check_branch_restrictions():
            current_branch = get_current_branch()
            context.output.continue_flow(f"Auto-commit not allowed on branch '{current_branch}'")
            return

        # Check if working tree should be clean
        if REQUIRE_CLEAN_WORKING_TREE and not is_working_tree_clean():
            context.output.continue_flow("Working tree is not clean, skipping auto-commit")
            return

        # Get git status
        git_status = get_git_status()
        files_to_commit = get_files_to_commit(git_status)

        if not files_to_commit:
            context.output.continue_flow("No files to commit")
            return

        # Add files if auto-add is enabled
        if AUTO_ADD:
            success = add_files_to_git(files_to_commit)
            if not success:
                context.output.fail("Failed to add files to git")
                return

        # Generate commit message
        commit_message = generate_commit_message(context, files_to_commit)

        # Commit changes
        success = commit_changes(commit_message)
        if not success:
            context.output.fail("Failed to commit changes")
            return

        # Push changes if auto-push is enabled
        pushed = False
        if AUTO_PUSH:
            pushed = push_changes()

        # Create response message
        file_count = len(files_to_commit)
        message = f"Auto-commit: committed {file_count} file{'s' if file_count != 1 else ''}"

        if pushed:
            message += " and pushed to remote"
        elif AUTO_PUSH:
            message += " but failed to push to remote"

        message += f"\\nCommit message: {commit_message}"

        context.output.continue_flow(message)
'''

        # Combine all parts
        return script_header + git_config + helper_functions + self.create_main_function(
            config.event_type, main_logic
        )

    def validate_config(self, config: Dict[str, Any]) -> ValidationResult:
        """Validate the git auto-commit configuration."""
        result = self.validate_schema(config, self.customization_schema)

        # Additional validation for commit message template
        template = config.get("commit_message_template", "")
        if template and "{" in template:
            # Check for valid placeholders
            valid_placeholders = ["tool_name", "summary", "file_count", "timestamp"]
            import re
            placeholders = re.findall(r'\{(\w+)\}', template)
            for placeholder in placeholders:
                if placeholder not in valid_placeholders:
                    result.add_warning(
                        field_name="commit_message_template",
                        warning_code="UNKNOWN_PLACEHOLDER",
                        message=f"Unknown placeholder '{placeholder}' in commit message template"
                    )

        # Validate email format if provided
        author_email = config.get("author_email", "")
        if author_email and "@" not in author_email:
            result.add_error(
                field_name="author_email",
                error_code="INVALID_EMAIL",
                message="Author email must be a valid email address",
                suggested_fix="Use format: user@domain.com"
            )

        return result

    def get_default_config(self) -> Dict[str, Any]:
        """Get default configuration for git auto-commit."""
        return {
            "auto_add": True,
            "auto_push": False,
            "commit_message_template": "{tool_name}: {summary}",
            "include_patterns": ["*"],
            "exclude_patterns": [".git/*", "*.tmp", "*.log"],
            "max_files": 50,
            "require_clean_working_tree": False,
            "author_name": "",
            "author_email": "",
            "branch_restrictions": [],
            "commit_prefix": "",
            "detailed_messages": True
        }

    def get_dependencies(self) -> List[str]:
        """Get dependencies for git auto-commit template."""
        return ["git"]
