# Quick Reference Guides

This folder contains quick lookup guides, checklists, and command references for common tasks.

## References Included

### SSL_CERTIFICATE_FIX_QUICK_REFERENCE.md
Quick troubleshooting guide for SSL certificate errors:
- Automatic fix script
- Manual fix options
- Verification procedures
- Troubleshooting tips

**When to use**: You see SSL certificate errors during metadata enrichment

### TESTING_QUICK_REFERENCE.md
Quick guide for running tests:
- Test execution commands
- Test structure overview
- Sample test outputs
- Live demo procedures
- Troubleshooting

**When to use**: Running tests or understanding test coverage

### SETUP_QUICK_REFERENCE.md (Planned)
Quick reference for system setup:
- Installation steps
- Configuration checklist
- Environment verification
- Common setup issues

**When to use**: Setting up the project for the first time

### DATABASE_SOURCES_GUIDE.md (if exists)
Guide to database sources and metadata:
- Each database source explained
- Which metadata each provides
- Coverage and reliability
- API requirements

**When to use**: Understanding metadata enrichment sources

### METADATA_LOGS_GUIDE.md (if exists)
Guide to viewing and interpreting logs:
- Log file locations
- Log format explanation
- Common log messages
- How to search logs

**When to use**: Debugging or monitoring enrichment operations

## Quick Reference Standards

All quick reference guides follow these standards:

### Content Structure
1. **Quick Summary** - What this guide covers
2. **When to Use** - Scenario for using this guide
3. **Quick Start** - Fastest way to accomplish task
4. **Detailed Steps** - Full procedures with options
5. **Troubleshooting** - Common issues and solutions
6. **Tips & Tricks** - Pro tips for efficiency
7. **Cross-references** - Links to related documents

### Formatting
- Minimal prose, maximum actionable content
- Code examples for every command
- Clear before/after comparisons
- Checkboxes for procedures

## Using These References

### For Developers
- Use SETUP_QUICK_REFERENCE.md for initial setup
- Use TESTING_QUICK_REFERENCE.md for test commands
- Use SSL_CERTIFICATE_FIX_QUICK_REFERENCE.md for SSL issues
- Use DATABASE_SOURCES_GUIDE.md to understand metadata

### For QA/Testing
- Use TESTING_QUICK_REFERENCE.md for test execution
- Use METADATA_LOGS_GUIDE.md for result interpretation
- Use DATABASE_SOURCES_GUIDE.md for coverage understanding

### For Operations/DevOps
- Use SETUP_QUICK_REFERENCE.md for deployment
- Use METADATA_LOGS_GUIDE.md for monitoring
- Use SSL_CERTIFICATE_FIX_QUICK_REFERENCE.md for troubleshooting

### For New Team Members
- Start with SETUP_QUICK_REFERENCE.md
- Then read TESTING_QUICK_REFERENCE.md
- Reference others as needed

## Creating New Quick References

When creating a quick reference guide:

1. **File naming**: `<TOPIC>_QUICK_REFERENCE.md`
   - Example: `TESTING_QUICK_REFERENCE.md`

2. **Location**: Place in `QUICK_REFERENCE/` folder

3. **Content requirements**:
   - Header with title and description
   - "When to Use" section
   - "Quick Start" section (fastest path)
   - "Detailed Steps" for each procedure
   - "Troubleshooting" section
   - Code examples for every command
   - Links to detailed documentation

4. **Style guidelines**:
   - Use action verbs (Run, Execute, Check, Verify)
   - Show command output when helpful
   - Include both simple and advanced options
   - Use bullets for lists, numbered steps for procedures

5. **Update this README**: Add brief description of new reference

6. **Cross-reference**: Link to detailed docs (specs, architecture)

## Quick Reference Topics

### System Setup & Configuration
- `SETUP_QUICK_REFERENCE.md` - Getting started
- `SSL_CERTIFICATE_FIX_QUICK_REFERENCE.md` - SSL troubleshooting

### Development & Testing
- `TESTING_QUICK_REFERENCE.md` - Running tests
- `DATABASE_SOURCES_GUIDE.md` - Data sources

### Operations & Monitoring
- `METADATA_LOGS_GUIDE.md` - Log files and monitoring

## Cross-References

- **Implementation Reports**: See `IMPLEMENTATION_REPORTS/` for detailed analysis
- **Project Summaries**: See `PROJECT_SUMMARIES/` for status information
- **Requirements**: See `docs/requirements/` for specifications
- **Architecture**: See `SRC_ARCHITECTURE_GUIDE.md` for technical details

---

**Last Updated**: January 3, 2026  
**Total References**: 2 (SSL_FIX, TESTING)  
**Planned**: 3 (SETUP, DATABASE_SOURCES, METADATA_LOGS)  
**Status**: Quick reference framework complete
