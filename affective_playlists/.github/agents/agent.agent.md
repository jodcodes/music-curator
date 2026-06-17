# AI Agent Instructions

This repository follows a spec-driven brownfield workflow.

## Source of Truth
- Current source-of-truth specs live in `openspec/specs/`.
- Legacy specs in `docs/requirements/` are inputs for migration and reference.
- For new changes, do not edit `openspec/specs/` directly.

## Workflow
1. Read relevant specs in `openspec/specs/<domain>/spec.md`.
2. For new behavior, create a change package first.
3. Implement one task at a time with tests.
4. Run quality gates before commit.
5. Archive completed changes so delta specs merge into base specs.

## OpenSpec Commands
- `openspec list`
- `openspec propose <change-name>`
- `openspec verify`
- `openspec archive <change-name>`

## Build and Validation Commands
- `python -m pip install -e ".[dev]"`
- `pytest tests/ -v`
- `pytest tests/ -v --cov=src`
- `mypy src/`
- `pylint src/`
- `black --check src/ tests/`
- `isort --check-only src/ tests/`

## Coding Rules
- Follow `docs/rules/CODE_QUALITY_STANDARDS.md`.
- No placeholder implementations.
- No bare `except:` clauses.
- Use module logger, not print, in operational code.
- Add or update tests for behavior changes.

## Brownfield Guardrails
- Seed specs from real code behavior first.
- Track uncovered areas in `spec_debt.md`.
- Use `fix_plan.md` for prioritized execution.
- Keep changes small and reviewable.
