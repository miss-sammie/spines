"""
Logging configuration for Spines 2.0
"""
import logging
import sys
from pathlib import Path

def setup_logging(log_level='INFO'):
    """Setup structured logging for the application"""
    
    # Create logs directory if it doesn't exist
    logs_dir = Path(__file__).parent.parent.parent / 'logs'
    logs_dir.mkdir(exist_ok=True)
    
    # Configure logging format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler
    file_handler = logging.FileHandler(logs_dir / 'spines.log')
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # Reduce noise from some libraries
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('PyPDF2._cmap').setLevel(logging.ERROR)
    
    return root_logger

def get_logger(name):
    """Get a logger for a specific module"""
    return logging.getLogger(name) 