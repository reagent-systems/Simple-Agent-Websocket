"""
WebSocket Event Handlers

Handles all WebSocket events for the SimpleAgent WebSocket server.
"""

import logging
import threading
from flask import request
from flask_socketio import emit, disconnect
from datetime import datetime

from .core_loader import core_loader
from .agent_wrapper import SessionManager

logger = logging.getLogger(__name__)

# Global session manager
session_manager = SessionManager()


def register_handlers(socketio):
    """Register all WebSocket event handlers"""
    
    @socketio.on('connect')
    def handle_connect():
        """Handle client connection"""
        session_id = request.sid
        logger.info(f"Client connected: {session_id}")
        
        # Load core modules for version info
        core = core_loader.load_core_modules()
        AGENT_VERSION = core['AGENT_VERSION']
        API_PROVIDER = core['API_PROVIDER']
        
        # Create session
        session_data = session_manager.create_session(session_id)
        
        # Send connection confirmation
        emit('connected', {
            'session_id': session_id,
            'agent_version': AGENT_VERSION,
            'api_provider': API_PROVIDER,
            'output_dir': session_data['output_dir'],
            'timestamp': datetime.now().isoformat()
        })

    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle client disconnection"""
        session_id = request.sid
        logger.info(f"Client disconnected: {session_id}")
        
        # Clean up session
        session_manager.remove_session(session_id)

    @socketio.on('run_agent')
    def handle_run_agent(data):
        """Handle agent run request"""
        session_id = request.sid
        
        session_data = session_manager.get_session(session_id)
        if not session_data:
            emit('error', {'message': 'Session not found'})
            return
        
        wrapper = session_data['wrapper']
        
        # Check if agent is already running
        if wrapper.is_running:
            emit('error', {'message': 'Agent is already running'})
            return
        
        # Extract parameters
        instruction = data.get('instruction', '')
        max_steps = data.get('max_steps', 10)
        auto_continue = data.get('auto_continue', 0)
        
        if not instruction:
            emit('error', {'message': 'Instruction is required'})
            return
        
        # Run agent in a separate thread
        def run_agent_thread():
            wrapper.run_async(instruction, max_steps, auto_continue, socketio)
        
        thread = threading.Thread(target=run_agent_thread)
        thread.daemon = True
        thread.start()

    @socketio.on('stop_agent')
    def handle_stop_agent():
        """Handle agent stop request"""
        session_id = request.sid
        
        session_data = session_manager.get_session(session_id)
        if not session_data:
            emit('error', {'message': 'Session not found'})
            return
        
        wrapper = session_data['wrapper']
        
        if not wrapper.is_running:
            emit('error', {'message': 'Agent is not running'})
            return
        
        # Stop the agent
        success = wrapper.stop()
        emit('agent_stop_requested', {
            'success': success,
            'timestamp': datetime.now().isoformat()
        })

    @socketio.on('user_input')
    def handle_user_input(data):
        """Handle user input for running agent"""
        session_id = request.sid
        
        session_data = session_manager.get_session(session_id)
        if not session_data:
            emit('error', {'message': 'Session not found'})
            return
        
        wrapper = session_data['wrapper']
        
        if not wrapper.is_running:
            emit('error', {'message': 'Agent is not running'})
            return
        
        user_input = data.get('input', '')
        if not user_input:
            emit('error', {'message': 'Input is required'})
            return
        
        # Provide input to the agent
        wrapper.provide_user_input(user_input)
        emit('user_input_sent', {
            'input': user_input,
            'timestamp': datetime.now().isoformat()
        })

    @socketio.on('get_status')
    def handle_get_status():
        """Handle status request"""
        session_id = request.sid
        
        session_data = session_manager.get_session(session_id)
        if not session_data:
            emit('error', {'message': 'Session not found'})
            return
        
        wrapper = session_data['wrapper']
        
        # Load core modules for version info
        core = core_loader.load_core_modules()
        AGENT_VERSION = core['AGENT_VERSION']
        API_PROVIDER = core['API_PROVIDER']
        
        emit('status', {
            'session_id': session_id,
            'is_running': wrapper.is_running,
            'connected_at': session_data['connected_at'],
            'agent_version': AGENT_VERSION,
            'api_provider': API_PROVIDER,
            'output_dir': session_data['output_dir'],
            'timestamp': datetime.now().isoformat()
        })


def get_session_manager():
    """Get the global session manager"""
    return session_manager 