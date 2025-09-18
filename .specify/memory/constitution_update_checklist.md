# Constitution Update Checklist

When amending the constitution (`/memory/constitution.md`), ensure all dependent documents are updated to maintain consistency.

## Templates to Update

### When adding/modifying ANY article:
- [ ] `/templates/plan-template.md` - Update Constitution Check section
- [ ] `/templates/spec-template.md` - Update if requirements/scope affected
- [ ] `/templates/tasks-template.md` - Update if new task types needed
- [ ] `/.claude/commands/plan.md` - Update if planning process changes
- [ ] `/.claude/commands/tasks.md` - Update if task generation affected
- [ ] `/CLAUDE.md` - Update runtime development guidelines

### Article-specific updates:

#### Article I (Library-First Development):
- [ ] Ensure templates emphasize library creation with type hints
- [ ] Update CLI command examples for hook development
- [ ] Add Python package structure requirements
- [ ] Include factory pattern usage examples

#### Article II (CLI Interface Excellence):
- [ ] Update CLI flag requirements in templates
- [ ] Add text I/O protocol reminders for Claude Code integration
- [ ] Include .claude/settings.json configuration examples
- [ ] Add JSON/human-readable output format requirements

#### Article III (Test-First Development):
- [ ] Update test order in all templates
- [ ] Emphasize TDD requirements for hook types
- [ ] Add test approval gates for hook validation
- [ ] Include 9 hook types coverage requirements

#### Article IV (Hook Integration Testing):
- [ ] List integration test triggers for hook changes
- [ ] Update test type priorities for Claude Code compatibility
- [ ] Add real dependency requirements for hook contexts
- [ ] Include cross-hook interaction test cases

#### Article V (Type Safety & Observability):
- [ ] Add type hints requirements to templates
- [ ] Include structured logging for hook execution
- [ ] Update error handling with field-specific messages
- [ ] Add dual output mode support (simple/advanced)

#### Article VI (Python Package Standards):
- [ ] Add semantic versioning increment reminders
- [ ] Include backwards compatibility procedures for hooks
- [ ] Update migration requirements for breaking changes
- [ ] Add pyproject.toml and src/ layout requirements

#### Article VII (Simplicity & Developer Experience):
- [ ] Update dependency minimization guidelines
- [ ] Add YAGNI reminders for hook development
- [ ] Include factory pattern simplification examples
- [ ] Add developer documentation requirements

## Python Package Specific Updates

### CLI API Development:
- [ ] Add command structure validation (UNIX conventions)
- [ ] Include stdin/file input handling requirements
- [ ] Add exit code standardization
- [ ] Include configuration file integration

### Hook Development Standards:
- [ ] Add context validation requirements
- [ ] Include JSON output structure consistency
- [ ] Add custom exception hierarchy usage
- [ ] Include performance overhead guidelines

### Quality Gates:
- [ ] Add make targets validation (test, type-check, lint)
- [ ] Include coverage reporting requirements
- [ ] Add integration test standards with Claude Code
- [ ] Include CLI workflow validation

## Validation Steps

1. **Before committing constitution changes:**
   - [ ] All templates reference new Python/CLI requirements
   - [ ] Hook development examples updated to match new rules
   - [ ] No contradictions between package and CLI standards
   - [ ] Type safety requirements consistently applied

2. **After updating templates:**
   - [ ] Run through a sample hook implementation plan
   - [ ] Verify all constitution requirements addressed for CLI tools
   - [ ] Check that templates support both library and CLI development
   - [ ] Validate Claude Code integration compatibility

3. **Version tracking:**
   - [ ] Update constitution version number
   - [ ] Note version in template footers
   - [ ] Add amendment to constitution history
   - [ ] Update package version requirements

## Common Misses

Watch for these often-forgotten updates:
- Command documentation for CLI tools (`/commands/*.md`)
- Hook type checklist items in templates
- Example code for hook development and CLI usage
- Python-specific variations (type hints, packaging, testing)
- Cross-references between hook types and CLI commands
- Claude Code integration testing examples

## Template Sync Status

Last sync check: 2025-09-18
- Constitution version: 1.0.0
- Templates aligned: ✅ (updated with cchooks CLI requirements)
- Python package standards: ✅ (src/ layout, pyproject.toml, type hints)
- CLI API standards: ✅ (UNIX conventions, JSON/text output, .claude/settings.json)
- Hook development: ✅ (9 hook types, validation, factory patterns)
- Template updates completed: ✅
  - plan-template.md: Constitution Check section updated
  - spec-template.md: CLI-specific guidance added
  - tasks-template.md: Python package task patterns added
  - Project CLAUDE.md: CLI development guidelines added

## Package-Specific Checkpoints

### CLI Tools Development:
- [ ] Command naming follows package conventions (cchooks-*)
- [ ] Configuration integrates with .claude/settings.json
- [ ] Output formats support both automation and human use
- [ ] Error messages provide actionable guidance

### Hook Library Integration:
- [ ] New CLI tools extend existing hook contexts
- [ ] Factory pattern maintained for ease of use
- [ ] Type safety preserved across CLI and library interfaces
- [ ] Documentation covers both library and CLI usage

### Testing Requirements:
- [ ] CLI commands have end-to-end tests
- [ ] Hook integration tested with real Claude Code scenarios
- [ ] Performance impact measured for CLI overhead
- [ ] Cross-platform compatibility validated

---

*This checklist ensures the constitution's principles are consistently applied across all cchooks project documentation and CLI development.*