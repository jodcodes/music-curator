# Rule: Markdown File Organization & Location

## Overview

All markdown documentation files in the affective_playlists project must follow a consistent organization structure and be properly categorized by their purpose.

## Root-Level Markdown Files

Root-level `.md` files are reserved for project-level documentation and should be minimal. Only the following are allowed at the project root:

```
/
├── README.md                    # Project overview and getting started
├── QUICKSTART.md                # Quick start guide
├── LICENSE                      # License information
└── (other essential files)
```

### Allowed Root-Level Markdown Files

| File | Purpose | When to Update |
|------|---------|----------------|
| `README.md` | Project overview, features, requirements | When project scope changes |
| `QUICKSTART.md` | Quick start guide for users | When setup process changes |
| `SETUP_COMPLETE.md` | Setup verification and status | When major features are added |
| `SSL_CERTIFICATE_FIX.md` | SSL troubleshooting guide | When SSL issues are fixed |

## Docs Folder Organization

All detailed documentation must be organized in the `docs/` folder following the structure below:

```
docs/
├── rules/                              # All organizational and style rules
│   ├── DOCUMENTATION_STANDARDS.md     # Documentation format standards
│   ├── TEST_ORGANIZATION_RULE.md      # Test file organization rules
│   ├── MARKDOWN_FILE_ORGANIZATION.md  # This file
│   └── README.md                       # Rules index
├── requirements/                       # Functional & technical specifications
│   ├── SPEC_*.md                      # Functional specifications
│   ├── TECH_REQ_*.md                  # Technical requirements
│   └── README.md                       # Requirements index
├── summary/                            # Reports and summaries
│   ├── IMPLEMENTATION_REPORTS/
│   │   ├── *_REPORT.md
│   │   └── TEST_RESULTS_REPORT.md
│   ├── PROJECT_SUMMARIES/
│   │   ├── *_SUMMARY.md
│   │   └── STATUS_SUMMARY.md
│   ├── QUICK_REFERENCE/
│   │   ├── *_QUICK_REFERENCE.md
│   │   └── API_QUICK_REFERENCE.md
│   └── README.md                       # Summary index
└── OVERVIEW.md                         # Project architecture overview
```

## File Naming Conventions

### Specifications & Requirements

- **Functional Specifications**: `SPEC_<FEATURE>.md`
  - Example: `SPEC_METADATA_ENRICHMENT.md`
- **Technical Requirements**: `TECH_REQ_<FEATURE>.md`
  - Example: `TECH_REQ_SYSTEM_ARCHITECTURE.md`

### Reports

- **Implementation Reports**: `<FEATURE>_REPORT.md`
  - Example: `METADATA_ENRICHMENT_REPORT.md`
  - Location: `docs/summary/IMPLEMENTATION_REPORTS/`
- **Test Results**: `TEST_RESULTS_REPORT.md`
  - Location: `docs/summary/IMPLEMENTATION_REPORTS/`

### Summaries

- **Phase/Feature Summaries**: `<PHASE>_SUMMARY.md`
  - Example: `PHASE_1_SUMMARY.md`, `METADATA_ENRICHMENT_SUMMARY.md`
  - Location: `docs/summary/PROJECT_SUMMARIES/`
- **Status Summaries**: `STATUS_SUMMARY.md`
  - Location: `docs/summary/PROJECT_SUMMARIES/`

### Quick References

- **Quick References**: `<TOPIC>_QUICK_REFERENCE.md`
  - Example: `TESTING_QUICK_REFERENCE.md`, `API_QUICK_REFERENCE.md`
  - Location: `docs/summary/QUICK_REFERENCE/`

### Rules

- **Rules**: `<TOPIC>_RULE.md` or `<TOPIC>_STANDARDS.md`
  - Example: `TEST_ORGANIZATION_RULE.md`, `DOCUMENTATION_STANDARDS.md`
  - Location: `docs/rules/`

## Documentation Checklist

When creating new documentation:

- [ ] File is in the correct folder (`docs/` or root level only)
- [ ] File name follows the naming convention above
- [ ] File has a clear title (`# Title`)
- [ ] File includes an "Overview" section
- [ ] File includes relevant subsections
- [ ] For specifications: includes Acceptance Criteria section
- [ ] For rules: includes examples and best practices
- [ ] File includes version/date information in footer
- [ ] Links to related documentation are included
- [ ] File is referenced in appropriate index/README

## Creating New Documentation

### For New Features

