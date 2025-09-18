# Template Development Guide

## Overview

This guide shows how to create and register custom hook templates for the cchooks CLI tools. Templates allow you to generate complex Python hook scripts with customizable logic.

## Quick Start: Creating Your First Template

### Step 1: Create Template Class

```python
# my_custom_template.py
from cchooks.templates import BaseTemplate, template
from cchooks.types import HookEventType
from typing import List, Dict, Any

@template(
    name="database-backup",
    events=[HookEventType.POST_TOOL_USE],
    description="Automatically backup database when files are modified"
)
class DatabaseBackupTemplate(BaseTemplate):

    @property
    def customization_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "database_url": {"type": "string", "description": "Database connection URL"},
                "backup_path": {"type": "string", "description": "Backup file location"},
                "file_patterns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": ["*.sql", "migrations/*"],
                    "description": "File patterns that trigger backup"
                },
                "compression": {"type": "boolean", "default": True}
            },
            "required": ["database_url", "backup_path"]
        }

    def get_default_config(self) -> Dict[str, Any]:
        return {
            "database_url": "postgresql://localhost/mydb",
            "backup_path": "./backups/",
            "file_patterns": ["*.sql", "migrations/*"],
            "compression": True
        }

    def get_dependencies(self) -> List[str]:
        return ["psycopg2", "gzip"]  # Required Python packages

    def generate(self, config) -> str:
        db_url = config.customization.get("database_url")
        backup_path = config.customization.get("backup_path")
        patterns = config.customization.get("file_patterns", [])
        compression = config.customization.get("compression", True)

        return f'''#!/usr/bin/env python3
import os
import subprocess
from datetime import datetime
from cchooks import create_context, PostToolUseContext

DATABASE_URL = "{db_url}"
BACKUP_PATH = "{backup_path}"
FILE_PATTERNS = {patterns}
USE_COMPRESSION = {compression}

c = create_context()

assert isinstance(c, PostToolUseContext)
if c.tool_name == "Write":
    file_path = c.tool_input.get("file_path", "")

    # Check if file matches our patterns
    if any(pattern in file_path for pattern in FILE_PATTERNS):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"{{BACKUP_PATH}}/backup_{{timestamp}}.sql"

        if USE_COMPRESSION:
            backup_file += ".gz"

        try:
            # Create backup
            cmd = ["pg_dump", DATABASE_URL]
            if USE_COMPRESSION:
                cmd.extend(["|", "gzip", ">", backup_file])
            else:
                cmd.extend([">", backup_file])

            subprocess.run(" ".join(cmd), shell=True, check=True)
            print(f"Database backup created: {{backup_file}}")

        except subprocess.CalledProcessError as e:
            print(f"Backup failed: {{e}}", file=sys.stderr)

c.output.exit_success()
'''
```

### Step 2: Register Template

```bash
# Method 1: Register from file
cc_registertemplate --name database-backup --file ./my_custom_template.py

# Method 2: Register globally
cc_registertemplate --name database-backup --file ./my_custom_template.py --global

# Method 3: Register with custom description
cc_registertemplate \
  --name database-backup \
  --file ./my_custom_template.py \
  --description "Auto-backup database on file changes" \
  --events PostToolUse
```

### Step 3: Use Template

```bash
# Generate script from your template
cc_generatehook \
  --type database-backup \
  --event PostToolUse \
  --output ./hooks/db_backup.py \
  --customization '{
    "database_url": "postgresql://prod:password@localhost/myapp",
    "backup_path": "/var/backups/db",
    "file_patterns": ["*.sql", "models/*", "migrations/*"],
    "compression": true
  }' \
  --add-to-settings

# List your custom templates
cc_listtemplates --source user
```

## Advanced Template Features

### 1. Multi-Event Templates

```python
@template(
    name="git-workflow",
    events=[HookEventType.POST_TOOL_USE, HookEventType.SESSION_END],
    description="Complete Git workflow automation"
)
class GitWorkflowTemplate(BaseTemplate):
    def generate(self, config) -> str:
        event = config.event_type

        if event == HookEventType.POST_TOOL_USE:
            return self._generate_post_tool_use(config)
        elif event == HookEventType.SESSION_END:
            return self._generate_session_end(config)

    def _generate_post_tool_use(self, config) -> str:
        return '''#!/usr/bin/env python3
# Auto-commit changes
from cchooks import create_context, PostToolUseContext
# ... implementation
'''

    def _generate_session_end(self, config) -> str:
        return '''#!/usr/bin/env python3
# Push all commits at session end
from cchooks import create_context, SessionEndContext
# ... implementation
'''
```

### 2. Template Inheritance

```python
class SecurityBaseTemplate(BaseTemplate):
    """Base class for security-related templates"""

    def get_common_security_code(self) -> str:
        return '''
# Common security utilities
def is_sensitive_file(path):
    sensitive_patterns = [".env", ".secret", "id_rsa", "passwords"]
    return any(pattern in path.lower() for pattern in sensitive_patterns)

def log_security_event(event, details):
    import json
    import datetime
    log_entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "event": event,
        "details": details
    }
    with open("/var/log/claude-security.log", "a") as f:
        f.write(json.dumps(log_entry) + "\\n")
'''

@template(
    name="advanced-security",
    events=[HookEventType.PRE_TOOL_USE],
    description="Advanced security with logging and alerts"
)
class AdvancedSecurityTemplate(SecurityBaseTemplate):
    def generate(self, config) -> str:
        return f'''#!/usr/bin/env python3
from cchooks import create_context, PreToolUseContext

{self.get_common_security_code()}

c = create_context()
assert isinstance(c, PreToolUseContext)

# Custom security logic using base utilities
if c.tool_name == "Write":
    file_path = c.tool_input.get("file_path", "")
    if is_sensitive_file(file_path):
        log_security_event("blocked_write", {{"file": file_path}})
        c.output.deny("Blocked sensitive file write",
                     system_message="🔒 Security policy prevents writing to sensitive files")

c.output.allow()
'''
```

