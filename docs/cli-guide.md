# CCHooks CLI Guide

Complete guide for using the CCHooks CLI tools to manage Claude Code hook configurations.

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Commands Overview](#commands-overview)
- [Hook Management Commands](#hook-management-commands)
- [Template Management Commands](#template-management-commands)
- [Output Formats](#output-formats)
- [Settings File Levels](#settings-file-levels)
- [Hook Event Types](#hook-event-types)
- [Built-in Templates](#built-in-templates)
- [Examples & Workflows](#examples--workflows)
- [Error Handling](#error-handling)
- [Best Practices](#best-practices)

## Installation

```bash
# Install from wheel package
pip install dist/cchooks-0.1.0-py3-none-any.whl

# Or install in development mode
pip install -e .

# Verify installation
cchooks --help
```

## Quick Start

```bash
# List all available commands
cchooks --help

# List all configured hooks
cchooks listhooks

# Add a simple hook
cchooks addhook --event SessionStart --command "echo 'Claude started'" --level project

# Generate a security guard hook
cchooks generatehook security-guard PreToolUse ./security.py --matcher "Bash|Write" --add-to-settings

# Validate all hook configurations
cchooks validatehooks
```

## Commands Overview

CCHooks provides 9 main commands organized into two categories:

### Hook Management
- `addhook` - Add a new hook configuration
- `updatehook` - Update existing hook configuration
- `removehook` - Remove hook configuration
- `listhooks` - List configured hooks
- `validatehooks` - Validate hook configurations

### Template Management
- `generatehook` - Generate hook script from template
- `registertemplate` - Register custom hook template
- `listtemplates` - List available templates
- `unregistertemplate` - Unregister custom template

## Hook Management Commands

### cchooks addhook

Add a new hook configuration to settings file.

**Syntax:**
```bash
cchooks addhook --event EVENT [--command COMMAND | --script SCRIPT] [OPTIONS]
```

**Required Arguments:**
- `--event` - Hook event type (PreToolUse, PostToolUse, Notification, UserPromptSubmit, Stop, SubagentStop, PreCompact, SessionStart, SessionEnd)

**Required (one of):**
- `--command` - Shell command to execute
- `--script` - Path to Python script file

**Optional Arguments:**
- `--matcher` - Tool name pattern (required for PreToolUse/PostToolUse)
- `--timeout` - Execution timeout in seconds (1-3600)
- `--level` - Settings level (project, user) [default: project]
- `--format` - Output format (json, table, quiet) [default: table]
- `--dry-run` - Preview changes without applying
- `--backup` - Create backup before changes [default: true]
- `--auto-chmod` - Make script executable [default: true]

**Examples:**

```bash
# Add a simple notification hook
cchooks addhook --event SessionStart --command "echo 'Welcome to Claude Code!'" --level project

# Add a PreToolUse security hook with timeout
cchooks addhook --event PreToolUse --command "python security_check.py" --matcher "Bash|Write" --timeout 30 --level project

# Add a PostToolUse hook using script file
cchooks addhook --event PostToolUse --script ./hooks/formatter.py --matcher "Write" --level user

# Preview adding a hook without actually creating it
cchooks addhook --event Stop --command "cleanup.sh" --dry-run --format json

# Add hook with no backup
cchooks addhook --event SessionEnd --command "save_session.py" --backup false
```

### cchooks updatehook

Update existing hook configuration.

**Syntax:**
```bash
cchooks updatehook --event EVENT --index INDEX [OPTIONS]
```

**Required Arguments:**
- `--event` - Hook event type
- `--index` - Index of hook to update (from `listhooks`)

**Optional Arguments:**
- `--command` - New shell command
- `--matcher` - New tool matcher pattern
- `--timeout` - New timeout value
- `--level` - Settings level [default: project]
- `--format` - Output format [default: table]
- `--dry-run` - Preview changes without applying
- `--backup` - Create backup before changes [default: true]

**Examples:**

```bash
# Update command for first PreToolUse hook
cchooks updatehook --event PreToolUse --index 0 --command "python new_security.py"

# Update timeout for PostToolUse hook
cchooks updatehook --event PostToolUse --index 1 --timeout 60 --level user

# Preview updating a hook
cchooks updatehook --event SessionStart --index 0 --command "new_startup.sh" --dry-run

# Update matcher pattern
cchooks updatehook --event PreToolUse --index 2 --matcher "Write|Edit|MultiEdit"
```

### cchooks removehook

Remove hook configuration from settings.

**Syntax:**
```bash
cchooks removehook --event EVENT --index INDEX [OPTIONS]
```

**Required Arguments:**
- `--event` - Hook event type
- `--index` - Index of hook to remove (from `listhooks`)

**Optional Arguments:**
- `--level` - Settings level [default: project]
- `--format` - Output format [default: table]
- `--dry-run` - Preview changes without applying
- `--backup` - Create backup before changes [default: true]

**Examples:**

```bash
# Remove first PreToolUse hook
cchooks removehook --event PreToolUse --index 0

# Remove hook from user-level settings
cchooks removehook --event SessionEnd --index 1 --level user

# Preview removing a hook
cchooks removehook --event Notification --index 0 --dry-run --format json

# Remove without creating backup
cchooks removehook --event Stop --index 2 --backup false
```

### cchooks listhooks

List configured hooks with filtering options.

**Syntax:**
```bash
cchooks listhooks [OPTIONS]
```

**Optional Arguments:**
- `--event` - Filter by event type
- `--level` - Settings level to query (project, user, all) [default: all]
- `--format` - Output format (json, table, yaml) [default: table]

**Examples:**

```bash
# List all hooks in table format
cchooks listhooks

# List only PreToolUse hooks
cchooks listhooks --event PreToolUse

# List project-level hooks only
cchooks listhooks --level project

# List user hooks in JSON format
cchooks listhooks --level user --format json

# List SessionStart hooks in YAML format
cchooks listhooks --event SessionStart --format yaml
```

### cchooks validatehooks

Validate hook configurations for errors and compliance.

**Syntax:**
```bash
cchooks validatehooks [OPTIONS]
```

**Optional Arguments:**
- `--level` - Settings level to validate (project, user, all) [default: all]
- `--format` - Output format (json, table) [default: table]
- `--strict` - Treat warnings as errors

**Examples:**

```bash
# Validate all hooks
cchooks validatehooks

# Validate only project hooks
cchooks validatehooks --level project

# Validate with strict mode (warnings become errors)
cchooks validatehooks --strict --format json

# Validate user-level hooks only
cchooks validatehooks --level user
```

## Template Management Commands

### cchooks generatehook

Generate Python hook script from predefined templates.

**Syntax:**
```bash
cchooks generatehook TYPE EVENT OUTPUT [OPTIONS]
```

**Required Arguments:**
- `TYPE` - Template type (security-guard, auto-formatter, auto-linter, git-auto-commit, permission-logger, desktop-notifier, task-manager, prompt-filter, context-loader, cleanup-handler)
- `EVENT` - Hook event type
- `OUTPUT` - Output file path for generated script

**Optional Arguments:**
- `--add-to-settings` - Automatically add to settings
- `--level` - Settings level when adding [default: project]
- `--matcher` - Tool matcher pattern (for PreToolUse/PostToolUse)
- `--customization` - Template-specific options (JSON format)
- `--format` - Output format [default: table]
- `--overwrite` - Overwrite existing file

**Examples:**

```bash
# Generate security guard hook
cchooks generatehook security-guard PreToolUse ./hooks/security.py --matcher "Bash|Write"

# Generate and add to settings automatically
cchooks generatehook auto-formatter PostToolUse ./hooks/format.py --matcher "Write" --add-to-settings

# Generate with custom configuration
cchooks generatehook context-loader SessionStart ./hooks/context.py \
  --customization '{"context_files": [".claude-context", "README.md"], "include_git_status": true}' \
  --add-to-settings

# Generate task manager hook
cchooks generatehook task-manager Stop ./hooks/cleanup.py --level user

# Generate with overwrite permission
cchooks generatehook desktop-notifier Notification ./hooks/notify.py --overwrite --format json
```

### cchooks registertemplate

Register a new custom hook template.

**Syntax:**
```bash
cchooks registertemplate --name NAME [--file FILE | --class CLASS] [OPTIONS]
```

**Required Arguments:**
- `--name` - Unique template name/ID

**Required (one of):**
- `--file` - Path to Python file containing template class
- `--class` - Fully qualified class name (module.ClassName)

**Optional Arguments:**
- `--description` - Template description
- `--events` - Supported hook events (space-separated)
- `--version` - Template version [default: 1.0.0]
- `--global` - Register globally vs project-level
- `--force` - Overwrite existing template
- `--format` - Output format [default: table]

**Examples:**

```bash
# Register template from file
cchooks registertemplate --name team-workflow --file ./templates/team.py \
  --description "Team workflow automation" --events PreToolUse PostToolUse

# Register template by class name
cchooks registertemplate --name custom-logger --class mypackage.CustomLoggerTemplate \
  --events Notification --version 2.0.0

# Register globally
cchooks registertemplate --name org-security --file ./security_template.py --global

# Force overwrite existing template
cchooks registertemplate --name existing-template --file ./new_template.py --force
```

### cchooks listtemplates

List available hook templates.

**Syntax:**
```bash
cchooks listtemplates [OPTIONS]
```

**Optional Arguments:**
- `--event` - Filter by supported event type
- `--source` - Filter by source (builtin, user, file, plugin, all) [default: all]
- `--format` - Output format (json, table, yaml) [default: table]
- `--show-config` - Show customization options

**Examples:**

```bash
# List all templates
cchooks listtemplates

# List templates for PreToolUse events
cchooks listtemplates --event PreToolUse

# List only built-in templates
cchooks listtemplates --source builtin

# List user templates with configuration options
cchooks listtemplates --source user --show-config

# List all templates in JSON format
cchooks listtemplates --format json
```

### cchooks unregistertemplate

Unregister a custom hook template.

**Syntax:**
```bash
cchooks unregistertemplate --name NAME [OPTIONS]
```

**Required Arguments:**
- `--name` - Template name/ID to unregister

**Optional Arguments:**
- `--global` - Unregister from global registry
- `--force` - Force unregister without confirmation
- `--format` - Output format [default: table]

**Examples:**

```bash
# Unregister a template
cchooks unregistertemplate --name old-template

# Unregister global template
cchooks unregistertemplate --name org-template --global

# Force unregister without confirmation
cchooks unregistertemplate --name unwanted-template --force
```

## Output Formats

CCHooks supports multiple output formats for different use cases:

### Table Format (Default)
Human-readable tabular output with clear formatting.

```bash
cchooks listhooks --format table
```

### JSON Format
Machine-readable structured data for scripting and automation.

```bash
cchooks listhooks --format json | jq '.data.hooks'
```

### YAML Format
Human-readable structured data (where supported).

```bash
cchooks listhooks --format yaml
```

### Quiet Format
Minimal output for scripting (some commands only).

```bash
cchooks addhook --event SessionStart --command "echo test" --format quiet
```

## Settings File Levels

CCHooks manages hooks at two levels:

### Project Level
- **Location**: `.claude/settings.json` in current directory
- **Scope**: Current project only
- **Use case**: Project-specific hooks
- **Default**: Most commands default to project level

### User Level
- **Location**: `~/.claude/settings.json` in home directory
- **Scope**: All Claude Code projects for the user
- **Use case**: Global hooks and preferences
- **Access**: Use `--level user` flag

### All Levels
- **Scope**: Query both project and user levels
- **Use case**: Complete view of active hooks
- **Access**: Use `--level all` flag (default for `listhooks` and `validatehooks`)

**Precedence**: Project-level hooks take precedence over user-level hooks.

## Hook Event Types

CCHooks supports all Claude Code hook events:

| Event Type | Description | When Triggered | Requires Matcher |
|------------|-------------|----------------|------------------|
| `PreToolUse` | Before tool execution | Before any tool is used | Yes |
| `PostToolUse` | After tool execution | After tool completes | Yes |
| `Notification` | System notifications | On system notifications | No |
| `UserPromptSubmit` | User input validation | When user submits prompt | No |
| `Stop` | Interruption handling | When execution is stopped | No |
| `SubagentStop` | Subagent termination | When subagent stops | No |
| `PreCompact` | Before compaction | Before context compaction | No |
| `SessionStart` | Session initialization | When Claude Code starts | No |
| `SessionEnd` | Session cleanup | When Claude Code ends | No |

### Matcher Patterns

For `PreToolUse` and `PostToolUse` events, you must specify which tools to match:

```bash
# Single tool
--matcher "Write"

# Multiple tools (OR logic)
--matcher "Write|Edit|MultiEdit"

# All tools
--matcher "*"

# Pattern matching
--matcher ".*Edit.*"
```

## Built-in Templates

CCHooks includes 10 built-in templates for common use cases:

### 1. Security Guard
**Type**: `security-guard`
**Events**: PreToolUse
**Description**: Multi-tool security protection with configurable rules.

```bash
cchooks generatehook security-guard PreToolUse ./security.py --matcher "Bash|Write"
```

**Customization Options**:
```json
{
  "blocked_patterns": ["rm -rf", "sudo rm"],
  "protected_paths": ["/", "/etc", "~/.ssh"],
  "warning_only": false,
  "log_file": "~/.claude/security.log"
}
```

### 2. Auto Formatter
**Type**: `auto-formatter`
**Events**: PostToolUse
**Description**: Automatically formats Python files after tool operations.

```bash
cchooks generatehook auto-formatter PostToolUse ./formatter.py --matcher "Write|Edit"
```

**Customization Options**:
```json
{
  "formatters": ["black", "isort"],
  "max_line_length": 88,
  "file_patterns": ["*.py"],
  "skip_patterns": ["*test*"]
}
```

### 3. Auto Linter
**Type**: `auto-linter`
**Events**: PostToolUse
**Description**: Automatic code quality checking with multiple linters.

```bash
cchooks generatehook auto-linter PostToolUse ./linter.py --matcher "Write"
```

### 4. Git Auto Commit
**Type**: `git-auto-commit`
**Events**: PostToolUse
**Description**: Automatic git operations with intelligent commit messages.

```bash
cchooks generatehook git-auto-commit PostToolUse ./git_commit.py --matcher "Write|Edit"
```

### 5. Permission Logger
**Type**: `permission-logger`
**Events**: PreToolUse
**Description**: Comprehensive logging of tool usage requests.

```bash
cchooks generatehook permission-logger PreToolUse ./logger.py --matcher "*"
```

### 6. Desktop Notifier
**Type**: `desktop-notifier`
**Events**: Notification
**Description**: Cross-platform desktop notifications.

```bash
cchooks generatehook desktop-notifier Notification ./notifier.py
```

### 7. Task Manager
**Type**: `task-manager`
**Events**: Stop
**Description**: Resource cleanup and state management.

```bash
cchooks generatehook task-manager Stop ./task_mgr.py
```

### 8. Prompt Filter
**Type**: `prompt-filter`
**Events**: UserPromptSubmit
**Description**: Sensitive information detection and filtering.

```bash
cchooks generatehook prompt-filter UserPromptSubmit ./filter.py
```

### 9. Context Loader
**Type**: `context-loader`
**Events**: SessionStart
**Description**: Loads project-specific context when Claude Code starts.

```bash
cchooks generatehook context-loader SessionStart ./context.py
```

**Customization Options**:
```json
{
  "context_files": [".claude-context", "README.md"],
  "include_git_status": true,
  "max_file_size": 1024000
}
```

### 10. Cleanup Handler
**Type**: `cleanup-handler`
**Events**: SessionEnd
**Description**: Comprehensive session cleanup and resource management.

```bash
cchooks generatehook cleanup-handler SessionEnd ./cleanup.py
```

## Examples & Workflows

### Basic Hook Management Workflow

```bash
# 1. Check current hooks
cchooks listhooks

# 2. Add a simple startup message
cchooks addhook --event SessionStart --command "echo 'Claude Code started at $(date)'" --level project

# 3. Add security monitoring
cchooks generatehook security-guard PreToolUse ./hooks/security.py --matcher "Bash" --add-to-settings

# 4. Validate all configurations
cchooks validatehooks

# 5. List hooks to verify
cchooks listhooks --format table
```

### Development Workflow Setup

```bash
# Create hooks directory
mkdir -p ./hooks

# Add context loader for development environment
cchooks generatehook context-loader SessionStart ./hooks/dev_context.py \
  --customization '{"context_files": [".env", "README.md", "pyproject.toml"]}' \
  --add-to-settings

# Add auto-formatter for Python files
cchooks generatehook auto-formatter PostToolUse ./hooks/format.py \
  --matcher "Write|Edit" --add-to-settings

# Add git auto-commit for documentation
cchooks generatehook git-auto-commit PostToolUse ./hooks/git_commit.py \
  --matcher "Write" \
  --customization '{"auto_commit_patterns": ["*.md", "*.rst"], "commit_prefix": "docs: "}' \
  --add-to-settings

# Add cleanup on session end
cchooks generatehook cleanup-handler SessionEnd ./hooks/cleanup.py --add-to-settings
```

### Security-Focused Setup

```bash
# Add comprehensive security guard
cchooks generatehook security-guard PreToolUse ./hooks/security.py \
  --matcher "*" \
  --customization '{
    "blocked_patterns": ["rm -rf", "sudo rm", "chmod 777", "dd if=", "mkfs"],
    "protected_paths": ["/", "/boot", "/etc", "/usr", "~/.ssh", "~/.aws"],
    "warning_only": false,
    "log_file": "~/.claude/security.log"
  }' \
  --add-to-settings

# Add permission logging
cchooks generatehook permission-logger PreToolUse ./hooks/audit.py \
  --matcher "*" --add-to-settings

# Add prompt filtering for sensitive data
cchooks generatehook prompt-filter UserPromptSubmit ./hooks/filter.py --add-to-settings

# Validate security setup
cchooks validatehooks --strict
```

### Team Template Management

```bash
# Register a team-specific template
cat > team_template.py << 'EOF'
from cchooks.templates import BaseTemplate, template
from cchooks.types import HookEventType

@template(
    name="team-notification",
    events=[HookEventType.POST_TOOL_USE],
    description="Team Slack notifications for code changes"
)
class TeamNotificationTemplate(BaseTemplate):
    def get_default_config(self):
        return {
            "slack_webhook": "",
            "channels": ["#dev", "#notifications"],
            "file_patterns": ["*.py", "*.js", "*.md"]
        }

    def generate(self, config):
        # Template implementation
        pass
EOF

# Register the template
cchooks registertemplate --name team-notification --file team_template.py \
  --description "Team Slack notifications" --events PostToolUse

# List available templates
cchooks listtemplates --source user

# Use the custom template
cchooks generatehook team-notification PostToolUse ./hooks/team_notify.py \
  --matcher "Write|Edit" \
  --customization '{"slack_webhook": "https://hooks.slack.com/..."}' \
  --add-to-settings
```

### Multi-Level Configuration

```bash
# Set up user-level global hooks
cchooks addhook --event SessionStart --command "notify-send 'Claude Code Started'" --level user
cchooks generatehook desktop-notifier Notification ./hooks/global_notify.py --level user --add-to-settings

# Set up project-specific hooks
cchooks generatehook security-guard PreToolUse ./hooks/project_security.py --matcher "Bash" --level project --add-to-settings
cchooks generatehook auto-formatter PostToolUse ./hooks/project_format.py --matcher "Write" --level project --add-to-settings

# View complete configuration
cchooks listhooks --level all --format json

# Validate both levels
cchooks validatehooks --level all
```

### Backup and Recovery

```bash
# Create backup before major changes
cchooks listhooks --format json > hooks_backup.json

# Make changes with automatic backup
cchooks addhook --event PreToolUse --command "security_check.py" --matcher "Bash" --backup true

# Preview changes without applying
cchooks updatehook --event PreToolUse --index 0 --command "new_security.py" --dry-run

# Remove hook with backup
cchooks removehook --event PreToolUse --index 0 --backup true
```

## Error Handling

CCHooks provides comprehensive error handling with clear, actionable messages:

### Common Error Scenarios

#### Missing Required Arguments
```bash
$ cchooks addhook --event PreToolUse --command "echo test"
错误: PreToolUse 事件类型需要 --matcher 参数
```

#### Invalid Event Type
```bash
$ cchooks addhook --event InvalidEvent --command "test"
错误: 无效的事件类型 'InvalidEvent'。支持的类型: PreToolUse, PostToolUse, ...
```

#### File Not Found
```bash
$ cchooks addhook --event SessionStart --script ./nonexistent.py
错误: 脚本文件不存在: ./nonexistent.py
```

#### Permission Errors
```bash
$ cchooks addhook --event SessionStart --command "test" --level user
错误: 无法写入用户设置文件: 权限被拒绝
建议: 检查 ~/.claude/ 目录的写入权限
```

#### Validation Errors
```bash
$ cchooks validatehooks --strict
验证失败:
- PreToolUse Hook #0: 缺少必需的 matcher 字段
- PostToolUse Hook #1: 超时值 3700 超出允许范围 (1-3600)
```

### Exit Codes

CCHooks uses standard exit codes for scripting:

- `0` - Success
- `1` - Validation error or user error
- `2` - System error (file permissions, etc.)

### Error Recovery

```bash
# Check validation status
cchooks validatehooks --format json

# Fix specific issues
cchooks updatehook --event PreToolUse --index 0 --matcher "Bash"

# Verify fix
cchooks validatehooks --level project
```

## Best Practices

### 1. Hook Organization

```bash
# Create dedicated hooks directory
mkdir -p ./hooks

# Use descriptive names
cchooks generatehook security-guard PreToolUse ./hooks/security_guard.py
cchooks generatehook auto-formatter PostToolUse ./hooks/python_formatter.py
```

### 2. Configuration Management

```bash
# Always validate after changes
cchooks addhook --event SessionStart --command "startup.py" --level project
cchooks validatehooks --level project

# Use dry-run for testing
cchooks updatehook --event PreToolUse --index 0 --timeout 60 --dry-run

# Keep backups enabled (default)
cchooks addhook --event PostToolUse --script ./formatter.py --matcher "Write" --backup true
```

### 3. Template Customization

```bash
# Use JSON files for complex configurations
cat > security_config.json << 'EOF'
{
  "blocked_patterns": ["rm -rf", "sudo rm", "chmod 777"],
  "protected_paths": ["/", "/etc", "~/.ssh"],
  "warning_only": false,
  "log_file": "~/.claude/security.log",
  "whitelist_commands": ["ls", "cat", "echo"]
}
EOF

cchooks generatehook security-guard PreToolUse ./hooks/security.py \
  --matcher "Bash" \
  --customization "$(cat security_config.json)" \
  --add-to-settings
```

### 4. Performance Optimization

```bash
# Use specific matchers instead of "*"
cchooks addhook --event PreToolUse --command "security_check.py" --matcher "Bash|Write"

# Set appropriate timeouts
cchooks addhook --event PostToolUse --script "./heavy_formatter.py" --matcher "Write" --timeout 120

# Monitor performance
cchooks validatehooks --format json | jq '.data.validation_results[] | select(.warnings)'
```

### 5. Security Considerations

```bash
# Always validate scripts before adding
python -m py_compile ./hooks/security.py
cchooks addhook --event PreToolUse --script ./hooks/security.py --matcher "Bash"

# Use project-level for project-specific security
cchooks generatehook security-guard PreToolUse ./hooks/project_security.py --level project

# Use user-level for global security policies
cchooks generatehook security-guard PreToolUse ~/.claude/hooks/global_security.py --level user
```

### 6. Debugging and Troubleshooting

```bash
# Use verbose JSON output for debugging
cchooks listhooks --format json | jq '.'

# Validate with strict mode
cchooks validatehooks --strict --format json

# Check individual hook status
cchooks listhooks --event PreToolUse --format table

# Test generated scripts independently
python ./hooks/security.py < test_input.json
```

### 7. Documentation

```bash
# Document your hooks
cchooks listtemplates --show-config > available_templates.md
cchooks listhooks --format yaml > current_hooks.yaml

# Export configuration for sharing
cchooks listhooks --level project --format json > project_hooks.json
```

### 8. Version Control

```bash
# Include hooks in version control
git add ./hooks/
git add .claude/settings.json

# Document hook setup in README
echo "## Hook Setup" >> README.md
echo "Run: cchooks validatehooks" >> README.md
echo "Templates: cchooks listtemplates" >> README.md
```

---

For more advanced usage and troubleshooting, see the [CCHooks API Reference](./api-reference.md) and [Template Development Guide](./template-development.md).