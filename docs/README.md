# CCHooks Documentation

Welcome to the CCHooks documentation! This directory contains comprehensive guides and references for both the CLI tools and Python SDK.

## Documentation Structure

### 📚 CLI Tools Documentation
- **[CLI Guide](cli-guide.md)** - Complete CLI reference with detailed examples and workflows
- **[CLI Quick Reference](cli-reference.md)** - Command cheat sheet for quick lookup

### 🐍 Python SDK Documentation
- **[API Reference](api-reference.md)** - Complete Python API documentation and examples

### 📋 Project Documentation
- **[Implementation Plan](../specs/001-add-cli-api/plan.md)** - Complete implementation roadmap
- **[Task Breakdown](../specs/001-add-cli-api/tasks.md)** - Detailed task execution record

## Quick Navigation

### New to CCHooks?
1. Start with the [main README](../README.md) for an overview
2. Try the CLI tools with the [CLI Guide](cli-guide.md)
3. Write custom hooks using the [API Reference](api-reference.md)

### CLI Users
- **Getting Started**: [CLI Guide - Quick Start](cli-guide.md#quick-start)
- **Command Reference**: [CLI Quick Reference](cli-reference.md)
- **Common Workflows**: [CLI Guide - Examples & Workflows](cli-guide.md#examples--workflows)

### Python Developers
- **Hook Development**: [API Reference](api-reference.md)
- **Template Creation**: [CLI Guide - Template Management](cli-guide.md#template-management-commands)
- **Advanced Usage**: [API Reference - Advanced Features](api-reference.md)

### System Administrators
- **Security Setup**: [CLI Guide - Security-Focused Setup](cli-guide.md#security-focused-setup)
- **Multi-Level Configuration**: [CLI Guide - Multi-Level Configuration](cli-guide.md#multi-level-configuration)
- **Validation & Monitoring**: [CLI Guide - Error Handling](cli-guide.md#error-handling)

## Key Features Documentation

### CLI Management
| Feature | Documentation | Description |
|---------|---------------|-------------|
| Hook Management | [CLI Guide - Hook Management](cli-guide.md#hook-management-commands) | Add, update, remove, list, validate hooks |
| Template System | [CLI Guide - Template Management](cli-guide.md#template-management-commands) | Generate hooks from 10 built-in templates |
| Output Formats | [CLI Reference - Output Formats](cli-reference.md#output-formats) | JSON, table, YAML support |
| Settings Levels | [CLI Reference - Settings Levels](cli-reference.md#settings-levels) | Project vs user-level configuration |

### Python SDK
| Feature | Documentation | Description |
|---------|---------------|-------------|
| Context Creation | [API Reference](api-reference.md) | One-liner hook setup |
| Type Safety | [API Reference](api-reference.md) | Full type hints and validation |
| Event Types | [CLI Reference - Event Types](cli-reference.md#event-types) | All 9 Claude Code hook events |
| Output Control | [API Reference](api-reference.md) | Exit codes and JSON responses |

### Built-in Templates
| Template | Event Type | Documentation |
|----------|------------|---------------|
| Security Guard | PreToolUse | [CLI Guide - Security Guard](cli-guide.md#1-security-guard) |
| Auto Formatter | PostToolUse | [CLI Guide - Auto Formatter](cli-guide.md#2-auto-formatter) |
| Auto Linter | PostToolUse | [CLI Guide - Auto Linter](cli-guide.md#3-auto-linter) |
| Git Auto Commit | PostToolUse | [CLI Guide - Git Auto Commit](cli-guide.md#4-git-auto-commit) |
| Permission Logger | PreToolUse | [CLI Guide - Permission Logger](cli-guide.md#5-permission-logger) |
| Desktop Notifier | Notification | [CLI Guide - Desktop Notifier](cli-guide.md#6-desktop-notifier) |
| Task Manager | Stop | [CLI Guide - Task Manager](cli-guide.md#7-task-manager) |
| Prompt Filter | UserPromptSubmit | [CLI Guide - Prompt Filter](cli-guide.md#8-prompt-filter) |
| Context Loader | SessionStart | [CLI Guide - Context Loader](cli-guide.md#9-context-loader) |
| Cleanup Handler | SessionEnd | [CLI Guide - Cleanup Handler](cli-guide.md#10-cleanup-handler) |

## Common Use Cases

### Development Workflow
```bash
# Quick setup for development environment
cchooks generatehook context-loader SessionStart ./hooks/dev_context.py --add-to-settings
cchooks generatehook auto-formatter PostToolUse ./hooks/format.py --matcher "Write" --add-to-settings
cchooks validatehooks
```

### Security & Monitoring
```bash
# Comprehensive security setup
cchooks generatehook security-guard PreToolUse ./hooks/security.py --matcher "*" --add-to-settings
cchooks generatehook permission-logger PreToolUse ./hooks/audit.py --matcher "*" --add-to-settings
cchooks validatehooks --strict
```

### Team Collaboration
```bash
# Share hook configurations
cchooks listhooks --format json > team_hooks.json
cchooks listtemplates --source user > custom_templates.md
```

## Getting Help

### Command Line Help
```bash
cchooks --help                    # Main help
cchooks COMMAND --help            # Command-specific help
cchooks listtemplates --show-config  # Template customization options
```

### Documentation Issues
If you find any issues with the documentation, please [open an issue](https://github.com/gowaylee/cchooks/issues) on GitHub.

### Community Support
- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: Questions and community support
- **Documentation**: Complete guides and references

---

**Last Updated**: 2025-09-19
**CLI Version**: 1.0.0
**Python SDK Version**: 0.1.0