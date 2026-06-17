#!/usr/bin/env python
"""
Local deployment setup for affective_playlists with Celery + Redis.

This script sets up a complete development environment with:
- Flask web server (port 5000)
- Celery worker (background tasks)
- Redis (broker + result backend)
- SQLite database (default)

Requirements:
- Python 3.10+
- Redis server running locally or accessible
- Dependencies: pip install -r requirements.txt
"""

import subprocess
import sys
import time
import os
from pathlib import Path


def check_python():
    """Check Python version."""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 10):
        print(f"❌ Python 3.10+ required (found {version.major}.{version.minor})")
        sys.exit(1)
    print(f"✓ Python {version.major}.{version.minor}.{version.micro}")


def check_redis():
    """Check if Redis is available."""
    try:
        result = subprocess.run(
            ["redis-cli", "ping"],
            capture_output=True,
            timeout=2,
        )
        if result.returncode == 0:
            print("✓ Redis is running")
            return True
    except Exception:
        pass

    print("⚠ Redis not detected (required for Celery broker)")
    print("  Install: brew install redis (macOS) or apt-get install redis-server (Linux)")
    print("  Or run: docker run -d -p 6379:6379 redis:7")
    return False


def check_dependencies():
    """Check if required packages are installed."""
    required = {
        "flask": "Flask",
        "sqlalchemy": "SQLAlchemy",
        "celery": "Celery",
        "redis": "Redis Python client",
    }

    missing = []
    for module, name in required.items():
        try:
            __import__(module)
            print(f"✓ {name}")
        except ImportError:
            print(f"❌ {name} missing")
            missing.append(module)

    if missing:
        print(f"\n⚠ Install missing packages:")
        print(f"  pip install {' '.join(missing)}")
        return False

    return True


def show_menu():
    """Show deployment options."""
    print("\n" + "=" * 70)
    print("AFFECTIVE_PLAYLISTS - LOCAL DEPLOYMENT")
    print("=" * 70)
    print("\nSelect how to run:")
    print("  1) Flask web server ONLY (no background jobs)")
    print("  2) Flask + Celery worker (full stack)")
    print("  3) Database initialization ONLY")
    print("  4) Run tests")
    print("  5) Exit")

    choice = input("\nChoice [1-5]: ").strip()
    return choice


def start_flask():
    """Start Flask development server."""
    print("\n🚀 Starting Flask web server...")
    print("   URL: http://127.0.0.1:4000")
    print("   Press Ctrl+C to stop\n")

    os.environ["FLASK_APP"] = "src.web_server"
    os.environ["FLASK_ENV"] = "development"

    subprocess.run(
        [sys.executable, "-m", "src.web_server"],
        cwd=Path(__file__).parent,
    )


def start_celery():
    """Start Celery worker."""
    print("\n🎯 Starting Celery worker...")
    print("   Broker: redis://localhost:6379/0")
    print("   Queues: enrichment, temperament, organization, background")
    print("   Press Ctrl+C to stop\n")

    subprocess.run(
        [
            sys.executable,
            "-m",
            "celery",
            "-A",
            "src.celery_app",
            "worker",
            "-l",
            "info",
            "-c",
            "2",  # 2 concurrent workers
        ],
        cwd=Path(__file__).parent,
    )


def start_full_stack():
    """Start Flask + Celery (requires 2 terminals)."""
    print("\n" + "=" * 70)
    print("FULL STACK DEPLOYMENT")
    print("=" * 70)
    print("\nThis requires TWO terminal windows:")
    print("\n  Terminal 1 - Flask Web Server:")
    print("    $ python run_local.py")
    print("    Select option: 1 (Flask only)")
    print("\n  Terminal 2 - Celery Worker:")
    print("    $ python run_local.py")
    print("    Select option: 2 (Celery worker)")
    print("\nOR:")
    print("  Terminal 1 - Run: python -m src.web_server")
    print("  Terminal 2 - Run: celery -A src.celery_app worker -l info")
    print("  Terminal 3 (optional) - Run: celery -A src.celery_app events")
    print("\nThen:")
    print("  • Open browser: http://127.0.0.1:4000")
    print("  • Submit enrichment job")
    print("  • Watch progress in real-time")


def init_database():
    """Initialize database."""
    print("\n📊 Initializing database...")

    from src.db import init_db

    try:
        db_url = os.getenv("DATABASE_URL", "sqlite:///jobs.db")
        engine, SessionLocal = init_db(db_url)
        print(f"✓ Database initialized: {db_url}")
        print("  Tables created: jobs, job_results, job_events, job_statistics")
        return True
    except Exception as e:
        print(f"❌ Failed to initialize database: {e}")
        return False


def run_tests():
    """Run test suite."""
    print("\n🧪 Running test suite...")
    print("   (excluding Celery import tests which require Redis)\n")

    subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/",
            "-k",
            "not (test_celery_initialized or test_job_id_format_enrichment)",
            "-v",
            "--tb=short",
        ],
        cwd=Path(__file__).parent,
    )


def show_environment():
    """Show deployment environment info."""
    print("\n📋 DEPLOYMENT ENVIRONMENT")
    print("=" * 70)
    print(f"  Database:   {os.getenv('DATABASE_URL', 'sqlite:///jobs.db')}")
    print(f"  Celery Broker: {os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')}")
    print(f"  Worker Concurrency: {os.getenv('CELERY_WORKER_CONCURRENCY', '2')}")
    print(f"  Web Host: {os.getenv('WEB_HOST', '127.0.0.1')}")
    print(f"  Web Port: {os.getenv('WEB_PORT', '4000')}")
    print("\n  Environment variables can be set in .env file or shell:")
    print("    export DATABASE_URL=postgresql://user:pass@localhost/db")
    print("    export CELERY_BROKER_URL=redis://localhost:6379/0")
    print("=" * 70 + "\n")


def main():
    """Main deployment menu."""
    print("\n" + "=" * 70)
    print("AFFECTIVE PLAYLISTS - PRODUCTION-READY FEATURES")
    print("=" * 70)

    # Check environment
    print("\n📦 Environment Check:")
    check_python()
    redis_ok = check_redis()
    deps_ok = check_dependencies()

    if not deps_ok:
        print("\n💡 Install dependencies: pip install -r requirements.txt")
        return

    show_environment()

    # Initialize database
    db_init = input("Initialize database? [y/n] (default: y): ").strip().lower()
    if db_init != "n":
        init_database()

    # Menu loop
    while True:
        choice = show_menu()

        if choice == "1":
            start_flask()
        elif choice == "2":
            if not redis_ok:
                print("\n❌ Redis required for Celery")
                continue
            start_celery()
        elif choice == "3":
            init_database()
        elif choice == "4":
            run_tests()
        elif choice == "5":
            print("\n👋 Goodbye!")
            break
        else:
            print("Invalid choice")


if __name__ == "__main__":
    main()
