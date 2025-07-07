"""
OCR Service - Optical Character Recognition processing
Extracted from spines v1.0 MetadataExtractor OCR queue methods
"""
from pathlib import Path
import json
from datetime import datetime
from utils.logging import get_logger
from flask import current_app

logger = get_logger(__name__)

class OCRService:
    """Service for managing OCR processing queue"""
    
    def __init__(self, config):
        self.config = config
        self.ocr_queue_path = Path(config.DATA_PATH) / 'ocr_queue.json'
        self.library_path = Path(config.BOOKS_PATH)
        self.data_path = Path(config.DATA_PATH)
        
    def get_ocr_queue(self):
        """Get OCR processing queue with summary"""
        try:
            extractor = current_app.extractor
            
            queue = extractor.load_ocr_queue()
            summary = extractor.get_ocr_queue_summary()
            
            return {
                "queue": queue,
                "summary": summary
            }
            
        except Exception as e:
            logger.exception("Error loading OCR queue")
            return {
                "queue": [],
                "summary": {
                    "total": 0,
                    "pending": 0,
                    "processing": 0,
                    "completed": 0,
                    "failed": 0
                }
            }
    
    def add_to_ocr_queue(self, book_id, pages=None):
        """Add book to OCR processing queue"""
        try:
            extractor = current_app.extractor
            
            # Find the book's PDF path
            if book_id not in extractor.library_index.get("books", {}):
                logger.error(f"Book {book_id} not found in library")
                return False
            
            book_info = extractor.library_index["books"][book_id]
            folder_name = book_info.get("folder_name", book_id)
            book_dir = Path(self.library_path) / folder_name
            
            # Find PDF file in the book directory
            pdf_files = list(book_dir.glob("*.pdf"))
            if not pdf_files:
                logger.error(f"No PDF files found for book {book_id}")
                return False
            
            pdf_path = pdf_files[0]  # Take the first PDF
            reason = f"manual_request_book_{book_id}"
            
            # Add to OCR queue using existing method
            extractor.add_to_ocr_queue(pdf_path, reason)
            
            logger.info(f"Book {book_id} added to OCR queue")
            return True
            
        except Exception as e:
            logger.exception(f"Error adding book {book_id} to OCR queue")
            return False
    
    def add_to_ocr_queue_by_ids(self, book_ids, reason="manual_request"):
        """Add multiple books to OCR queue"""
        try:
            extractor = current_app.extractor
            
            added_count = 0
            for book_id in book_ids:
                # Find the book's PDF path
                if book_id in extractor.library_index.get("books", {}):
                    book_info = extractor.library_index["books"][book_id]
                    folder_name = book_info.get("folder_name", book_id)
                    book_dir = Path(self.library_path) / folder_name
                    
                    # Find PDF file in the book directory
                    pdf_files = list(book_dir.glob("*.pdf"))
                    if pdf_files:
                        pdf_path = pdf_files[0]  # Take the first PDF
                        extractor.add_to_ocr_queue(pdf_path, reason)
                        added_count += 1
            
            logger.info(f"Added {added_count} books to OCR queue")
            return added_count
            
        except Exception as e:
            logger.exception("Error adding books to OCR queue")
            return 0
    
    def process_ocr_queue(self, max_items=None):
        """Process items in OCR queue"""
        try:
            extractor = current_app.extractor
            
            # Process OCR queue using existing method
            processed_ids = extractor.process_ocr_queue()
            
            result = {
                "success": True,
                "processed_count": len(processed_ids),
                "processed_books": processed_ids
            }
            
            logger.info(f"OCR queue processing completed: {result}")
            return result
            
        except Exception as e:
            logger.exception("Error processing OCR queue")
            return {
                "success": False,
                "error": str(e),
                "processed_count": 0,
                "processed_books": []
            }
    
    def get_ocr_status(self, job_id):
        """Get OCR processing status for a specific job"""
        # This would be enhanced in the future with proper job tracking
        # For now, return basic status based on queue contents
        try:
            queue_data = self.get_ocr_queue()
            queue = queue_data.get("queue", [])
            
            for item in queue:
                if item.get("id") == job_id:
                    return {
                        "job_id": job_id,
                        "status": item.get("status", "unknown"),
                        "progress": item.get("progress", 0),
                        "created_at": item.get("created_at"),
                        "updated_at": item.get("updated_at")
                    }
            
            # Job not found in queue - might be completed
            return {
                "job_id": job_id,
                "status": "not_found",
                "message": "Job not found in queue - may be completed or never existed"
            }
            
        except Exception as e:
            logger.exception(f"Error getting OCR status for job {job_id}")
            return {
                "job_id": job_id,
                "status": "error",
                "error": str(e)
            } 