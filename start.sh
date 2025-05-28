#!/bin/bash

# Initialize git submodules
echo "🔧 Initializing git submodules..."
git submodule update --init --recursive

# Create symlink for SimpleAgent
echo "🔗 Creating SimpleAgent symlink..."
ln -sf SimpleAgent-Core/SimpleAgent SimpleAgent

# Check if symlink was created successfully
if [ -d "SimpleAgent" ]; then
    echo "✅ SimpleAgent symlink created successfully"
    ls -la SimpleAgent/
else
    echo "❌ Failed to create SimpleAgent symlink"
    exit 1
fi

# Start the server
echo "🚀 Starting Simple-Agent-Websocket server..."
python main.py --host 0.0.0.0 --port 8080