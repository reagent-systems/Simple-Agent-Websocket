"""
WebSocket Agent Wrapper

Wrapper class that adapts SimpleAgent for WebSocket communication.
Manages agent sessions and threading.
"""

import os
import uuid
import logging
import threading
from datetime import datetime

from .core_loader import core_loader
from .run_manager import WebSocketRunManager

logger = logging.getLogger(__name__)


class WebSocketAgentWrapper:
    """
    Wrapper class that adapts SimpleAgent for WebSocket communication.
    """
    
    def __init__(self, session_id: str, output_dir: str, model: str = None):
        self.session_id = session_id
        self.output_dir = output_dir
        self.model = model
        self.is_running = False
        self.stop_requested = False
        self.run_manager = None
        
    def run_async(self, instruction: str, max_steps: int = 10, auto_continue: int = 0, socketio_instance=None):
        """Run the agent asynchronously and emit progress updates"""
        self.is_running = True
        self.stop_requested = False
        
        try:
            # Create WebSocket-enabled run manager
            self.run_manager = WebSocketRunManager(
                model=self.model,
                output_dir=self.output_dir,
                session_id=self.session_id,
                socketio_instance=socketio_instance
            )
            
            # Run the agent
            self.run_manager.run(instruction, max_steps, auto_continue)
            
        except Exception as e:
            logger.error(f"Error in agent execution: {e}")
            if socketio_instance:
                socketio_instance.emit('agent_error', {
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                }, room=self.session_id)
        finally:
            self.is_running = False
    
    def stop(self):
        """Request the agent to stop"""
        self.stop_requested = True
        if self.run_manager:
            self.run_manager.stop_requested = True
            if hasattr(self.run_manager, 'execution_manager'):
                self.run_manager.execution_manager.stop_requested = True
        return True
        
    def provide_user_input(self, user_input: str):
        """Provide user input to the running agent"""
        if self.run_manager and self.is_running:
            self.run_manager.provide_user_input(user_input)


class SessionManager:
    """Manages WebSocket agent sessions"""
    
    def __init__(self):
        self.sessions = {}
        
    def create_session(self, session_id: str, model: str = None):
        """Create a new agent session"""
        # Load core modules to get version info
        core = core_loader.load_core_modules()
        AGENT_VERSION = core['AGENT_VERSION']
        DEFAULT_MODEL = core['DEFAULT_MODEL']
        
        # Create a unique output directory for this session
        base_output_dir = os.path.abspath('output')
        if not os.path.exists(base_output_dir):
            os.makedirs(base_output_dir)
        
        run_id = str(uuid.uuid4())[:8]
        version_folder = 'v' + '_'.join(AGENT_VERSION.lstrip('v').split('.'))
        session_output_dir = os.path.join(base_output_dir, f"{version_folder}_{session_id}_{run_id}")
        os.makedirs(session_output_dir, exist_ok=True)
        
        # Initialize agent wrapper for this session
        wrapper = WebSocketAgentWrapper(
            session_id=session_id, 
            output_dir=session_output_dir, 
            model=model or DEFAULT_MODEL
        )
        
        # Store session data
        self.sessions[session_id] = {
            'wrapper': wrapper,
            'output_dir': session_output_dir,
            'connected_at': datetime.now().isoformat()
        }
        
        logger.info(f"Created session {session_id} with output dir: {session_output_dir}")
        return self.sessions[session_id]
        
    def get_session(self, session_id: str):
        """Get an existing session"""
        return self.sessions.get(session_id)
        
    def remove_session(self, session_id: str):
        """Remove a session"""
        if session_id in self.sessions:
            session_data = self.sessions[session_id]
            wrapper = session_data['wrapper']
            
            # Stop any running agent
            if wrapper.is_running:
                wrapper.stop()
            
            # Remove session
            del self.sessions[session_id]
            logger.info(f"Removed session {session_id}")
            
    def list_sessions(self):
        """List all active sessions"""
        sessions = []
        for session_id, session_data in self.sessions.items():
            sessions.append({
                'session_id': session_id,
                'connected_at': session_data['connected_at'],
                'is_running': session_data['wrapper'].is_running,
                'output_dir': session_data['output_dir']
            })
        return sessions
        
    def get_session_count(self):
        """Get the number of active sessions"""
        return len(self.sessions) 