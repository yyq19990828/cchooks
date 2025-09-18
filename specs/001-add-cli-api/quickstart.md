# Quickstart: CLI API Tools for Hook Management

## Overview

This guide demonstrates the CLI tools for managing Claude Code hook configurations. Follow these steps to validate the implementation and verify all user stories work correctly.

## ⚠️ CRITICAL VALIDATION REQUIREMENTS

**Claude Code Format Compliance**:
- Verify CLI tools only modify the `hooks` section
- Ensure hook objects contain ONLY: `type`, `command`, `timeout` (optional)
- Confirm `type` field is always "command"
- Validate all other settings fields are preserved unchanged

## Prerequisites

- Python 3.11+ with cchooks library installed
- Claude Code project with `.claude/` directory
- CLI tools installed and available in PATH

## Test Scenarios

### Scenario 1: Generate Complex Python Hook

**Story**: As a developer, I want to generate a security guard hook that blocks dangerous operations across multiple tools.

**Steps**:
```bash
# 1. Generate security guard Python script
cc_generatehook \
  --type security-guard \
  --event PreToolUse \
  --output ./hooks/security.py \
  --add-to-settings \
  --level project \
  --matcher "*" \
  --format json

# 2. Verify script was generated and is executable
ls -la ./hooks/security.py
cat ./hooks/security.py

# 3. Verify hook was added to settings
cc_listhooks --event PreToolUse --level project --format table

# 4. Test the generated hook with a dangerous command
echo '{"tool_name": "Bash", "tool_input": {"command": "rm -rf /"}}' | python ./hooks/security.py
```

**Expected Results**:
- Python script generated with security guard logic
- Script is executable (chmod +x applied)
- Hook automatically added to project settings
- Script blocks dangerous commands and provides clear warnings

### Scenario 2: Add Hook to Existing Settings File

**Story**: Given I have a Claude Code project with .claude/settings.json, when I run a CLI command to add a pre-tool-use hook, then the hook is correctly added to the settings file with proper JSON structure.

**Steps**:
```bash
# 1. Verify existing settings file
cc_listhooks --level project --format table

# 2. Add a new PreToolUse hook
cc_addhook \
  --event PreToolUse \
  --command "echo 'Validating tool use'" \
  --matcher "Write|Edit" \
  --timeout 30 \
  --level project \
  --format json

# 3. Verify hook was added
cc_listhooks --event PreToolUse --level project

# 4. Validate the configuration
cc_validatehooks --level project
```

**Expected Results**:
- Hook successfully added to project settings
- JSON structure preserved and valid
- Hook appears in list output
- Validation passes without errors

### Scenario 2: Add Hook When Settings File Doesn't Exist

**Story**: Given .claude/settings.json doesn't exist, when I add a hook via CLI, then the file is created with proper structure and the hook is added.

**Steps**:
```bash
# 1. Ensure no project settings exist (for test)
# (Implementation should handle missing file gracefully)

# 2. Add first hook to non-existent settings
cc_addhook \
  --event SessionStart \
  --command "echo 'Session started'" \
  --level project \
  --format table

# 3. Verify file was created with proper structure
cc_listhooks --level project --format json

# 4. Validate the new configuration
cc_validatehooks --level project --format table
```

**Expected Results**:
- Settings file created automatically
- Proper JSON structure with hooks section
- Hook correctly configured
- All validation passes

### Scenario 3: Handle Invalid Hook Configuration

**Story**: Given I provide invalid hook configuration via CLI, when the command executes, then I receive clear error messages and the settings file remains unchanged.

**Steps**:
```bash
# 1. Get current hook count
cc_listhooks --level project --format json | jq '.data.total_count'

# 2. Attempt to add invalid hook (missing required matcher for PreToolUse)
cc_addhook \
  --event PreToolUse \
  --command "echo 'invalid'" \
  --level project
# Should fail with validation error

# 3. Attempt to add hook with invalid event type
cc_addhook \
  --event InvalidEvent \
  --command "echo 'test'" \
  --level project
# Should fail with validation error

# 4. Verify settings file unchanged
cc_listhooks --level project --format json | jq '.data.total_count'

# 5. Validate existing configuration still intact
cc_validatehooks --level project
```

