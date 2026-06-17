#!/bin/bash

# Apple2Spfy Drive Sync Setup
# This script sets up automatic playlist sync when a specific drive is connected

echo "╔════════════════════════════════════════════════════════════╗"
echo "║        Apple2Spfy Drive-Triggered Sync Setup              ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Get project root (parent of scripts/)
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# Capture current Python path
CURRENT_PYTHON="$(which python3)"

# Ask for drive name
echo "Enter the name of your drive as it appears in /Volumes/"
echo "Example: If your drive shows as '/Volumes/MyDrive', enter 'MyDrive'"
echo ""
read -p "Drive name: " DRIVE_NAME

if [ -z "$DRIVE_NAME" ]; then
    echo "❌ Error: Drive name cannot be empty"
    exit 1
fi

echo ""
echo "Creating auto-sync wrapper script..."

# Create auto_sync_on_drive.sh
cat > "$SCRIPT_DIR/auto_sync_on_drive.sh" << 'EOF'
#!/bin/bash

# Configuration
DRIVE_NAME="DRIVE_NAME_PLACEHOLDER"
DRIVE_PATH="/Volumes/$DRIVE_NAME"
SCRIPT_DIR="SCRIPT_DIR_PLACEHOLDER"
FALLBACK_PYTHON="FALLBACK_PYTHON_PLACEHOLDER"
SYNC_MARKER="$DRIVE_PATH/.apple2spfy_synced"
LOG_FILE="/tmp/apple2spfy_drive.log"

# Auto-detect Python path (venv, conda, or system)
detect_python() {
    # Check if we're in a virtual environment
    if [ -n "$VIRTUAL_ENV" ]; then
        echo "$VIRTUAL_ENV/bin/python3"
    # Check if we're in a conda environment
    elif [ -n "$CONDA_PREFIX" ]; then
        echo "$CONDA_PREFIX/bin/python3"
    # Check for venv in script directory
    elif [ -f "$SCRIPT_DIR/venv/bin/python3" ]; then
        echo "$SCRIPT_DIR/venv/bin/python3"
    # Fall back to the Python that was active during setup
    else
        echo "$FALLBACK_PYTHON"
    fi
}

PYTHON_CMD=$(detect_python)

# Check if drive is mounted
if [ ! -d "$DRIVE_PATH" ]; then
    exit 0
fi

LAST_RUN_FILE="$HOME/.apple2spfy_last_run"

# Check if last run was less than 24 hours ago
if [ -f "$LAST_RUN_FILE" ]; then
    LAST_RUN=$(cat "$LAST_RUN_FILE")
    CURRENT_TIME=$(date +%s)
    TIME_DIFF=$((CURRENT_TIME - LAST_RUN))
    
    # 24 hours = 86400 seconds
    if [ $TIME_DIFF -lt 86400 ]; then
        HOURS_LEFT=$(((86400 - TIME_DIFF) / 3600))
        echo "$(date): Less than 24h since last sync (approx ${HOURS_LEFT}h remaining). Skipping." >> "$LOG_FILE"
        exit 0
    fi
fi

# Run sync
echo "$(date): Drive '$DRIVE_NAME' detected and 24h passed, starting playlist sync..." >> "$LOG_FILE"
cd "$SCRIPT_DIR"

# Run the sync
$PYTHON_CMD sync_playlists.py --clean-sync >> "$LOG_FILE" 2>&1
SYNC_EXIT_CODE=$?

# Create marker file if successful
if [ $SYNC_EXIT_CODE -eq 0 ]; then
    date +%s > "$LAST_RUN_FILE"
    echo "$(date): ✅ Sync completed successfully" >> "$LOG_FILE"
else
    echo "$(date): ❌ Sync failed with exit code $SYNC_EXIT_CODE" >> "$LOG_FILE"
    exit 1
fi
EOF

# Replace placeholders
sed -i '' "s|DRIVE_NAME_PLACEHOLDER|$DRIVE_NAME|g" "$SCRIPT_DIR/auto_sync_on_drive.sh"
sed -i '' "s|SCRIPT_DIR_PLACEHOLDER|$SCRIPT_DIR|g" "$SCRIPT_DIR/auto_sync_on_drive.sh"
sed -i '' "s|FALLBACK_PYTHON_PLACEHOLDER|$CURRENT_PYTHON|g" "$SCRIPT_DIR/auto_sync_on_drive.sh"


chmod +x "$SCRIPT_DIR/auto_sync_on_drive.sh"
echo "✅ Created: auto_sync_on_drive.sh"

# Create Launch Agent
PLIST_PATH="$HOME/Library/LaunchAgents/com.user.apple2spfy.drive.plist"
mkdir -p "$HOME/Library/LaunchAgents"

echo "Creating Launch Agent..."

cat > "$PLIST_PATH" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.apple2spfy.drive</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$SCRIPT_DIR/auto_sync_on_drive.sh</string>
    </array>
    
    <key>WatchPaths</key>
    <array>
        <string>/Volumes</string>
    </array>
    
    <key>RunAtLoad</key>
    <false/>
    
    <key>StandardOutPath</key>
    <string>/tmp/apple2spfy_drive.log</string>
    
    <key>StandardErrorPath</key>
    <string>/tmp/apple2spfy_drive.error.log</string>
</dict>
</plist>
EOF

echo "✅ Created: $PLIST_PATH"

# Load Launch Agent
echo "Loading Launch Agent..."
launchctl unload "$PLIST_PATH" 2>/dev/null
launchctl load "$PLIST_PATH"

if [ $? -eq 0 ]; then
    echo "✅ Launch Agent loaded successfully"
else
    echo "⚠️  Warning: Failed to load Launch Agent"
fi

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                    Setup Complete! ✅                      ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "Configuration:"
echo "  📁 Drive name: $DRIVE_NAME"
echo "  📂 Watch path: /Volumes/$DRIVE_NAME"
echo "  📝 Log file: /tmp/apple2spfy_drive.log"
echo "  🔧 Launch Agent: $PLIST_PATH"
echo ""
echo "How it works:"
echo "  1. Connect your drive '$DRIVE_NAME'"
echo "  2. Sync runs automatically (respects STALE_SYNC_DAYS from .env)"
echo "  3. Cooldown prevents syncing more frequently than STALE_SYNC_DAYS"
echo "  4. Playlists also respect STALE_SYNC_DAYS in sync_playlists.py"
echo "  5. Each playlist tracks its own sync timestamp"
echo ""
echo "Useful commands:"
echo "  📊 View logs:    tail -f /tmp/apple2spfy_drive.log"
echo "  🔍 Check status: launchctl list | grep apple2spfy"
echo "  ⏸️  Disable:      launchctl unload $PLIST_PATH"
echo "  ▶️  Enable:       launchctl load $PLIST_PATH"
echo ""
echo "Test it now by connecting your drive!"
echo ""
