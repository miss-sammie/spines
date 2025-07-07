"""
Main page routes for Spines 2.0
"""
from flask import Blueprint, render_template, render_template_string, request, current_app
from utils.logging import get_logger
from services.book_service import BookService
from services.file_service import FileService

logger = get_logger(__name__)
main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Main library page"""
    config = current_app.config['SPINES_CONFIG']
    book_service = BookService(config)
    file_service = FileService(config)
    
    # Get books for display
    books = book_service.get_books()
    
    # Check for file changes
    new_files, modified_files, last_scan_time = file_service.check_for_changes()
    total_changes = len(new_files) + len(modified_files)
    
    # Check review queue status
    try:
        review_summary = current_app.extractor.get_review_queue_summary()
    except Exception as e:
        logger.warning(f"Could not get review queue summary: {e}")
        review_summary = {'pending_review': 0}
    
    # Filter for public if needed
    if current_app.access_control.is_public_request(request):
        books = current_app.access_control.filter_for_public(books)
    
    return render_template(
        'index.html',
        books=books,
        book_count=len(books),
        access_mode=config.ACCESS_MODE,
        is_public=current_app.access_control.is_public_request(request),
        contributor=request.args.get('contributor', ''),
        total_changes=total_changes,
        pending_review=review_summary['pending_review'],
        last_scan_time=last_scan_time
    )

@main_bp.route('/book/<book_id>')
def book_detail(book_id):
    """Individual book page"""
    config = current_app.config['SPINES_CONFIG']
    book_service = BookService(config)
    
    book = book_service.get_book(book_id)
    if not book:
        return "Book not found", 404
    
    # Filter for public if needed
    if current_app.access_control.is_public_request(request):
        book = current_app.access_control.filter_for_public(book)
    
    return render_template('book-detail.html', book=book) 