**Expected Results**:
- Clear, actionable error messages
- Settings file remains unchanged
- Hook count unchanged
- Existing configuration still valid

### Scenario 4: Update Existing Hook

**Story**: Given I have an existing hook, when I update it via CLI, then the hook configuration is modified while preserving other settings.

**Steps**:
```bash
# 1. List existing hooks to get index
cc_listhooks --event PreToolUse --level project --format table

# 2. Update the first PreToolUse hook
cc_updatehook \
  --event PreToolUse \
  --index 0 \
  --command "echo 'Updated validation'" \
  --timeout 60 \
  --level project \
  --format json

# 3. Verify the update
cc_listhooks --event PreToolUse --level project --format table

# 4. Validate updated configuration
cc_validatehooks --level project
```

**Expected Results**:
- Hook successfully updated
- Other hooks remain unchanged
- Configuration remains valid
- Backup created (if enabled)

### Scenario 5: Remove Hook

**Story**: Given I have configured hooks, when I remove a hook via CLI, then the hook is removed while preserving other configurations.

**Steps**:
```bash
# 1. Get current hook list and count
cc_listhooks --level project --format json

# 2. Remove a specific hook
cc_removehook \
  --event SessionStart \
  --index 0 \
  --level project \
  --format table

# 3. Verify removal
cc_listhooks --level project --format json

# 4. Validate remaining configuration
cc_validatehooks --level project
```

**Expected Results**:
- Specified hook removed successfully
- Other hooks remain intact
- Hook count decreased by 1
- Remaining configuration valid

### Scenario 6: Cross-Level Configuration Management

**Story**: As a developer, I want to manage both project-level and user-level hooks independently.

**Steps**:
```bash
# 1. Add user-level hook
cc_addhook \
  --event Notification \
  --command "notify-send 'Claude notification'" \
  --level user \
  --format json

# 2. List all hooks across levels
cc_listhooks --level all --format table

# 3. Validate both levels
cc_validatehooks --level all --format json

# 4. Demonstrate precedence (project hooks take priority)
cc_listhooks --event Notification --level all --format table
```

**Expected Results**:
- User-level hook added successfully
- Project and user hooks listed separately
- Both levels validate successfully
- Clear indication of precedence/source

### Scenario 7: Auto-Formatter Hook Generation

**Story**: As a Python developer, I want to automatically format Python files after Claude writes them.

**Steps**:
```bash
# 1. Generate auto-formatter hook
cc_generatehook \
  --type auto-formatter \
  --event PostToolUse \
  --output ./hooks/formatter.py \
  --customization '{"formatters": ["black", "isort"], "max_line_length": 88}' \
  --add-to-settings \
  --matcher "Write|Edit"

# 2. Test by creating a messy Python file
cc_addhook \
  --event PostToolUse \
  --script ./hooks/formatter.py \
  --matcher "Write" \
  --level project

# 3. Verify formatter runs after file writes
# (Implementation should test this via mocked tool execution)
```

**Expected Results**:
- Auto-formatter script generated with black and isort
- Custom line length configuration applied
- Hook automatically triggered after Python file writes
- Files are properly formatted according to configuration

### Scenario 8: Context Loader for Development

**Story**: As a developer, I want to load project-specific context when Claude Code starts.

**Steps**:
```bash
# 1. Generate context loader hook
cc_generatehook \
  --type context-loader \
  --event SessionStart \
  --output ./hooks/context.py \
  --customization '{"context_files": [".claude-context", "README.md"], "include_git_status": true}' \
  --add-to-settings

# 2. Create context file
echo "This is a Python web application using FastAPI" > .claude-context

# 3. Test context loading
# (Should load context when Claude Code starts)
```

**Expected Results**:
- Context loader script generated
- Script reads project context files
- Git status included in context
- Context automatically loaded on session start

### Scenario 9: Custom Template Registration

**Story**: As a developer, I want to create and register my own hook template for team workflows.

