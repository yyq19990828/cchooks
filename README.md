# cchooks

A Python library for developing Claude Code hooks with type-safe interfaces and streamlined APIs. This module provides structured contexts and decision-making tools for all 6 Claude Code hook types.

> **New to Claude Code hooks?** See [docs/what-is-cc-hook.md](docs/what-is-cc-hook.md) for a comprehensive introduction.

## Features

- **Type-safe contexts** for all 6 Claude Code hook types
- **Simple and advanced modes** - exit codes or JSON decision control
- **Automatic JSON parsing** and validation from stdin
- **Context-specific APIs** for each hook type
- **Built-in error handling** with helpful validation messages

## Installation

```bash
pip install cchooks
```

Or with uv:

```bash
uv add cchooks
```

## Quick Start

Create a hook script that blocks writes to sensitive files:

```python
#!/usr/bin/env python3
from cchooks import create_context

c = create_context()

if c.hook_event_name == "PreToolUse":
    if c.tool_name == "Write" and ".env" in c.tool_input.get("file_path", ""):
        c.output.simple_block("Refusing to write to .env file")
    else:
        c.output.simple_approve()
```

Save as `hooks/pre-write-check.py` and make executable:

```bash
chmod +x hooks/pre-write-check.py
```

## Hook Types

### 1. PreToolUse
Runs before tool execution, can approve/block tools.

```python
from cchooks import create_context

c = create_context()

if c.hook_event_name == "PreToolUse":
    # Block dangerous Bash commands
    if c.tool_name == "Bash" and "rm -rf" in c.tool_input.get("command", ""):
        c.output.block("Dangerous command detected")

    # Auto-approve safe operations
    elif c.tool_name == "Read":
        c.output.approve()

    # Use simple mode
    else:
        c.output.simple_approve()
```

### 2. PostToolUse
Runs after tool execution, provides feedback only.

```python
from cchooks import create_context

c = create_context()

if c.hook_event_name == "PostToolUse":
    if c.tool_name == "Write":
        file_path = c.tool_input.get("file_path")
        if file_path and file_path.endswith(".py"):
            # Could trigger auto-formatting here
            print(f"Python file written: {file_path}")
```

### 3. Notification
Processes notifications from Claude Code.

```python
from cchooks import create_context

c = create_context()

if c.hook_event_name == "Notification":
    message = c.message
    if "permission" in message.lower():
        # Send to custom notification system
        print(f"Permission required: {message}")
```

### 4. Stop
Controls when Claude Code should stop responding.

```python
from cchooks import create_context

c = create_context()

if c.hook_event_name == "Stop":
    # Always allow Claude to stop by default
    c.output.simple_approve()
```

### 5. SubagentStop
Controls subagent stopping behavior.

```python
from cchooks import create_context

c = create_context()

if c.hook_event_name == "SubagentStop":
    # Allow subagents to complete normally
    c.output.simple_approve()
```

### 6. PreCompact
Runs before transcript compaction.

```python
from cchooks import create_context

c = create_context()

if c.hook_event_name == "PreCompact":
    trigger = c.trigger  # "manual" or "auto"
    print(f"Compacting transcript ({trigger} trigger)")
    c.output.simple_approve()
```

## API Reference

### Core Functions

#### `create_context()`
Creates the appropriate context object based on stdin input.

```python
from cchooks import create_context

context = create_context()
# Returns: PreToolUseContext, PostToolUseContext, etc.
```

### Context Classes

#### `PreToolUseContext`
- `tool_name: str` - Tool being executed
- `tool_input: dict` - Tool parameters
- Methods:
  - `simple_approve(message=None)` - Exit 0, simple approval
  - `simple_block(message)` - Exit 2, simple block
  - `stop_processing(stop_reason, suppress_output=False)` - JSON stop
  - `continue_approve(reason, suppress_output=False)` - JSON approve
  - `continue_block(reason, suppress_output=False)` - JSON block
  - `continue_direct(suppress_output=False)` - JSON continue

#### `PostToolUseContext`
- `tool_name: str` - Tool that was executed
- `tool_input: dict` - Original tool parameters
- `tool_response: dict` - Tool execution result
- Methods:
  - `simple_approve(message=None)` - Exit 0, simple approval
  - `simple_block(message)` - Exit 2, simple block
  - `stop_processing(stop_reason, suppress_output=False)` - JSON stop
  - `continue_block(reason, suppress_output=False)` - JSON prompt Claude
  - `continue_direct(suppress_output=False)` - JSON continue

#### `NotificationContext`
- `message: str` - Notification message

#### `StopContext`
- `stop_hook_active: bool` - Whether stop hook is active
- Methods:
  - `simple_approve(message=None)` - Exit 0, simple approval
  - `simple_block(message)` - Exit 2, simple block
  - `stop_processing(stop_reason, suppress_output=False)` - JSON stop
  - `continue_block(reason, suppress_output=False)` - JSON prevent stopping
  - `continue_direct(suppress_output=False)` - JSON allow stopping

