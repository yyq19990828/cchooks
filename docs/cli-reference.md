# CCHooks CLI Quick Reference

## Command Structure
```
cchooks COMMAND [ARGS] [OPTIONS]
```

## Hook Management Commands

### addhook
```bash
cchooks addhook --event EVENT [--command CMD | --script FILE] [--matcher PATTERN] [OPTIONS]

# Examples
cchooks addhook --event SessionStart --command "echo 'Started'" --level project
cchooks addhook --event PreToolUse --script ./security.py --matcher "Bash|Write"
cchooks addhook --event PostToolUse --command "formatter.py" --matcher "Write" --timeout 30
```

### updatehook
```bash
cchooks updatehook --event EVENT --index INDEX [--command CMD] [--timeout SEC] [OPTIONS]

# Examples
cchooks updatehook --event PreToolUse --index 0 --command "new_security.py"
cchooks updatehook --event PostToolUse --index 1 --timeout 60 --dry-run
```

### removehook
```bash
cchooks removehook --event EVENT --index INDEX [OPTIONS]

# Examples
cchooks removehook --event PreToolUse --index 0
cchooks removehook --event SessionEnd --index 1 --level user --dry-run
```

### listhooks
```bash
cchooks listhooks [--event EVENT] [--level LEVEL] [--format FORMAT]

# Examples
cchooks listhooks                              # All hooks, table format
cchooks listhooks --event PreToolUse           # Filter by event
cchooks listhooks --level user --format json   # User hooks, JSON format
```

### validatehooks
```bash
cchooks validatehooks [--level LEVEL] [--format FORMAT] [--strict]

# Examples
cchooks validatehooks                    # Validate all hooks
cchooks validatehooks --level project    # Project hooks only
cchooks validatehooks --strict           # Treat warnings as errors
```

## Template Management Commands

### generatehook
```bash
cchooks generatehook TYPE EVENT OUTPUT [--matcher PATTERN] [--customization JSON] [OPTIONS]

# Examples
cchooks generatehook security-guard PreToolUse ./security.py --matcher "Bash"
cchooks generatehook auto-formatter PostToolUse ./format.py --add-to-settings
cchooks generatehook context-loader SessionStart ./context.py \
  --customization '{"context_files": ["README.md"]}'
```

### registertemplate
```bash
cchooks registertemplate --name NAME [--file FILE | --class CLASS] [OPTIONS]

# Examples
cchooks registertemplate --name team-hook --file ./template.py
cchooks registertemplate --name custom --class mymodule.Template --global
```

### listtemplates
```bash
cchooks listtemplates [--event EVENT] [--source SOURCE] [--format FORMAT]

# Examples
cchooks listtemplates                           # All templates
cchooks listtemplates --source builtin         # Built-in only
cchooks listtemplates --event PreToolUse        # For specific event
```

### unregistertemplate
```bash
cchooks unregistertemplate --name NAME [--global] [--force]

# Examples
cchooks unregistertemplate --name old-template
cchooks unregistertemplate --name global-template --global --force
```

## Event Types
| Event | Description | Requires Matcher |
|-------|-------------|------------------|
| `PreToolUse` | Before tool execution | ✓ |
| `PostToolUse` | After tool execution | ✓ |
| `SessionStart` | Session initialization | - |
| `SessionEnd` | Session cleanup | - |
| `Notification` | System notifications | - |
| `UserPromptSubmit` | User input validation | - |
| `Stop` | Interruption handling | - |
| `SubagentStop` | Subagent termination | - |
| `PreCompact` | Before compaction | - |

## Settings Levels
- `project` - `.claude/settings.json` in current directory (default)
- `user` - `~/.claude/settings.json` in home directory
- `all` - Both project and user (query only)

## Output Formats
- `table` - Human-readable table (default)
- `json` - Machine-readable JSON
- `yaml` - Human-readable YAML (where supported)
- `quiet` - Minimal output (some commands)

## Built-in Templates
| Template | Event Types | Description |
|----------|-------------|-------------|
| `security-guard` | PreToolUse | Security protection and validation |
| `auto-formatter` | PostToolUse | Automatic code formatting |
| `auto-linter` | PostToolUse | Code quality checking |
| `git-auto-commit` | PostToolUse | Automatic git operations |
| `permission-logger` | PreToolUse | Tool usage logging |
| `desktop-notifier` | Notification | Desktop notifications |
| `task-manager` | Stop | Resource cleanup |
| `prompt-filter` | UserPromptSubmit | Input filtering |
| `context-loader` | SessionStart | Context loading |
| `cleanup-handler` | SessionEnd | Session cleanup |

## Common Options
| Option | Description | Default |
|--------|-------------|---------|
| `--level LEVEL` | Settings level (project/user) | project |
| `--format FORMAT` | Output format | table |
| `--dry-run` | Preview without applying | false |
| `--backup` | Create backup | true |
| `--timeout SEC` | Execution timeout (1-3600) | - |
| `--matcher PATTERN` | Tool name pattern | - |
| `--force` | Force operation | false |
| `--strict` | Strict validation | false |

## Matcher Patterns
```bash
--matcher "Write"              # Single tool
--matcher "Write|Edit"         # Multiple tools (OR)
--matcher "*"                  # All tools
--matcher ".*Edit.*"           # Regex pattern
```

## Quick Start Examples

### Basic Setup
```bash
# Check current status
cchooks listhooks
cchooks validatehooks

# Add simple hooks
cchooks addhook --event SessionStart --command "echo 'Started'" --level project
cchooks addhook --event SessionEnd --command "cleanup.sh" --level project
```

### Security Setup
```bash
# Generate and add security guard
cchooks generatehook security-guard PreToolUse ./hooks/security.py \
  --matcher "Bash|Write" --add-to-settings

# Add permission logging
cchooks generatehook permission-logger PreToolUse ./hooks/logger.py \
  --matcher "*" --add-to-settings
```

### Development Setup
```bash
# Auto-formatter for Python files
cchooks generatehook auto-formatter PostToolUse ./hooks/format.py \
  --matcher "Write|Edit" --add-to-settings

# Context loader for development
cchooks generatehook context-loader SessionStart ./hooks/context.py \
  --customization '{"context_files": [".env", "README.md"]}' --add-to-settings
```

### Validation and Debugging
```bash
# Validate configuration
cchooks validatehooks --strict

# Check specific events
cchooks listhooks --event PreToolUse --format json

# Preview changes
cchooks updatehook --event PreToolUse --index 0 --timeout 60 --dry-run
```

## Exit Codes
- `0` - Success
- `1` - Validation/user error
- `2` - System error

## Getting Help
```bash
cchooks --help                    # Main help
cchooks COMMAND --help            # Command-specific help
cchooks listtemplates --show-config  # Template options
```