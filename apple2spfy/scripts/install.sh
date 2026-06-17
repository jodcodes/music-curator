#!/bin/bash

# Apple Music to Spotify Playlist Sync - Installation Script

echo "🎵 Apple Music to Spotify Playlist Sync - Installation"
echo "====================================================="

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed."
    echo "Please install Python 3 from https://python.org"
    exit 1
fi

echo "✅ Python 3 found: $(python3 --version)"

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 is required but not installed."
    echo "Please install pip3"
    exit 1
fi

echo "✅ pip3 found"

# Check for virtual environment
echo ""
echo "🔍 Checking Python environment..."

if [ -n "$VIRTUAL_ENV" ]; then
    echo "✅ Running in virtual environment: $VIRTUAL_ENV"
elif [ -n "$CONDA_DEFAULT_ENV" ]; then
    echo "✅ Running in conda environment: $CONDA_DEFAULT_ENV"
else
    echo "⚠️  Not running in a virtual environment"
    echo ""
    read -p "Would you like to create a virtual environment? (recommended) [Y/n]: " create_venv
    create_venv=${create_venv:-Y}
    
    if [[ $create_venv =~ ^[Yy]$ ]]; then
        echo "📦 Creating virtual environment..."
        python3 -m venv venv
        
        if [ $? -eq 0 ]; then
            echo "✅ Virtual environment created"
            echo ""
            echo "To activate it, run:"
            echo "  source venv/bin/activate"
            echo ""
            read -p "Activate now and continue installation? [Y/n]: " activate_now
            activate_now=${activate_now:-Y}
            
            if [[ $activate_now =~ ^[Yy]$ ]]; then
                source venv/bin/activate
                echo "✅ Virtual environment activated"
            else
                echo ""
                echo "Please activate the virtual environment and run this script again:"
                echo "  source venv/bin/activate"
                echo "  ./scripts/install.sh"
                exit 0
            fi
        else
            echo "❌ Failed to create virtual environment"
            echo "Continuing with system Python..."
        fi
    else
        echo "Continuing with system Python..."
    fi
fi

# Install Python dependencies
echo ""
echo "📦 Installing Python dependencies..."
pip3 install -r requirements.txt

if [ $? -eq 0 ]; then
    echo "✅ Dependencies installed successfully"
else
    echo "❌ Failed to install dependencies"
    exit 1
fi

# Create logs directory
echo "📁 Creating logs directory..."
mkdir -p logs

# Create cache directory
echo "📁 Creating cache directory..."
mkdir -p ~/.spotify_cache

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating from template..."
    cp env.example .env
    echo "📝 Please edit .env file with your Spotify credentials"
    echo "   You can get them from: https://developer.spotify.com/dashboard"
else
    echo "✅ .env file found"
fi

# Make scripts executable
echo "🔧 Making scripts executable..."
chmod +x sync_playlists.py
chmod +x debug_sync.py
chmod +x test_setup.py

echo ""
echo "🎉 Installation completed!"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your Spotify credentials"
echo "2. Set up your AppleScript file path in .env"
echo "3. Run 'python3 test_setup.py' to verify your setup"
echo "4. Run 'python3 debug_sync.py' for debugging"
echo "5. Run 'python3 sync_playlists.py' to start syncing"
echo ""
echo "For more information, see README.md"
