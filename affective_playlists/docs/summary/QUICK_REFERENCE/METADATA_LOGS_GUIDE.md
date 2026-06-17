# Metadata Enrichment Logs Guide

When you run metadata enrichment through `python main.py` or `python -m src.metadata_fill`, detailed logs are automatically written to:

```
data/logs/metadata_enrichment.log
```

## Viewing Logs

### Option 1: View Live Logs (macOS/Linux)
```bash
# Follow logs in real-time while enrichment is running
tail -f data/logs/metadata_enrichment.log

# In another terminal, run enrichment:
python main.py
# Select: 2. Metadata Enrichment
```

### Option 2: View Complete Log After Enrichment
```bash
# Open the log file
cat data/logs/metadata_enrichment.log

# Or view last 50 lines
tail -50 data/logs/metadata_enrichment.log

# Or use a text editor
vim data/logs/metadata_enrichment.log
nano data/logs/metadata_enrichment.log
```

### Option 3: Search Logs for Specific Tracks
```bash
# Find all mentions of a track
grep "Artist Name" data/logs/metadata_enrichment.log

# Find all enriched tracks
grep "✓ ENRICHED" data/logs/metadata_enrichment.log

# Find all failed enrichments
grep "✗ FAILED" data/logs/metadata_enrichment.log

# Find all skipped tracks
grep "Skipped" data/logs/metadata_enrichment.log

# Count enriched tracks
grep "✓ ENRICHED" data/logs/metadata_enrichment.log | wc -l
```

## Log Format

### Example Success Entry
```
2026-01-03 15:23:45 - metadata_fill - INFO -   ✓ ENRICHED: Artist Name - Song Title (year=2020, bpm=120, genre=Rock)
```

### Example Skip Entry
```
2026-01-03 15:23:46 - metadata_fill - DEBUG -   └─ Skipped: No enrichment data found
```

### Example Failure Entry
```
2026-01-03 15:23:47 - metadata_fill - WARNING -   ✗ FAILED to write tags: Artist Name - Song Title
```

## Log Levels

The logs contain different levels of detail:

### INFO Level (Always Shown)
- ✓ Successfully enriched tracks with fields added
- ✗ Failed enrichment operations
- Summary statistics at the end
- Operation start/end markers

### DEBUG Level (Detailed)
- Each track being processed: `[1/34] Processing: Artist - Title`
- Why tracks were skipped
- Current metadata values before enrichment
- Database query results
- Fields being written
- File write operations

## Enabling Debug Logging

Debug logs are automatically enabled when you run through `python main.py` (the interactive menu).

To also see debug logs on console when running directly:
```bash
python -m src.metadata_fill --playlist "Playlist Name" -v
```

The `-v` or `--verbose` flag shows DEBUG level logs on screen and in the file.

## Log Rotation

The logs are automatically rotated:
- **Max file size**: 10 MB
- **Backup count**: 5 previous logs kept
- **Naming**: `metadata_enrichment.log`, `metadata_enrichment.log.1`, `metadata_enrichment.log.2`, etc.

Old logs are archived when the file reaches 10MB.

## What the Logs Tell You

### Processing Status
```
Starting metadata enrichment for 34 tracks
[1/34] Processing: Taylor Swift - Love Story
```

### Enrichment Results for Each Track
```
  └─ Current tags: BPM=None, Year=None, Genre=None
  └─ Querying databases for: Taylor Swift - Love Story
  └─ Found 3 metadata entries from databases
  └─ Writing 3 fields: year=2008, bpm=116, genre=Pop
  ✓ ENRICHED: Taylor Swift - Love Story (year=2008, bpm=116, genre=Pop)
```

### Skip Reasons
```
  └─ Skipped: No enrichment data found
  └─ Skipped: File not downloaded or not found
  └─ Skipped: Cloud status is 'ineligible' (not uploaded/matched)
  └─ Skipped: Incomplete track info (missing artist or title)
```

### Final Summary
```
================================================================================
Metadata Enrichment Complete
================================================================================
Total Processed: 34 tracks
Successfully Enriched: 8 tracks
Skipped: 26 tracks
Log file: data/logs/metadata_enrichment.log
================================================================================
```

## Troubleshooting with Logs

### Issue: "Enriched: 0 items"

Check the logs for:
```bash
grep "✓ ENRICHED" data/logs/metadata_enrichment.log
```

If no results, tracks may be:
- Already have complete metadata (check "Current tags" lines)
- Not found in databases (check "Found 0 metadata entries" lines)
- Failing to write (check "✗ FAILED" lines)

### Issue: "Why wasn't track X enriched?"

Search for your track:
```bash
grep "Track X" data/logs/metadata_enrichment.log
```

Look for the reason in the lines following the track name.

### Issue: "What fields were written?"

Check the enrichment line:
```bash
grep "✓ ENRICHED.*Your Song" data/logs/metadata_enrichment.log
```

The fields are shown in parentheses: `(year=2020, bpm=120, genre=Rock)`

## Log File Location

```
affective_playlists/
├── data/
│   └── logs/
│       ├── metadata_enrichment.log      (Current log)
│       ├── metadata_enrichment.log.1    (Previous logs)
│       └── ...
├── main.py
└── ...
```

## Archiving Old Logs

To save logs for later analysis:
```bash
# Create archive
cp data/logs/metadata_enrichment.log data/logs/metadata_enrichment_backup_$(date +%Y%m%d).log

# Or compress
gzip data/logs/metadata_enrichment.log
```

## Related Documentation

- **Testing Guide**: `docs/summary/QUICK_REFERENCE/TESTING_QUICK_REFERENCE.md`
- **Metadata Spec**: `docs/requirements/SPEC_METADATA_ENRICHMENT.md`
- **Full Report**: `docs/summary/IMPLEMENTATION_REPORTS/METADATA_ENRICHMENT_REPORT.md`
