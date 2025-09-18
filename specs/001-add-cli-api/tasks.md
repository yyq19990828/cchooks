# Tasks: CLI API Tools for Hook Management

**Input**: Design documents from `/specs/001-add-cli-api/`
**Prerequisites**: plan.md (✓), research.md (✓), data-model.md (✓), contracts/ (✓), quickstart.md (✓)

## Execution Flow (main)
```
1. Load plan.md from feature directory
   → Found: tech stack = argparse, pathlib, json
   → Libraries: cchooks, Python 3.11+, zero external dependencies
2. Load design documents:
   → data-model.md: 9 entities → model tasks
   → contracts/: 2 files → contract test tasks
   → quickstart.md: 11 scenarios → integration tests
3. Generate tasks by category:
   → Setup: project init, dependencies, CLI structure
   → Tests: contract tests, integration tests
   → Core: models, CLI commands, settings API
   → Integration: file operations, validation
   → Polish: unit tests, performance, docs
4. Apply task rules:
   → Different files = mark [P] for parallel
   → Same file = sequential (no [P])
   → Tests before implementation (TDD)
5. Number tasks sequentially (T001, T002...)
6. Generate dependency graph
7. Create parallel execution examples
8. Validate task completeness:
   → All CLI commands have tests ✓
   → All entities have models ✓
   → All contracts have tests ✓
9. Return: SUCCESS (tasks ready for execution)
```

## Format: `[ID] [P?] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- Include exact file paths in descriptions

## Path Conventions
- **Single project**: `src/cchooks/`, `tests/` at repository root
- Paths shown below follow Python package structure

## Phase 3.1: Setup
- [ ] T001 Add required project structure per implementation plan (src/cchooks/cli/commands/, src/cchooks/models/, src/cchooks/services/, src/cchooks/api/, src/cchooks/templates/builtin/, tests/cli/, tests/contract/, tests/scenarios/)
- [ ] T002 Initialize Python package with __init__.py files and CLI entry points in pyproject.toml
- [ ] T003 [P] Setup argparse CLI framework in src/cchooks/cli/argument_parser.py
- [ ] T004 [P] Configure pathlib file operations in src/cchooks/utils/file_operations.py
- [ ] T005 [P] Setup JSON manipulation utilities in src/cchooks/utils/json_handler.py
- [ ] T006 [P] Create settings discovery module in src/cchooks/settings/discovery.py

## Phase 3.2: Tests First (TDD) ⚠️ MUST COMPLETE BEFORE 3.3
**CRITICAL: These tests MUST be written and MUST FAIL before ANY implementation**
- [ ] T007 [P] Settings file API contract tests in tests/contract/test_settings_api.py
- [ ] T008 [P] CLI commands contract tests in tests/contract/test_cli_commands.py
- [ ] T009 [P] Hook configuration validation tests in tests/unit/test_hook_validation.py
- [ ] T010 [P] Settings file manipulation tests in tests/unit/test_settings_operations.py
- [ ] T011 [P] JSON formatting preservation tests in tests/unit/test_json_formatting.py
- [ ] T012 [P] File discovery integration tests in tests/integration/test_file_discovery.py

## Phase 3.3: Core Implementation (ONLY after tests are failing)
### 3.3.1: Data Models & Types
- [ ] T013 [P] HookConfiguration model in src/cchooks/models/hook_config.py
- [ ] T014 [P] SettingsFile model in src/cchooks/models/settings_file.py
- [ ] T015 [P] ValidationResult model in src/cchooks/models/validation.py
- [ ] T016 [P] Enumerations (HookEventType, SettingsLevel) in src/cchooks/types/enums.py

### 3.3.2: Core Services
- [ ] T017 [P] SettingsManager service in src/cchooks/services/settings_manager.py
- [ ] T018 [P] HookValidator service in src/cchooks/services/hook_validator.py
- [ ] T019 Settings file operations API in src/cchooks/api/settings_operations.py
- [ ] T020 [P] Output formatters (JSON/table/YAML) in src/cchooks/utils/formatters.py

