#!/usr/bin/env python3
"""
OpenSpec CLI - Specification-driven development workflow automation.

Commands:
  openspec list              - List all specs and changes
  openspec propose <name>    - Create new change package
  openspec verify            - Verify all specs against code
  openspec archive <name>    - Archive completed change to base spec
  openspec status            - Show spec/change status
"""

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class OpenSpecCLI:
    """OpenSpec CLI for managing specs and changes."""

    def __init__(self, root_dir: str = "."):
        """Initialize OpenSpec CLI.

        Args:
            root_dir: Root directory of openspec folder
        """
        self.root = Path(root_dir)
        self.specs_dir = self.root / "specs"
        self.changes_dir = self.root / "changes"

        # Ensure directories exist
        self.specs_dir.mkdir(exist_ok=True)
        self.changes_dir.mkdir(exist_ok=True)

    def list_specs(self) -> int:
        """List all base specifications."""
        print("\n📋 Base Specifications (openspec/specs/):\n")

        specs = sorted([d for d in self.specs_dir.iterdir() if d.is_dir()])
        if not specs:
            print("  (no specs found)")
            return 0

        for spec_dir in specs:
            spec_file = spec_dir / "spec.md"
            if spec_file.exists():
                size = spec_file.stat().st_size
                lines = len(spec_file.read_text(encoding="utf-8").splitlines())
                print(f"  ✓ {spec_dir.name}/")
                print(f"    └─ spec.md ({lines} lines, {size} bytes)")
            else:
                print(f"  ⚠ {spec_dir.name}/ (missing spec.md)")

        return 0

    def list_changes(self) -> int:
        """List all change packages."""
        print("\n🔧 Change Packages (openspec/changes/):\n")

        changes = sorted([d for d in self.changes_dir.iterdir() if d.is_dir()])
        if not changes:
            print("  (no changes in progress)")
            return 0

        for change_dir in changes:
            spec_file = change_dir / "spec.md"
            if spec_file.exists():
                size = spec_file.stat().st_size
                lines = len(spec_file.read_text(encoding="utf-8").splitlines())
                mtime = datetime.fromtimestamp(spec_file.stat().st_mtime)
                print(f"  ⧗ {change_dir.name}/")
                print(f"    ├─ spec.md ({lines} lines, {size} bytes)")
                print(f"    └─ modified: {mtime.strftime('%Y-%m-%d %H:%M')}")
            else:
                print(f"  ⚠ {change_dir.name}/ (missing spec.md - empty change)")

        return 0

    def list_all(self) -> int:
        """List all specs and changes."""
        self.list_specs()
        self.list_changes()
        print()
        return 0

    def propose_change(self, change_name: str) -> int:
        """Create a new change package.

        Args:
            change_name: Name of the change

        Returns:
            Exit code
        """
        change_dir = self.changes_dir / change_name

        if change_dir.exists():
            print(f"❌ Change '{change_name}' already exists")
            return 1

        try:
            change_dir.mkdir(parents=True, exist_ok=True)

            # Create spec template
            spec_file = change_dir / "spec.md"
            spec_file.write_text(
                f"""# {change_name} - Change Package

## Overview
Describe what this change implements.

## Scenarios
Add GIVEN/WHEN/THEN scenarios here.

## Implementation Notes
- [ ] Implement feature
- [ ] Add tests
- [ ] Update documentation
- [ ] Run quality checks
- [ ] Ready for archive

## Related Specs
- Link to related base specs here

---
**Created**: {datetime.now().isoformat()}
**Status**: In Progress
""",
                encoding="utf-8",
            )

            print(f"✓ Created change: openspec/changes/{change_name}/")
            print(f"  └─ spec.md (template)")
            return 0

        except Exception as e:
            print(f"❌ Failed to create change: {e}")
            return 1

    def verify_specs(self) -> int:
        """Verify all specs exist and are valid.

        Returns:
            Exit code (0 = all valid, 1 = errors found)
        """
        print("\n✔ Verifying specifications...\n")

        errors = 0
        total = 0

        # Check base specs
        for spec_dir in self.specs_dir.iterdir():
            if not spec_dir.is_dir():
                continue

            total += 1
            spec_file = spec_dir / "spec.md"

            if not spec_file.exists():
                print(f"  ❌ {spec_dir.name}/ - missing spec.md")
                errors += 1
                continue

            # Check for required sections
            content = spec_file.read_text(encoding="utf-8")
            required_sections = ["# ", "## Overview", "### Requirement"]

            missing = [s for s in required_sections if s not in content]
            if missing:
                print(f"  ⚠ {spec_dir.name}/ - missing sections: {missing}")
            else:
                req_count = content.count("### Requirement")
                print(f"  ✓ {spec_dir.name}/ ({req_count} requirements)")

        # Check changes
        for change_dir in self.changes_dir.iterdir():
            if not change_dir.is_dir():
                continue

            total += 1
            spec_file = change_dir / "spec.md"

            if not spec_file.exists():
                print(f"  ❌ {change_dir.name}/ - missing spec.md")
                errors += 1
                continue

            print(f"  ⧗ {change_dir.name}/ (in progress)")

        print(f"\n📊 Total: {total} specs, Errors: {errors}\n")
        return 1 if errors > 0 else 0

    def archive_change(self, change_name: str) -> int:
        """Archive a change package to base specs.

        Args:
            change_name: Name of the change to archive

        Returns:
            Exit code
        """
        change_dir = self.changes_dir / change_name
        spec_file = change_dir / "spec.md"

        if not change_dir.exists():
            print(f"❌ Change '{change_name}' not found")
            return 1

        if not spec_file.exists():
            print(f"❌ Change '{change_name}' has no spec.md")
            return 1

        # Create destination
        base_spec_dir = self.specs_dir / change_name
        base_spec_file = base_spec_dir / "spec.md"

        try:
            # If base spec exists, backup old version
            if base_spec_dir.exists():
                backup_dir = base_spec_dir / ".backup"
                backup_dir.mkdir(exist_ok=True)
                old_spec = backup_dir / f"spec.md.backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
                if base_spec_file.exists():
                    content = base_spec_file.read_text(encoding="utf-8")
                    old_spec.write_text(content, encoding="utf-8")
                    print(f"  📦 Backed up existing spec to {old_spec.relative_to(self.root)}")
            else:
                base_spec_dir.mkdir(parents=True, exist_ok=True)

            # Copy spec to base
            content = spec_file.read_text(encoding="utf-8")
            base_spec_file.write_text(content, encoding="utf-8")

            # Remove change directory
            shutil.rmtree(change_dir)

            print(f"✓ Archived change: {change_name}")
            print(f"  └─ openspec/specs/{change_name}/spec.md")
            print(f"\n  💡 Change merged into base specification.")
            return 0

        except Exception as e:
            print(f"❌ Failed to archive change: {e}")
            return 1

    def status(self) -> int:
        """Show spec/change status summary.

        Returns:
            Exit code
        """
        specs_count = len([d for d in self.specs_dir.iterdir() if d.is_dir()])
        changes_count = len([d for d in self.changes_dir.iterdir() if d.is_dir()])

        print(f"\n📊 OpenSpec Status\n")
        print(f"  Base Specifications:  {specs_count}")
        print(f"  In-Progress Changes:  {changes_count}")
        print(f"  Root Directory:       {self.root.resolve()}\n")

        if changes_count > 0:
            print("  Pending changes to archive:")
            for change_dir in sorted(self.changes_dir.iterdir()):
                if change_dir.is_dir():
                    print(f"    • {change_dir.name}")
            print()

        return 0


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="OpenSpec CLI - Specification-driven development workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  openspec list              List all specs and changes
  openspec propose mychange  Create new change package
  openspec verify            Verify all specs
  openspec archive mychange  Archive change to base spec
  openspec status            Show current status
        """,
    )

    parser.add_argument(
        "command",
        nargs="?",
        choices=["list", "propose", "verify", "archive", "status"],
        default="list",
        help="Command to run",
    )

    parser.add_argument(
        "arg",
        nargs="?",
        help="Argument for command (e.g., change name for propose/archive)",
    )

    parser.add_argument(
        "--root",
        default=".",
        help="OpenSpec root directory (default: current directory)",
    )

    args = parser.parse_args()

    cli = OpenSpecCLI(args.root)

    if args.command == "list":
        return cli.list_all()
    elif args.command == "propose":
        if not args.arg:
            print("❌ propose requires a change name")
            return 1
        return cli.propose_change(args.arg)
    elif args.command == "verify":
        return cli.verify_specs()
    elif args.command == "archive":
        if not args.arg:
            print("❌ archive requires a change name")
            return 1
        return cli.archive_change(args.arg)
    elif args.command == "status":
        return cli.status()
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
