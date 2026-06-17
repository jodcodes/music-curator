# Legacy Specifications (Reference Only)

This folder contains legacy spec documents from the brownfield migration phase. These files are **reference and traceability only** — they document the historical context and original requirements gathering.

## Why These Exist

The affective_playlists project uses a spec-driven brownfield workflow (see [AGENTS.md](../../AGENTS.md)). During the migration phase, existing documentation was seeded into the system. Legacy specs here served as inputs for creating the authoritative OpenSpec specifications.

## Current Source of Truth

**All authoritative specifications now live in [openspec/specs/](../../openspec/specs/):**
- [openspec/specs/metadata/spec.md](../../openspec/specs/metadata/spec.md) — Metadata enrichment behavior
- [openspec/specs/playlists/spec.md](../../openspec/specs/playlists/spec.md) — Playlist organization behavior
- [openspec/specs/temperament/spec.md](../../openspec/specs/temperament/spec.md) — Temperament analysis behavior

## Files in This Folder

### Functional Specifications

- **SPEC_METADATA_ENRICHMENT.md** — Original metadata enrichment specification  
  Legacy source for [openspec/specs/metadata/spec.md](../../openspec/specs/metadata/spec.md)

- **SPEC_PLAYLIST_ORGANIZATION.md** — Original playlist organization specification  
  Legacy source for [openspec/specs/playlists/spec.md](../../openspec/specs/playlists/spec.md)

- **SPEC_TEMPERAMENT_ANALYZER.md** — Original temperament analysis specification  
  Legacy source for [openspec/specs/temperament/spec.md](../../openspec/specs/temperament/spec.md)

### Technical Specifications

- **TECH_REQ_SYSTEM_ARCHITECTURE.md** — Original system architecture documentation  
  Referenced by [docs/architecture/README.md](../architecture/README.md)

## How to Use These Files

1. **For understanding current behavior**: Use OpenSpec specs ([openspec/specs/](../../openspec/specs/)) and archived-reports instead.
2. **For historical traceability**: These files show the original requirements and context from the brownfield phase.
3. **For references in code review**: Always link to OpenSpec specs, not legacy specs.

## Migration Status

- ✅ Metadata enrichment specification migrated to OpenSpec
- ✅ Playlist organization specification migrated to OpenSpec
- ✅ Temperament analysis specification migrated to OpenSpec
- ✅ System architecture documented in [docs/architecture/](../architecture/)
- ✅ Domain guides created with OpenSpec references

## Related Documentation

- [OpenSpec Specs](../../openspec/specs/) — Current authoritative specifications
- [Architecture Guide](../architecture/) — Current system design
- [OpenSpec](../../openspec/) — Source of truth for all specs

This folder contains all functional specifications and technical requirements for the affective_playlists system.

## Functional Specifications

Complete specifications for each feature module:

- **SPEC_TEMPERAMENT_ANALYZER.md** - AI-based emotion classification (4tempers)
  - Input: Playlists
  - Output: Emotion classifications (Woe, Frolic, Dread, Malice)
  - Key requirement: OpenAI API integration

- **SPEC_METADATA_ENRICHMENT.md** - Automatic metadata filling (metad_enr)
  - Input: Playlists or folders
  - Output: Enriched metadata (BPM, Genre, Year)
  - Key requirement: Multi-source database integration

- **SPEC_PLAYLIST_ORGANIZATION.md** - Genre-based organization (plsort)
  - Input: Playlists
  - Output: Genre-classified and organized playlists
  - Key requirement: Whitelist support and dry-run mode

## Technical Requirements

System-wide technical specifications:

- **TECH_REQ_SYSTEM_ARCHITECTURE.md** - Complete system design
  - Core components and modules
  - API integration points
  - Data models and schemas
  - Performance requirements
  - Security considerations
  - CI/CD and testing strategy

## Organization

Each specification includes:

1. **Overview** - Brief description
2. **Purpose** - Problem solved
3. **Functional Requirements** - What must be done
4. **Technical Requirements** - How it's implemented
5. **Dependencies** - External systems and libraries
6. **Data Models/Schemas** - Data structures with examples
7. **Acceptance Criteria** - Definition of done
8. **Constraints & Compatibility** - Limits and versions
9. **Test Strategy** - How to verify implementation
10. **Performance Requirements** - Speed and scale targets
11. **Security & Privacy** - Data protection policies
12. **Error Handling** - Failure scenarios
13. **State Management** - Persistence and recovery

## How to Read These Documents

### For Developers
Start with the relevant SPEC_*.md for your feature, then reference TECH_REQ_SYSTEM_ARCHITECTURE.md for system-wide concerns.

### For QA/Testing
Review the Acceptance Criteria and Test Strategy sections to understand what to validate.

### For Project Managers
The Constraints & Compatibility and Performance Requirements sections show scope and limits.

### For Architects
TECH_REQ_SYSTEM_ARCHITECTURE.md provides the complete system design.

## Updating Requirements

When requirements change:

1. Update the relevant spec file
2. Include date and version number
3. Note what changed (use git diffs)
4. Update related files (e.g., if SPEC changes, update TECH_REQ)
5. Commit with clear message: "Req: Updated SPEC_X feature requirements"

## Non-Functional Requirements

All implementations must meet these non-functional requirements:

1. **Code Quality**
   - All code must follow Python standards in `docs/rules/CODE_QUALITY_STANDARDS.md`
   - Type hints required on all function signatures
   - Comprehensive docstrings required (Google style)
   - No bare exception handling

2. **Logging**
   - Use centralized logger from `src/logger.py`
   - No `print()` statements in operational code
   - Appropriate log levels (DEBUG, INFO, WARNING, ERROR)

3. **Testing**
   - Unit tests required for all public functions
   - Minimum 70% code coverage target
   - Integration tests for critical workflows

4. **Performance**
   - API requests must timeout within 30 seconds
   - Playlist operations must complete within 5 minutes
   - No loading entire playlists into memory without streaming large data

5. **Error Handling**
   - Specific exception types, never bare `except:`
   - Meaningful error messages with context
   - Graceful degradation where possible

## Cross-References

- Implementation details: See `src/` folder
- Test coverage: See `tests/` folder
- Reports and summaries: See `docs/summary/` folder
- Architecture overview: See `docs/OVERVIEW.md`
- Code quality standards: See `docs/rules/CODE_QUALITY_STANDARDS.md`
- Development roadmap: See `../../NEXT_STEPS.md`

---

**Last Updated**: January 4, 2026  
**Status**: All specifications complete and tested
