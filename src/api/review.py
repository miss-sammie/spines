"""
Review Queue API - Managing metadata review workflow
Extracted from spines v1.0 web_server.py lines 4368-5360
"""
from flask import Blueprint, request, jsonify, send_from_directory, current_app
from pathlib import Path
from services.review_service import ReviewService
from utils.auth import require_write_access
from utils.logging import get_logger

logger = get_logger(__name__)
review_api = Blueprint('review_api', __name__)

@review_api.route('/review-queue')
def get_review_queue():
    """Get review queue status and items"""
    try:
        config = current_app.config['SPINES_CONFIG']
        service = ReviewService(config)
        
        queue = service.get_review_queue()
        summary = service.get_review_queue_summary()
        
        return jsonify({
            "queue": queue,
            "summary": summary
        })
        
    except Exception as e:
        logger.exception("Error getting review queue")
        return jsonify({"error": str(e)}), 500

@review_api.route('/review-queue/<review_id>/approve', methods=['POST'])
@require_write_access
def approve_review(review_id):
    """Approve and process a review queue item with corrected metadata"""
    try:
        config = current_app.config['SPINES_CONFIG']
        service = ReviewService(config)
        
        data = request.get_json()
        updated_metadata = data.get('metadata', {})
        contributor = data.get('contributor', 'anonymous')
        copy_action = data.get('copy_action', 'auto')  # 'auto', 'separate_copy', 'add_to_existing'
        
        # Store the copy action preference in metadata for processing
        updated_metadata['_copy_action'] = copy_action
        
        book_id = service.approve_review(review_id, updated_metadata, contributor)
        
        if book_id:
            logger.info(f"Review item {review_id} approved, created book {book_id}")
            return jsonify({
                "success": True,
                "book_id": book_id,
                "message": "Book processed successfully"
            })
        else:
            logger.error(f"Failed to process review item {review_id}")
            return jsonify({"error": "Failed to process book"}), 500
            
    except Exception as e:
        logger.exception(f"Error approving review item {review_id}")
        return jsonify({"error": str(e)}), 500

@review_api.route('/review-queue/<review_id>/reject', methods=['POST'])
@require_write_access
def reject_review(review_id):
    """Reject review item"""
    try:
        config = current_app.config['SPINES_CONFIG']
        service = ReviewService(config)
        
        data = request.get_json()
        reason = data.get('reason', 'Rejected by user')
        
        success = service.reject_review(review_id, reason)
        
        if success:
            logger.info(f"Review item {review_id} rejected: {reason}")
            return jsonify({
                "success": True,
                "message": "Review item rejected"
            })
        else:
            logger.error(f"Failed to reject review item {review_id}")
            return jsonify({"error": "Failed to reject review item"}), 500
            
    except Exception as e:
        logger.exception(f"Error rejecting review item {review_id}")
        return jsonify({"error": str(e)}), 500

@review_api.route('/review-queue/<review_id>/pdf')
def get_review_pdf(review_id):
    """Serve PDF file for review queue item"""
    try:
        config = current_app.config['SPINES_CONFIG']
        service = ReviewService(config)
        
        item = service.get_review_item(review_id)
        
        if not item:
            return "Review item not found", 404
        
        file_path = Path(item["path"])
        if not file_path.exists():
            return "File not found", 404
        
        return send_from_directory(
            file_path.parent,
            file_path.name,
            as_attachment=False,
            mimetype='application/pdf'
        )
        
    except Exception as e:
        logger.exception(f"Error serving review PDF {review_id}")
        return "Error serving PDF", 500

@review_api.route('/review-queue/<review_id>/similar-books')
def get_similar_books(review_id):
    """Get similar books for review item comparison"""
    try:
        config = current_app.config['SPINES_CONFIG']
        service = ReviewService(config)
        
        similar_books = service.get_similar_books(review_id)
        
        return jsonify({
            "similar_books": similar_books
        })
        
    except Exception as e:
        logger.exception(f"Error getting similar books for review {review_id}")
        return jsonify({"error": str(e)}), 500 