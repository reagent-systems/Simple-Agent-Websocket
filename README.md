# Simple-Agent-Websocket

A lightweight WebSocket wrapper around the [SimpleAgent Core](https://github.com/reagent-systems/Simple-Agent-Core) that provides real-time web interface capabilities without duplicating the core codebase.

## 🎯 Philosophy

This project follows the **"Don't Repeat Yourself" (DRY)** principle by:
- **Not duplicating** the SimpleAgent core code
- **Using git submodules** to reference the official SimpleAgent Core repository
- **Acting as a thin wrapper** that adds WebSocket functionality
- **Staying automatically up-to-date** with core improvements

## 🏗️ Architecture

```
Simple-Agent-Websocket/
├── main.py                      # Main entry point
├── websocket_server.py          # Backward compatibility wrapper
├── websocket_server/            # Modular server package
│   ├── __init__.py             # Package initialization
│   ├── core_loader.py          # SimpleAgent core loading
│   ├── run_manager.py          # WebSocket-enhanced RunManager
│   ├── agent_wrapper.py        # Agent session management
│   ├── event_handlers.py       # WebSocket event handlers
│   ├── routes.py               # HTTP API routes
│   └── server.py               # Main server class
├── test_client_enhanced.html    # Enhanced test client with real-time UI
├── setup_submodule.sh          # Linux/Mac setup script
├── setup_submodule.bat         # Windows setup script
├── requirements.txt            # WebSocket-specific dependencies
└── SimpleAgent/                # → Symlink to SimpleAgent-Core/SimpleAgent
    └── (SimpleAgent Core via git submodule)
```

## ✨ Features

- **🔄 Real-time Updates**: See each step of agent execution as it happens
- **💬 Bidirectional Communication**: Send messages to the agent during execution
- **📊 Progress Tracking**: Visual progress bars and step indicators
- **🎨 Modern UI**: Clean, responsive web interface
- **📦 No Code Duplication**: Uses the official SimpleAgent Core as a git submodule
- **🔄 Auto-sync**: Easy updates when the core repository changes
- **🌐 Multi-session**: Support for multiple concurrent WebSocket sessions
- **🧩 Modular Design**: Clean, maintainable code structure

## 🚀 Quick Start

### 1. Clone and Setup

```bash
# Clone this repository
git clone https://github.com/your-username/Simple-Agent-Websocket.git
cd Simple-Agent-Websocket

# Run the setup script to configure git submodules
# Linux/Mac:
chmod +x setup_submodule.sh
./setup_submodule.sh

# Windows:
setup_submodule.bat
```

### 2. Configure Environment

Create a `.env` file in the `SimpleAgent` directory (or copy from the core):

```env
# API Provider (openai, lmstudio, or gemini)
API_PROVIDER=openai

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Model settings
DEFAULT_MODEL=gpt-4o
SUMMARIZER_MODEL=gpt-3.5-turbo

# Application settings
MAX_STEPS=10
DEBUG_MODE=False
```

### 3. Start the WebSocket Server

```bash
# New modular interface (recommended)
python main.py

# Or with options
python main.py --host 0.0.0.0 --port 8080 --debug

# Backward compatibility (deprecated but still works)
python websocket_server.py
```

The server will start on `http://localhost:5000` by default.

### 4. Open the Test Client

Open `test_client_enhanced.html` in your web browser to interact with the agent through a modern web interface.

## 📡 WebSocket API

### Events from Client to Server

- `run_agent`: Start agent execution
  ```json
  {
    "instruction": "Your task description",
    "max_steps": 10,
    "auto_continue": 0
  }
  ```

- `stop_agent`: Stop running agent
- `user_input`: Send user input during execution
  ```json
  {
    "input": "User response"
  }
  ```

- `get_status`: Get current session status

### Events from Server to Client

- `connected`: Connection established
- `agent_started`: Agent execution began
- `step_start`: New step started
- `assistant_message`: AI assistant response
- `tool_call`: Tool/function execution
- `step_summary`: Step completion summary
- `waiting_for_input`: Agent waiting for user input
- `task_completed`: Task finished successfully
- `agent_finished`: Agent execution completed
- `agent_error`: Error occurred

## 🔄 Keeping Up-to-Date

The beauty of this approach is that you can easily update to the latest SimpleAgent Core:

```bash
# Update the SimpleAgent core to the latest version
git submodule update --remote

# Or update and commit the new version
git submodule update --remote
git add SimpleAgent-Core
git commit -m "Update SimpleAgent core to latest version"
```

## 🛠️ Development

### Project Structure

The server is now organized into clean, modular components:

- **`main.py`**: Entry point with argument parsing
- **`websocket_server/core_loader.py`**: Handles loading SimpleAgent core from submodule
- **`websocket_server/run_manager.py`**: WebSocket-enhanced RunManager
- **`websocket_server/agent_wrapper.py`**: Session management and agent wrapping
- **`websocket_server/event_handlers.py`**: WebSocket event handling
- **`websocket_server/routes.py`**: HTTP API endpoints
- **`websocket_server/server.py`**: Main server class and initialization
- **`test_client_enhanced.html`**: Full-featured test client with real-time UI

### Adding Features

Since this is a modular wrapper, you can:
1. **Extend WebSocket events**: Add new event types in `event_handlers.py`
2. **Add HTTP endpoints**: Extend `routes.py` with new API routes
3. **Enhance the UI**: Modify `test_client_enhanced.html`
4. **Customize behavior**: Override methods in the wrapper classes
5. **Add new modules**: Create new modules in the `websocket_server/` package

### Core Updates

When the SimpleAgent Core gets updated:
1. Your WebSocket wrapper automatically gets the new features
2. No need to manually sync code changes
3. Just update the submodule and restart the server

## 🔧 Configuration Options

### Server Options

```bash
python main.py --help
```

- `--host`: Host to bind to (default: localhost)
- `--port`: Port to bind to (default: 5000)
- `--debug`: Enable debug mode
- `--eager-loading`: Use eager loading for tools

### Environment Variables

All SimpleAgent Core environment variables are supported. See the [core documentation](https://github.com/reagent-systems/Simple-Agent-Core) for details.

## 🌐 API Endpoints

- `GET /health`: Health check and server status
- `GET /sessions`: List active WebSocket sessions
- `GET /version`: Version information for both WebSocket server and core
- `WebSocket /socket.io/`: Main WebSocket endpoint

## 🧩 Modular Benefits

The new modular structure provides:

- **🔧 Maintainability**: Each component has a single responsibility
- **🧪 Testability**: Individual modules can be tested in isolation
- **📈 Scalability**: Easy to add new features without affecting existing code
- **🔍 Debuggability**: Clear separation makes issues easier to track down
- **👥 Team Development**: Multiple developers can work on different modules
- **📚 Documentation**: Each module is self-contained and well-documented

## 🔒 Security Considerations

- **CORS**: Currently allows all origins (`*`) - configure for production
- **Authentication**: No built-in auth - add as needed for your use case
- **Rate Limiting**: Consider adding rate limiting for production deployments
- **File Access**: Inherits SimpleAgent Core's security model (output directory restrictions)

## 🤝 Contributing

1. **For WebSocket features**: Contribute to this repository
2. **For core agent features**: Contribute to [SimpleAgent Core](https://github.com/reagent-systems/Simple-Agent-Core)
3. **For tools**: Contribute to [Simple-Agent-Tools](https://github.com/reagent-systems/Simple-Agent-Tools)

## 📄 License

This project follows the same license as the SimpleAgent Core.

## 🙏 Acknowledgments

- Built on top of [SimpleAgent Core](https://github.com/reagent-systems/Simple-Agent-Core)
- Uses Flask-SocketIO for WebSocket functionality
- Inspired by the need for real-time AI agent interfaces

---

**Why This Approach?**

✅ **No code duplication** - Uses official core as submodule  
✅ **Always up-to-date** - Easy to sync with core updates  
✅ **Lightweight** - Only adds WebSocket functionality  
✅ **Maintainable** - Core changes don't require manual updates  
✅ **Focused** - This repo only handles WebSocket concerns  
✅ **Modular** - Clean, organized code structure  

❌ **Alternative approaches we avoided:**
- Forking the core (creates maintenance burden)
- Copying core files (leads to version drift)
- Modifying core directly (breaks separation of concerns)
- Monolithic server files (hard to maintain and extend)
