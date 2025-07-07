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
from routes.main import main_bp
from routes.admin import admin_bp
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
    
    # Pass services to MetadataExtractor
    from src.metadata_extractor import MetadataExtractor
    app.extractor = MetadataExtractor(config, book_service=app.book_service, text_service=app.text_service)
    
    # Setup access control
    access_control = AccessControl(app)
    app.access_control = access_control
    
    # Register blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)
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
    
    logger.info(f"Flask app created with access mode: {config.ACCESS_MODE}")
    
    return app 