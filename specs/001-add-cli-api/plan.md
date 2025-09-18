
# Implementation Plan: CLI API Tools for Hook Management

**Branch**: `001-add-cli-api` | **Date**: 2025-09-18 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-add-cli-api/spec.md`

## Execution Flow (/plan command scope)
```
1. Load feature spec from Input path
   → Feature spec loaded successfully
2. Fill Technical Context (scan for NEEDS CLARIFICATION)
   → Project Type: single (Python library with CLI)
   → Structure Decision: Option 1 (src/ layout)
3. Fill the Constitution Check section based on the content of the constitution document.
4. Evaluate Constitution Check section below
   → Constitution requirements align with feature design
   → Update Progress Tracking: Initial Constitution Check
5. Execute Phase 0 → research.md
   → All clarifications resolved from user input
6. Execute Phase 1 → contracts, data-model.md, quickstart.md, CLAUDE.md
7. Re-evaluate Constitution Check section
   → Update Progress Tracking: Post-Design Constitution Check
8. Plan Phase 2 → Describe task generation approach (DO NOT create tasks.md)
9. STOP - Ready for /tasks command
```

**IMPORTANT**: The /plan command STOPS at step 7. Phases 2-4 are executed by other commands:
- Phase 2: /tasks command creates tasks.md
- Phase 3-4: Implementation execution (manual or via tools)

## Summary
Primary requirement: Extend cchooks library with CLI tools for managing Claude Code hook configurations in .claude/settings.json. Technical approach: Create new CLI module using Python CLI patterns with comprehensive hook validation via cchooks library types. Support `cc_addhook` command with `--event` and `--level` flags for full CRUD operations.

## Technical Context
**Language/Version**: Python 3.11+
**Primary Dependencies**: cchooks library (existing), click or argparse for CLI
**Storage**: .claude/settings.json files (user-level ~/.claude/ and project-level)
**Testing**: pytest (existing test framework)
**Target Platform**: Cross-platform CLI (Linux, macOS, Windows)
**Project Type**: single - Python library with CLI extensions
**Performance Goals**: CLI response time <100ms for typical operations
**Constraints**: Zero additional runtime dependencies beyond existing cchooks requirements
**Scale/Scope**: Support all 9 hook types, handle settings files up to 10MB

**User-Provided Technical Details**:
- Expand current cchooks lib by adding CLI tools
- Example: `cc_addhook` command to add hooks to settings
- `--event` flag to define hook event (e.g., PreToolUse)
- `--level` flag to define project level or user-system level
- Design first version for comprehensive hook management

## Constitution Check
*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Article I (Library-First Development):
- [x] Feature starts as standalone library with clear interfaces
- [x] Self-contained, independently testable with type hints
- [x] Clear purpose defined (no organizational-only libraries)
- [x] Extends cchooks package foundational hook types

### Article II (CLI Interface Excellence):
- [x] Functionality exposed via CLI commands
- [x] Text-based protocol: stdin/args → stdout, errors → stderr
- [x] Supports both JSON and human-readable formats
- [x] Claude Code integration compatibility
- [x] .claude/settings.json configuration support

### Article III (Test-First Development):
- [x] TDD mandatory: Tests written → User approved → Tests fail → Implement
- [x] Red-Green-Refactor cycle enforced
- [x] All 9 hook types have comprehensive test coverage
- [x] Edge cases and real-world scenarios included

### Article IV (Hook Integration Testing):
- [x] New hook type contract tests planned
- [x] Hook context validation changes tested
- [x] Claude Code integration compatibility verified
- [x] Cross-hook type interactions tested
- [x] CLI tool end-to-end workflows covered

### Article V (Type Safety & Observability):
- [x] Complete type hints for all public APIs
- [x] Structured logging for hook execution
- [x] Hook validation errors provide field-specific messages
- [x] Supports both simple (exit codes) and advanced (JSON) output modes

### Article VI (Python Package Standards):
- [x] Follows src/ layout, pyproject.toml configuration
- [x] Semantic versioning maintained
- [x] Backwards compatibility for hook interfaces preserved
- [x] Breaking changes include migration guides

### Article VII (Simplicity & Developer Experience):
- [x] YAGNI principles applied
- [x] Minimal external dependencies (zero runtime deps maintained)
- [x] Factory patterns (create_context()) preserved
- [x] Documentation accessible to both library and CLI users

## Project Structure

### Documentation (this feature)
```
specs/001-add-cli-api/
├── plan.md              # This file (/plan command output)
├── research.md          # Phase 0 output (/plan command)
├── data-model.md        # Phase 1 output (/plan command)
├── quickstart.md        # Phase 1 output (/plan command)
├── contracts/           # Phase 1 output (/plan command)
└── tasks.md             # Phase 2 output (/tasks command - NOT created by /plan)
```

### Source Code (repository root)
```
# Option 1: Single project (DEFAULT) - CLEANED UP
src/
├── cchooks/
│   ├── cli/           # NEW: CLI commands module (self-contained)
│   ├── contexts/      # EXISTING: Hook contexts
│   ├── types/         # EXISTING: Type definitions directory
│   ├── types.py       # EXISTING: Type definitions
│   ├── utils/         # EXISTING: Utilities directory
│   └── utils.py       # EXISTING: Utilities
│
# REMOVED: api/, models/, services/, settings/ directories (empty and unnecessary)
# CLI data models and settings management will be contained within cli/ module

