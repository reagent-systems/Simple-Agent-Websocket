"""
Flask Routes

HTTP endpoints for the SimpleAgent WebSocket server.
"""

from flask import Blueprint
from datetime import datetime

from .core_loader import core_loader
from .event_handlers import get_session_manager

# Create blueprint for routes
api_bp = Blueprint('api', __name__)


@api_bp.route('/health')
def health_check():
    """Health check endpoint"""
    # Load core modules for version info
    core = core_loader.load_core_modules()
    AGENT_VERSION = core['AGENT_VERSION']
    API_PROVIDER = core['API_PROVIDER']
    
    session_manager = get_session_manager()
    
    return {
        'status': 'healthy',
        'agent_version': AGENT_VERSION,
        'api_provider': API_PROVIDER,
        'active_sessions': session_manager.get_session_count(),
        'timestamp': datetime.now().isoformat()
    }


@api_bp.route('/sessions')
def list_sessions():
    """List active sessions"""
    session_manager = get_session_manager()
    sessions = session_manager.list_sessions()
    
    return {
        'sessions': sessions,
        'count': len(sessions),
        'timestamp': datetime.now().isoformat()
    }


@api_bp.route('/version')
def get_version():
    """Get version information"""
    # Load core modules for version info
    core = core_loader.load_core_modules()
    AGENT_VERSION = core['AGENT_VERSION']
    API_PROVIDER = core['API_PROVIDER']
    
    from .. import __version__ as websocket_version
    
    return {
        'websocket_server_version': websocket_version,
        'agent_core_version': AGENT_VERSION,
        'api_provider': API_PROVIDER,
        'timestamp': datetime.now().isoformat()
    } 