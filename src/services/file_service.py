"""
File Service - File processing and management for Spines 2.0
"""
import os
import json
import shutil
from pathlib import Path
from datetime import datetime
from werkzeug.utils import secure_filename
from utils.logging import get_logger
from flask import current_app

logger = get_logger(__name__)

class FileService:
    def __init__(self, config):
        self.config = config
        self.library_path = Path(config.BOOKS_PATH)
        self.data_path = Path(config.DATA_PATH)
        self.temp_path = Path(config.TEMP_PATH)
        
        # Ensure directories exist
        self.temp_path.mkdir(exist_ok=True)
        self.data_path.mkdir(exist_ok=True)
        self.library_path.mkdir(exist_ok=True)
    
    def check_for_changes(self):
        """Check for new or modified PDFs using metadata extractor"""
        try:
            extractor = current_app.extractor
            new_files, modified_files = extractor.get_files_needing_scan()
            
            # Get last scan time from library metadata
            last_scan_time = extractor.library_index.get("metadata", {}).get("last_scan")
            
            return new_files, modified_files, last_scan_time
            
        except Exception as e:
            logger.error(f"Error checking for changes: {e}")
            return [], [], None
    
    def upload_files(self, uploaded_files, contributor='anonymous'):
        """Handle file uploads to temp directory"""
        try:
            if not uploaded_files:
                raise ValueError("No files provided")
            
            saved_files = []
            supported_extensions = ['.pdf', '.epub', '.mobi', '.azw', '.azw3', '.djvu', '.djv']
            
            for file in uploaded_files:
                if file and file.filename:
                    filename_lower = file.filename.lower()
                    
                    if any(filename_lower.endswith(ext) for ext in supported_extensions):
                        # Secure the filename
                        filename = secure_filename(file.filename)
                        
                        # Save to temp directory
                        file_path = self.temp_path / filename
                        
                        # Handle duplicate names by adding a counter
                        counter = 1
                        original_path = file_path
                        while file_path.exists():
                            name_part = original_path.stem
                            suffix = original_path.suffix
                            file_path = self.temp_path / f"{name_part}_{counter}{suffix}"
                            counter += 1
                        
                        file.save(str(file_path))
                        saved_files.append(file_path)
                        logger.info(f"Uploaded to temp: {file_path.name}")
            
            if not saved_files:
                raise ValueError("No valid ebook files were uploaded")
            
            return {
                "success": True,
                "uploaded_count": len(saved_files),
                "message": "Files uploaded successfully. Processing will start automatically."
            }
            
        except Exception as e:
            logger.error(f"Error uploading files: {e}")
            raise
    
    def process_files(self, contributor='anonymous'):
        """Process new/modified files via API"""
        try:
            extractor = current_app.extractor
            
            # Get files that need processing
            new_files, modified_files = extractor.get_files_needing_scan()
            total_files = len(new_files) + len(modified_files)
            
            if total_files == 0:
                return {
                    "success": True,
                    "processed_count": 0,
                    "processed_books": [],
                    "message": "No files need processing"
                }
            
            # Process files with progress tracking
            processed_ids = []
            
            # Process new files
            for i, pdf_path in enumerate(new_files):
                logger.info(f"Processing new file {i+1}/{len(new_files)}: {pdf_path.name}")
                book_id = extractor.process_book(pdf_path, contributor)
                if book_id:
                    processed_ids.append(book_id)
            
            # Process modified files
            for i, (pdf_path, existing_book_id) in enumerate(modified_files):
                logger.info(f"Processing modified file {i+1}/{len(modified_files)}: {pdf_path.name}")
                # Remove from index and re-process
                if existing_book_id in extractor.library_index["books"]:
                    del extractor.library_index["books"][existing_book_id]
                
                book_id = extractor.process_book(pdf_path, contributor)
                if book_id:
                    processed_ids.append(book_id)
            
            # Update scan time
            extractor.update_last_scan()
            
            return {
                "success": True,
                "processed_count": len(processed_ids),
                "processed_books": processed_ids
            }
            
        except Exception as e:
            logger.error(f"Error processing files: {e}")
            raise
    
    def cleanup_temp_files(self):
        """Clean up orphaned temp files"""
        try:
            extractor = current_app.extractor
            
            result = extractor.cleanup_temp_files()
            
            return {
                "success": True,
                "cleaned": result["cleaned"],
                "errors": result["errors"]
            }
            
        except Exception as e:
            logger.error(f"Error cleaning up temp files: {e}")
            raise
    
    def generate_progress_stream(self, contributor='anonymous'):
        """Generate real-time progress updates for file processing from the temp folder."""
        import json
        import time
        import sys
        
        try:
            logger.info("Starting SSE stream for file processing from temp folder")
            
            # Send initial ping to test connection
            yield f"data: {json.dumps({'type': 'ping', 'message': 'Connection established'})}\n\n"
            time.sleep(0.1)
            
            logger.info(f"Processing uploaded files from temp for contributor: {contributor}")
            
            extractor = current_app.extractor
            
            # Get files from temp directory, sorted by modification time
            files_to_process = sorted([p for p in self.temp_path.iterdir() if p.is_file()], key=lambda p: p.stat().st_mtime)
            total_files = len(files_to_process)
            
            logger.info(f"Found {total_files} files to process in temp folder.")
            
            if total_files == 0:
                yield f"data: {json.dumps({'type': 'complete', 'processed_count': 0, 'review_queue_count': 0, 'message': 'No uploaded files to process'})}\n\n"
                return
            
            filenames = [p.name for p in files_to_process]
            yield f"data: {json.dumps({'type': 'start', 'total_files': total_files, 'filenames': filenames})}\n\n"
            time.sleep(0.1)
            
            processed_count = 0
            review_queue_count = 0
            failed_count = 0
            
            for i, file_path in enumerate(files_to_process):
                current_file_num = i + 1
                logger.info(f"Processing temp file {current_file_num}/{total_files}: {file_path.name}")
                
                yield f"data: {json.dumps({'type': 'progress', 'current_file': current_file_num, 'total_files': total_files, 'filename': file_path.name, 'status': 'processing'})}\n\n"
                sys.stdout.flush()
                
                def progress_callback(status_detail):
                    """Nested function to send detail updates."""
                    logger.info(f"  -> Detail update for {file_path.name}: {status_detail}")
                    yield f"data: {json.dumps({'type': 'detail', 'filename': file_path.name, 'detail': status_detail})}\n\n"
                    sys.stdout.flush()

                try:
                    # Pass the callback to the processing function
                    result = extractor.process_book_in_temp(file_path, contributor, progress_callback=progress_callback)
                    
                    status = 'unknown'
                    if result and result.get('status') == 'processed':
                        processed_count += 1
                        status = 'success'
                    elif result and result.get('status') == 'review_queue':
                        review_queue_count += 1
                        status = 'review'
                    else:
                        failed_count += 1
                        status = 'failed'
                    
                    yield f"data: {json.dumps({'type': 'file_complete', 'filename': file_path.name, 'status': status, 'result': result})}\n\n"

                except Exception as e:
                    failed_count += 1
                    logger.error(f"Error processing {file_path.name}: {e}")
                    yield f"data: {json.dumps({'type': 'file_complete', 'filename': file_path.name, 'status': 'error', 'error': str(e)})}\n\n"
                
                sys.stdout.flush()
            
            # Update scan time to refresh library view
            extractor.update_last_scan()
            
            logger.info(f"Completed processing temp files: {processed_count} processed, {review_queue_count} for review, {failed_count} failed.")
            yield f"data: {json.dumps({'type': 'complete', 'processed_count': processed_count, 'review_queue_count': review_queue_count, 'failed_count': failed_count})}\n\n"
            
        except Exception as e:
            logger.error(f"SSE stream error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n" 