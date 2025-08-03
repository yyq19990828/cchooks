# cchooks Development Guide

## Project Overview
Python library for developing Claude Code hooks - user-defined shell commands that execute at various points in Claude Code's lifecycle. Provides type-safe interfaces for 7 hook types.

## Essential Commands

### Testing
- `make test` - Run all tests with coverage
- `make test-quick` - Run tests without coverage (faster)
- `uv run pytest tests/contexts/test_pre_tool_use.py -v` - Run specific test file
- `uv run pytest tests/contexts/test_pre_tool_use.py::test_valid_context_creation -v` - Run single test

### Code Quality
- `make check` - Run all checks (lint, type-check, format, test)
- `make lint` - Lint code (ruff check)
- `make lint-fix` - Auto-fix linting issues
- `make format` - Format code (ruff format)
- `make type-check` - Type checking (mypy)

### Build & Setup
- `make setup` - Install dependencies
- `uv sync` - Alternative dependency install
- `make build` - Build package
- `make clean` - Clean build artifacts

## Hook Types & Usage

### 7 Hook Types
1. **PreToolUse**: Before tool execution, can approve/block
2. **PostToolUse**: After tool execution, feedback only
3. **Notification**: Process notifications, no decisions
4. **Stop**: Control Claude stopping behavior
5. **SubagentStop**: Control subagent stopping
6. **PreCompact**: Before transcript compaction
7. **SessionStart**: When Claude Code starts or resumes sessions

### Usage Pattern
```python
from cchooks import create_context

c = create_context()

if isinstance(c, PreToolUseContext):
    if c.tool_name == "Write" and "password" in c.tool_input.get("file_path", ""):
        c.output.simple_block("Refusing to write to password file")
    else:
        c.output.simple_approve()
```

## Code Style Guidelines

### Python Conventions
- **Type hints**: Required for all function signatures and public attributes
- **Imports**: Group imports (stdlib, third-party, local) with blank lines
- **Naming**: 
  - Classes: PascalCase (PreToolUseContext)
  - Functions/Methods: snake_case (validate_fields)
  - Constants: UPPER_SNAKE_CASE (HOOK_TYPE_MAP)
  - Private: _single_underscore

### Error Handling
- Use custom exceptions from `cchooks.exceptions`
- Validate input data in context constructors
- Provide clear error messages with field names
- Use `HookValidationError` for missing required fields

### Testing Patterns
- Test files: `test_*.py` in `tests/` directory
- Test classes: `Test*` 
- Test methods: `test_*`
- Use pytest fixtures for sample data
- Mock stdin/stdout for I/O testing

### Project Structure
- Main module: `src/cchooks/`
- Contexts: `src/cchooks/contexts/` (one file per hook type)
- Tests: Mirror source structure in `tests/`
- Type definitions: `src/cchooks/types.py`

### Hook Development
- Each hook has dedicated Context and Output classes
- Inherit from BaseHookContext/BaseHookOutput
- Validate required fields in constructor
- Use factory function `create_context()` for instantiation
- Follow JSON input/output patterns for Claude Code integration

## Input/Output Patterns
- **Simple Mode**: Exit codes (0=success, 1=non-blocking, 2=blocking)
- **Advanced Mode**: JSON with `continue`, `decision`, `reason` fields

## Key Files
- `src/cchooks/__init__.py`: Main entry point and factory function
- `src/cchooks/contexts/pre_tool_use.py`: Most complex hook with approval decisions
- `src/cchooks/types.py`: Complete type system for Claude Code integration