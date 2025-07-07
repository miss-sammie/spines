"""
Admin routes for Spines 2.0
"""
from flask import Blueprint, render_template, current_app
from utils.auth import require_write_access
from utils.logging import get_logger

logger = get_logger(__name__)
admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/admin')
@require_write_access
def admin():
    """Admin dashboard"""
    return render_template('admin/dashboard.html')

@admin_bp.route('/admin/review-queue')
@require_write_access
def review_queue():
    """Review queue management page"""
    try:
        # Get review queue summary from the app's extractor instance
        review_summary = current_app.extractor.get_review_queue_summary()
        
        return render_template(
            'admin/review-queue.html',
            pending_review=review_summary['pending_review'],
            total_processed=review_summary.get('total_processed', 0)
        )
        
    except Exception as e:
        logger.exception("Failed to load review queue page")
        return f"Error loading review queue: {e}", 500

@admin_bp.route('/admin/ocr-management')
@require_write_access
def ocr_management():
    """OCR queue management page"""
    try:
        # Get OCR queue summary from the app's extractor instance
        ocr_summary = current_app.extractor.get_ocr_queue_summary()
        
        return render_template(
            'admin/ocr-management.html',
            pending_ocr=ocr_summary.get('pending', 0),
            completed_ocr=ocr_summary.get('completed', 0)
        )
        
    except Exception as e:
        logger.exception("Failed to load OCR management page")
        return f"Error loading OCR management: {e}", 500 