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
        import os
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
                                
                                # Scan for new files after tool execution
                                self._scan_for_new_files()
                                
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
            
            # Emit agent_stopped if stopped by user or external request
            if self.stop_requested or self.execution_manager.stop_requested:
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
            # Always restore the original working directory
            if os.getcwd() != original_cwd:
                os.chdir(original_cwd) 

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