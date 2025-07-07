"""
Review Service - Business logic for metadata review workflow
Extracted from spines v1.0 MetadataExtractor review queue methods
"""
from pathlib import Path
import json
from datetime import datetime
from utils.logging import get_logger
from src.services.book_service import BookService

logger = get_logger(__name__)

class ReviewService:
    """Service for managing the review queue workflow"""
    
    def __init__(self, config):
        self.config = config
        self.review_queue_path = Path(config.DATA_PATH) / 'review_queue.json'
        self.library_path = Path(config.BOOKS_PATH)
        self.data_path = Path(config.DATA_PATH)
        # We need the book service for approving reviews
        self.book_service = BookService(config)
        
    def get_review_queue(self):
        """Get all review queue items"""
        try:
            if not self.review_queue_path.exists():
                return []
            
            try:
                with open(self.review_queue_path, 'r', encoding='utf-8') as f:
                    queue = json.load(f)
            except json.JSONDecodeError as e:
                # Gracefully recover from a partially-written JSON file
                logger.warning(f"Corrupted review_queue.json detected – attempting recovery: {e}")
                raw = self.review_queue_path.read_text(encoding='utf-8', errors='ignore')
                start = raw.find('[')
                end = raw.rfind(']')
                if start != -1 and end != -1 and end > start:
                    try:
                        recovered = json.loads(raw[start:end+1])
                        queue = recovered
                        # Backup the corrupted file and write the recovered version atomically
                        self.review_queue_path.rename(self.review_queue_path.with_suffix('.corrupted.json'))
                        with open(self.review_queue_path, 'w', encoding='utf-8') as fw:
                            json.dump(queue, fw, indent=2, ensure_ascii=False)
                        logger.info("review_queue.json successfully recovered and re-written")
                    except Exception as rec_err:
                        logger.error(f"Recovery failed: {rec_err}")
                        queue = []
                else:
                    queue = []
            
            # Validate queue items and filter out invalid ones
            valid_queue = []
            for item in queue:
                if self._validate_review_item(item):
                    valid_queue.append(item)
                else:
                    logger.warning(f"Invalid review item removed: {item.get('id', 'unknown')}")
            
            return valid_queue
            
        except Exception as e:
            logger.exception("Error loading review queue")
            return []
    
    def get_review_queue_summary(self):
        """Get summary statistics for the review queue"""
        queue = self.get_review_queue()
        
        summary = {
            'total': len(queue),
            'pending_review': 0,
            'file_missing': 0,
            'processing_failed': 0
        }
        
        for item in queue:
            status = item.get('status', 'unknown')
            if status == 'pending_review':
                summary['pending_review'] += 1
            elif status == 'file_missing':
                summary['file_missing'] += 1
            elif status == 'processing_failed':
                summary['processing_failed'] += 1
        
        return summary
    
    def get_review_item(self, review_id):
        """Get a specific review item by ID"""
        queue = self.get_review_queue()
        
        for item in queue:
            if item.get('id') == review_id:
                return item
        
        return None
    
    def approve_review(self, review_id, updated_metadata, contributor):
        """Approve a review item and create/update a book"""
        try:
            # Load the review queue
            queue = self.get_review_queue()
            
            # Find the item
            item = None
            item_index = None
            for i, entry in enumerate(queue):
                if entry.get('id') == review_id:
                    item = entry
                    item_index = i
                    break
            
            if not item:
                logger.error(f"Review item {review_id} not found")
                return None
            
            # Use the app's extractor instance for the actual processing
            from flask import current_app
            extractor = current_app.extractor
            
            # Use the existing approve_from_review_queue method
            book_id = extractor.approve_from_review_queue(review_id, updated_metadata, contributor)
            
            # Cleanup orphaned temp files if queue shrank
            try:
                extractor.cleanup_temp_files()
            except Exception as _e:
                logger.debug(f"Temp cleanup skipped: {_e}")

            return book_id
            
        except Exception as e:
            logger.exception(f"Error approving review item {review_id}")
            return None
    
    def reject_review(self, review_id, reason):
        """Reject a review item and remove it from the queue"""
        try:
            # Use the app's extractor instance for the actual processing
            from flask import current_app
            extractor = current_app.extractor
            
            # Use the existing reject_from_review_queue method
            success = extractor.reject_from_review_queue(review_id, reason)
            
            if success:
                try:
                    extractor.cleanup_temp_files()
                except Exception as _e:
                    logger.debug(f"Temp cleanup skipped: {_e}")

            return success
            
        except Exception as e:
            logger.exception(f"Error rejecting review item {review_id}")
            return False
    
    def get_similar_books(self, review_id):
        """Find similar books for a review item"""
        try:
            item = self.get_review_item(review_id)
            if not item:
                return []
            
            # Use the app's extractor instance for similarity search
            from flask import current_app
            extractor = current_app.extractor
            
            # Find similar books using the extracted metadata
            similar_books = extractor.find_similar_books(item.get("extracted_metadata", {}))
            
            # Format for frontend
            similar_data = []
            for similar in similar_books[:5]:  # Top 5 matches
                similar_data.append({
                    "book_id": similar["book_id"],
                    "title": similar["metadata"].get("title", "Unknown"),
                    "author": similar["metadata"].get("author", "Unknown"),
                    "year": similar["metadata"].get("year", ""),
                    "contributors": similar["metadata"].get("contributor", []),
                    "confidence": similar["confidence"],
                    "similarity_type": similar["similarity_type"]
                })
            
            return {
                "similar_books": similar_data,
                "has_matches": len(similar_data) > 0
            }
            
        except Exception as e:
            logger.exception(f"Error finding similar books for review {review_id}")
            return []
    
    def _validate_review_item(self, item):
        """Validate that a review item has required fields"""
        required_fields = ['id', 'path', 'status']
        
        for field in required_fields:
            if field not in item:
                return False
        
        # Check if file still exists
        file_path = Path(item['path'])
        if not file_path.exists():
            # Update status to file_missing
            item['status'] = 'file_missing'
            return True  # Keep it in queue but mark as missing
        
        return True 