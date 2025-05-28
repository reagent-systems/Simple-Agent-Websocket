"""
Simple-Agent-Websocket Server

A lightweight WebSocket wrapper around the SimpleAgent core that provides
real-time web interface capabilities without duplicating the core codebase.

This server acts as a thin layer that:
1. Imports the SimpleAgent core from the git submodule
2. Wraps the core functionality with WebSocket events
3. Provides bidirectional communication for web UIs
"""

import os
import sys
import json
import time
import uuid
import logging
import threading
import queue
from typing import Dict, Any, Optional
from flask import Flask, request
from flask_socketio import SocketIO, emit, disconnect
from datetime import datetime

# Add the SimpleAgent core to the Python path
CORE_PATH = os.path.join(os.path.dirname(__file__), 'SimpleAgent')
if os.path.exists(CORE_PATH):
    sys.path.insert(0, CORE_PATH)
else:
    print("❌ SimpleAgent core not found!")
    print("Please run the setup script first:")
    print("  Linux/Mac: ./setup_submodule.sh")
    print("  Windows: setup_submodule.bat")
    sys.exit(1)

# Set up basic logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logging.getLogger("httpx").setLevel(logging.WARNING)

try:
    # Import from SimpleAgent core
    import commands
    from commands import REGISTERED_COMMANDS, COMMAND_SCHEMAS
    from core.agent import SimpleAgent
    from core.config import OPENAI_API_KEY, MAX_STEPS, API_PROVIDER, API_BASE_URL, GEMINI_API_KEY, create_client
    from core.version import AGENT_VERSION
    from core.run_manager import RunManager
    from core.conversation import ConversationManager
    from core.execution import ExecutionManager
    from core.memory import MemoryManager
except ImportError as e:
    print(f"❌ Failed to import SimpleAgent core: {e}")
    print("Please ensure the SimpleAgent core is properly set up.")
    print("Run the setup script:")
    print("  Linux/Mac: ./setup_submodule.sh")
    print("  Windows: setup_submodule.bat")
    sys.exit(1)

# Check for proper configuration based on API provider
if API_PROVIDER == "lmstudio":
    if not API_BASE_URL:
        logging.error("Error: API_BASE_URL environment variable not set for LM-Studio provider.")
        logging.info("Please set API_BASE_URL to your LM-Studio endpoint (e.g., http://192.168.0.2:1234/v1)")
        logging.info("You can set it in a .env file or in your environment variables.")
        sys.exit(1)
    logging.info(f"Using LM-Studio provider at: {API_BASE_URL}")
elif API_PROVIDER == "openai":
    if not OPENAI_API_KEY:
        logging.error("Error: OPENAI_API_KEY environment variable not set for OpenAI provider.")
        logging.info("Please set it in a .env file or in your environment variables.")
        sys.exit(1)
    logging.info("Using OpenAI provider")
elif API_PROVIDER == "gemini":
    if not GEMINI_API_KEY:
        logging.error("Error: GEMINI_API_KEY environment variable not set for Gemini provider.")
        logging.info("Please set it in a .env file or in your environment variables.")
        sys.exit(1)
    logging.info("Using Gemini provider")
else:
    logging.error(f"Error: Unknown API_PROVIDER '{API_PROVIDER}'. Supported providers: 'openai', 'lmstudio', 'gemini'")
    sys.exit(1)

# Initialize Flask app and SocketIO
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'simple-agent-websocket-secret')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Global storage for agent sessions
agent_sessions: Dict[str, Dict[str, Any]] = {}


