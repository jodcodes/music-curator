# Metadata Database Sources Guide

The metadata enrichment system queries multiple music databases for track information. This guide explains each source, what they provide, and how to enable them.

## Database Sources (Priority Order)

### 1. 🎵 MusicBrainz
**Type**: Free, no authentication required  
**URL**: https://musicbrainz.org  
**Provides**: Genre, Release Year, Track ID  
**Confidence**: High (70-90%)  
**Status**: ✓ Always active (no setup needed)

**What it is**: Community-driven open music encyclopedia with detailed metadata for millions of recordings.

**Data quality**: Very good for mainstream releases, less complete for obscure/local tracks.

### 2. 🔊 AcousticBrainz
**Type**: Free, no authentication required  
**URL**: https://acousticbrainz.org  
**Provides**: BPM (Beats Per Minute)  
**Confidence**: Very high (95%)  
**Status**: ✓ Always active (requires MusicBrainz lookup first)

**What it is**: Audio analysis database with technical features extracted from audio files.

**How it works**: 
1. Finds track in MusicBrainz (gets MusicBrainz ID)
2. Uses that ID to query AcousticBrainz for BPM
3. BPM accuracy depends on audio analysis quality

**Data quality**: Excellent for BPM, available for many tracks.

### 3. 📀 Discogs
**Type**: Free with API token (optional but recommended)  
**URL**: https://www.discogs.com  
**Provides**: Genre, Release Year  
**Confidence**: Good (75-85%)  
**Status**: ⚠️ Optional - only works with API token

**What it is**: Comprehensive database of physical and digital music releases with collector-curated data.

**Setup Required**:
```bash
# 1. Go to https://www.discogs.com/settings/developers
# 2. Register as a developer
# 3. Create an app to get your personal token
# 4. Add to .env file:
DISCOGS_TOKEN=your-token-here
```

**Data quality**: Very good, especially for vinyl/physical releases.

### 4. 🌐 Wikidata
**Type**: Free, no authentication required  
**URL**: https://www.wikidata.org  
**Provides**: Release Year, Genre  
**Confidence**: Medium (60-80%)  
**Status**: ✓ Always active

**What it is**: Linked open data project with structured information about musical works.

**Data quality**: Sparse coverage, mainly for major releases by known artists.

### 5. 🏆 Last.fm
**Type**: Free with API key (optional)  
**URL**: https://www.last.fm  
**Provides**: Genre (user tags, not official)  
**Confidence**: Medium (50%)  
**Status**: ⚠️ Optional - only works with API key

**What it is**: Music scrobbling platform where users tag tracks with genres.

**Setup Required**:
```bash
# 1. Go to https://www.last.fm/api/account/create
# 2. Create an API account
# 3. Get your API key
# 4. Add to .env file:
LASTFM_API_KEY=your-key-here
```

**Data quality**: Very subjective (depends on user tags), good for discovering popular genres.

## Configuration

### Minimum Setup (No Optional APIs)

Works out of the box - no configuration needed:

```bash
# MusicBrainz (free) + AcousticBrainz (free) + Wikidata (free)
python main.py
# Select: 2. Metadata Enrichment
```

These three sources provide reasonable metadata coverage for most tracks.

### Recommended Setup (With Discogs)

Get better genre and year data:

```bash
# 1. Get Discogs token from https://www.discogs.com/settings/developers
# 2. Add to .env:
DISCOGS_TOKEN=your-token-here

# 3. Run enrichment
python main.py
```

### Full Setup (All APIs)

Maximum coverage:

```bash
# 1. Set up Discogs (optional)
DISCOGS_TOKEN=your-token-here

# 2. Set up Last.fm (optional)
LASTFM_API_KEY=your-key-here

# 3. Run enrichment
python main.py
```

## Query Priority (Which Source Wins?)

When multiple databases have data for the same field:

1. **Higher confidence wins** - If AcousticBrainz reports BPM at 95% confidence and MusicBrainz reports it at 70%, AcousticBrainz wins
2. **First match wins** - Sources are queried in order, first valid result is kept

