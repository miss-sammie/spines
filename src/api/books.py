"""
Books API endpoints for Spines 2.0
"""
from flask import Blueprint, jsonify, request, current_app, send_from_directory
from datetime import datetime
from werkzeug.utils import secure_filename
from pathlib import Path
from utils.auth import AccessControl
from utils.logging import get_logger
from services.book_service import BookService

logger = get_logger(__name__)
books_api = Blueprint('books_api', __name__)

@books_api.route('/books')
def get_books():
    """Get books with optional filtering and pagination"""
    config = current_app.config['SPINES_CONFIG']
    book_service = BookService(config)
    
    # Get query parameters
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 10000))
    search = request.args.get('search')
    
    try:
        books = book_service.get_books(page=page, limit=limit, search=search)
        
        # Filter for public access if needed
        if current_app.access_control.is_public_request(request):
            books = current_app.access_control.filter_for_public(books)
        
        return jsonify({
            'books': books,
            'page': page,
            'limit': limit,
            'total': len(books)
        })
        
    except Exception as e:
        logger.error(f"Error getting books: {e}")
        return jsonify({'error': 'Failed to get books'}), 500

@books_api.route('/books/<book_id>')
def get_book(book_id):
    """Get a specific book"""
    config = current_app.config['SPINES_CONFIG']
    book_service = BookService(config)
    
    try:
        book = book_service.get_book(book_id)
        if not book:
            return jsonify({'error': 'Book not found'}), 404
        
        # Filter for public access if needed
        if current_app.access_control.is_public_request(request):
            book = current_app.access_control.filter_for_public(book)
        
        return jsonify(book)
        
    except Exception as e:
        logger.error(f"Error getting book {book_id}: {e}")
        return jsonify({'error': 'Failed to get book'}), 500

@books_api.route('/books/<book_id>/files')
def get_book_files(book_id):
    """Get all readable files for a specific book"""
    config = current_app.config['SPINES_CONFIG']
    book_service = BookService(config)

    book = book_service.get_book(book_id)
    if not book:
        return jsonify({'error': 'Book not found'}), 404

    folder_name = book.get("folder_name", book_id)
    book_dir = Path(config.BOOKS_PATH) / folder_name

    readable_files = []
    supported_exts = ['.pdf', '.epub', '.mobi', '.azw', '.azw3', '.djvu', '.djv', '.txt']

    if book_dir.exists():
        for p in book_dir.iterdir():
            if p.is_file() and p.suffix.lower() in supported_exts:
                readable_files.append({
                    "name": p.name,
                    "type": p.suffix.lower().strip('.')
                })

    # Also check for files directly in the library root (legacy)
    for ext in supported_exts:
        direct_file = Path(config.BOOKS_PATH) / f"{folder_name}{ext}"
        if direct_file.exists():
            # Avoid duplicates if already found in a folder
            if not any(f['name'] == direct_file.name for f in readable_files):
                 readable_files.append({
                    "name": direct_file.name,
                    "type": ext.strip('.')
                })

    return jsonify(readable_files)

@books_api.route('/books/<book_id>', methods=['PUT'])
def update_book(book_id):
    """Update book metadata"""
    # Check write access
    if current_app.access_control.is_public_request(request) and current_app.config['PUBLIC_READ_ONLY']:
        return jsonify({
            'error': 'Read-only access',
            'message': 'Public access is read-only. Use Tailscale for full access.'
        }), 403
    
    config = current_app.config['SPINES_CONFIG']
    book_service = BookService(config)
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        book = book_service.update_book(book_id, data)
        return jsonify({'success': True, 'book': book})
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Error updating book {book_id}: {e}")
        return jsonify({'error': 'Failed to update book'}), 500

@books_api.route('/books/<book_id>', methods=['DELETE'])
def delete_book(book_id):
    """Delete a book"""
    # Check write access
    if current_app.access_control.is_public_request(request) and current_app.config['PUBLIC_READ_ONLY']:
        return jsonify({
            'error': 'Read-only access',
            'message': 'Public access is read-only. Use Tailscale for full access.'
        }), 403
    
    config = current_app.config['SPINES_CONFIG']
    book_service = BookService(config)
    
    try:
        book = book_service.delete_book(book_id)
        return jsonify({'message': 'Book deleted', 'book': book})
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Error deleting book {book_id}: {e}")
        return jsonify({'error': 'Failed to delete book'}), 500

