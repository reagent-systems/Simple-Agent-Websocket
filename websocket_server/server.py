"""
WebSocket Server

Main server module that initializes and runs the SimpleAgent WebSocket server.
"""

import os
import logging
from flask import Flask
from flask_socketio import SocketIO

from .core_loader import core_loader
from .event_handlers import register_handlers
from .routes import api_bp

logger = logging.getLogger(__name__)


class SimpleAgentWebSocketServer:
    """Main WebSocket server class"""
    
    def __init__(self, host='localhost', port=5000, debug=False):
        self.host = host
        self.port = port
        self.debug = debug
        self.app = None
        self.socketio = None
        
    def initialize(self, eager_loading=False):
        """Initialize the server"""
        # Setup logging
        logging.basicConfig(
            level=logging.INFO, 
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        logging.getLogger("httpx").setLevel(logging.WARNING)
        
        # Setup core path and load modules
        if not core_loader.setup_core_path():
            return False
            
        core = core_loader.load_core_modules()
        core_loader.validate_configuration()
        
        # Initialize commands based on user preference
        commands = core['commands']
        dynamic_loading = not eager_loading
        print(f"🔧 Initializing tools with {'dynamic' if dynamic_loading else 'eager'} loading...")
        commands.init(dynamic=dynamic_loading)
        
        # Initialize Flask app
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'simple-agent-websocket-secret')
        
        # Initialize SocketIO
        self.socketio = SocketIO(self.app, cors_allowed_origins="*", async_mode='threading')
        
        # Register routes
        self.app.register_blueprint(api_bp)
        
        # Register WebSocket event handlers
        register_handlers(self.socketio)
        
        logger.info("Server initialized successfully")
        return True
        
    def run(self):
        """Run the server"""
        if not self.app or not self.socketio:
            raise RuntimeError("Server not initialized. Call initialize() first.")
            
        # Load core modules for version info
        core = core_loader.load_core_modules()
        AGENT_VERSION = core['AGENT_VERSION']
        API_PROVIDER = core['API_PROVIDER']
        
        try:
            print(f"🚀 Starting Simple-Agent-Websocket Server...")
            print(f"📡 Server will be available at: http://{self.host}:{self.port}")
            print(f"🔌 WebSocket endpoint: ws://{self.host}:{self.port}/socket.io/")
            print(f"🏥 Health check: http://{self.host}:{self.port}/health")
            print(f"📊 Sessions endpoint: http://{self.host}:{self.port}/sessions")
            print(f"📋 Version endpoint: http://{self.host}:{self.port}/version")
            print(f"🤖 Agent version: {AGENT_VERSION}")
            print(f"🔗 API provider: {API_PROVIDER}")
            print(f"💬 Features: Real-time step updates, bidirectional communication")
            print(f"📦 Core: SimpleAgent from git submodule")
            
            # Start the server
            self.socketio.run(
                self.app,
                host=self.host,
                port=self.port,
                debug=self.debug,
                use_reloader=False,  # Disable reloader to prevent issues with threading
                allow_unsafe_werkzeug=True  # Allow running in production environments
            )
        finally:
            # Clean up tool manager resources
            core = core_loader.load_core_modules()
            commands = core['commands']
            commands.cleanup()


def create_server(host='localhost', port=5000, debug=False):
    """Factory function to create a server instance"""
    return SimpleAgentWebSocketServer(host=host, port=port, debug=debug) 