**Steps**:
```bash
# 1. Create custom template file
cat > ./my_template.py << 'EOF'
from cchooks.templates import BaseTemplate, template
from cchooks.types import HookEventType

@template(
    name="team-workflow",
    events=[HookEventType.POST_TOOL_USE],
    description="Team-specific workflow automation"
)
class TeamWorkflowTemplate(BaseTemplate):
    def get_default_config(self):
        return {"slack_webhook": "", "auto_commit": True}

    def generate(self, config):
        return '''#!/usr/bin/env python3
from cchooks import create_context, PostToolUseContext
import requests
import subprocess

c = create_context()
assert isinstance(c, PostToolUseContext)

if c.tool_name == "Write" and c.tool_input.get("file_path", "").endswith(".py"):
    # Send Slack notification
    webhook_url = "''' + config.customization.get("slack_webhook", "") + '''"
    if webhook_url:
        requests.post(webhook_url, json={"text": f"Python file updated: {c.tool_input['file_path']}"})

    # Auto-commit if enabled
    if ''' + str(config.customization.get("auto_commit", True)) + ''':
        subprocess.run(["git", "add", c.tool_input["file_path"]])
        subprocess.run(["git", "commit", "-m", "Auto-commit: Updated Python file"])

c.output.exit_success()
'''
EOF

# 2. Register the custom template
cc_registertemplate \
  --name team-workflow \
  --file ./my_template.py \
  --description "Team workflow automation with Slack notifications" \
  --events PostToolUse

# 3. Verify registration
cc_listtemplates --source user --format table

# 4. Use the custom template
cc_generatehook \
  --type team-workflow \
  --event PostToolUse \
  --output ./hooks/team.py \
  --customization '{"slack_webhook": "https://hooks.slack.com/...", "auto_commit": true}' \
  --add-to-settings
```

**Expected Results**:
- Custom template registered successfully
- Template appears in user templates list
- Generated script includes team-specific logic
- Slack webhook and auto-commit configured properly

### Scenario 10: Template Management

**Story**: As a team lead, I want to manage templates across projects and see what's available.

**Steps**:
```bash
# 1. List all available templates
cc_listtemplates --format table --show-config

# 2. Filter templates by event type
cc_listtemplates --event PreToolUse --source all

# 3. View specific template details
cc_listtemplates --source builtin --format json | jq '.data.templates[] | select(.name=="security-guard")'

# 4. Unregister a template if needed
cc_unregistertemplate --name old-template --force

# 5. Register global template for organization
cc_registertemplate \
  --name org-security \
  --file ./org_security_template.py \
  --global \
  --force
```

**Expected Results**:
- Complete template listing with configuration options
- Successful filtering by event type and source
- Template details properly displayed
- Template registration/unregistration works correctly

### Scenario 11: Dry Run Operations

**Story**: As a cautious user, I want to preview changes before applying them.

**Steps**:
```bash
# 1. Preview adding a hook without applying
cc_addhook \
  --event Stop \
  --command "echo 'Stopping'" \
  --level project \
  --dry-run \
  --format json

# 2. Verify no changes were made
cc_listhooks --event Stop --level project

# 3. Preview removing a hook
cc_removehook \
  --event PreToolUse \
  --index 0 \
  --level project \
  --dry-run \
  --format table

# 4. Verify hook still exists
cc_listhooks --event PreToolUse --level project
```

**Expected Results**:
- Preview shows intended changes
- No actual modifications made to settings
- Clear indication of dry-run mode
- Settings remain unchanged

## Validation Checklist

### Functional Requirements Validation

- [ ] **FR-001**: CLI commands successfully add hook configurations ✓
- [ ] **FR-002**: Hook configurations validated before adding ✓
- [ ] **FR-003**: Existing settings preserved during modifications ✓
- [ ] **FR-004**: Settings file created when missing ✓
- [ ] **FR-005**: Clear error messages for invalid configurations ✓
- [ ] **FR-006**: All 9 hook types supported ✓
- [ ] **FR-007**: Create, update, and delete operations work ✓
- [ ] **FR-008**: Semantic validation using cchooks library ✓
- [ ] **FR-009**: Graceful handling of file system errors ✓
- [ ] **FR-010**: JSON formatting consistency maintained ✓
- [ ] **FR-011**: Only "hooks" section modified in settings.json ✓
- [ ] **FR-012**: No fields outside "hooks" section modified ✓
- [ ] **FR-013**: Hook objects contain only allowed fields ✓
- [ ] **FR-014**: All existing non-hook settings preserved ✓

