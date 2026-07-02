# Quick Reference: SSL Certificate Fix for macOS

If you see errors like this during metadata enrichment:

```
SSL: CERTIFICATE_VERIFY_FAILED certificate verify failed: unable to get local issuer certificate
```

This means Python cannot verify SSL certificates for HTTPS connections to music databases.

## Quick Fix (Automatic) ⚡

Run the provided fix script:

```bash
bash fix_ssl_certificates.sh
```

This will:
1. Find your Python installation
2. Install/update SSL certificates
3. Test the connection to MusicBrainz
4. Verify the fix worked

## Manual Fix (if script doesn't work)

### Option 1: Python Installer (Recommended)

Find your Python version:
```bash
python3 --version
```

Then run the installer for your version:

**Python 3.11:**
```bash
"/Applications/Python 3.11/Install Certificates.command"
```

**Python 3.10:**
```bash
"/Applications/Python 3.10/Install Certificates.command"
```

**Python 3.9:**
```bash
"/Applications/Python 3.9/Install Certificates.command"
```

### Option 2: Update certifi Package

```bash
# Make sure you're in the right environment
source activate.sh

# Upgrade the certifi package (contains SSL certificates)
python3 -m pip install --upgrade certifi
```

### Option 3: Homebrew Python

If you installed Python via Homebrew:

```bash
# Reinstall Python to get proper certificates
brew reinstall python3
```

## Verify the Fix ✓

After running any of the above, test that SSL works:

```bash
python3 << 'EOF'
import urllib.request
import json

url = "https://musicbrainz.org/ws/2/recording?query=artist%3A%22Test%22&limit=1&fmt=json"
headers = {'User-Agent': 'metad-fill/1.0'}
req = urllib.request.Request(url, headers=headers)

try:
    with urllib.request.urlopen(req, timeout=5) as response:
        print("✓ SSL connection works!")
        print(f"  Status: {response.status}")
except Exception as e:
    print(f"✗ Still failing: {e}")
EOF
```

If you see `✓ SSL connection works!`, your SSL certificates are fixed.

## Why This Happens

Python on macOS uses OpenSSL for SSL/TLS connections. The Python installer includes a bundle of CA (Certificate Authority) certificates, but they:

1. May not be installed by default in newer Python versions
2. Can expire and need updating
3. Are different from the system's certificates

## What Metadata Features Use HTTPS

The metadata enrichment system queries:

- **MusicBrainz** - https://musicbrainz.org/ (REQUIRES HTTPS)
- **AcousticBrainz** - https://acousticbrainz.org/ (REQUIRES HTTPS)
- **Wikidata** - https://www.wikidata.org/ (REQUIRES HTTPS)
- **Discogs** - https://api.discogs.com/ (REQUIRES HTTPS)
- **Last.fm** - uses HTTP (no SSL issue)

Without proper SSL certificates, queries to these services will fail.

## After Fixing

Try enriching metadata again:

```bash
python main.py
# Select: 2. Metadata Enrichment
```

You should now see successful database queries instead of SSL errors in the logs:

```
✓ ENRICHED: Artist - Song (year=2020, bpm=120, genre=Rock)
```

## Troubleshooting

**Still getting SSL errors?**

1. Try the automatic fix script first: `bash fix_ssl_certificates.sh`
2. Check your Python version: `python3 --version`
3. Verify certifi is installed: `python3 -m pip list | grep certifi`
4. Try reinstalling certifi: `python3 -m pip install --force-reinstall certifi`

**Which Python is being used?**

```bash
which python3
# Shows the path to your Python executable
```

**Check certificate bundle location:**

```bash
python3 -c "import certifi; print(certifi.where())"
# Shows where Python's CA certificates are stored
```

---

**Last Updated**: January 3, 2026  
**Status**: Active - Use this if you encounter SSL errors  
**Related**: [SETUP_STATUS_SUMMARY.md](../PROJECT_SUMMARIES/SETUP_STATUS_SUMMARY.md), [SPEC_METADATA_ENRICHMENT.md](../../requirements/SPEC_METADATA_ENRICHMENT.md)
