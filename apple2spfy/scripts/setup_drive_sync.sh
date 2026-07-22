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

# Generate auto_sync_on_drive.sh FROM the template (the single source of
# truth for the wrapper's body) — never keep a second embedded copy here,
# or the template and the deployed wrapper drift apart.
TEMPLATE="$SCRIPT_DIR/scripts/auto_sync_on_drive.sh.template"
if [ ! -f "$TEMPLATE" ]; then
    echo "❌ Error: template not found at $TEMPLATE"
    exit 1
fi

cp "$TEMPLATE" "$SCRIPT_DIR/auto_sync_on_drive.sh"
sed -i '' "s|DRIVE_NAME=\"YOUR_DRIVE_NAME\"|DRIVE_NAME=\"$DRIVE_NAME\"|" "$SCRIPT_DIR/auto_sync_on_drive.sh"
sed -i '' "s|FALLBACK_PYTHON_PLACEHOLDER|$CURRENT_PYTHON|" "$SCRIPT_DIR/auto_sync_on_drive.sh"

chmod +x "$SCRIPT_DIR/auto_sync_on_drive.sh"

if ! bash -n "$SCRIPT_DIR/auto_sync_on_drive.sh"; then
    echo "❌ Error: generated auto_sync_on_drive.sh failed syntax check"
    exit 1
fi
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

# Validate the generated plist before ever loading it.
if ! plutil -lint "$PLIST_PATH" >/dev/null; then
    echo "❌ Error: generated plist failed validation (plutil -lint): $PLIST_PATH"
    exit 1
fi
echo "✅ plist validated (plutil -lint)"

# Load Launch Agent
echo "Loading Launch Agent..."
launchctl unload "$PLIST_PATH" 2>/dev/null
if ! launchctl load "$PLIST_PATH"; then
    echo "❌ Error: failed to load Launch Agent: $PLIST_PATH"
    exit 1
fi
echo "✅ Launch Agent loaded successfully"

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