@books_api.route('/books/<book_id>/file')
def serve_book_file(book_id):
    """Serve book file for download/viewing. Can specify a filename."""
    try:
        config = current_app.config['SPINES_CONFIG']
        book_service = BookService(config)
        
        # Get book metadata to find file path
        book = book_service.get_book(book_id)
        if not book:
            return "Book not found", 404
        
        folder_name = book.get("folder_name", book_id)
        book_dir = Path(config.BOOKS_PATH) / folder_name
        
        # Check for specific filename request
        requested_filename = request.args.get('filename')
        book_file = None

        if requested_filename:
            candidate_path = book_dir / requested_filename
            if candidate_path.exists():
                book_file = candidate_path
            else:
                # Fallback to root for legacy files
                legacy_path = Path(config.BOOKS_PATH) / requested_filename
                if legacy_path.exists():
                    book_file = legacy_path
                    book_dir = Path(config.BOOKS_PATH)
        else:
            # Existing logic to find the best file if no specific filename is given
            # 1) Prefer explicit filename stored in metadata
            preferred_names = [
                book.get("pdf_filename"),
                book.get("filename"),
                f"{folder_name}.pdf"
            ]
            for name in preferred_names:
                if name:
                    candidate = book_dir / name
                    if candidate.exists():
                        book_file = candidate
                        break
            
            # 2) If not found, pick first non-archived PDF in folder
            if not book_file and book_dir.exists():
                pdf_candidates = [p for p in book_dir.glob("*.pdf") if not p.stem.endswith("_old")]
                if pdf_candidates:
                    pdf_candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                    book_file = pdf_candidates[0]

            # 3) If still not found, look for legacy files in root
            if not book_file:
                direct_pdf = Path(config.BOOKS_PATH) / f"{folder_name}.pdf"
                if direct_pdf.exists():
                    book_file = direct_pdf
                    book_dir = Path(config.BOOKS_PATH)
                else: # Final fallback for other ebook types
                    ebook_files = []
                    for ext in ['.pdf', '.epub', '.mobi', '.azw', '.azw3', '.djvu', '.djv']:
                        potential = Path(config.BOOKS_PATH) / f"{folder_name}{ext}"
                        if potential.exists():
                            ebook_files.append(potential)
                    if ebook_files:
                        ebook_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                        book_file = ebook_files[0]
                        book_dir = Path(config.BOOKS_PATH)

        if not book_file or not book_file.exists():
            return "No readable file found for this book", 404

        logger.info(f"Serving file: {book_file}")
        
        return send_from_directory(
            str(book_dir),
            book_file.name,
            as_attachment=False
        )
        
    except Exception as e:
        logger.exception(f"Error serving book file {book_id}")
        return f"Error serving file: {str(e)}", 500

@books_api.route('/books/<book_id>/file', methods=['PUT'])
def save_book_file(book_id):
    """Save a text file for a book"""
    if current_app.access_control.is_public_request(request) and current_app.config['PUBLIC_READ_ONLY']:
        return jsonify({'error': 'Read-only access'}), 403

    config = current_app.config['SPINES_CONFIG']
    book_service = BookService(config)

    book = book_service.get_book(book_id)
    if not book:
        return jsonify({'error': 'Book not found'}), 404

    filename = request.args.get('filename')
    if not filename:
        return jsonify({'error': 'Filename parameter is required'}), 400

    if not filename.lower().endswith('.txt'):
        return jsonify({'error': 'Only .txt files can be edited'}), 400

    folder_name = book.get("folder_name", book_id)
    book_dir = Path(config.BOOKS_PATH) / folder_name
    file_path = book_dir / filename

    if not file_path.parent.exists():
        return jsonify({'error': 'Book directory does not exist'}), 404

    try:
        data = request.get_data(as_text=True)
        file_path.write_text(data, encoding='utf-8')
        logger.info(f"Updated text file: {file_path}")
        return jsonify({'success': True, 'message': f'{filename} saved successfully.'})
    except Exception as e:
        logger.exception(f"Error saving file {filename} for book {book_id}: {e}")
        return jsonify({'error': 'Failed to save file'}), 500

@books_api.route('/books/<book_id>/replace-file', methods=['POST'])
def replace_file(book_id):
    """Replace the main PDF of a book – archive old file, save new one under canonical name"""
    # Respect public read-only mode
    if current_app.access_control.is_public_request(request) and current_app.config['PUBLIC_READ_ONLY']:
        return jsonify({
            'error': 'Read-only access',
            'message': 'Public access is read-only. Use Tailscale for full access.'
        }), 403

    try:
        config = current_app.config['SPINES_CONFIG']
        book_service = BookService(config)

        # Validate book exists
        book = book_service.get_book(book_id)
        if not book:
            return jsonify({'error': 'Book not found'}), 404

        # Validate uploaded file
        uploaded = request.files.get('file')
        if not uploaded or uploaded.filename == '':
            return jsonify({'error': 'No file provided'}), 400
        if not uploaded.filename.lower().endswith('.pdf'):
            return jsonify({'error': 'Only PDF files are supported at the moment'}), 400

        # Locate book directory
        folder_name = book.get('folder_name', book_id)
        book_dir = Path(config.BOOKS_PATH) / folder_name
        book_dir.mkdir(exist_ok=True)

        # Archive existing PDFs with timestamp suffix
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        for pdf in book_dir.glob('*.pdf'):
            backup_name = f"{pdf.stem}_old_{timestamp}{pdf.suffix}"
            pdf.rename(pdf.with_name(backup_name))

        # Determine canonical filename using MetadataExtractor logic
        canonical_stem = current_app.extractor.normalize_filename(book)
        new_filename = secure_filename(f"{canonical_stem}.pdf")
        new_file_path = book_dir / new_filename

        # Save uploaded file
        uploaded.save(str(new_file_path))

        logger.info(f"Replaced file for {book_id}: {new_filename}")
        return jsonify({
            'success': True,
            'new_filename': new_filename,
            'message': 'File replaced successfully'
        })

    except Exception as e:
        logger.exception(f"Error replacing file for {book_id}")
        return jsonify({'error': str(e)}), 500

@books_api.route('/books/<book_id>/extract-text', methods=['POST'])
def extract_text(book_id):
    """Extract text from book using OCR"""
    # Check write access
    if current_app.access_control.is_public_request(request) and current_app.config['PUBLIC_READ_ONLY']:
        return jsonify({
            'error': 'Read-only access',
            'message': 'Public access is read-only. Use Tailscale for full access.'
        }), 403
    
    try:
        config = current_app.config['SPINES_CONFIG']
        book_service = BookService(config)
        
        result = book_service.extract_text(book_id)
        
        if result.get('success'):
            logger.info(f"Text extraction completed for book {book_id}")
            return jsonify(result)
        else:
            return jsonify({"error": result.get('error', 'Text extraction failed')}), 500
            
    except Exception as e:
        logger.exception(f"Error extracting text from book {book_id}")
        return jsonify({"error": str(e)}), 500 