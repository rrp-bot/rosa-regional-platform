# Changelog

All notable changes to the spec-to-pr orchestrator will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-05-05

### Added

- Initial implementation of spec-to-pr orchestrator
- Python package with CLI (run, status, resume, validate subcommands)
- Deterministic state machine for phase transitions (spec ingestion → implementation → deployment → E2E → debug → PR submission)
- Claude Agent SDK integration via Vertex AI with custom tool-use loop (Read, Edit, Write, Bash, Grep, Glob)
- Persona system with developer and qa-engineer personas loaded from `.claude/agents/` files
- Circuit breaker with heuristics: max attempts, repeated error fingerprints, no-progress detection
- File-backed session storage in `.spec-to-pr/sessions/{work_id}/` with resume capability
- Debug loop that accumulates context across attempts and injects into retry sessions
- Multi-repository support framework (RepoState tracking, coordinated PR creation)
- Containerfile based on UBI9 Python 3.11 with gh CLI, uv, git, make
- 59 passing tests across unit, integration (mocked), and CLI e2e layers

### Known Limitations

- Multi-repo tracking not yet populated during implementation phase (framework exists, needs agent integration)
- E2E test result parsing is basic (exit code only, no structured test output)
- JIRA integration is stubbed (accepts IDs but doesn't fetch content)
- Container-in-container builds not yet supported (ECR image push deferred)
