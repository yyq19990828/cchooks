# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python library (`cchooks`) for developing Claude Code hooks - user-defined shell commands that execute at various points in Claude Code's lifecycle. The library provides type-safe interfaces and utilities for all 6 hook types.

## Architecture

The codebase is organized into:

- **Core Types**: `src/cchooks/types.py` - Type definitions and literals for hook events, tools, and decisions
- **Base Classes**: `src/cchooks/contexts/base.py` - Abstract base classes for contexts and outputs
- **Hook Contexts**: Individual files in `src/cchooks/contexts/` for each hook type
- **Utilities**: `src/cchooks/utils.py` - JSON parsing and validation helpers
- **Exceptions**: `src/cchooks/exceptions.py` - Custom exception hierarchy

## Hook Types

1. **PreToolUse**: Runs before tool execution, can approve/block tools
2. **PostToolUse**: Runs after tool execution, can only provide feedback
3. **Notification**: Processes notifications, no decision control
4. **Stop**: Controls Claude's stopping behavior
5. **SubagentStop**: Controls subagent stopping behavior
6. **PreCompact**: Runs before transcript compaction

## Development Commands

### Setup
```bash
# Install dependencies (none currently)
uv sync
```

### Usage Pattern

```python
from cchooks import create_context

# Read from stdin automatically
c = create_context()

# Type-specific handling
if isinstance(c, PreToolUseContext):
    if c.tool_name == "Write" and "password" in c.tool_input.get("file_path", ""):
        c.output.simple_block("Refusing to write to password file")
    else:
        c.output.simple_approve()
```

## Input/Output Patterns

### Simple Mode (Exit Codes)
- `exit 0`: Success/approve
- `exit 1`: Non-blocking error
- `exit 2`: Blocking error

### Advanced Mode (JSON)
- Use context-specific output methods
- Each context provides specialized decision methods
- JSON output includes `continue`, `decision`, `reason` fields

## Key Files to Understand

- `src/cchooks/__init__.py`: Main entry point and factory function
- `src/cchooks/contexts/pre_tool_use.py`: Most complex hook with approval decisions
- `src/cchooks/types.py`: Complete type system for Claude Code integration
- `docs/what-is-cc-hook.md`: Comprehensive documentation of Claude Code hooks

## Development Best Practices

- When generating git commit messages, follow the patterns like "feat: " "fix: " "docs: " "refactor: " and other best practice for this.