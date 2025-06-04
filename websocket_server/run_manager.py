"""
WebSocket Run Manager

Extends the core RunManager to provide WebSocket-based real-time communication
and event emission capabilities.
"""

import json
import time
import queue
import logging
from typing import Dict, Any
from datetime import datetime

from .core_loader import core_loader

logger = logging.getLogger(__name__)


class WebSocketRunManager:
    """
    Enhanced RunManager that emits WebSocket events during execution.
    This extends the core RunManager without modifying it.
    """
    
    def __init__(self, model: str, output_dir: str, session_id: str, socketio_instance):
        # Load core modules
        core = core_loader.load_core_modules()
        RunManager = core['RunManager']
        
        # Initialize the base run manager
        self.run_manager = RunManager(model, output_dir)
        
        # WebSocket specific attributes
        self.session_id = session_id
        self.socketio = socketio_instance
        self.user_input_queue = queue.Queue()
        self.waiting_for_input = False
        self.stop_requested = False
        
        # File tracking
        self.created_files = []
        self.initial_files = set()
        
        # Expose core manager attributes for compatibility
        self.conversation_manager = self.run_manager.conversation_manager
        self.execution_manager = self.run_manager.execution_manager
        self.memory_manager = self.run_manager.memory_manager
        self.summarizer = self.run_manager.summarizer
        self.output_dir = self.run_manager.output_dir
        
        # Initialize file tracking
        self._scan_initial_files()
        
        # Hook into the execution manager to intercept function calls
        self._setup_execution_hooks()
        
    def _setup_execution_hooks(self):
        """Set up hooks to intercept core manager operations for WebSocket events"""
        # Store original methods
        self._original_execute_function = self.execution_manager.execute_function
        self._original_get_next_action = self.execution_manager.get_next_action
        
        # Replace with hooked versions
        self.execution_manager.execute_function = self._hooked_execute_function
        self.execution_manager.get_next_action = self._hooked_get_next_action
        
    def _hooked_execute_function(self, function_name: str, function_args: dict):
        """Hooked version of execute_function that emits WebSocket events"""
        # Call the original function
        result, change = self._original_execute_function(function_name, function_args)
        
        # Emit tool call event
        self.emit_tool_call(function_name, function_args, str(result))
        
        # Scan for new files after tool execution
        self._scan_for_new_files()
        
        return result, change
        
    def _hooked_get_next_action(self, conversation_history):
        """Hooked version of get_next_action that emits assistant messages"""
        # Call the original function
        assistant_message = self._original_get_next_action(conversation_history)
        
        # Emit assistant message if there's content
        if assistant_message and hasattr(assistant_message, 'content') and assistant_message.content:
            self.emit_assistant_message(assistant_message.content)
        elif assistant_message and isinstance(assistant_message, dict) and 'content' in assistant_message:
            self.emit_assistant_message(assistant_message['content'])
            
        return assistant_message
        
    def emit_message(self, event: str, data: Dict[str, Any]):
        """Emit a message to the WebSocket client with error handling"""
        try:
            if self.socketio and self.session_id:
                self.socketio.emit(event, data, room=self.session_id)
        except Exception as e:
            logger.warning(f"Failed to emit WebSocket event '{event}' to session {self.session_id}: {e}")
            # Don't re-raise the exception to avoid breaking the agent execution
        
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
        This wraps the core RunManager's run method with WebSocket events.
        """
        # Reset stop flag
        self.stop_requested = False
        
        # Emit start event
        self.emit_message('agent_started', {
            'instruction': user_instruction,
            'max_steps': max_steps,
            'auto_continue': auto_continue,
            'output_dir': self.output_dir,
            'timestamp': datetime.now().isoformat()
        })
        
        try:
            # Hook into the core run manager's print statements to emit WebSocket events
            # We'll need to patch the input function to use our WebSocket input
            import builtins
            original_input = builtins.input
            original_print = builtins.print
            
            def websocket_input(prompt=""):
                """Replace input() calls with WebSocket input"""
                return self.get_user_input(prompt)
                
            def websocket_print(*args, **kwargs):
                """Capture print statements and optionally emit them"""
                # Call original print
                original_print(*args, **kwargs)
                
                # Parse print content for specific events
                if args:
                    text = ' '.join(str(arg) for arg in args)
                    
                    # Detect step transitions
                    if "--- Step" in text:
                        try:
                            # Extract step info: "--- Step 1/10 ---"
                            parts = text.split()
                            step_part = [p for p in parts if '/' in p][0]
                            step, max_steps = map(int, step_part.split('/'))
                            self.emit_step_start(step, max_steps)
                        except:
                            pass  # Ignore parsing errors
                            
                    # Detect task completion
                    elif "✅ Task completed" in text:
                        self.emit_message('task_completed', {
                            'message': 'Task completed successfully',
                            'timestamp': datetime.now().isoformat()
                        })
                        
                    # Detect directory changes
                    elif "🔄 Changed working directory to:" in text:
                        self.emit_message('directory_changed', {
                            'directory': text.split("🔄 Changed working directory to: ")[-1],
                            'timestamp': datetime.now().isoformat()
                        })
                        
                    # Detect auto-continue messages
                    elif "🔄 Auto-continuing" in text:
                        self.emit_message('auto_continue', {
                            'message': 'Auto-continuing execution',
                            'timestamp': datetime.now().isoformat()
                        })
                        
                    # Detect warnings
                    elif "⚠️" in text:
                        self.emit_message('warning', {
                            'message': text,
                            'timestamp': datetime.now().isoformat()
                        })
            
            # Patch built-in functions
            builtins.input = websocket_input
            builtins.print = websocket_print
            
            try:
                # Call the core run manager's run method
                # This will handle all the prompting, conversation management, etc.
                self.run_manager.run(user_instruction, max_steps, auto_continue)
                
                # Check if we were stopped externally
                if self.stop_requested:
                    self.emit_message('agent_stopped', {
                        'message': 'Agent was stopped by user or external request',
                        'timestamp': datetime.now().isoformat()
                    })
                else:
                    self.emit_message('agent_finished', {
                        'message': 'Agent execution completed',
                        'timestamp': datetime.now().isoformat()
                    })
                    
            finally:
                # Restore original functions
                builtins.input = original_input
                builtins.print = original_print
                
        except Exception as e:
            self.emit_message('execution_error', {
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
            raise

    def _scan_initial_files(self):
        """Scan the output directory for initial files"""
        import os
        try:
            if os.path.exists(self.output_dir):
                for root, dirs, files in os.walk(self.output_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        self.initial_files.add(file_path)
        except Exception as e:
            logger.warning(f"Failed to scan initial files: {e}")
    
    def _scan_for_new_files(self):
        """Scan for new files created since initialization"""
        import os
        new_files = []
        try:
            if os.path.exists(self.output_dir):
                for root, dirs, files in os.walk(self.output_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        if file_path not in self.initial_files and file_path not in [f['path'] for f in self.created_files]:
                            # Get file info
                            stat = os.stat(file_path)
                            relative_path = os.path.relpath(file_path, self.output_dir)
                            
                            file_info = {
                                'path': file_path,
                                'relative_path': relative_path,
                                'name': file,
                                'size': stat.st_size,
                                'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
                            }
                            
                            new_files.append(file_info)
                            self.created_files.append(file_info)
                            
                            # Emit file creation event
                            self.emit_file_created(file_info)
                            
        except Exception as e:
            logger.warning(f"Failed to scan for new files: {e}")
            
        return new_files
    
    def emit_file_created(self, file_info: dict):
        """Emit file creation event with only the required fields"""
        # Build the minimal file object
        file_payload = {
            'name': file_info.get('name'),
            'size': file_info.get('size'),
            'created': file_info.get('created'),
            'modified': file_info.get('modified')
        }
        # Always include at least name and size
        if not file_payload['name'] or file_payload['size'] is None:
            # Do not emit if required fields are missing
            return
        self.emit_message('file_created', {
            'file': file_payload,
            'session_id': self.session_id
        })
    
    def get_created_files(self):
        """Get list of all created files"""
        return self.created_files.copy() 