"""
Library API endpoints for Spines 2.0
"""
from flask import Blueprint, jsonify, request, current_app
from utils.logging import get_logger
from services.book_service import BookService
from services.migration_service import MigrationService
from utils.auth import require_write_access

logger = get_logger(__name__)
library_api = Blueprint('library_api', __name__)

@library_api.route('/library/stats')
def get_library_stats():
    """Get library statistics"""
    try:
        config = current_app.config['SPINES_CONFIG']
        book_service = BookService(config)
        
        books = book_service.get_books()
        
        # Calculate stats
        total_books = len(books)
        contributors = set()
        media_types = {}
        
        for book in books:
            if book.get('contributor'):
                if isinstance(book['contributor'], list):
                    contributors.update(book['contributor'])
                else:
                    contributors.add(book['contributor'])
            
            media_type = book.get('media_type', 'unknown')
            media_types[media_type] = media_types.get(media_type, 0) + 1
        
        return jsonify({
            'total_books': total_books,
            'total_contributors': len(contributors),
            'contributors': sorted(list(contributors)),
            'media_types': media_types
        })
        
    except Exception as e:
        logger.exception("Failed to get library stats")
        return jsonify({'error': str(e)}), 500

@library_api.route('/library/metadata')
def get_library_metadata():
    """Get library metadata and index information"""
    try:
        # Load library index directly from the app's extractor instance
        library_index = current_app.extractor.library_index
        
        return jsonify({
            'metadata': library_index.get('metadata', {}),
            'book_count': len(library_index.get('books', {})),
            'last_updated': library_index.get('metadata', {}).get('last_updated'),
            'last_scan': library_index.get('metadata', {}).get('last_scan')
        })
        
    except Exception as e:
        logger.exception("Failed to get library metadata")
        return jsonify({'error': str(e)}), 500

@library_api.route('/library/isbn-lookup', methods=['POST'])
def isbn_lookup():
    """Look up metadata for an ISBN"""
    try:
        config = current_app.config['SPINES_CONFIG']
        book_service = BookService(config)
        
        data = request.get_json()
        isbn = data.get('isbn', '').strip()
        
        if not isbn:
            return jsonify({"error": "ISBN is required"}), 400
        
        # Use the new BookService method
        isbn_metadata = book_service.enhanced_isbn_lookup(isbn)
        
        if isbn_metadata and isbn_metadata.get('title'):
            return jsonify({
                "found": True,
                "metadata": {
                    "title": isbn_metadata.get('title'),
                    "author": isbn_metadata.get('author'),
                    "year": isbn_metadata.get('year'),
                    "publisher": isbn_metadata.get('publisher'),
                    "isbn": isbn
                }
            })
        else:
            return jsonify({
                "found": False,
                "message": "No metadata found for this ISBN"
            })
        
    except Exception as e:
        logger.exception("ISBN lookup failed")
        return jsonify({"error": str(e)}), 500

@library_api.route('/migration/status')
def get_migration_status():
    """Get migration status from v1.0 to v2.0"""
    try:
        config = current_app.config['SPINES_CONFIG']
        migration_service = MigrationService(config)
        
        status = migration_service.get_migration_status()
        return jsonify(status)
        
    except Exception as e:
        logger.exception("Failed to get migration status")
        return jsonify({'error': str(e)}), 500

@library_api.route('/migration/run', methods=['POST'])
@require_write_access
def run_migration():
    """Run migration from v1.0 to v2.0"""
    try:
        config = current_app.config['SPINES_CONFIG']
        migration_service = MigrationService(config)
        
        data = request.get_json() or {}
        source_path = data.get('source_path')
        
        if not source_path:
            return jsonify({'error': 'source_path is required'}), 400
        
        result = migration_service.migrate_from_v1(source_path)
        return jsonify(result)
        
    except Exception as e:
        logger.exception("Migration failed")
        return jsonify({'error': str(e)}), 500 