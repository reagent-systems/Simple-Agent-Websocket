#!/usr/bin/env python3
"""
Simple-Agent-Websocket Main Entry Point

A lightweight WebSocket wrapper around the SimpleAgent core that provides
real-time web interface capabilities without duplicating the core codebase.
"""

import argparse
import os
import sys

from websocket_server.server import create_server


def main():
    """Main function to start the WebSocket server"""
    parser = argparse.ArgumentParser(description='Simple-Agent-Websocket Server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=int(os.environ.get('PORT', 5000)), 
                      help='Port to bind to (default: PORT env var or 5000)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--eager-loading', action='store_true',
                      help='Use eager loading (load all tools at startup) instead of dynamic loading')
    
    args = parser.parse_args()
    
    # Create and initialize server
    server = create_server(host=args.host, port=args.port, debug=args.debug)
    
    if not server.initialize(eager_loading=args.eager_loading):
        print("❌ Failed to initialize server")
        sys.exit(1)
    
    # Run the server
    server.run()


if __name__ == "__main__":
    main() 