tests/
├── cli/               # NEW: CLI-specific tests (only addition needed)
├── contract/          # EXISTING: Hook contract tests
├── contexts/          # EXISTING: Context-specific tests
├── fixtures/          # EXISTING: Test fixtures
├── integration/       # EXISTING: Integration tests
└── test_*.py          # EXISTING: Unit tests

# CLI entry points will be added to pyproject.toml
```

**Structure Decision**: Single project with new CLI module in existing cchooks package

## Phase 0: Outline & Research
1. **Extract unknowns from Technical Context** above:
   - For each NEEDS CLARIFICATION → research task
   - For each dependency → best practices task
   - For each integration → patterns task

2. **Generate and dispatch research agents**:
   ```
   For each unknown in Technical Context:
     Task: "Research {unknown} for {feature context}"
   For each technology choice:
     Task: "Find best practices for {tech} in {domain}"
   ```

3. **Consolidate findings** in `research.md` using format:
   - Decision: [what was chosen]
   - Rationale: [why chosen]
   - Alternatives considered: [what else evaluated]

**Output**: research.md with all NEEDS CLARIFICATION resolved

## Phase 1: Design & Contracts
*Prerequisites: research.md complete*

1. **Extract entities from feature spec** → `data-model.md`:
   - Entity name, fields, relationships
   - Validation rules from requirements
   - State transitions if applicable

2. **Generate API contracts** from functional requirements:
   - For each user action → endpoint
   - Use standard REST/GraphQL patterns
   - Output OpenAPI/GraphQL schema to `/contracts/`

3. **Generate contract tests** from contracts:
   - One test file per endpoint
   - Assert request/response schemas
   - Tests must fail (no implementation yet)

4. **Extract test scenarios** from user stories:
   - Each story → integration test scenario
   - Quickstart test = story validation steps

5. **Update agent file incrementally** (O(1) operation):
   - Run `.specify/scripts/bash/update-agent-context.sh claude` for your AI assistant
   - If exists: Add only NEW tech from current plan
   - Preserve manual additions between markers
   - Update recent changes (keep last 3)
   - Keep under 150 lines for token efficiency
   - Output to repository root

**Output**: data-model.md, /contracts/*, failing tests, quickstart.md, agent-specific file

## Phase 2: Task Planning Approach
*This section describes what the /tasks command will do - DO NOT execute during /plan*

**Task Generation Strategy**:
- Load `.specify/templates/tasks-template.md` as base
- Generate tasks from Phase 1 design docs (contracts, data model, quickstart)
- Each contract → contract test task [P]
- Each entity → model creation task [P] 
- Each user story → integration test task
- Implementation tasks to make tests pass

**Ordering Strategy**:
- TDD order: Tests before implementation 
- Dependency order: Models before services before UI
- Mark [P] for parallel execution (independent files)

**Estimated Output**: 25-30 numbered, ordered tasks in tasks.md

**IMPORTANT**: This phase is executed by the /tasks command, NOT by /plan

## Phase 3+: Future Implementation
*These phases are beyond the scope of the /plan command*

**Phase 3**: Task execution (/tasks command creates tasks.md)  
**Phase 4**: Implementation (execute tasks.md following constitutional principles)  
**Phase 5**: Validation (run tests, execute quickstart.md, performance validation)

## Complexity Tracking
*Fill ONLY if Constitution Check has violations that must be justified*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |


## Progress Tracking
*This checklist is updated during execution flow*

**Phase Status**:
- [x] Phase 0: Research complete (/plan command)
- [x] Phase 1: Design complete (/plan command)
- [x] Phase 2: Task planning complete (/plan command - describe approach only)
- [ ] Phase 3: Tasks generated (/tasks command)
- [ ] Phase 4: Implementation complete
- [ ] Phase 5: Validation passed

**Gate Status**:
- [x] Initial Constitution Check: PASS
- [x] Post-Design Constitution Check: PASS
- [x] All NEEDS CLARIFICATION resolved
- [x] Complexity deviations documented

**Artifacts Generated**:
- [x] research.md - Technology choices and rationale
- [x] data-model.md - Core entities and validation rules
- [x] contracts/cli_commands.yaml - CLI interface contracts
- [x] contracts/settings_file_api.yaml - Settings management API
- [x] quickstart.md - End-to-end validation scenarios
- [x] CLAUDE.md - Updated with CLI development context

---
*Based on Constitution v1.0.0 - See `/memory/constitution.md`*
