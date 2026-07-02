#!/usr/bin/env python3
"""
plMetaTemp Integration Test Suite

Tests that the refactored unified architecture works correctly.
Verifies:
- Shared modules can be imported
- Module functionality works
- Backwards compatibility is maintained
- Directory structure is correct
"""

import os
import sys
from pathlib import Path

# Colors for output
GREEN = "\033[0;32m"
RED = "\033[0;31m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
NC = "\033[0m"  # No Color


def print_section(title):
    """Print a section header."""
    print(f"\n{BLUE}{'='*70}")
    print(f"{BLUE}➜ {title}{NC}")
    print(f"{BLUE}{'='*70}{NC}\n")


def print_check_result(name, passed, details=""):
    """Print test result (helper function, not a test)."""
    status = f"{GREEN}✓ PASS{NC}" if passed else f"{RED}✗ FAIL{NC}"
    print(f"  {status} - {name}")
    if details:
        print(f"         {details}")


def check_directory_structure():
    """Test that all required directories exist."""
    print_section("Testing Directory Structure")

    required_dirs = [
        ("shared", "Shared modules"),
        ("4tempers", "4tempers subrepo"),
        ("metad_enr", "metad_enr subrepo"),
        ("plsort", "plsort subrepo"),
        ("shared", "Shared modules"),
    ]

    all_passed = True
    for dir_name, description in required_dirs:
        dir_path = PROJECT_ROOT / dir_name
        exists = dir_path.exists() and dir_path.is_dir()
        print_check_result(description, exists, f"{dir_path}")
        all_passed = all_passed and exists

    assert all_passed
    return all_passed


def check_shared_files():
    """Test that shared module files exist."""
    print_section("Testing Shared Module Files")

    required_files = [
        ("shared/__init__.py", "Shared package init"),
        ("shared/apple_music.py", "Apple Music interface"),
        ("shared/normalizer.py", "Text normalizer"),
        ("shared/logger.py", "Logger utilities"),
    ]

    all_passed = True
    for file_path, description in required_files:
        full_path = PROJECT_ROOT / file_path
        exists = full_path.exists() and full_path.is_file()
        print_check_result(description, exists, file_path)
        all_passed = all_passed and exists

    assert all_passed
    return all_passed


def check_root_files():
    """Test that root config files exist."""
    print_section("Testing Root Configuration Files")

    required_files = [
        ("main.py", "Main CLI entry point"),
        ("setup.sh", "Setup script"),
        ("activate.sh", "Activation script"),
        ("requirements.txt", "Dependencies"),
        (".env.example", "Environment template"),
        ("README.md", "Project README"),
        ("QUICKSTART.md", "Quick start guide"),
        ("REFACTORING_GUIDE.md", "Refactoring guide"),
        ("MIGRATION_GUIDE.md", "Migration guide"),
        ("__init__.py", "Package init"),
    ]

    all_passed = True
    for file_path, description in required_files:
        full_path = PROJECT_ROOT / file_path
        exists = full_path.exists() and full_path.is_file()
        print_check_result(description, exists, file_path)
        all_passed = all_passed and exists

    assert all_passed
    return all_passed


def check_shared_imports():
    """Test that shared modules can be imported."""
    print_section("Testing Shared Module Imports")

    all_passed = True

    # Test importing from shared package
    try:
        from shared import AppleMusicInterface, TextNormalizer, setup_logger

        print_check_result("Import from shared package", True)
    except ImportError as e:
        print_check_result("Import from shared package", False, str(e))
        all_passed = False

    # Test importing AppleMusicInterface
    try:
        from shared.apple_music import AppleMusicInterface

        print_check_result("Import AppleMusicInterface", True)
    except ImportError as e:
        print_check_result("Import AppleMusicInterface", False, str(e))
        all_passed = False

    # Test importing TextNormalizer
    try:
        from shared.normalizer import TextNormalizer

        print_check_result("Import TextNormalizer", True)
    except ImportError as e:
        print_check_result("Import TextNormalizer", False, str(e))
        all_passed = False

    # Test importing setup_logger
    try:
        from shared.logger import setup_logger

        print_check_result("Import setup_logger", True)
    except ImportError as e:
        print_check_result("Import setup_logger", False, str(e))
        all_passed = False

    assert all_passed
    return all_passed


