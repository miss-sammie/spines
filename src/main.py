"""
spines main entry point
Can run CLI commands or start web server
"""

import sys
import os
from pathlib import Path

def main():
    """Main entry point for spines"""
    
    # If no arguments, start web server
    if len(sys.argv) == 1:
        from src.web_server import create_app
        
        # Use /app paths when running in Docker container
        library_path = "/app/books" if os.path.exists("/app/books") else "./books"
        data_path = "/app/data" if os.path.exists("/app/data") else "./data"
        
        app = create_app(library_path=library_path, data_path=data_path)
        print("🌾 spines server starting...")
        print(f"📚 Library path: {library_path}")
        print("📚 Library accessible at http://localhost:8888")
        app.run(host='0.0.0.0', port=8888, debug=True)
    else:
        # Run CLI
        from src.cli import cli
        cli()

if __name__ == '__main__':
    main() 