1. Create functional spec: `docs/requirements/SPEC_<FEATURE>.md`
2. Create technical requirements: `docs/requirements/TECH_REQ_<FEATURE>.md`
3. After implementation: Create implementation report: `docs/summary/IMPLEMENTATION_REPORTS/<FEATURE>_REPORT.md`
4. Update `docs/summary/README.md` with link to report

### For Rules & Standards

1. Create in `docs/rules/<TOPIC>_RULE.md` or `docs/rules/<TOPIC>_STANDARDS.md`
2. Include clear examples and best practices
3. Update `docs/rules/README.md` with link

### For Project Summaries

1. Create in `docs/summary/PROJECT_SUMMARIES/<PHASE>_SUMMARY.md`
2. Include scope, progress, and next steps
3. Update `docs/summary/README.md` with link

## Index Files

Every folder in `docs/` must have a `README.md` index file:

### docs/README.md
```markdown
# Documentation Index

- [Rules](rules/README.md) - Project rules and standards
- [Requirements](requirements/README.md) - Specifications
- [Summaries](summary/README.md) - Reports and progress
```

### docs/rules/README.md
```markdown
# Rules & Standards

- [Documentation Standards](DOCUMENTATION_STANDARDS.md)
- [Test Organization Rule](TEST_ORGANIZATION_RULE.md)
- [Markdown File Organization](MARKDOWN_FILE_ORGANIZATION.md)
```

### docs/requirements/README.md
```markdown
# Specifications & Requirements

- [Functional Specifications](#functional-specifications)
- [Technical Requirements](#technical-requirements)

## Functional Specifications
- [Metadata Enrichment](SPEC_METADATA_ENRICHMENT.md)

## Technical Requirements
- [System Architecture](TECH_REQ_SYSTEM_ARCHITECTURE.md)
```

### docs/summary/README.md
```markdown
# Reports & Summaries

- [Implementation Reports](IMPLEMENTATION_REPORTS/)
- [Project Summaries](PROJECT_SUMMARIES/)
- [Quick References](QUICK_REFERENCE/)
```

## Markdown Content Standards

All documentation files must follow these standards:

### Header Structure
```markdown
# Main Title (H1)

## Overview (H2)
Brief description

## Section Name (H2)
Content...

### Subsection (H3)
More details...
```

### Required Sections

**For Specifications:**
1. Overview
2. Purpose
3. Functional Requirements
4. Technical Requirements
5. Acceptance Criteria
6. Related Documents

**For Rules:**
1. Overview
2. Directory Structure (if applicable)
3. Naming Convention
4. Rules (numbered)
5. Examples
6. Best Practices
7. Checklist (if applicable)

**For Reports:**
1. Overview
2. Executive Summary
3. Key Findings
4. Detailed Analysis
5. Conclusions/Recommendations
6. Appendices (if applicable)

### Footer Format
```markdown
---

**Last Updated**: January 3, 2026  
**Status**: Draft | In Progress | Approved | Deprecated  
**Author**: [Name]  
**Related**: [Link to related docs]
```

## Archiving Old Documentation

When documentation becomes outdated:

1. Move to `docs/archive/<YEAR>/<old_file>.md`
2. Add note at top: `> **ARCHIVED**: This document is no longer maintained. See [Link to current version].`
3. Update all links to point to current version

## Enforcement

- [ ] All `.md` files should be in `docs/` folder (except README.md, QUICKSTART.md at root)
- [ ] All files follow naming conventions
- [ ] All folders have `README.md` index files
- [ ] All specifications have implementation reports
- [ ] All rules are documented with examples
- [ ] Cross-references are maintained

## Examples

### Good Structure
```
docs/
├── rules/
│   ├── TEST_ORGANIZATION_RULE.md
│   └── README.md
├── requirements/
│   ├── SPEC_METADATA_ENRICHMENT.md
│   └── README.md
└── summary/
    ├── IMPLEMENTATION_REPORTS/
    │   └── METADATA_ENRICHMENT_REPORT.md
    └── README.md
```

### Bad Structure ❌
```
docs/
├── test_org_rule.md              # Wrong: lowercase, should be in rules/
├── metadata_enrichment_spec.md   # Wrong: should be SPEC_*.md
└── metadata_report.md            # Wrong: should be in summary/IMPLEMENTATION_REPORTS/
```

---

**Last Updated**: January 3, 2026  
**Status**: Active  
**Related**: [DOCUMENTATION_STANDARDS.md](DOCUMENTATION_STANDARDS.md), [TEST_ORGANIZATION_RULE.md](TEST_ORGANIZATION_RULE.md)
