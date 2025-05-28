@echo off
REM Setup script for Simple-Agent-Websocket (Windows)
REM This script sets up the SimpleAgent core as a git submodule

echo 🚀 Setting up Simple-Agent-Websocket...

REM Remove existing SimpleAgent directory if it exists
if exist "SimpleAgent" (
    echo 📁 Removing existing SimpleAgent directory...
    rmdir /s /q SimpleAgent
)

REM Add SimpleAgent core as a git submodule
echo 📦 Adding SimpleAgent core as git submodule...
git submodule add https://github.com/reagent-systems/Simple-Agent-Core.git SimpleAgent-Core

REM Create junction (Windows symlink equivalent) to SimpleAgent core
echo 🔗 Creating junction to SimpleAgent core...
mklink /J SimpleAgent SimpleAgent-Core\SimpleAgent

REM Initialize and update submodules
echo 🔄 Initializing git submodules...
git submodule init
git submodule update

REM Install requirements
echo 📋 Installing requirements...
if exist "SimpleAgent\requirements.txt" (
    pip install -r SimpleAgent\requirements.txt
)

REM Install additional WebSocket requirements
echo 📋 Installing WebSocket requirements...
pip install flask flask-socketio eventlet

echo ✅ Setup complete!
echo.
echo 📖 Usage:
echo   To update SimpleAgent core: git submodule update --remote
echo   To run WebSocket server: python main.py
echo. 