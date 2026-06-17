# Fix Plan

## Priority 1 (Critical)
- [x] [spec-seed-metadata] Seed metadata domain into `openspec/specs/metadata/spec.md`
- [x] [spec-seed-temperament] Seed temperament domain into `openspec/specs/temperament/spec.md`
- [x] [spec-seed-playlists] Seed playlist organization domain into `openspec/specs/playlists/spec.md`
- [x] [ci-quality-gates] Enforce tests, type-check, lint, and formatting in CI
  → Status: Already implemented in `.github/workflows/ci.yml`
  → Checks: pytest, mypy, pylint, black, isort on push & PR

## Priority 2 (High)
- [x] [packaging-hardening] Reduce runtime import-path hacks and improve package execution model
  → Status: COMPLETE ✓
  → All 6 phases verified complete (analysis discovered code was already refactored)
  → 0 active sys.path.insert() instances in code
  → Updated: pyproject.toml (owner URLs), CODE_QUALITY_STANDARDS.md, architecture/README.md
  → Ready for: `pip install -e .` workflows
- [x] [platform-guarding] Keep macOS-only flows explicitly guarded with clear user guidance
  → Status: Verified complete in main.py
  → Guards: require_macos() for temperament, organization
  → User guidance: Clear error messages on non-macOS
- [x] [docs-drift] Keep docs and repository links aligned with current owner and workflows
  → Fixed: Removed duplicate "Source of Truth" entries in docs/README.md
  → Status: All links point to jodcodes/affective_playlists correcty

## Priority 3 (Medium)
- [x] [spec-seed-apple-music] Seed Apple Music integration behavior spec
  → Created: openspec/specs/apple_music/spec.md
  → Coverage: 12 MUST/SHALL scenarios with GIVEN-WHEN-THEN
  → Topics: Playlist enumeration, track extraction, AppleScript execution, org, error resilience
- [x] [spec-seed-llm-client] Seed LLM client behavior spec
  → Created: openspec/specs/llm_client/spec.md
  → Coverage: 11 MUST/SHALL scenarios
  → Topics: Provider abstraction, credentials, retry policy, timeout, mock fallback, resilience
- [ ] [coverage-growth] Raise coverage around enrichment edge-cases and fallback paths
  → Status: Test plan created (docs/project-management/COVERAGE_GROWTH_PLAN.md)
  → Target: 21 new tests covering critical fallback paths
  → Current tests: 169 passing
  → Focus areas: enrichment fallbacks, network failures, org safeguards, LLM resilience

## Completed
- [x] [brownfield-bootstrap] Create OpenSpec baseline files and migration scaffold
- [x] [test-platform-guards] Add platform guards and API validation tests
  → Implementation: main.py, tests/test_main_platform_guards.py, tests/test_main_cli_platform.py
  → Specs: Merged into openspec/specs/temperament/spec.md and openspec/specs/playlists/spec.md
  → Results: 12 new tests, all 169 tests passing
  → Status: ARCHIVED in openspec/changes/test-platform-guards/
- [x] [domain-guides-migration] Integrate domain-guides context into openspec/specs
  → Status: Completed alongside Priority 1 (specs already have implementation context)
  → Result: domain-guides files converted to redirects
  → Navigation: All docs point to openspec/specs/ as source of truth
