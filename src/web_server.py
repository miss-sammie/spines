"""
Spines 2.0 Web Server
Minimal Flask app factory - no more 5,418-line monoliths!
"""
from flask import Flask
from utils.logging import get_logger
from utils.auth import AccessControl
from services.book_service import BookService
from services.text_service import TextService
from services.file_service import FileService
from services.review_service import ReviewService
from services.ocr_service import OCRService
from services.database_service import DatabaseService
from routes.main import main_bp
from routes.admin import admin_bp
from routes.collections import collections_bp

from api.books import books_api
from api.library import library_api
from api.files import files_api
from api.review import review_api
from api.ocr import ocr_api

logger = get_logger(__name__)

def create_app(config):
    """Create and configure Flask application"""
    
    # Set template and static folders using absolute paths
    import os
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    app = Flask(__name__, 
                template_folder=os.path.join(base_dir, 'static', 'templates'),
                static_folder=os.path.join(base_dir, 'static'))
    
    # Store config in app for access in routes
    app.config.update({
        'SPINES_CONFIG': config,
        'ACCESS_MODE': config.ACCESS_MODE,
        'PUBLIC_READ_ONLY': config.PUBLIC_READ_ONLY,
        'ADMIN_USERS': config.ADMIN_USERS
    })
    
    # Setup services and attach to app
    app.book_service = BookService(config)
    app.text_service = TextService(config)
    app.file_service = FileService(config)
    app.review_service = ReviewService(config)
    app.ocr_service = OCRService(config)
    app.database_service = DatabaseService(config)
    
    # Pass services to MetadataExtractor
    from metadata_extractor import MetadataExtractor
    app.extractor = MetadataExtractor(config, book_service=app.book_service, text_service=app.text_service)
    
    # Setup access control
    access_control = AccessControl(app)
    app.access_control = access_control
    
    # Register blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)
    # Collections blueprint (API)
    app.register_blueprint(collections_bp, url_prefix="/api")
    app.register_blueprint(books_api, url_prefix='/api')
    app.register_blueprint(library_api, url_prefix='/api')
    app.register_blueprint(files_api, url_prefix='/api')
    app.register_blueprint(review_api, url_prefix='/api')
    app.register_blueprint(ocr_api, url_prefix='/api')
    
    # Health check endpoint
    @app.route('/api/health')
    def health_check():
        return {
            'status': 'healthy',
            'version': '2.0',
            'access_mode': config.ACCESS_MODE
        }
    
    # Database migration management endpoints
    @app.route('/api/database/status')
    def database_status():
        """Get database status and migration information"""
        try:
            sqlite_enabled = app.database_service.use_sqlite
            sqlite_exists = app.database_service.db_path.exists()
            json_count = len(app.book_service.load_library().get('books', {}))
            sqlite_count = app.database_service.count_books() if sqlite_exists else 0
            
            return {
                'sqlite_enabled': sqlite_enabled,
                'sqlite_exists': sqlite_exists,
                'json_books': json_count,
                'sqlite_books': sqlite_count,
                'migration_ready': sqlite_exists and sqlite_count > 0,
                'current_source': 'sqlite' if sqlite_enabled and sqlite_exists else 'json'
            }
        except Exception as e:
            logger.error(f"Error getting database status: {e}")
            return {'error': str(e)}, 500
    
    @app.route('/api/database/enable-sqlite', methods=['POST'])
    def enable_sqlite():
        """Enable SQLite mode"""
        try:
            app.database_service.enable_sqlite()
            app.book_service.enable_sqlite()
            logger.info("SQLite mode enabled via API")
            return {'success': True, 'message': 'SQLite mode enabled'}
        except Exception as e:
            logger.error(f"Error enabling SQLite: {e}")
            return {'error': str(e)}, 500
    
    @app.route('/api/database/disable-sqlite', methods=['POST'])
    def disable_sqlite():
        """Disable SQLite mode (rollback to JSON)"""
        try:
            app.database_service.disable_sqlite()
            app.book_service.disable_sqlite()
            logger.info("SQLite mode disabled via API")
            return {'success': True, 'message': 'SQLite mode disabled, using JSON fallback'}
        except Exception as e:
            logger.error(f"Error disabling SQLite: {e}")
            return {'error': str(e)}, 500
    
    # Debug endpoint to check static files
    @app.route('/api/debug/static')
    def debug_static():
        import os
        static_path = app.static_folder
        template_path = app.template_folder
        
        static_files = []
        if os.path.exists(static_path):
            for root, dirs, files in os.walk(static_path):
                for file in files:
                    rel_path = os.path.relpath(os.path.join(root, file), static_path)
                    static_files.append(rel_path)
        
        return {
            'static_folder': static_path,
            'template_folder': template_path,
            'static_files': static_files[:20],  # First 20 files
            'static_exists': os.path.exists(static_path),
            'template_exists': os.path.exists(template_path)
        }
    
    # Debug endpoint to check request details
    @app.route('/api/debug/request')
    def debug_request():
        from flask import request
        return {
            'remote_addr': request.remote_addr,
            'host': request.host,
            'url': request.url,
            'is_tailscale': app.access_control.is_tailscale_request(request),
            'is_public': app.access_control.is_public_request(request),
            'headers': dict(request.headers)
        }
    
    return app 