### 3.3.3: CLI Commands Implementation
- [ ] T021 [P] cc_addhook command in src/cchooks/cli/commands/add_hook.py
- [ ] T022 [P] cc_updatehook command in src/cchooks/cli/commands/update_hook.py
- [ ] T023 [P] cc_removehook command in src/cchooks/cli/commands/remove_hook.py
- [ ] T024 [P] cc_listhooks command in src/cchooks/cli/commands/list_hooks.py
- [ ] T025 [P] cc_validatehooks command in src/cchooks/cli/commands/validate_hooks.py

## Phase 3.4: Python Hook Generation System
### 3.4.1: Template Framework
- [ ] T026 [P] BaseTemplate abstract class in src/cchooks/templates/base_template.py
- [ ] T027 [P] TemplateRegistry service in src/cchooks/templates/registry.py
- [ ] T028 [P] Template validation system in src/cchooks/templates/validator.py

### 3.4.2: Built-in Templates
- [ ] T029 [P] SecurityGuardTemplate in src/cchooks/templates/builtin/security_guard.py
- [ ] T030 [P] AutoFormatterTemplate in src/cchooks/templates/builtin/auto_formatter.py
- [ ] T031 [P] ContextLoaderTemplate in src/cchooks/templates/builtin/context_loader.py
- [ ] T032 [P] Additional templates (7 more) in src/cchooks/templates/builtin/
- [ ] T033 Template generation engine in src/cchooks/services/script_generator.py

### 3.4.3: Template CLI Commands
- [ ] T034 [P] cc_generatehook command in src/cchooks/cli/commands/generate_hook.py
- [ ] T035 [P] cc_registertemplate command in src/cchooks/cli/commands/register_template.py
- [ ] T036 [P] cc_listtemplates command in src/cchooks/cli/commands/list_templates.py
- [ ] T037 [P] cc_unregistertemplate command in src/cchooks/cli/commands/unregister_template.py

## Phase 3.5: Integration & Configuration
- [ ] T038 CLI entry point configuration and main dispatcher in src/cchooks/cli/main.py
- [ ] T039 Package setup and installation configuration
- [ ] T040 Cross-platform file permission handling
- [ ] T041 Error handling and user-friendly error messages
- [ ] T042 Settings file backup and recovery system in src/cchooks/utils/backup.py

## Phase 3.6: Integration Tests & Scenarios
- [ ] T043 [P] Scenario 1: Generate complex Python hook (tests/scenarios/test_python_generation.py)
- [ ] T044 [P] Scenario 2: Add hook to existing settings (tests/scenarios/test_add_to_existing.py)
- [ ] T045 [P] Scenario 3: Handle missing settings file (tests/scenarios/test_missing_settings.py)
- [ ] T046 [P] Scenario 4: Invalid configuration handling (tests/scenarios/test_invalid_config.py)
- [ ] T047 [P] Scenario 5: Update existing hook (tests/scenarios/test_update_hook.py)
- [ ] T048 [P] Scenario 6: Remove hook (tests/scenarios/test_remove_hook.py)
- [ ] T049 [P] Scenario 7: Cross-level management (tests/scenarios/test_cross_level.py)
- [ ] T050 [P] Scenario 8: Template management (tests/scenarios/test_template_mgmt.py)
- [ ] T051 [P] Scenario 9: Dry run operations (tests/scenarios/test_dry_run.py)

## Phase 3.7: Polish & Validation
- [ ] T052 [P] Performance optimization for large settings files
- [ ] T053 [P] Comprehensive CLI help text and documentation
- [ ] T054 [P] Edge case handling and error recovery
- [ ] T055 Type checking validation (ensure all types are correctly defined)
- [ ] T056 Integration testing with real Claude Code installation
- [ ] T057 Cross-platform compatibility testing
- [ ] T058 Security validation (prevent shell injection, path traversal)

## Dependencies
- Setup (T001-T006) before tests (T007-T012)
- Tests (T007-T012) before implementation (T013-T042)
- Data models (T013-T016) before services (T017-T019)
- Core services before CLI commands (T021-T025)
- Template framework (T026-T028) before built-in templates (T029-T032)
- Templates before template CLI commands (T034-T037)
- Core implementation before integration tests (T043-T051)

