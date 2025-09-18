# cchooks Constitution

## Core Principles

### I. Library-First Development
Every feature starts as a standalone library with clear interfaces. Libraries must be self-contained, independently testable, and well-documented with type hints. Each component serves a clear purpose - no organizational-only libraries. The cchooks package provides foundational hook types that other tools can extend.

### II. CLI Interface Excellence
Every library function exposes functionality via CLI commands. Text-based protocol: stdin/args → stdout, errors → stderr. Support both JSON and human-readable formats for Claude Code integration. CLI tools must be intuitive for both programmatic and manual use.

### III. Test-First Development (NON-NEGOTIABLE)
TDD mandatory: Tests written → User approved → Tests fail → Then implement. Red-Green-Refactor cycle strictly enforced. All 9 hook types must have comprehensive test coverage including edge cases and real-world scenarios.

### IV. Hook Integration Testing
Focus areas requiring integration tests:
- New hook type contract tests
- Hook context validation changes
- Claude Code integration compatibility
- Cross-hook type interactions
- CLI tool end-to-end workflows

### V. Type Safety & Observability
Complete type hints required for all public APIs. Structured logging for hook execution. Text I/O ensures debuggability. Hook validation errors must provide clear field-specific messages. Support both simple (exit codes) and advanced (JSON) output modes.

### VI. Python Package Standards
Follow Python packaging best practices: src/ layout, pyproject.toml configuration, semantic versioning. Maintain backwards compatibility for hook interfaces. Breaking changes require migration guides and deprecation warnings.

### VII. Simplicity & Developer Experience
Start simple, apply YAGNI principles. Minimize external dependencies (currently zero runtime deps). Provide clear factory patterns (create_context()) for easy hook development. Documentation must be accessible to both library users and Claude Code hook developers.

## Development Workflow

### Code Quality Standards
- **Type checking**: pyright/mypy required for all code
- **Linting**: ruff for code style and error detection
- **Testing**: pytest with coverage reporting
- **Documentation**: Clear docstrings and usage examples

### CLI API Requirements
- **Command structure**: Follows UNIX conventions (short/long flags)
- **Input handling**: Support both file and stdin input
- **Output formatting**: JSON for programmatic, table/text for human
- **Error handling**: Meaningful exit codes and error messages
- **Configuration**: Support .claude/settings.json integration

### Hook Development Standards
- **Context validation**: Required fields checked at initialization
- **Output consistency**: Unified JSON structure across hook types
- **Error propagation**: Custom exception hierarchy
- **Performance**: Minimal overhead for Claude Code integration

## Quality Gates

### Pre-commit Requirements
- All tests pass (`make test`)
- Type checking passes (`make type-check`)
- Linting passes (`make lint`)
- Documentation builds successfully
- No security vulnerabilities in dependencies

### Release Criteria
- 100% test coverage for new features
- Integration tests pass with Claude Code
- CLI tools validated with real workflows
- Performance benchmarks meet requirements
- Migration guides for breaking changes

## Governance

Constitution supersedes all other development practices. Amendments require:
1. Documentation of rationale and impact
2. Stakeholder approval process
3. Migration plan for existing code
4. Template and tooling updates

All PRs must verify compliance with constitution principles. Complexity must be justified with clear benefits. Use project CLAUDE.md for runtime development guidance.

**Version**: 1.0.0 | **Ratified**: 2025-09-18 | **Last Amended**: 2025-09-18