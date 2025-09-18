# Research: CLI API Tools for Hook Management

## CLI Framework Choice

**Decision**: Use `argparse` (Python standard library)

**Rationale**:
- Zero external dependencies (maintains constitutional requirement)
- Sufficient functionality for CLI argument parsing and help generation
- Well-documented and stable
- Integrates well with existing cchooks type system

**Alternatives considered**:
- `click`: More features but adds external dependency
- `typer`: Modern CLI framework but adds external dependency
- Custom argument parsing: Too much reinvention

## Settings File Discovery Patterns

**Decision**: Multi-level discovery with precedence order

**Rationale**:
- Follow Claude Code's own discovery pattern
- Support both project-level and user-level configurations
- Clear precedence rules for conflicting settings

**Implementation**:
1. `.claude/settings.json` (project-level, highest precedence)
2. `.claude/settings.local.json` (local project-level)
3. `~/.claude/settings.json` (user-level, lowest precedence)

**Alternatives considered**:
- Single file only: Too limited for different use cases
- Environment variables: Not compatible with Claude Code patterns
- XDG Base Directory: Different from Claude Code conventions

## JSON Manipulation with Formatting Preservation

**Decision**: Use `json` + custom formatting preservation

**Rationale**:
- Preserve existing formatting when possible
- Handle comments gracefully (warn and preserve structure)
- Maintain readability of settings files

**Implementation**:
- Load with `json.load()`
- Preserve indentation patterns from original file
- Use `json.dump()` with consistent 2-space indentation
- Backup original file before modifications

**Alternatives considered**:
- `ruamel.yaml` with JSON mode: Adds dependency
- Custom JSON parser: Too complex for benefits
- No formatting preservation: Poor user experience

## Cross-Platform File Permission Handling

**Decision**: Python `pathlib` with graceful degradation

**Rationale**:
- Cross-platform compatibility
- Clear error messages for permission issues
- Follow principle of least surprise

**Implementation**:
- Use `pathlib.Path` for all file operations
- Check write permissions before modifications
- Provide clear error messages for common issues
- Create parent directories if they don't exist

**Alternatives considered**:
- Platform-specific code: Too complex to maintain
- Ignore permissions: Poor error handling
- Third-party libraries: Adds dependencies

## CLI Command Structure

**Decision**: Hierarchical command structure with consistent flags

**Commands**:
- `cc_addhook` - Add new hook to settings
- `cc_updatehook` - Update existing hook configuration
- `cc_removehook` - Remove hook from settings
- `cc_listhooks` - List configured hooks
- `cc_validatehooks` - Validate hook configurations

**Common Flags**:
- `--level` - target level: `project`, `user`
- `--format` - output format: `json`, `table`, `yaml`
- `--dry-run` - preview changes without applying
- `--backup` - create backup before changes

**Hook-Specific Flags** (for add/update):
- `--event` - hook event type (required)
- `--command` - hook command (required)
- `--matcher` - tool matcher pattern
- `--timeout` - execution timeout

**Rationale**:
- Intuitive naming with `cc_` prefix
- Consistent flag patterns across commands
- Supports both interactive and automation use cases