#### `SubagentStopContext`
- `stop_hook_active: bool` - Whether subagent stop hook is active
- Methods:
  - `simple_approve(message=None)` - Exit 0, simple approval
  - `simple_block(message)` - Exit 2, simple block
  - `stop_processing(stop_reason, suppress_output=False)` - JSON stop
  - `continue_block(reason, suppress_output=False)` - JSON prevent stopping
  - `continue_direct(suppress_output=False)` - JSON allow stopping

#### `PreCompactContext`
- `trigger: str` - "manual" or "auto"
- `custom_instructions: str` - Custom compact instructions

## Advanced Usage

### JSON Mode Output

Each context provides specific JSON methods for precise control. Instead of simple exit codes, you can use structured JSON responses with fine-grained control.

#### PreToolUse JSON Methods

```python
from cchooks import create_context

c = create_context()

if c.hook_event_name == "PreToolUse":
    if c.tool_name == "Write":
        file_path = c.tool_input.get("file_path", "")
        
        if "password" in file_path:
            # Block tool execution and stop processing
            c.output.stop_processing("Security policy violation")
            
        elif file_path.endswith(".tmp"):
            # Approve tool execution and continue
            c.output.continue_approve("Temporary file approved")
            
        elif "config" in file_path:
            # Block tool execution but continue processing
            c.output.continue_block("Config files require review")
            
        else:
            # Continue processing without decision
            c.output.continue_direct()
```

#### Stop JSON Methods

```python
from cchooks import create_context

c = create_context()

if c.hook_event_name == "Stop":
    if not c.stop_hook_active:
        # Prevent Claude from stopping
        c.output.continue_block("More tasks to complete")
    else:
        # Allow Claude to stop
        c.output.continue_direct()
```

#### PostToolUse JSON Methods

```python
from cchooks import create_context

c = create_context()

if c.hook_event_name == "PostToolUse":
    if c.tool_name == "Write":
        file_path = c.tool_input.get("file_path", "")
        if file_path.endswith(".py"):
            # Run auto-formatting and continue
            print(f"Auto-formatting: {file_path}")
            c.output.continue_direct(suppress_output=True)
```

### JSON Response Fields

All JSON methods output structured responses:

- `continue`: boolean - Whether Claude should continue processing
- `stopReason`: string - Reason shown to user when stopping
- `suppressOutput`: boolean - Hide stdout from transcript mode
- `decision`: string - Tool-specific decisions ("approve", "block", or omitted)
- `reason`: string - Explanation for decisions

### Suppress Output

Use `suppress_output=True` to hide JSON responses from transcript mode:

```python
c.output.continue_direct(suppress_output=True)  # Hidden from transcript
```

### Conditional Approval

```python
from cchooks import create_context

c = create_context()

if c.hook_event_name == "PreToolUse":
    if c.tool_name == "Bash":
        command = c.tool_input.get("command", "")

        # Allow safe commands
        safe_commands = ["ls", "pwd", "git status"]
        if any(safe in command for safe in safe_commands):
            c.output.approve("Safe command approved")
        else:
            c.output.block("Command requires manual review")
```

## Examples

### Auto-format Python files

```python
#!/usr/bin/env python3
import subprocess
from cchooks import create_context

c = create_context()

if c.hook_event_name == "PostToolUse":
    if c.tool_name == "Write" and c.tool_input.get("file_path", "").endswith(".py"):
        file_path = c.tool_input["file_path"]
        try:
            subprocess.run(["black", file_path], check=True)
            print(f"Auto-formatted: {file_path}")
        except subprocess.CalledProcessError:
            print(f"Failed to format: {file_path}")
```

### Block sensitive file modifications

```python
#!/usr/bin/env python3
from cchooks import create_context

SENSITIVE_FILES = {".env", "config.json", "secrets.yaml"}

c = create_context()

if c.hook_event_name == "PreToolUse":
    if c.tool_name == "Write":
        file_path = c.tool_input.get("file_path", "")
        filename = file_path.split("/")[-1]

        if filename in SENSITIVE_FILES:
            c.output.block(f"Cannot modify sensitive file: {filename}")
        else:
            c.output.approve()
```

## Error Handling

The library provides built-in validation and error handling:

```python
from cchooks import create_context
from cchooks.exceptions import HookValidationError

try:
    c = create_context()
    # Your hook logic here
except HookValidationError as e:
    print(f"Invalid hook input: {e}", file=sys.stderr)
    sys.exit(1)
```

## Development

### Setup

```bash
git clone <repository>
cd cchooks
uv sync
```

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

For questions or issues, please open a GitHub issue.