class WebSocketRunManager(RunManager):
    """
    Enhanced RunManager that emits WebSocket events during execution.
    This extends the core RunManager without modifying it.
    """
    
    def __init__(self, model: str, output_dir: str, session_id: str, socketio_instance):
        super().__init__(model, output_dir)
        self.session_id = session_id
        self.socketio = socketio_instance
        self.user_input_queue = queue.Queue()
        self.waiting_for_input = False
        self.stop_requested = False
        
    def emit_message(self, event: str, data: Dict[str, Any]):
        """Emit a message to the WebSocket client"""
        self.socketio.emit(event, data, room=self.session_id)
        
    def emit_step_start(self, step: int, max_steps: int):
        """Emit step start event"""
        self.emit_message('step_start', {
            'step': step,
            'max_steps': max_steps,
            'timestamp': datetime.now().isoformat()
        })
        
    def emit_assistant_message(self, content: str):
        """Emit assistant message"""
        self.emit_message('assistant_message', {
            'content': content,
            'timestamp': datetime.now().isoformat()
        })
        
    def emit_tool_call(self, function_name: str, function_args: dict, result: str):
        """Emit tool call execution"""
        self.emit_message('tool_call', {
            'function_name': function_name,
            'function_args': function_args,
            'result': result,
            'timestamp': datetime.now().isoformat()
        })
        
    def emit_step_summary(self, summary: str):
        """Emit step summary"""
        self.emit_message('step_summary', {
            'summary': summary,
            'timestamp': datetime.now().isoformat()
        })
        
    def emit_waiting_for_input(self, prompt: str):
        """Emit waiting for input event"""
        self.waiting_for_input = True
        self.emit_message('waiting_for_input', {
            'prompt': prompt,
            'timestamp': datetime.now().isoformat()
        })
        
    def get_user_input(self, prompt: str = "") -> str:
        """Get user input via WebSocket"""
        self.emit_waiting_for_input(prompt)
        
        # Wait for user input
        try:
            user_input = self.user_input_queue.get(timeout=300)  # 5 minute timeout
            self.waiting_for_input = False
            return user_input
        except queue.Empty:
            self.waiting_for_input = False
            return "n"  # Default to stop if no input received
            
    def provide_user_input(self, user_input: str):
        """Provide user input from WebSocket"""
        if self.waiting_for_input:
            self.user_input_queue.put(user_input)
            
    def run(self, user_instruction: str, max_steps: int = 10, auto_continue: int = 0):
        """
        Enhanced run method with WebSocket integration.
        This overrides the parent run method to add WebSocket events.
        """
        # Reset stop flag
        self.execution_manager.stop_requested = False
        self.stop_requested = False
        
        # Emit start event
        self.emit_message('agent_started', {
            'instruction': user_instruction,
            'max_steps': max_steps,
            'auto_continue': auto_continue,
            'output_dir': self.output_dir,
            'timestamp': datetime.now().isoformat()
        })
        
        # Get current date and time information for the system message
        current_datetime = time.strftime("%Y-%m-%d %H:%M:%S")
        current_year = time.strftime("%Y")
        
        # Save and change to the output directory
        original_cwd = os.getcwd()
        
        try:
            # Change to the output directory so all operations happen there
            if os.path.exists(self.output_dir):
                os.chdir(self.output_dir)
                self.emit_message('directory_changed', {
                    'directory': os.getcwd(),
                    'timestamp': datetime.now().isoformat()
                })
            
            # Clear the conversation history and start fresh
            self.conversation_manager.clear()
            
            # Create system message
            system_message_content = f"""You are an AI agent that can manage its own execution steps.
You are currently running with the following capabilities:
- You can stop execution early if the task is complete
- You can continue automatically if more steps are needed
- You should be mindful of the current step number and total steps available

Current date and time: {current_datetime}
Your knowledge cutoff might be earlier, but you should consider the current date when processing tasks.
Always work with the understanding that it is now {current_year} when handling time-sensitive information.

When responding:
1. Always consider if the task truly needs more steps
2. If a task is complete, include phrases like "task complete", "all done", "finished", or "completed successfully"
3. If you need more steps than allocated, make this clear in your response

Current execution context:
- Auto-continue is {"enabled" if auto_continue > 0 else "disabled"}
"""
            
            self.conversation_manager.add_message("system", system_message_content)
            
            # Add the user instruction to the conversation
            self.conversation_manager.add_message("user", user_instruction)
            
            # Track changes for summarization
            changes_made = []
            step_changes = []
            
            # Run the agent loop
            step = 0
            auto_steps_remaining = 0 if auto_continue is None else auto_continue
            
            while step < max_steps and not self.stop_requested and not self.execution_manager.stop_requested:
                try:
                    step += 1
                    self.emit_step_start(step, max_steps)
                    
                    # Get current date and time for the system message
                    current_datetime = time.strftime("%Y-%m-%d %H:%M:%S")
                    current_year = time.strftime("%Y")
                    
                    # Update system message with current step info
                    if auto_steps_remaining == -1:
                        auto_status = "enabled (infinite)"
                        auto_mode_guidance = """IMPORTANT: You are running in AUTO-CONTINUE mode with infinite steps. 
Do NOT ask the user questions or for input during task execution. 
Instead, make decisions independently and proceed with executing the task to completion.
Your goal is to complete the requested task fully without human intervention."""
                    elif auto_steps_remaining > 0:
                        auto_status = f"enabled ({auto_steps_remaining} steps remaining)"
                        auto_mode_guidance = """IMPORTANT: You are running in AUTO-CONTINUE mode.
Do NOT ask the user questions or for input during task execution.
Instead, make decisions independently and proceed with executing the task.
Your goal is to complete as much of the task as possible without human intervention."""
                    else:
                        auto_status = "disabled"
                        auto_mode_guidance = """You are running in MANUAL mode.
If you need user input, make it clear by using phrases like "do you need", "would you like", etc.
The user will be prompted after each step to continue or provide new instructions."""
                    
                    # Update the system message
                    updated_system_content = f"""You are an AI agent that can manage its own execution steps.
You are currently running with the following capabilities:
- You can stop execution early if the task is complete
- You can continue automatically if more steps are needed
- You should be mindful of the current step number and total steps available

Current date and time: {current_datetime}
Your knowledge cutoff might be earlier, but you should consider the current date when processing tasks.
Always work with the understanding that it is now {current_year} when handling time-sensitive information.

When responding:
1. Always consider if the task truly needs more steps
2. If a task is complete, include phrases like "task complete", "all done", "finished", or "completed successfully"
3. If you need more steps than allocated, make this clear in your response

{auto_mode_guidance}

Current execution context:
- You are on step {step} of {max_steps} total steps
- Auto-continue is {auto_status}
"""
                    self.conversation_manager.update_system_message(updated_system_content)
                    
                    try:
                        # Get the next action from the model
                        assistant_message = self.execution_manager.get_next_action(
                            self.conversation_manager.get_history()
                        )
                        
                        if not assistant_message:
                            self.emit_message('error', {
                                'message': 'Failed to get a response from the model',
                                'timestamp': datetime.now().isoformat()
                            })
                            break
                            
                        # Extract and emit assistant content
                        content = None
                        if hasattr(assistant_message, 'content'):
                            content = assistant_message.content
                        elif isinstance(assistant_message, dict) and 'content' in assistant_message:
                            content = assistant_message['content']
                            
                        if content:
                            self.emit_assistant_message(content)
                        
                        # Create a proper assistant message for the conversation history
                        message_dict = {"role": "assistant"}
                        if content:
                            message_dict["content"] = content
                        
                        # Add tool calls if present
                        if hasattr(assistant_message, 'tool_calls') and assistant_message.tool_calls:
                            message_dict["tool_calls"] = [
                                {
                                    "id": tool_call.id,
                                    "type": "function",
                                    "function": {
                                        "name": tool_call.function.name,
                                        "arguments": tool_call.function.arguments
                                    }
                                } for tool_call in assistant_message.tool_calls
                            ]
                        
                        # Add the complete assistant message to the conversation
                        self.conversation_manager.conversation_history.append(message_dict)
                        
                        # Reset step changes
                        step_changes = []
                        
                        # Handle any tool calls
                        if hasattr(assistant_message, 'tool_calls') and assistant_message.tool_calls:
                            for tool_call in assistant_message.tool_calls:
                                function_name = tool_call.function.name
                                function_args = json.loads(tool_call.function.arguments)
                                
                                # Execute the function
                                function_response, change = self.execution_manager.execute_function(
                                    function_name, function_args
                                )
                                
                                # Emit tool call execution
                                self.emit_tool_call(function_name, function_args, str(function_response))
                                
                                # Track changes if any were made
                                if change:
                                    changes_made.append(change)
                                    step_changes.append(change)
                                
                                # Add the function call and response to the conversation
                                self.conversation_manager.add_message(
                                    "tool", 
                                    str(function_response), 
                                    tool_call_id=tool_call.id,
                                    name=function_name
                                )
                        
                        # Generate a summary of changes for this step if any were made
                        if step_changes:
                            step_summary = self.summarizer.summarize_changes(step_changes, is_step_summary=True)
                            if step_summary:
                                self.emit_step_summary(step_summary)
                        
                        # Check if the agent is done or needs to continue
                        should_continue = True
                        needs_more_steps = False
                        
                        if content:
                            content_lower = content.lower()
                            
                            # Check for completion phrases
                            if any(phrase in content_lower for phrase in [
                                "task complete",
                                "i've completed",
                                "all done",
                                "finished",
                                "completed successfully"
                            ]):
                                self.emit_message('task_completed', {
                                    'message': 'Task completed successfully',
                                    'timestamp': datetime.now().isoformat()
                                })
                                break
                                
                            # Check if the assistant is just waiting for input
                            elif not hasattr(assistant_message, 'tool_calls') and any(phrase in content_lower for phrase in [
                                "do you need",
                                "would you like",
                                "let me know",
                                "please specify",
                                "can you clarify",
                                "if you need"
                            ]):
                                # Only set should_continue to False in manual mode
                                if auto_steps_remaining == 0:  # Only in manual mode
                                    should_continue = False
                                    
                            # Check if more steps are needed
                            elif any(phrase in content_lower for phrase in [
                                "need more steps",
                                "additional steps required",
                                "more steps needed",
                                "cannot complete within current steps"
                            ]):
                                needs_more_steps = True
                        
                        # Handle continuation logic
                        if step < max_steps and should_continue and not self.stop_requested and not self.execution_manager.stop_requested:
                            # Handle auto-continue
                            if auto_steps_remaining == -1 or auto_steps_remaining > 0:
                                if auto_steps_remaining > 0:
                                    auto_steps_remaining -= 1
                                
                                # Check if the model is asking a question in auto mode
                                if not hasattr(assistant_message, 'tool_calls') and content and any(phrase in content_lower for phrase in [
                                    "do you need", "would you like", "let me know", "please specify", 
                                    "can you clarify", "if you need", "what would you like", "your preference",
                                    "should i", "do you want"
                                ]):
                                    # Add an automatic 'y' response in auto-mode
                                    self.conversation_manager.add_message("user", "y")
                                    self.emit_message('auto_continue', {
                                        'message': 'Auto-continuing with "y" response',
                                        'timestamp': datetime.now().isoformat()
                                    })
                                
                                if needs_more_steps:
                                    self.emit_message('warning', {
                                        'message': 'Task requires more steps than currently allocated',
                                        'timestamp': datetime.now().isoformat()
                                    })
                                
                                continue
                            
                            # Manual mode - request user input
                            if not should_continue:
                                self.emit_message('step_completed', {
                                    'message': 'No further actions needed',
                                    'timestamp': datetime.now().isoformat()
                                })
                                break
                            else:
                                user_input = self.get_user_input("Enter your next instruction, 'y' to continue with current task, or 'n' to stop")
                                
                                # Normalize the input
                                normalized_input = user_input.strip().lower()
                                
                                if normalized_input == 'n':
                                    self.emit_message('user_stopped', {
                                        'message': 'User requested to stop',
                                        'timestamp': datetime.now().isoformat()
                                    })
                                    break
                                elif normalized_input == 'y':
                                    # Simply continue
                                    continue
                                else:
                                    # Add the custom message to the conversation
                                    self.conversation_manager.add_message("user", user_input)
                                    self.emit_message('user_input_received', {
                                        'input': user_input,
                                        'timestamp': datetime.now().isoformat()
                                    })
                        else:
                            # If we're at max steps or have nothing more to do, break
                            if not should_continue:
                                self.emit_message('step_completed', {
                                    'message': 'No further actions needed',
                                    'timestamp': datetime.now().isoformat()
                                })
                            elif needs_more_steps:
                                self.emit_message('warning', {
                                    'message': 'Reached maximum steps but task requires more steps',
                                    'timestamp': datetime.now().isoformat()
                                })
                            break
                    
                    except Exception as e:
                        self.emit_message('step_error', {
                            'error': str(e),
                            'step': step,
                            'timestamp': datetime.now().isoformat()
                        })
                        break
                
                except Exception as e:
                    self.emit_message('execution_error', {
                        'error': str(e),
                        'step': step,
                        'timestamp': datetime.now().isoformat()
                    })
                    break
            
            # Generate a final summary of all changes
            if changes_made:
                final_summary = self.summarizer.summarize_changes(changes_made)
                self.emit_message('final_summary', {
                    'summary': final_summary,
                    'timestamp': datetime.now().isoformat()
                })
            
            # Save the memory
            self.memory_manager.add_conversation(self.conversation_manager.get_history())
            self.memory_manager.save_memory()
            
            self.emit_message('agent_finished', {
                'message': 'Agent execution completed',
                'timestamp': datetime.now().isoformat()
            })
            
        finally:
            # Always restore the original working directory
            if os.getcwd() != original_cwd:
                os.chdir(original_cwd)


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
        
    def run_async(self, instruction: str, max_steps: int = 10, auto_continue: int = 0):
        """Run the agent asynchronously and emit progress updates"""
        self.is_running = True
        self.stop_requested = False
        
        try:
            # Create WebSocket-enabled run manager
            self.run_manager = WebSocketRunManager(
                model=self.model,
                output_dir=self.output_dir,
                session_id=self.session_id,
                socketio_instance=socketio
            )
            
            # Run the agent
            self.run_manager.run(instruction, max_steps, auto_continue)
            
        except Exception as e:
            logging.error(f"Error in agent execution: {e}")
            socketio.emit('agent_error', {
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


@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    session_id = request.sid
    logging.info(f"Client connected: {session_id}")
    
    # Create a unique output directory for this session
    base_output_dir = os.path.abspath('output')
    if not os.path.exists(base_output_dir):
        os.makedirs(base_output_dir)
    
    run_id = str(uuid.uuid4())[:8]
    version_folder = 'v' + '_'.join(AGENT_VERSION.lstrip('v').split('.'))
    session_output_dir = os.path.join(base_output_dir, f"{version_folder}_{session_id}_{run_id}")
    os.makedirs(session_output_dir, exist_ok=True)
    
    # Initialize agent wrapper for this session
    from core.config import DEFAULT_MODEL
    wrapper = WebSocketAgentWrapper(session_id, session_output_dir, DEFAULT_MODEL)
    
    # Store session data
    agent_sessions[session_id] = {
        'wrapper': wrapper,
        'output_dir': session_output_dir,
        'connected_at': datetime.now().isoformat()
    }
    
    # Send connection confirmation
    emit('connected', {
        'session_id': session_id,
        'agent_version': AGENT_VERSION,
        'api_provider': API_PROVIDER,
        'output_dir': session_output_dir,
        'timestamp': datetime.now().isoformat()
    })


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    session_id = request.sid
    logging.info(f"Client disconnected: {session_id}")
    
    # Clean up session data
    if session_id in agent_sessions:
        session_data = agent_sessions[session_id]
        wrapper = session_data['wrapper']
        
        # Stop any running agent
        if wrapper.is_running:
            wrapper.stop()
        
        # Remove session
        del agent_sessions[session_id]


@socketio.on('run_agent')
def handle_run_agent(data):
    """Handle agent run request"""
    session_id = request.sid
    
    if session_id not in agent_sessions:
        emit('error', {'message': 'Session not found'})
        return
    
    session_data = agent_sessions[session_id]
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
        wrapper.run_async(instruction, max_steps, auto_continue)
    
    thread = threading.Thread(target=run_agent_thread)
    thread.daemon = True
    thread.start()


@socketio.on('stop_agent')
def handle_stop_agent():
    """Handle agent stop request"""
    session_id = request.sid
    
    if session_id not in agent_sessions:
        emit('error', {'message': 'Session not found'})
        return
    
    session_data = agent_sessions[session_id]
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
    
    if session_id not in agent_sessions:
        emit('error', {'message': 'Session not found'})
        return
    
    session_data = agent_sessions[session_id]
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
    
    if session_id not in agent_sessions:
        emit('error', {'message': 'Session not found'})
        return
    
    session_data = agent_sessions[session_id]
    wrapper = session_data['wrapper']
    
    emit('status', {
        'session_id': session_id,
        'is_running': wrapper.is_running,
        'connected_at': session_data['connected_at'],
        'agent_version': AGENT_VERSION,
        'api_provider': API_PROVIDER,
        'output_dir': session_data['output_dir'],
        'timestamp': datetime.now().isoformat()
    })


@app.route('/health')
def health_check():
    """Health check endpoint"""
    return {
        'status': 'healthy',
        'agent_version': AGENT_VERSION,
        'api_provider': API_PROVIDER,
        'active_sessions': len(agent_sessions),
        'timestamp': datetime.now().isoformat()
    }


@app.route('/sessions')
def list_sessions():
    """List active sessions"""
    sessions = []
    for session_id, session_data in agent_sessions.items():
        sessions.append({
            'session_id': session_id,
            'connected_at': session_data['connected_at'],
            'is_running': session_data['wrapper'].is_running,
            'output_dir': session_data['output_dir']
        })
    
    return {
        'sessions': sessions,
        'count': len(sessions),
        'timestamp': datetime.now().isoformat()
    }


def main():
    """Main function to start the WebSocket server"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Simple-Agent-Websocket Server')
    parser.add_argument('--host', default='localhost', help='Host to bind to (default: localhost)')
    parser.add_argument('--port', type=int, default=5000, help='Port to bind to (default: 5000)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--eager-loading', action='store_true',
                      help='Use eager loading (load all tools at startup) instead of dynamic loading')
    
    args = parser.parse_args()
    
    # Initialize commands based on user preference
    dynamic_loading = not args.eager_loading
    print(f"🔧 Initializing tools with {'dynamic' if dynamic_loading else 'eager'} loading...")
    commands.init(dynamic=dynamic_loading)
    
    try:
        print(f"🚀 Starting Simple-Agent-Websocket Server...")
        print(f"📡 Server will be available at: http://{args.host}:{args.port}")
        print(f"🔌 WebSocket endpoint: ws://{args.host}:{args.port}/socket.io/")
        print(f"🏥 Health check: http://{args.host}:{args.port}/health")
        print(f"📊 Sessions endpoint: http://{args.host}:{args.port}/sessions")
        print(f"🤖 Agent version: {AGENT_VERSION}")
        print(f"🔗 API provider: {API_PROVIDER}")
        print(f"💬 Features: Real-time step updates, bidirectional communication")
        print(f"📦 Core: SimpleAgent from git submodule")
        
        # Start the server
        socketio.run(
            app,
            host=args.host,
            port=args.port,
            debug=args.debug,
            use_reloader=False  # Disable reloader to prevent issues with threading
        )
    finally:
        # Clean up tool manager resources
        commands.cleanup()


if __name__ == "__main__":
    main() 