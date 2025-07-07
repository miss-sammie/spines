"""
OCR API - Optical Character Recognition management
Extracted from spines v1.0 web_server.py lines 3415-3490
"""
from flask import Blueprint, request, jsonify, current_app
from services.ocr_service import OCRService
from utils.auth import require_write_access
from utils.logging import get_logger

logger = get_logger(__name__)
ocr_api = Blueprint('ocr_api', __name__)

@ocr_api.route('/ocr-queue')
def get_ocr_queue():
    """Get OCR processing queue"""
    try:
        config = current_app.config['SPINES_CONFIG']
        service = OCRService(config)
        
        queue_data = service.get_ocr_queue()
        
        return jsonify(queue_data)
        
    except Exception as e:
        logger.exception("Error getting OCR queue")
        return jsonify({"error": str(e)}), 500

@ocr_api.route('/ocr-queue', methods=['POST'])
@require_write_access
def add_to_ocr_queue():
    """Add book to OCR queue"""
    try:
        config = current_app.config['SPINES_CONFIG']
        service = OCRService(config)
        
        data = request.get_json()
        book_id = data.get('book_id')
        pages = data.get('pages')  # Optional: specific pages to OCR
        
        if not book_id:
            return jsonify({"error": "book_id is required"}), 400
        
        success = service.add_to_ocr_queue(book_id, pages)
        
        if success:
            logger.info(f"Book {book_id} added to OCR queue")
            return jsonify({
                "success": True,
                "message": "Book added to OCR queue"
            })
        else:
            return jsonify({"error": "Failed to add book to OCR queue"}), 500
            
    except Exception as e:
        logger.exception("Error adding book to OCR queue")
        return jsonify({"error": str(e)}), 500

@ocr_api.route('/ocr-queue/process', methods=['POST'])
@require_write_access
def process_ocr_queue():
    """Process OCR queue"""
    try:
        config = current_app.config['SPINES_CONFIG']
        service = OCRService(config)
        
        data = request.get_json() or {}
        max_items = data.get('max_items', 5)  # Process up to 5 items by default
        
        result = service.process_ocr_queue(max_items)
        
        logger.info(f"OCR queue processing completed: {result}")
        return jsonify(result)
        
    except Exception as e:
        logger.exception("Error processing OCR queue")
        return jsonify({"error": str(e)}), 500 