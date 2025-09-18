# Tasks: [FEATURE NAME]

**Input**: Design documents from `/specs/[###-feature-name]/`
**Prerequisites**: plan.md (required), research.md, data-model.md, contracts/

## Execution Flow (main)
```
1. Load plan.md from feature directory
   → If not found: ERROR "No implementation plan found"
   → Extract: tech stack, libraries, structure
2. Load optional design documents:
   → data-model.md: Extract entities → model tasks
   → contracts/: Each file → contract test task
   → research.md: Extract decisions → setup tasks
3. Generate tasks by category:
   → Setup: project init, dependencies, linting
   → Tests: contract tests, integration tests
   → Core: models, services, CLI commands
   → Integration: DB, middleware, logging
   → Polish: unit tests, performance, docs
4. Apply task rules:
   → Different files = mark [P] for parallel
   → Same file = sequential (no [P])
   → Tests before implementation (TDD)
5. Number tasks sequentially (T001, T002...)
6. Generate dependency graph
7. Create parallel execution examples
8. Validate task completeness:
   → All contracts have tests?
   → All entities have models?
   → All endpoints implemented?
9. Return: SUCCESS (tasks ready for execution)
```

## Format: `[ID] [P?] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- Include exact file paths in descriptions

## Path Conventions
- **Single project**: `src/`, `tests/` at repository root
- **Web app**: `backend/src/`, `frontend/src/`
- **Mobile**: `api/src/`, `ios/src/` or `android/src/`
- Paths shown below assume single project - adjust based on plan.md structure

## Phase 3.1: Setup
- [ ] T001 Create project structure per implementation plan (src/cchooks/, tests/)
- [ ] T002 Initialize Python project with pyproject.toml and dependencies
- [ ] T003 [P] Configure ruff linting and pyright type checking
- [ ] T004 [P] Setup pytest configuration with coverage
- [ ] T005 [P] Configure Makefile with standard targets (test, lint, type-check)

## Phase 3.2: Tests First (TDD) ⚠️ MUST COMPLETE BEFORE 3.3
**CRITICAL: These tests MUST be written and MUST FAIL before ANY implementation**
- [ ] T006 [P] Hook context validation tests in tests/contexts/test_new_hook.py
- [ ] T007 [P] CLI command tests in tests/cli/test_commands.py
- [ ] T008 [P] Integration test with .claude/settings.json in tests/integration/test_config.py
- [ ] T009 [P] Contract test hook output formats in tests/contract/test_output_formats.py

## Phase 3.3: Core Implementation (ONLY after tests are failing)
- [ ] T010 [P] Hook context classes in src/cchooks/contexts/new_hook.py
- [ ] T011 [P] CLI command parser in src/cchooks/cli/commands.py
- [ ] T012 [P] Configuration manager in src/cchooks/config/settings.py
- [ ] T013 Hook factory pattern updates in src/cchooks/__init__.py
- [ ] T014 Output formatters (JSON/text) in src/cchooks/utils.py
- [ ] T015 Type validation and error handling
- [ ] T016 Hook integration with Claude Code protocol

## Phase 3.4: Integration
- [ ] T017 CLI entry points in pyproject.toml
- [ ] T018 Package installation and distribution setup
- [ ] T019 .claude/settings.json integration and validation
- [ ] T020 Hook execution logging and error reporting

## Phase 3.5: Polish
- [ ] T021 [P] Unit tests for utilities in tests/unit/test_utils.py
- [ ] T022 Performance benchmarks (minimal overhead requirement)
- [ ] T023 [P] Update documentation and examples
- [ ] T024 Type checking validation (mypy/pyright)
- [ ] T025 Integration testing with real Claude Code scenarios

## Dependencies
- Setup (T001-T005) before tests (T006-T009)
- Tests (T006-T009) before implementation (T010-T016)
- T010 blocks T013 (hook contexts before factory updates)
- T012 blocks T019 (config manager before settings integration)
- Implementation before polish (T021-T025)

## Parallel Example
```
# Launch T006-T009 together:
Task: "Hook context validation tests in tests/contexts/test_new_hook.py"
Task: "CLI command tests in tests/cli/test_commands.py"
Task: "Integration test with .claude/settings.json in tests/integration/test_config.py"
Task: "Contract test hook output formats in tests/contract/test_output_formats.py"
```

## Notes
- [P] tasks = different files, no dependencies
- Verify tests fail before implementing
- Commit after each task
- Avoid: vague tasks, same file conflicts

## Task Generation Rules
*Applied during main() execution*

1. **From Hook Specifications**:
   - Each hook type → context validation test [P]
   - Each CLI command → command test task [P]

2. **From Configuration Requirements**:
   - Settings integration → config test [P]
   - Output formats → format validation test [P]

3. **From User Stories**:
   - Each CLI workflow → integration test [P]
   - Hook development scenarios → end-to-end tests

4. **Python Package Specific**:
   - Type hints → type checking tasks
   - CLI entry points → installation tests
   - Factory patterns → unit tests

5. **Ordering**:
   - Setup → Tests → Hook Contexts → CLI Commands → Integration → Polish
   - Dependencies block parallel execution

## Validation Checklist
*GATE: Checked by main() before returning*

- [ ] All hook types have corresponding context tests
- [ ] All CLI commands have test tasks
- [ ] All tests come before implementation (TDD enforced)
- [ ] Parallel tasks truly independent (different files)
- [ ] Each task specifies exact file path in src/cchooks/ or tests/
- [ ] No task modifies same file as another [P] task
- [ ] Type checking and linting tasks included
- [ ] Configuration integration tests present
- [ ] Python package standards followed (pyproject.toml, setup)