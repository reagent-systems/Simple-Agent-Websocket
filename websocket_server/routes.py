"""
Flask Routes

HTTP endpoints for the SimpleAgent WebSocket server.
"""

import os
from flask import Blueprint, send_file, abort, jsonify, Response
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


@api_bp.route('/sessions/<session_id>/files')
def list_session_files(session_id):
    """List files created by a specific session"""
    session_manager = get_session_manager()
    session_data = session_manager.get_session(session_id)
    
    if not session_data:
        abort(404, description="Session not found")
    
    wrapper = session_data['wrapper']
    if hasattr(wrapper, 'run_manager') and wrapper.run_manager:
        files = wrapper.run_manager.get_created_files()
        return {
            'session_id': session_id,
            'files': files,
            'count': len(files),
            'timestamp': datetime.now().isoformat()
        }
    
    return {
        'session_id': session_id,
        'files': [],
        'count': 0,
        'timestamp': datetime.now().isoformat()
    }


@api_bp.route('/sessions/<session_id>/files/<path:filename>')
def download_session_file(session_id, filename):
    """Download a file created by a specific session"""
    session_manager = get_session_manager()
    session_data = session_manager.get_session(session_id)
    
    if not session_data:
        abort(404, description="Session not found")
    
    # Get the session's output directory
    output_dir = session_data['output_dir']
    file_path = os.path.join(output_dir, filename)
    
    # Security check: ensure the file is within the session's output directory
    if not os.path.abspath(file_path).startswith(os.path.abspath(output_dir)):
        abort(403, description="Access denied")
    
    # Check if file exists
    if not os.path.exists(file_path):
        abort(404, description="File not found")
    
    # Check if this file was created by the agent (optional security check)
    wrapper = session_data['wrapper']
    if hasattr(wrapper, 'run_manager') and wrapper.run_manager:
        created_files = wrapper.run_manager.get_created_files()
        file_allowed = any(f['relative_path'] == filename for f in created_files)
        if not file_allowed:
            abort(403, description="File not created by agent")
    
    try:
        return send_file(
            file_path,
            as_attachment=True,
            download_name=os.path.basename(filename)
        )
    except Exception as e:
        abort(500, description=f"Error downloading file: {str(e)}")


@api_bp.route('/sessions/<session_id>/files/<path:filename>/content')
def view_session_file_content(session_id, filename):
    """View the content of a file created by a specific session"""
    session_manager = get_session_manager()
    session_data = session_manager.get_session(session_id)
    
    if not session_data:
        abort(404, description="Session not found")
    
    # Get the session's output directory
    output_dir = session_data['output_dir']
    file_path = os.path.join(output_dir, filename)
    
    # Security check: ensure the file is within the session's output directory
    if not os.path.abspath(file_path).startswith(os.path.abspath(output_dir)):
        abort(403, description="Access denied")
    
    # Check if file exists
    if not os.path.exists(file_path):
        abort(404, description="File not found")
    
    # Check if this file was created by the agent (optional security check)
    wrapper = session_data['wrapper']
    if hasattr(wrapper, 'run_manager') and wrapper.run_manager:
        created_files = wrapper.run_manager.get_created_files()
        file_allowed = any(f['relative_path'] == filename for f in created_files)
        if not file_allowed:
            abort(403, description="File not created by agent")
    
    try:
        # Read file content
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Determine content type based on file extension
        file_ext = os.path.splitext(filename)[1].lower()
        if file_ext in ['.txt', '.md', '.py', '.js', '.html', '.css', '.json', '.yml', '.yaml']:
            content_type = 'text/plain; charset=utf-8'
        else:
            content_type = 'text/plain; charset=utf-8'
        
        return Response(content, mimetype=content_type)
        
    except UnicodeDecodeError:
        abort(400, description="File is not a text file or has unsupported encoding")
    except Exception as e:
        abort(500, description=f"Error reading file: {str(e)}")


@api_bp.route('/version')
def get_version():
    """Get version information"""
    # Load core modules for version info
    core = core_loader.load_core_modules()
    AGENT_VERSION = core['AGENT_VERSION']
    API_PROVIDER = core['API_PROVIDER']
    
    # Import websocket server version
    try:
        from . import __version__ as websocket_version
    except ImportError:
        websocket_version = "1.0.0"
    
    return {
        'websocket_server_version': websocket_version,
        'agent_core_version': AGENT_VERSION,
        'api_provider': API_PROVIDER,
        'timestamp': datetime.now().isoformat()
    } 