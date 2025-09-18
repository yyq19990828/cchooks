# Data Model: CLI API Tools for Hook Management

## Core Entities

### HookConfiguration

**Purpose**: Represents a single hook configuration entry in Claude Code format

**Fields** (EXACT Claude Code format):
- `type: str` - ALWAYS "command" (fixed value per Claude Code spec)
- `command: str` - Shell command to execute (required)
- `timeout: Optional[int]` - Execution timeout in seconds (optional)

**CLI-Internal Fields** (not stored in JSON):
- `event_type: HookEventType` - One of the 9 supported hook types
- `matcher: Optional[str]` - Tool name pattern (for PreToolUse/PostToolUse)

**Validation Rules**:
- `type` must always be "command"
- `command` must be non-empty string
- `timeout` must be positive integer if specified
- `matcher` required for PreToolUse/PostToolUse, optional for others
- NO additional fields allowed in hook object

**Relationships**:
- Belongs to SettingsFile
- Validated against cchooks library type definitions

### SettingsFile

**Purpose**: Represents a .claude/settings.json file and its manipulation

**Fields**:
- `path: Path` - Absolute path to settings file
- `level: SettingsLevel` - project, user-local, or user-global
- `content: Dict[str, Any]` - Parsed JSON content
- `hooks: List[HookConfiguration]` - Extracted hook configurations
- `backup_path: Optional[Path]` - Path to backup file if created

**Validation Rules**:
- Path must be valid and accessible
- Content must be valid JSON
- Hooks section must follow Claude Code schema
- Backup path must be writable if specified

**State Transitions**:
1. `NotFound` → `Created` (when creating new file)
2. `Exists` → `Loaded` (when reading existing file)
3. `Loaded` → `Modified` (when hooks are changed)
4. `Modified` → `Saved` (when changes are written)

### CLICommand

**Purpose**: Represents a CLI command execution context

**Fields**:
- `command_name: str` - Name of the CLI command
- `arguments: Dict[str, Any]` - Parsed command arguments
- `target_level: SettingsLevel` - Where to apply changes
- `output_format: OutputFormat` - How to format output
- `dry_run: bool` - Whether to preview changes only

**Validation Rules**:
- Command name must be recognized CLI command
- Arguments must match command schema
- Target level must be valid SettingsLevel
- Output format must be supported format

### ValidationResult

**Purpose**: Outcome of hook configuration validation

**Fields**:
- `is_valid: bool` - Overall validation result
- `errors: List[ValidationError]` - Field-specific validation errors
- `warnings: List[ValidationWarning]` - Non-blocking warnings
- `suggestions: List[str]` - Improvement suggestions

### HookTemplate

**Purpose**: Represents a predefined Python hook script template

**Fields**:
- `template_id: str` - Unique template identifier
- `name: str` - Human-readable template name
- `supported_events: List[HookEventType]` - Compatible hook events
- `description: str` - Template description
- `customization_options: Dict[str, Any]` - Available customization parameters
- `dependencies: List[str]` - Required Python packages or system tools
- `source: TemplateSource` - Where template is defined (builtin/user/file)
- `template_class: Type[BaseTemplate]` - Template implementation class
- `version: str` - Template version for compatibility

### BaseTemplate

**Purpose**: Abstract base class for all hook templates

**Methods**:
- `generate(config: TemplateConfig) -> str` - Generate script content
- `validate_config(config: Dict[str, Any]) -> ValidationResult` - Validate customization
- `get_default_config() -> Dict[str, Any]` - Return default configuration
- `get_dependencies() -> List[str]` - Return required dependencies

**Properties**:
- `name: str` - Template name
- `description: str` - Template description
- `supported_events: List[HookEventType]` - Compatible events
- `customization_schema: Dict[str, Any]` - JSON schema for customization

### TemplateRegistry

**Purpose**: Central registry for managing hook templates

**Fields**:
- `builtin_templates: Dict[str, HookTemplate]` - Built-in templates
- `user_templates: Dict[str, HookTemplate]` - User-registered templates
- `template_paths: List[Path]` - Search paths for templates
- `registry_file: Path` - Template registry file location

**Methods**:
- `register_template(template_id: str, template_class: Type[BaseTemplate])` - Register new template
- `unregister_template(template_id: str)` - Remove template
- `get_template(template_id: str) -> HookTemplate` - Get template by ID
- `list_templates(event_filter: Optional[HookEventType]) -> List[HookTemplate]` - List available templates
- `reload_templates()` - Reload templates from files

**Template Types**:
- `security-guard`: Multi-tool security protection
- `auto-formatter`: Python file auto-formatting
- `auto-linter`: Code quality checking
- `git-auto-commit`: Automatic git operations
- `permission-logger`: Request logging
- `desktop-notifier`: System notifications
- `task-manager`: Claude stop control
- `prompt-filter`: Sensitive data filtering
- `context-loader`: Project context loading
- `cleanup-handler`: Session cleanup tasks