Example: For BPM field
- AcousticBrainz found BPM (95% confidence) → **Use this**
- (MusicBrainz result ignored even if available)

## What Gets Logged

When enrichment runs, you'll see in the logs:

```
DEBUG: Querying MUSICBRAINZ for Artist - Song
DEBUG: Found MusicBrainz recording: xxx-xxx-xxx
DEBUG: Querying ACOUSTICBRAINZ for Artist - Song
DEBUG: Found BPM from AcousticBrainz: 120
DEBUG: Querying DISCOGS for Artist - Song
DEBUG: Found Discogs release: 12345
DEBUG: Found genre from Discogs: Rock
```

Each line shows which source is being queried and what was found.

## Common Scenarios

### Scenario 1: Obscure Indie Track
**Results**: MusicBrainz finds it, but AcousticBrainz doesn't have BPM analysis
- MusicBrainz: Genre ✓, Year ✓, BPM ✗
- AcousticBrainz: BPM ✗
- Discogs: Genre ✓ (different), Year ✓
- Final result: Genre (from Discogs, higher confidence), Year (from MusicBrainz)

### Scenario 2: Popular Mainstream Song
**Results**: Multiple sources have complete data
- MusicBrainz: Genre ✓, Year ✓, BPM ✗
- AcousticBrainz: BPM ✓
- Discogs: Genre ✓, Year ✓
- Final result: Genre (Discogs highest confidence), Year (MusicBrainz earliest), BPM (AcousticBrainz)

### Scenario 3: Very Obscure Track
**Results**: Only MusicBrainz has basic data
- MusicBrainz: Genre ✓, Year ✓
- Others: No results
- Final result: Enriched with MusicBrainz data

## Troubleshooting

### "Found 0 metadata entries"

Check the logs for SSL errors:

```bash
grep "SSL" data/logs/metadata_enrichment.log
```

If you see SSL errors, run the fix:

```bash
bash fix_ssl_certificates.sh
```

### "Discogs query returned nothing"

Possible causes:
1. Token not set or invalid - Check `.env` has `DISCOGS_TOKEN`
2. Track not in Discogs - Very obscure tracks may not be listed
3. Artist/title formatting - Try searching manually at discogs.com

### "Last.fm returns low confidence"

Last.fm user tags are subjective. If you see low confidence:
```
DEBUG: Found genre from Last.fm: Podcasts (confidence 0.5)
```

This is expected - you can prioritize other sources over Last.fm by adjusting confidence thresholds in the code.

## API Rate Limits

Each database has rate limiting:

- **MusicBrainz**: 1 request/second (enforced)
- **AcousticBrainz**: Free tier limit
- **Discogs**: Rate limiting per token
- **Wikidata**: Rate limiting per IP
- **Last.fm**: Rate limiting per API key

The enrichment system includes delays between queries (0.5 seconds) to respect these limits.

## Performance Impact

Adding optional APIs slightly increases processing time:

- **MusicBrainz only**: ~0.5 seconds per track
- **+ AcousticBrainz**: ~1.5 seconds per track (extra MBID lookup)
- **+ Discogs**: ~2.5 seconds per track
- **+ Last.fm**: ~3 seconds per track

Total: ~3 seconds per track with all APIs (vs ~0.5 without optional APIs).

## Checking What's Enabled

To see which APIs are active:

```bash
grep "Querying" data/logs/metadata_enrichment.log | tail -20
```

Shows which sources were queried for recent tracks.

## Improving Results

If enrichment isn't finding metadata:

1. **Fix SSL first** - Run `bash fix_ssl_certificates.sh`
2. **Add Discogs token** - Best optional source for genre/year
3. **Check track spelling** - Artist and song names must be exact-ish
4. **Check logs** - See what databases found what

---

**Next Steps**: 
- [View Logs Guide](METADATA_LOGS_GUIDE.md)
- [Testing Guide](TESTING_QUICK_REFERENCE.md)
- [Fix SSL Issues](../../SSL_CERTIFICATE_FIX.md)
