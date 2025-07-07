"""
Spines 2.0 - Modular Digital Library
Main entry point
"""
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from utils.config import Config
from utils.logging import setup_logging, get_logger
from web_server import create_app

def main():
    """Main application entry point"""
    # Setup configuration
    config = Config()
    
    # Setup logging
    setup_logging(config.LOG_LEVEL)
    logger = get_logger(__name__)
    
    logger.info("Starting Spines 2.0")
    logger.info(f"Books path: {config.BOOKS_PATH}")
    logger.info(f"Data path: {config.DATA_PATH}")
    logger.info(f"Access mode: {config.ACCESS_MODE}")
    
    # Create Flask app
    app = create_app(config)
    
    # Run server
    logger.info(f"Starting server on {config.HOST}:{config.PORT}")
    app.run(
        host=config.HOST,
        port=config.PORT,
        debug=config.DEBUG,
        threaded=True,  # Enable threading to handle concurrent requests
        use_reloader=False  # Disable auto-reloader to avoid restarts causing connection resets
    )

if __name__ == '__main__':
    main() 