## Parallel Example
```bash
# Launch T007-T012 together (contract & unit tests):
Task --subagent_type general-purpose "Settings file API contract tests in tests/contract/test_settings_api.py"
Task --subagent_type general-purpose "CLI commands contract tests in tests/contract/test_cli_commands.py"
Task --subagent_type general-purpose "Hook configuration validation tests in tests/unit/test_hook_validation.py"
Task --subagent_type general-purpose "Settings file manipulation tests in tests/unit/test_settings_operations.py"

# Launch T013-T016 together (data models):
Task --subagent_type general-purpose "HookConfiguration model in src/cchooks/models/hook_config.py"
Task --subagent_type general-purpose "SettingsFile model in src/cchooks/models/settings_file.py"
Task --subagent_type general-purpose "ValidationResult model in src/cchooks/models/validation.py"
Task --subagent_type general-purpose "Enumerations in src/cchooks/types/enums.py"

# Launch T021-T025 together (CLI commands):
Task --subagent_type general-purpose "cc_addhook command in src/cchooks/cli/commands/add_hook.py"
Task --subagent_type general-purpose "cc_updatehook command in src/cchooks/cli/commands/update_hook.py"
Task --subagent_type general-purpose "cc_removehook command in src/cchooks/cli/commands/remove_hook.py"
Task --subagent_type general-purpose "cc_listhooks command in src/cchooks/cli/commands/list_hooks.py"
```

## Critical Constraints Validation
*MUST be enforced in ALL tasks*

### Claude Code Format Compliance
- [ ] CLI tools ONLY modify the "hooks" section of settings.json
- [ ] Hook objects contain ONLY: "type", "command", "timeout" (optional)
- [ ] "type" field is ALWAYS "command"
- [ ] NO additional fields in hook objects
- [ ] Existing non-hook settings preserved exactly

### Implementation Requirements
- [ ] Zero external dependencies (only Python stdlib + cchooks)
- [ ] Cross-platform compatibility (Windows, macOS, Linux)
- [ ] Argparse for CLI argument parsing
- [ ] Pathlib for file operations
- [ ] JSON standard library for parsing
- [ ] Performance: CLI response time <100ms
- [ ] Security: No shell injection, path traversal protection

## Notes
- [P] tasks = different files, no dependencies between them
- Verify all tests fail before implementing corresponding features
- Follow TDD strictly: Test → Implement → Refactor
- Each task should result in a single commit
- Contract tests validate exact API specifications
- Integration tests validate end-to-end user scenarios
- Security and performance requirements must be met

## Task Generation Rules Applied

1. **From CLI Commands Contract** (8 commands):
   - Each command → test task [P] + implementation task [P]
   - Commands: add, update, remove, list, validate, generate, register, list-templates, unregister

2. **From Settings API Contract** (2 APIs):
   - SettingsManager → test + implementation
   - HookValidator → test + implementation

3. **From Data Model** (9 entities):
   - Each entity → model implementation task [P]
   - Core: HookConfiguration, SettingsFile, ValidationResult, CLICommand

4. **From Quickstart Scenarios** (11 scenarios):
   - Each scenario → integration test task [P]
   - Critical user workflows covered

5. **From Template System** (10 templates):
   - Template framework → base classes and registry
   - Built-in templates → 10 template implementations [P]
   - Template CLI → 4 additional commands

6. **Python Package Requirements**:
   - Setup tasks for project structure
   - Entry point configuration
   - Cross-platform compatibility
   - Performance and security validation

## Validation Checklist
*Verified before task list completion*

- [✓] All CLI commands have corresponding test tasks
- [✓] All data models have implementation tasks
- [✓] All contract specifications have test tasks
- [✓] All quickstart scenarios have integration tests
- [✓] Tests come before implementation (TDD enforced)
- [✓] Parallel tasks are truly independent (different files)
- [✓] Each task specifies exact file path
- [✓] No task modifies same file as another [P] task
- [✓] Claude Code format constraints addressed
- [✓] Zero external dependencies requirement met
- [✓] Cross-platform compatibility planned
- [✓] Performance requirements specified
- [✓] Security requirements included

**Total Tasks**: 58 tasks across 7 phases
**Parallel Opportunities**: 35 tasks can run in parallel
**Critical Path**: Setup → Tests → Models → Services → CLI → Templates → Integration
**Estimated Completion**: Ready for immediate execution