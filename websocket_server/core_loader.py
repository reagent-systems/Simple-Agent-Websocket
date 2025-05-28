"""
Core Loader Module

Handles loading and importing the SimpleAgent core from the git submodule.
This module ensures the core is properly available and provides helpful error messages.
"""

import os
import sys
import logging

logger = logging.getLogger(__name__)


class CoreLoader:
    """Handles loading the SimpleAgent core from the git submodule"""
    
    def __init__(self):
        self.core_path = None
        self.core_loaded = False
        self._core_modules = {}
        
    def setup_core_path(self, base_dir: str = None):
        """Setup the path to the SimpleAgent core"""
        if base_dir is None:
            base_dir = os.path.dirname(os.path.dirname(__file__))
            
        self.core_path = os.path.join(base_dir, 'SimpleAgent')
        
        if os.path.exists(self.core_path):
            sys.path.insert(0, self.core_path)
            logger.info(f"SimpleAgent core path added: {self.core_path}")
            return True
        else:
            self._show_setup_error()
            return False
            
    def _show_setup_error(self):
        """Show helpful error message when core is not found"""
        print("❌ SimpleAgent core not found!")
        print("Please run the setup script first:")
        print("  Linux/Mac: ./setup_submodule.sh")
        print("  Windows: setup_submodule.bat")
        
    def load_core_modules(self):
        """Load and cache core modules"""
        if self.core_loaded:
            return self._core_modules
            
        try:
            # Import core modules
            import commands
            from commands import REGISTERED_COMMANDS, COMMAND_SCHEMAS
            from core.agent import SimpleAgent
            from core.config import (
                OPENAI_API_KEY, MAX_STEPS, API_PROVIDER, 
                API_BASE_URL, GEMINI_API_KEY, create_client, DEFAULT_MODEL
            )
            from core.version import AGENT_VERSION
            from core.run_manager import RunManager
            from core.conversation import ConversationManager
            from core.execution import ExecutionManager
            from core.memory import MemoryManager
            
            # Cache the modules
            self._core_modules = {
                'commands': commands,
                'REGISTERED_COMMANDS': REGISTERED_COMMANDS,
                'COMMAND_SCHEMAS': COMMAND_SCHEMAS,
                'SimpleAgent': SimpleAgent,
                'OPENAI_API_KEY': OPENAI_API_KEY,
                'MAX_STEPS': MAX_STEPS,
                'API_PROVIDER': API_PROVIDER,
                'API_BASE_URL': API_BASE_URL,
                'GEMINI_API_KEY': GEMINI_API_KEY,
                'create_client': create_client,
                'DEFAULT_MODEL': DEFAULT_MODEL,
                'AGENT_VERSION': AGENT_VERSION,
                'RunManager': RunManager,
                'ConversationManager': ConversationManager,
                'ExecutionManager': ExecutionManager,
                'MemoryManager': MemoryManager,
            }
            
            self.core_loaded = True
            logger.info("SimpleAgent core modules loaded successfully")
            return self._core_modules
            
        except ImportError as e:
            print(f"❌ Failed to import SimpleAgent core: {e}")
            print("Please ensure the SimpleAgent core is properly set up.")
            print("Run the setup script:")
            print("  Linux/Mac: ./setup_submodule.sh")
            print("  Windows: setup_submodule.bat")
            sys.exit(1)
            
    def validate_configuration(self):
        """Validate the core configuration"""
        core = self._core_modules
        API_PROVIDER = core['API_PROVIDER']
        
        if API_PROVIDER == "lmstudio":
            if not core['API_BASE_URL']:
                logging.error("Error: API_BASE_URL environment variable not set for LM-Studio provider.")
                logging.info("Please set API_BASE_URL to your LM-Studio endpoint (e.g., http://192.168.0.2:1234/v1)")
                logging.info("You can set it in a .env file or in your environment variables.")
                sys.exit(1)
            logging.info(f"Using LM-Studio provider at: {core['API_BASE_URL']}")
            
        elif API_PROVIDER == "openai":
            if not core['OPENAI_API_KEY']:
                logging.error("Error: OPENAI_API_KEY environment variable not set for OpenAI provider.")
                logging.info("Please set it in a .env file or in your environment variables.")
                sys.exit(1)
            logging.info("Using OpenAI provider")
            
        elif API_PROVIDER == "gemini":
            if not core['GEMINI_API_KEY']:
                logging.error("Error: GEMINI_API_KEY environment variable not set for Gemini provider.")
                logging.info("Please set it in a .env file or in your environment variables.")
                sys.exit(1)
            logging.info("Using Gemini provider")
            
        else:
            logging.error(f"Error: Unknown API_PROVIDER '{API_PROVIDER}'. Supported providers: 'openai', 'lmstudio', 'gemini'")
            sys.exit(1)


# Global core loader instance
core_loader = CoreLoader() 