#!/bin/bash

# Setup script for Simple-Agent-Websocket
# This script sets up the SimpleAgent core as a git submodule

echo "🚀 Setting up Simple-Agent-Websocket..."

# Remove existing SimpleAgent directory if it exists
if [ -d "SimpleAgent" ]; then
    echo "📁 Removing existing SimpleAgent directory..."
    rm -rf SimpleAgent
fi

# Add SimpleAgent core as a git submodule
echo "📦 Adding SimpleAgent core as git submodule..."
git submodule add https://github.com/reagent-systems/Simple-Agent-Core.git SimpleAgent-Core

# Create symlink or copy the core files to expected location
echo "🔗 Creating symlink to SimpleAgent core..."
ln -sf SimpleAgent-Core/SimpleAgent SimpleAgent

# Initialize and update submodules
echo "🔄 Initializing git submodules..."
git submodule init
git submodule update

# Install requirements
echo "📋 Installing requirements..."
if [ -f "SimpleAgent/requirements.txt" ]; then
    pip install -r SimpleAgent/requirements.txt
fi

# Install additional WebSocket requirements
echo "📋 Installing WebSocket requirements..."
pip install flask flask-socketio eventlet

echo "✅ Setup complete!"
echo ""
echo "📖 Usage:"
echo "  To update SimpleAgent core: git submodule update --remote"
echo "  To run WebSocket server: python main.py"
echo "" 