"""
Configuration management for Spines 2.0
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    def __init__(self):
        # Core paths
        self.BASE_DIR = Path(__file__).parent.parent.parent
        self.BOOKS_PATH = Path(os.getenv('SPINES_BOOKS_PATH', self.BASE_DIR / 'books'))
        self.DATA_PATH = Path(os.getenv('SPINES_DATA_PATH', self.BASE_DIR / 'data'))
        self.TEMP_PATH = Path(os.getenv('SPINES_TEMP_PATH', self.BASE_DIR / 'temp'))
        self.LOGS_PATH = Path(os.getenv('SPINES_LOGS_PATH', self.BASE_DIR / 'logs'))
        
        # Server configuration
        self.HOST = os.getenv('SPINES_HOST', '0.0.0.0')
        self.PORT = int(os.getenv('SPINES_PORT', 8888))
        self.DEBUG = os.getenv('FLASK_DEBUG', '0') in ['1', 'true', 'True', 'TRUE']
        
        # Access control
        self.ACCESS_MODE = os.getenv('SPINES_ACCESS_MODE', 'local')  # local, hybrid, public
        self.PUBLIC_READ_ONLY = os.getenv('SPINES_PUBLIC_READ_ONLY', 'true').lower() == 'true'
        self.ADMIN_USERS = [u.strip() for u in os.getenv('SPINES_ADMIN_USERS', '').split(',') if u.strip()]
        
        # Network configuration
        self.TAILSCALE_PORT = int(os.getenv('SPINES_TAILSCALE_PORT', 8888))
        self.PUBLIC_PORT = int(os.getenv('SPINES_PUBLIC_PORT', 8889))
        self.DOMAIN = os.getenv('SPINES_DOMAIN', 'localhost')
        
        # Logging
        self.LOG_LEVEL = os.getenv('SPINES_LOG_LEVEL', 'INFO')
        
        # Migration settings
        self.MIGRATION_MODE = os.getenv('SPINES_MIGRATION_MODE', 'false').lower() == 'true'
        self.V1_BOOKS_PATH = Path(os.getenv('SPINES_V1_BOOKS_PATH', '../spines/books'))
        self.V1_DATA_PATH = Path(os.getenv('SPINES_V1_DATA_PATH', '../spines/data'))
        
        # Ensure directories exist
        self.ensure_directories()
        
    def ensure_directories(self):
        """Create necessary directories"""
        for path in [self.BOOKS_PATH, self.DATA_PATH, self.TEMP_PATH, self.LOGS_PATH]:
            path.mkdir(parents=True, exist_ok=True)
    
    def is_hybrid_mode(self):
        """Check if running in hybrid access mode"""
        return self.ACCESS_MODE == 'hybrid'
    
    def is_public_mode(self):
        """Check if running in public access mode"""
        return self.ACCESS_MODE == 'public'
    
    def get_library_metadata_path(self):
        """Get path to library metadata file"""
        return self.DATA_PATH / 'library.json' 