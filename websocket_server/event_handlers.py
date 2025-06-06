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


def safe_emit(event, data, **kwargs):
    """Safely emit a WebSocket event with error handling"""
    try:
        emit(event, data, **kwargs)
    except Exception as e:
        logger.warning(f"Failed to emit event '{event}': {e}")


def register_handlers(socketio):
    """Register all WebSocket event handlers"""
    
    @socketio.on('connect')
    def handle_connect():
        """Handle client connection"""
        try:
            session_id = request.sid
            logger.info(f"Client connected: {session_id}")
            
            # Load core modules for version info
            core = core_loader.load_core_modules()
            AGENT_VERSION = core['AGENT_VERSION']
            API_PROVIDER = core['API_PROVIDER']
            
            # Create session
            session_data = session_manager.create_session(session_id)
            
            # Send connection confirmation
            safe_emit('connected', {
                'session_id': session_id,
                'agent_version': AGENT_VERSION,
                'api_provider': API_PROVIDER,
                'output_dir': session_data['output_dir'],
                'timestamp': datetime.now().isoformat()
            })
        except Exception as e:
            logger.exception("Exception in handle_connect")
            safe_emit('error', {'message': str(e)})
            try:
                disconnect()
            except:
                pass  # Ignore disconnect errors

    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle client disconnection"""
        try:
            session_id = request.sid
            logger.info(f"Client disconnected: {session_id}")
            
            # Clean up session
            session_manager.remove_session(session_id)
        except Exception as e:
            logger.warning(f"Error during disconnect cleanup: {e}")

    @socketio.on('run_agent')
    def handle_run_agent(data):
        """Handle agent run request"""
        try:
            session_id = request.sid
            
            session_data = session_manager.get_session(session_id)
            if not session_data:
                safe_emit('error', {'message': 'Session not found'})
                return
            
            wrapper = session_data['wrapper']
            
            # Check if agent is already running
            if wrapper.is_running:
                safe_emit('error', {'message': 'Agent is already running'})
                return
            
            # Extract parameters
            instruction = data.get('instruction', '')
            max_steps = data.get('max_steps', 10)
            auto_continue = data.get('auto_continue', 0)
            
            if not instruction:
                safe_emit('error', {'message': 'Instruction is required'})
                return
            
            # Run agent in a separate thread
            def run_agent_thread():
                try:
                    wrapper.run_async(instruction, max_steps, auto_continue, socketio)
                except Exception as e:
                    logger.exception("Error in agent thread")
                    safe_emit('agent_error', {
                        'error': str(e),
                        'timestamp': datetime.now().isoformat()
                    })
            
            thread = threading.Thread(target=run_agent_thread)
            thread.daemon = True
            thread.start()
        except Exception as e:
            logger.exception("Exception in handle_run_agent")
            safe_emit('error', {'message': str(e)})

    @socketio.on('stop_agent')
    def handle_stop_agent():
        """Handle agent stop request"""
        try:
            session_id = request.sid
            
            session_data = session_manager.get_session(session_id)
            if not session_data:
                safe_emit('error', {'message': 'Session not found'})
                return
            
            wrapper = session_data['wrapper']
            
            if not wrapper.is_running:
                safe_emit('error', {'message': 'Agent is not running'})
                return
            
            # Stop the agent
            success = wrapper.stop()
            safe_emit('agent_stop_requested', {
                'success': success,
                'timestamp': datetime.now().isoformat()
            })
            # Note: 'agent_stopped' will be emitted by the agent when it actually stops (see run_manager.py)
        except Exception as e:
            logger.exception("Exception in handle_stop_agent")
            safe_emit('error', {'message': str(e)})

    @socketio.on('user_input')
    def handle_user_input(data):
        """Handle user input for running agent"""
        try:
            session_id = request.sid
            
            session_data = session_manager.get_session(session_id)
            if not session_data:
                safe_emit('error', {'message': 'Session not found'})
                return
            
            wrapper = session_data['wrapper']
            
            if not wrapper.is_running:
                safe_emit('error', {'message': 'Agent is not running'})
                return
            
            user_input = data.get('input', '')
            if not user_input:
                safe_emit('error', {'message': 'Input is required'})
                return
            
            # Provide input to the agent
            wrapper.provide_user_input(user_input)
            safe_emit('user_input_sent', {
                'input': user_input,
                'timestamp': datetime.now().isoformat()
            })
        except Exception as e:
            logger.exception("Exception in handle_user_input")
            safe_emit('error', {'message': str(e)})

    @socketio.on('get_status')
    def handle_get_status():
        """Handle status request"""
        try:
            session_id = request.sid
            
            session_data = session_manager.get_session(session_id)
            if not session_data:
                safe_emit('error', {'message': 'Session not found'})
                return
            
            wrapper = session_data['wrapper']
            
            # Load core modules for version info
            core = core_loader.load_core_modules()
            AGENT_VERSION = core['AGENT_VERSION']
            API_PROVIDER = core['API_PROVIDER']
            
            safe_emit('status', {
                'session_id': session_id,
                'is_running': wrapper.is_running,
                'connected_at': session_data['connected_at'],
                'agent_version': AGENT_VERSION,
                'api_provider': API_PROVIDER,
                'output_dir': session_data['output_dir'],
                'timestamp': datetime.now().isoformat()
            })
        except Exception as e:
            logger.exception("Exception in handle_get_status")
            safe_emit('error', {'message': str(e)})

    @socketio.on('get_files')
    def handle_get_files(data=None):
        """Handle request to get list of created files"""
        try:
            session_id = request.sid
            
            session_data = session_manager.get_session(session_id)
            if not session_data:
                safe_emit('error', {'message': 'Session not found'})
                return
            
            wrapper = session_data['wrapper']
            
            # Get created files if run manager exists
            files = []
            if hasattr(wrapper, 'run_manager') and wrapper.run_manager:
                files = wrapper.run_manager.get_created_files()
            
            safe_emit('files_list', {
                'session_id': session_id,
                'files': files,
                'count': len(files),
                'timestamp': datetime.now().isoformat()
            })
        except Exception as e:
            logger.exception("Exception in handle_get_files")
            safe_emit('error', {'message': str(e)})

    @socketio.on('refresh_files')
    def handle_refresh_files():
        """Handle request to refresh/scan for new files"""
        try:
            session_id = request.sid
            
            session_data = session_manager.get_session(session_id)
            if not session_data:
                safe_emit('error', {'message': 'Session not found'})
                return
            
            wrapper = session_data['wrapper']
            
            # Scan for new files if run manager exists
            new_files = []
            if hasattr(wrapper, 'run_manager') and wrapper.run_manager:
                new_files = wrapper.run_manager._scan_for_new_files()
            
            safe_emit('files_refreshed', {
                'session_id': session_id,
                'new_files': new_files,
                'count': len(new_files),
                'timestamp': datetime.now().isoformat()
            })
        except Exception as e:
            logger.exception("Exception in handle_refresh_files")
            safe_emit('error', {'message': str(e)})


def get_session_manager():
    """Get the global session manager"""
    return session_manager 