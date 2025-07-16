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
# Install dependencies
make setup

# Or with uv directly
uv sync
```

### Testing
```bash
# Run all tests with coverage
make test

# Run tests without coverage (faster)
make test-quick

# Run specific test file
uv run pytest tests/contexts/test_pre_tool_use.py -v

# Run single test
uv run pytest tests/contexts/test_pre_tool_use.py::test_pre_tool_use_approve -v
```

### Linting and Formatting
```bash
# Check all code quality
make check

# Run individual checks
make lint          # ruff check
make type-check    # mypy
make format-check  # ruff format --check
make test          # pytest with coverage

# Auto-fix issues
make lint-fix      # ruff check --fix
make format        # ruff format
```

### Build and Distribution
```bash
# Build package
make build

# Clean build artifacts
make clean

# Full release preparation
make release-check
```

### Development Utilities
```bash
# Install in development mode
make install-dev

# Show dependency tree
make deps-tree

# Update lockfile
make lock
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

## Project Structure

```
src/cchooks/
├── __init__.py           # Main factory function create_context()
├── types.py              # Type definitions and literals
├── exceptions.py         # Custom exception classes
├── utils.py              # JSON parsing utilities
└── contexts/
    ├── __init__.py       # Context exports
    ├── base.py          # Abstract base classes
    ├── pre_tool_use.py   # Pre-tool execution decisions
    ├── post_tool_use.py  # Post-tool execution feedback
    ├── notification.py   # Notification processing
    ├── stop.py          # Stop behavior control
    ├── subagent_stop.py  # Subagent stop control
    └── pre_compact.py    # Pre-compaction processing

tests/
├── contexts/            # Context-specific tests
├── fixtures/            # Test data and helpers
├── integration/         # End-to-end tests
├── test_context_creation.py  # Factory function tests
├── test_exceptions.py   # Exception handling tests
├── test_types.py        # Type validation tests
└── test_utils.py        # Utility function tests
```

## Key Files to Understand

- `src/cchooks/__init__.py`: Main entry point and factory function
- `src/cchooks/contexts/pre_tool_use.py`: Most complex hook with approval decisions
- `src/cchooks/types.py`: Complete type system for Claude Code integration
- `docs/what-is-cc-hook.md`: Comprehensive documentation of Claude Code hooks

## Development Best Practices

- When generating git commit messages, follow patterns like "feat:", "fix:", "docs:", "refactor:" and other best practices
- Use type hints throughout the codebase
- Write tests for all new functionality
- Run `make check` before committing changes
- Follow existing naming conventions and code style
- Document public APIs with clear docstrings