def check_shared_functionality():
    """Test that shared modules work correctly."""
    print_section("Testing Shared Module Functionality")

    all_passed = True

    # Test TextNormalizer
    try:
        from shared.normalizer import TextNormalizer

        normalizer = TextNormalizer()
        result = normalizer.normalize("  HELLO & World!  ")
        passed = result == "hello and world"
        print_check_result("TextNormalizer.normalize()", passed, f"Got: '{result}'")
        all_passed = all_passed and passed
    except Exception as e:
        print_check_result("TextNormalizer.normalize()", False, str(e))
        all_passed = False

    # Test TextNormalizer list normalization
    try:
        from shared.normalizer import TextNormalizer

        normalizer = TextNormalizer()
        result = normalizer.normalize_list(["  text1  ", "  text2  ", "  text1  "])
        passed = result == ["text1", "text2"] and len(result) == 2
        print_check_result("TextNormalizer.normalize_list()", passed, f"Got: {result}")
        all_passed = all_passed and passed
    except Exception as e:
        print_check_result("TextNormalizer.normalize_list()", False, str(e))
        all_passed = False

    # Test logger setup
    try:
        from shared.logger import setup_logger

        logger = setup_logger("test")
        logger.info("Test message")
        print_check_result("setup_logger()", True)
    except Exception as e:
        print_check_result("setup_logger()", False, str(e))
        all_passed = False

    # Test AppleMusicInterface instantiation
    try:
        import os

        from shared.apple_music import AppleMusicInterface

        shared_scripts = os.path.join(os.path.dirname(__file__), "..", "shared", "scripts")
        ami = AppleMusicInterface(scripts_dir=shared_scripts)
        print_check_result("AppleMusicInterface instantiation", True)
    except Exception as e:
        print_check_result("AppleMusicInterface instantiation", False, str(e))
        all_passed = False

    assert all_passed
    return all_passed


def check_backwards_compatibility():
    """Test that old imports still work."""
    print_section("Testing Backwards Compatibility")

    all_passed = True

    # Test src.apple_music import (now in src/)
    try:
        from apple_music import AppleMusicInterface

        print_check_result("src.apple_music import", True)
    except ImportError as e:
        print_check_result("src.apple_music import", False, str(e))
        all_passed = False

    # Test src.normalizer import (now in src/)
    try:
        from normalizer import TextNormalizer

        print_check_result("src.normalizer import", True)
    except ImportError as e:
        print_check_result("src.normalizer import", False, str(e))
        all_passed = False

    assert all_passed
    return all_passed


def check_syntax():
    """Test Python syntax of key files."""
    print_section("Testing Python Syntax")

    import py_compile

    files_to_check = [
        "main.py",
        "src/__init__.py",
        "src/apple_music.py",
        "src/normalizer.py",
        "src/logger.py",
    ]

    all_passed = True
    for file_path in files_to_check:
        try:
            full_path = PROJECT_ROOT / file_path
            if full_path.exists():
                py_compile.compile(str(full_path), doraise=True)
                print_check_result(f"Syntax check: {file_path}", True)
            else:
                print_check_result(f"Syntax check: {file_path}", False, "File not found")
                all_passed = False
        except py_compile.PyCompileError as e:
            print_check_result(f"Syntax check: {file_path}", False, str(e))
            all_passed = False

    assert all_passed
    return all_passed


def check_main_cli():
    """Test main.py CLI."""
    print_section("Testing Main CLI")

    all_passed = True

    # Test --help
    try:
        import subprocess

        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "main.py"), "--help"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        passed = result.returncode == 0
        print_check_result("main.py --help", passed, f"Return code: {result.returncode}")
        all_passed = all_passed and passed
    except Exception as e:
        print_check_result("main.py --help", False, str(e))
        all_passed = False

    # Test --list
    try:
        import subprocess

        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "main.py"), "--list"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        passed = result.returncode == 0 and "4tempers" in result.stdout
        print_check_result("main.py --list", passed, f"Return code: {result.returncode}")
        all_passed = all_passed and passed
    except Exception as e:
        print_check_result("main.py --list", False, str(e))
        all_passed = False

    assert all_passed
    return all_passed


def main():
    """Run all tests."""
    print(f"{BLUE}")
    print("╔═════════════════════════════════════════════════════════════════════╗")
    print("║         plMetaTemp - Integration Test Suite                         ║")
    print("║  Verifying unified architecture and shared modules                  ║")
    print("╚═════════════════════════════════════════════════════════════════════╝")
    print(f"{NC}")

    results = {
        "Directory Structure": check_directory_structure(),
        "Shared Module Files": check_shared_files(),
        "Root Configuration Files": check_root_files(),
        "Shared Module Imports": check_shared_imports(),
        "Shared Module Functionality": check_shared_functionality(),
        "Backwards Compatibility": check_backwards_compatibility(),
        "Python Syntax": check_syntax(),
        "Main CLI": check_main_cli(),
    }

    # Print summary
    print_section("Test Summary")

    total = len(results)
    passed = sum(1 for v in results.values() if v)
    failed = total - passed

    for test_name, result in results.items():
        status = f"{GREEN}PASS{NC}" if result else f"{RED}FAIL{NC}"
        print(f"  {status} - {test_name}")

    print()
    print(f"{BLUE}{'='*70}{NC}")
    print(f"  Total: {total} test suites")
    print(f"  {GREEN}Passed: {passed}{NC}")
    if failed > 0:
        print(f"  {RED}Failed: {failed}{NC}")
    print(f"{BLUE}{'='*70}{NC}\n")

    if failed == 0:
        print(f"{GREEN}✓ All tests passed! The unified architecture is working correctly.{NC}\n")
        return 0
    else:
        print(f"{RED}✗ Some tests failed. Please review the errors above.{NC}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
