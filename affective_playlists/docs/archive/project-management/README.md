# Project Management

Operational planning documents and prioritization for affective_playlists development.

## Active Planning Files

### [fix_plan.md](fix_plan.md)
Priority-based task list for the project. Tracks:
- **Priority 1 (Critical)**: Core spec seeding and CI infrastructure
- **Priority 2 (High)**: Code hardening and platform constraints
- **Priority 3 (Medium)**: Extended specs and coverage growth
- **Completed**: Central archive of finished tasks with results

Use this to understand current priorities and what's being worked on.

### [spec_debt.md](spec_debt.md)
Inventory of behavior not yet codified in OpenSpec. Organized by tier:
- **Critical**: Must spec before major changes (Apple Music, enrichment orchestration, playlist manager)
- **High**: Seed this iteration (LLM client, playlist classifier, track metadata)
- **Medium**: Backlog items (cover art, audio tags, result utilities)
- **Deferred**: Archives and non-active behavior

Use this to understand specification coverage gaps.

### [NEXT_STEPS.md](NEXT_STEPS.md)
Immediate, near-term, and mid-term development directions (30-90 day horizon).

- **Immediate**: OpenSpec CLI setup and spec verification
- **Near-term**: Tier-1 spec debt, CI coverage improvements, non-macOS tests
- **Mid-term**: Package hardening, resilience testing, docs sync practices

## Related Documentation

- [OpenSpec Specs](../../openspec/specs/) — Authoritative specifications with implementation context
- [OpenSpec](../../openspec/) — Specification management
- [Architecture](../architecture/) — System design overview
