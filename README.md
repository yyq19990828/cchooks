# cchooks

A lightweight Python library that makes building Claude Code hooks as simple as writing a few lines of code. Stop worrying about JSON parsing and focus on what your hook should actually do.

> **New to Claude Code hooks?** Check the [official docs](https://docs.anthropic.com/en/docs/claude-code/hooks) for the big picture.

> **Need the full API?** See the [API Reference](docs/api-reference.md) for complete documentation.

## Features

- **One-liner setup**: `create_context()` handles all the boilerplate
- **Zero config**: Automatic JSON parsing and validation from stdin
- **Smart detection**: Automatically figures out which hook you're building
- **Two modes**: Simple exit codes OR advanced JSON control
- **Type-safe**: Full type hints and IDE autocompletion

## Installation

```bash
pip install cchooks
# or
uv add cchooks
```

## Quick Start

Build a hook in 30 seconds that blocks dangerous file writes:

```python
#!/usr/bin/env python3
from cchooks import create_context

c = create_context()

# Block writes to .env files
if c.tool_name == "Write" and ".env" in c.tool_input.get("file_path", ""):
    c.output.simple_block("Nope! .env files are protected")
else:
    c.output.simple_approve()
```

Save as `hooks/env-guard.py`, make executable:

```bash
chmod +x hooks/env-guard.py
```

That's it. No JSON parsing, no validation headaches.

## 3-Minute Tutorial

Build each hook type with real examples:

### PreToolUse (Security Guard)
Block dangerous commands before they run:

```python
#!/usr/bin/env python3
from cchooks import create_context

c = create_context()

# Block rm -rf commands
if c.tool_name == "Bash" and "rm -rf" in c.tool_input.get("command", ""):
    c.output.simple_block("You should not execute this command: System protection: rm -rf blocked")
else:
    c.output.simple_approve()
```

### PostToolUse (Auto-formatter)
Format Python files after writing:

```python
#!/usr/bin/env python3
import subprocess
from cchooks import create_context

c = create_context()

if c.tool_name == "Write" and c.tool_input.get("file_path", "").endswith(".py"):
    file_path = c.tool_input["file_path"]
    subprocess.run(["black", file_path])
    print(f"Auto-formatted: {file_path}")
```

### Notification (Desktop Alerts)
Send desktop notifications:

```python
#!/usr/bin/env python3
import os
from cchooks import create_context

c = create_context()

if "permission" in c.message.lower():
    os.system(f'notify-send "Claude" "{c.message}"')
```

### Stop (Task Manager)
Keep Claude working on long tasks:

```python
#!/usr/bin/env python3
from cchooks import create_context

c = create_context()

if not c.stop_hook_active: # Claude has not been activated by other Stop Hook
    c.output.continue_block("Hey Claude, you should try to do more works!") # Prevent from stopping, and prompt Claude
else:
    c.output.continue_direct()  # Allow stop
```

> Since Hooks are executed in parallel in claude-code, it is necessary to check `stop_hook_active` to determine if claude has already been activated by another parallel Stop Hook.

### SubagentStop (Workflow Control)
Same as Stop, but for subagents:

```python
from cchooks import create_context
c = create_context()
c.output.simple_approve()  # Let subagents complete
```

### PreCompact (Custom Instructions)
Add custom compaction rules:

```python
from cchooks import create_context

c = create_context()

if c.custom_instructions:
    print(f"Using custom compaction: {c.custom_instructions}")
```

## Quick API Guide

| Hook Type | What You Get | Key Properties |
|-----------|--------------|----------------|
| **PreToolUse** | `c.tool_name`, `c.tool_input` | Block dangerous tools |
| **PostToolUse** | `c.tool_response` | React to tool results |
| **Notification** | `c.message` | Handle notifications |
| **Stop** | `c.stop_hook_active` | Control when Claude stops |
| **SubagentStop** | `c.stop_hook_active` | Control subagent behavior |
| **PreCompact** | `c.trigger`, `c.custom_instructions` | Modify transcript compaction |

### Simple Mode (Exit Codes)
```python
# Exit 0 = approve, Exit 2 = block
c.output.simple_approve()  # ✅
c.output.simple_block("reason")  # ❌
```

### Advanced Mode (JSON)
```python
# Precise control over Claude's behavior
c.output.continue_approve("reason")
c.output.continue_block("reason")
c.output.continue_direct()
```

## Production Examples

### Multi-tool Security Guard
Block dangerous operations across multiple tools:

```python
#!/usr/bin/env python3
from cchooks import create_context

DANGEROUS_COMMANDS = {"rm -rf", "sudo", "format", "fdisk"}
SENSITIVE_FILES = {".env", "secrets.json", "id_rsa"}

c = create_context()

# Block dangerous Bash commands
if c.tool_name == "Bash":
    command = c.tool_input.get("command", "")
    if any(danger in command for danger in DANGEROUS_COMMANDS):
        c.output.simple_block("Security: Dangerous command blocked")
    else:
        c.output.simple_approve()

# Block writes to sensitive files
elif c.tool_name == "Write":
    file_path = c.tool_input.get("file_path", "")
    if any(sensitive in file_path for sensitive in SENSITIVE_FILES):
        c.output.simple_block(f"Protected file: {file_path}")
    else:
        c.output.simple_approve()

else:
    c.output.continue_direct() # Pattern not matched, just bypass this hook
```

### Auto-linter Hook
Lint Python files after writing:

```python
#!/usr/bin/env python3
import subprocess
from cchooks import create_context

c = create_context()

if c.tool_name == "Write" and c.tool_input.get("file_path", "").endswith(".py"):
    file_path = c.tool_input["file_path"]

    # Run ruff linter
    result = subprocess.run(["ruff", "check", file_path], capture_output=True)

    if result.returncode == 0:
        print(f"✅ {file_path} passed linting")
    else:
        print(f"⚠️  {file_path} has issues:")
        print(result.stdout.decode())

    c.output.simple_approve()
```

### Git-aware Auto-commit
Auto-commit file changes:

```python
#!/usr/bin/env python3
import subprocess
from cchooks import create_context

c = create_context()

if c.tool_name == "Write":
    file_path = c.tool_input.get("file_path", "")

    # Skip non-git files
    if not file_path.startswith("/my-project/"):
        c.output.simple_approve()

    # Auto-commit Python changes
    if file_path.endswith(".py"):
        try:
            subprocess.run(["git", "add", file_path], check=True)
            subprocess.run([
                "git", "commit", "-m",
                f"auto: update {file_path.split('/')[-1]}"
            ], check=True)
            print(f"📁 Committed: {file_path}")
        except subprocess.CalledProcessError:
            print("Git commit failed - probably no changes")

    c.output.simple_approve()
```

### Permission Logger
Log all permission requests:

```python
#!/usr/bin/env python3
import json
import datetime
from cchooks import create_context

c = create_context()

if c.tool_name == "Write":
    log_entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "file": c.tool_input.get("file_path"),
        "action": "write_requested"
    }

    with open("/tmp/permission-log.jsonl", "a") as f:
        f.write(json.dumps(log_entry) + "\n")

    c.output.simple_approve()
```

## Development

```bash
git clone https://github.com/GowayLee/cchooks.git
cd cchooks
make help # See detailed dev commands
```

## License

MIT License - see LICENSE file for details.