### ScriptGenerationResult

**Purpose**: Result of Python script generation process

**Fields**:
- `success: bool` - Generation success status
- `generated_file: Path` - Path to generated script
- `template_used: HookTemplateType` - Template that was used
- `executable_set: bool` - Whether script was made executable
- `added_to_settings: bool` - Whether automatically added to settings
- `customizations_applied: Dict[str, Any]` - Applied customization options

**ValidationError Structure**:
- `field_name: str` - Name of the field with error
- `error_code: str` - Standardized error code
- `message: str` - Human-readable error description
- `suggested_fix: Optional[str]` - Suggested correction

**ValidationWarning Structure**:
- `field_name: str` - Name of the field with warning
- `warning_code: str` - Standardized warning code
- `message: str` - Human-readable warning description

## Enumerations

### HookEventType
```python
class HookEventType(str, Enum):
    PRE_TOOL_USE = "PreToolUse"
    POST_TOOL_USE = "PostToolUse"
    NOTIFICATION = "Notification"
    USER_PROMPT_SUBMIT = "UserPromptSubmit"
    STOP = "Stop"
    SUBAGENT_STOP = "SubagentStop"
    PRE_COMPACT = "PreCompact"
    SESSION_START = "SessionStart"
    SESSION_END = "SessionEnd"
```

### SettingsLevel
```python
class SettingsLevel(str, Enum):
    PROJECT = "project"         # .claude/settings.json
    USER_LOCAL = "user-local"   # .claude/settings.local.json
    USER_GLOBAL = "user"        # ~/.claude/settings.json
```

### OutputFormat
```python
class OutputFormat(str, Enum):
    JSON = "json"
    TABLE = "table"
    YAML = "yaml"
    QUIET = "quiet"
```

### HookTemplateType
```python
class HookTemplateType(str, Enum):
    SECURITY_GUARD = "security-guard"
    AUTO_FORMATTER = "auto-formatter"
    AUTO_LINTER = "auto-linter"
    GIT_AUTO_COMMIT = "git-auto-commit"
    PERMISSION_LOGGER = "permission-logger"
    DESKTOP_NOTIFIER = "desktop-notifier"
    TASK_MANAGER = "task-manager"
    PROMPT_FILTER = "prompt-filter"
    CONTEXT_LOADER = "context-loader"
    CLEANUP_HANDLER = "cleanup-handler"
```

### TemplateSource
```python
class TemplateSource(str, Enum):
    BUILTIN = "builtin"         # Built-in templates
    USER = "user"               # User-registered templates
    FILE = "file"               # File-based templates
    PLUGIN = "plugin"           # Plugin-provided templates
```

### TemplateConfig
```python
@dataclass
class TemplateConfig:
    template_id: str
    event_type: HookEventType
    customization: Dict[str, Any]
    output_path: Path
    matcher: Optional[str] = None
    timeout: Optional[int] = None
```

## JSON Schema Mappings

### Claude Code Settings Schema (EXACT FORMAT - DO NOT MODIFY)
```json
{
  "hooks": {
    "EventName": [
      {
        "matcher": "ToolPattern",
        "hooks": [
          {
            "type": "command",
            "command": "your-command-here",
            "timeout": 60
          }
        ]
      }
    ]
  }
}
```

**CRITICAL CONSTRAINTS**:
- CLI tools MUST only modify the `hooks` section
- CLI tools MUST NOT add, modify, or remove any other top-level fields
- Hook objects MUST only contain: `type`, `command`, `timeout` (optional)
- CLI tools MUST NOT add additional fields to hook objects
- `type` field is ALWAYS "command" (as per Claude Code specification)
- Existing non-hook settings MUST be preserved exactly as-is

### CLI Output Schema
```json
{
  "success": true,
  "message": "Hook added successfully",
  "data": {
    "hook": {
      "event_type": "PreToolUse",
      "command": "echo 'test'",
      "matcher": "Write",
      "timeout": 30
    },
    "settings_file": "/path/to/.claude/settings.json",
    "backup_created": true
  },
  "warnings": [],
  "errors": []
}
```

## Domain Constraints

### File System Constraints
- Settings files must be in `.claude/` directories
- Backup files use `.bak` extension with timestamp
- Parent directories created if missing
- File permissions respected and validated

### Performance Constraints
- Settings file size limit: 10MB
- Hook validation timeout: 5 seconds
- CLI response time target: <100ms
- Memory usage limit for file operations: <50MB

### Security Constraints
- No shell injection in hook commands (warning only)
- Path traversal protection for file operations
- Validation of file permissions before modifications
- Backup creation before destructive operations