### Python Hook Generation Validation

- [ ] **HG-001**: Security guard template generates functional script ✓
- [ ] **HG-002**: Auto-formatter template with custom configuration ✓
- [ ] **HG-003**: Context loader template reads project files ✓
- [ ] **HG-004**: Generated scripts are executable (chmod +x) ✓
- [ ] **HG-005**: Generated scripts integrate with cchooks library ✓
- [ ] **HG-006**: Template customization options work correctly ✓
- [ ] **HG-007**: Auto-add to settings option functions ✓
- [ ] **HG-008**: All 10 template types generate valid scripts ✓
- [ ] **HG-009**: Generated scripts handle errors gracefully ✓
- [ ] **HG-010**: Scripts follow README.md example patterns ✓

### Template System Validation

- [ ] **TS-001**: Custom template registration via file works ✓
- [ ] **TS-002**: Custom template registration via class name works ✓
- [ ] **TS-003**: Template listing shows all sources (builtin/user/file) ✓
- [ ] **TS-004**: Template filtering by event type functions ✓
- [ ] **TS-005**: Template unregistration removes correctly ✓
- [ ] **TS-006**: Global vs project-level template registration ✓
- [ ] **TS-007**: Template customization schema validation ✓
- [ ] **TS-008**: Template dependency checking works ✓
- [ ] **TS-009**: Template versioning support ✓
- [ ] **TS-010**: Decorator-based template registration ✓
- [ ] **TS-011**: Template search path discovery ✓
- [ ] **TS-012**: Template error handling and validation ✓

### Edge Cases Validation

- [ ] .claude directory doesn't exist → created automatically
- [ ] Malformed existing settings.json → clear error message
- [ ] Duplicate hook configurations → prevented or handled gracefully
- [ ] Insufficient file permissions → clear error message with suggestions
- [ ] Large settings files → performance remains acceptable
- [ ] Invalid JSON in existing settings → backup created, clear error

### CLI Interface Validation

- [ ] All commands follow consistent flag patterns
- [ ] Help text is clear and comprehensive
- [ ] Exit codes follow documented conventions
- [ ] JSON output is properly formatted and parseable
- [ ] Table output is readable and informative
- [ ] Error messages are actionable

### Integration Validation

- [ ] Works with existing Claude Code installations
- [ ] Compatible with all 9 hook types from cchooks library
- [ ] Respects Claude Code's settings file precedence
- [ ] Backup files created with proper naming
- [ ] Cross-platform compatibility (tested on target platforms)

## Performance Benchmarks

Run these commands to verify performance requirements:

```bash
# Test CLI response time (should be <100ms)
time cc_listhooks --level all --format json

# Test large settings file handling (create test file with many hooks)
# Settings file up to 10MB should be handled gracefully

# Test validation performance (should complete in <5 seconds)
time cc_validatehooks --level all --format json
```

## Completion Criteria

All scenarios should complete successfully with:
- ✅ Expected results achieved
- ✅ No unhandled errors or exceptions
- ✅ Performance requirements met
- ✅ Validation checklist items passed
- ✅ Integration with Claude Code confirmed

## Troubleshooting

### Common Issues

1. **Permission Denied**: Ensure write access to `.claude/` directory
2. **Command Not Found**: Verify CLI tools are installed and in PATH
3. **Invalid JSON**: Use `cc_validatehooks` to identify and fix issues
4. **Hook Not Found**: Use `cc_listhooks` to verify hook index/location

### Support Resources

- Run `cc_addhook --help` for command-specific help
- Use `--dry-run` flag to preview changes safely
- Check `cc_validatehooks` output for detailed validation errors
- Backup files (.bak) available for recovery if needed