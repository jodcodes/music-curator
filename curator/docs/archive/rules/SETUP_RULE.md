# Setup & Development Rule

## Virtual Environment Activation

### Rule: Always Run activate.sh

**All development work must start with virtual environment activation.**

```bash
source activate.sh
```

This script:
- Creates the Python virtual environment if it doesn't exist
- Activates the virtual environment
- Sets PYTHONPATH correctly
- Checks and installs dependencies from requirements.txt
- Provides helpful command hints

### When to Run

1. **Starting a new terminal session** - Always run `source activate.sh`
2. **After pulling code changes** - Run to ensure dependencies are up to date
3. **Before running any Python code** - All commands require the venv
4. **After modifying requirements.txt** - Automatically updates dependencies

### What It Does

```bash
#!/bin/bash
# 1. Creates virtual environment (venv/) if needed
# 2. Activates the environment
# 3. Sets PYTHONPATH to include project root
# 4. Checks for required packages
# 5. Installs dependencies if missing
# 6. Shows available commands
```

### Never

- ❌ Do NOT run Python directly without activate.sh
- ❌ Do NOT skip dependency checks
- ❌ Do NOT manually activate venv without this script

### Verification

After running activate.sh, you should see:

```
✓ affective_playlists environment ready!

Available commands:
  python main.py                      # Interactive menu
  python main.py temperament          # AI-based Playlist Temperament Analysis
  python main.py enrich               # Metadata Filling and Enrichment
  python main.py organize             # Playlist Organization by Genre
```

Your terminal prompt should show `(venv)` prefix.

---

## Python Development Standards

### File Organization

- All Python source code goes in `src/`
- All tests go in `tests/`
- All data/config files go in `data/`

### Before Running Any Command

```bash
# Step 1: Activate environment
source activate.sh

# Step 2: Run your command
python main.py
# OR
python3 -m unittest tests.test_metadata_enrichment -v
# OR
python3 run_metadata_enrichment_test.py
```

### Adding New Dependencies

1. Add package to `requirements.txt`
2. Run `source activate.sh` to auto-install
3. Commit both the code and updated `requirements.txt`

### Troubleshooting

**Issue: "Python module not found" errors**
```bash
# Solution: Ensure venv is active
source activate.sh
echo $VIRTUAL_ENV  # Should show path to venv/
```

**Issue: "No module named 'src'" errors**
```bash
# Solution: PYTHONPATH may not be set
source activate.sh
echo $PYTHONPATH  # Should include project root
```

**Issue: Old packages still loaded**
```bash
# Solution: Recreate venv
rm -rf venv
source activate.sh  # Creates fresh venv
```

---

## CI/CD & Testing Standards

When running tests or CI/CD:

```bash
#!/bin/bash
source activate.sh
python3 -m unittest tests.test_metadata_enrichment -v
```

All automated scripts must source activate.sh first.