### 3. Template Validation

```python
class ValidatedTemplate(BaseTemplate):
    def validate_config(self, config: Dict[str, Any]) -> ValidationResult:
        errors = []
        warnings = []

        # Custom validation logic
        if "api_key" in config and len(config["api_key"]) < 32:
            errors.append(ValidationError(
                field_name="api_key",
                error_code="INVALID_LENGTH",
                message="API key must be at least 32 characters"
            ))

        if "timeout" in config and config["timeout"] > 300:
            warnings.append(ValidationWarning(
                field_name="timeout",
                warning_code="HIGH_TIMEOUT",
                message="Timeout over 5 minutes may cause issues"
            ))

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            suggestions=["Consider using environment variables for secrets"]
        )
```

## Template Registration Methods

### 1. Decorator Registration (Recommended)

```python
# In your Python file
from cchooks.templates import template

@template(name="my-template", events=["PreToolUse"])
class MyTemplate(BaseTemplate):
    # ... implementation

# Template is automatically discovered and registered
```

### 2. Programmatic Registration

```python
# In your application code
from cchooks.templates import register_template
from my_module import MyTemplate

register_template("my-template", MyTemplate)
```

### 3. CLI Registration

```bash
# Register from file
cc_registertemplate --name my-template --file ./my_template.py

# Register from installed module
cc_registertemplate --name my-template --class my_package.MyTemplate
```

### 4. Plugin-based Registration

```python
# setup.py or pyproject.toml
entry_points = {
    "cchooks.templates": [
        "my-template = my_package:MyTemplate",
        "another-template = my_package:AnotherTemplate"
    ]
}
```

## Template Discovery

Templates are discovered in this order:

1. **Built-in templates** - Part of cchooks library
2. **User-registered templates** - Via CLI or programmatic registration
3. **File-based templates** - Python files in template directories
4. **Plugin templates** - Via entry points

### Template Search Paths

```
~/.config/cchooks/templates/     # Global user templates
./.cchooks/templates/            # Project-specific templates
./templates/                     # Local templates directory
```

## Best Practices

### 1. Template Structure

```python
@template(
    name="descriptive-name",
    events=[HookEventType.PRE_TOOL_USE],  # Be specific about supported events
    description="Clear description of what this template does"
)
class WellStructuredTemplate(BaseTemplate):
    def get_default_config(self) -> Dict[str, Any]:
        """Provide sensible defaults"""
        return {"timeout": 30, "enabled": True}

    def get_dependencies(self) -> List[str]:
        """List required packages"""
        return ["requests", "python-dateutil"]

    def validate_config(self, config: Dict[str, Any]) -> ValidationResult:
        """Validate configuration before generation"""
        # ... validation logic

    def generate(self, config: TemplateConfig) -> str:
        """Generate the actual script"""
        # ... generation logic
```

### 2. Error Handling

```python
def generate(self, config: TemplateConfig) -> str:
    try:
        # Template generation logic
        return script_content
    except KeyError as e:
        raise TemplateError(f"Missing required configuration: {e}")
    except Exception as e:
        raise TemplateError(f"Template generation failed: {e}")
```

### 3. Security Considerations

```python
def generate(self, config: TemplateConfig) -> str:
    # Sanitize user inputs
    safe_path = os.path.abspath(config.customization.get("path", ""))
    if not safe_path.startswith("/allowed/directory/"):
        raise TemplateError("Path outside allowed directory")

    # Use proper escaping for shell commands
    import shlex
    safe_command = shlex.quote(config.customization.get("command", ""))

    return f'''
# Generated script with safe inputs
safe_path = "{safe_path}"
safe_command = "{safe_command}"
'''
```

## Testing Templates

### Unit Testing

```python
import unittest
from my_template import MyTemplate
from cchooks.templates import TemplateConfig

class TestMyTemplate(unittest.TestCase):
    def setUp(self):
        self.template = MyTemplate()

    def test_generation(self):
        config = TemplateConfig(
            template_id="my-template",
            event_type=HookEventType.PRE_TOOL_USE,
            customization={"key": "value"},
            output_path=Path("./test.py")
        )

        result = self.template.generate(config)
        self.assertIn("from cchooks import create_context", result)

    def test_validation(self):
        invalid_config = {"invalid": "config"}
        result = self.template.validate_config(invalid_config)
        self.assertFalse(result.is_valid)
```

### Integration Testing

```bash
# Test template registration
cc_registertemplate --name test-template --file ./test_template.py

# Test template generation
cc_generatehook --type test-template --event PreToolUse --output ./test.py

# Test generated script
echo '{"tool_name": "Write", "tool_input": {}}' | python ./test.py
```

## Common Template Patterns

### 1. Configuration-driven Templates

For templates that need extensive customization options.

### 2. Event-specific Templates

Templates optimized for specific hook events.

### 3. Security Templates

Focus on security validation and policy enforcement.

### 4. Automation Templates

For workflow automation and CI/CD integration.

### 5. Monitoring Templates

For logging, metrics, and observability.

This guide provides a complete framework for creating sophisticated, reusable hook templates that integrate seamlessly with the cchooks CLI tools.