"""
Book Service for Spines 2.0
Business logic for book operations with SQLite migration support
"""
import json
from pathlib import Path
from utils.logging import get_logger
from flask import current_app
from .database_service import DatabaseService

logger = get_logger(__name__)

class BookService:
    def __init__(self, config):
        self.config = config
        self.library_file = config.get_library_metadata_path()
        self.database_service = DatabaseService(config)
        
    def load_library(self):
        """Load library metadata"""
        if not self.library_file.exists():
            return {
                'metadata': {
                    'version': '2.0',
                    'total_books': 0,
                    'library_path': 'books'
                },
                'books': {}
            }
        
        try:
            with open(self.library_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.warning(f"Corrupted library.json detected – attempting recovery: {e}")
            raw = self.library_file.read_text(encoding='utf-8', errors='ignore')
            start = raw.find('{')
            end = raw.rfind('}')
            if start != -1 and end != -1 and end > start:
                try:
                    recovered = json.loads(raw[start:end+1])
                    # Backup corrupted
                    self.library_file.rename(self.library_file.with_suffix('.corrupted.json'))
                    with open(self.library_file, 'w', encoding='utf-8') as fw:
                        json.dump(recovered, fw, indent=2, ensure_ascii=False)
                    logger.info("library.json successfully recovered and re-written")
                    return recovered
                except Exception as rec_err:
                    logger.error(f"Recovery failed: {rec_err}")
            logger.error("Could not recover library.json – returning empty library")
            return {'metadata': {}, 'books': {}}
        except Exception as e:
            logger.error(f"Error loading library: {e}")
            return {'metadata': {}, 'books': {}}
    
    def save_library(self, library_data):
        """Save library metadata"""
        try:
            with open(self.library_file, 'w', encoding='utf-8') as f:
                json.dump(library_data, f, indent=2, default=str, ensure_ascii=False)
            logger.info("Library metadata saved")
        except Exception as e:
            logger.error(f"Error saving library: {e}")
            raise
    
    def get_books(self, page=1, limit=None, search=None, filters=None):
        """Get books with optional pagination and filtering, using SQLite if available"""
        # Try SQLite first if enabled
        if self.database_service.use_sqlite:
            try:
                books = self.database_service.get_books(page=page, limit=limit, search=search)
                if books:
                    logger.info(f"Retrieved {len(books)} books from SQLite")
                    return books
            except Exception as e:
                logger.warning(f"SQLite query failed, falling back to JSON: {e}")
        
        # Fallback to JSON method
        logger.info("Using JSON fallback for get_books")
        return self._get_books_from_json(page, limit, search, filters)
    
    def _get_books_from_json(self, page=1, limit=None, search=None, filters=None):
        """Get books from JSON (original method as fallback)"""
        library = self.load_library()
        book_summaries = library.get('books', {})
        books = []
        
        # Load full metadata for each book
        for book_id, summary in book_summaries.items():
            # Try to load per-book metadata.json first
            folder_name = summary.get('folder_name', book_id)
            book_dir = Path(self.config.BOOKS_PATH) / folder_name
            metadata_file = book_dir / 'metadata.json'
            
            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        book_metadata = json.load(f)
                    # Ensure ID is set
                    book_metadata['id'] = book_id
                    books.append(book_metadata)
                except Exception as e:
                    logger.warning(f"Failed to load per-book metadata for {book_id}: {e}")
                    # Fallback to summary
                    summary['id'] = book_id
                    books.append(summary)
            else:
                # Use summary if no metadata.json exists
                summary['id'] = book_id
                books.append(summary)
        
        # Apply search if provided
        if search:
            search_lower = search.lower()
            books = [
                book for book in books
                if (search_lower in book.get('title', '').lower() or
                    search_lower in book.get('author', '').lower() or
                    search_lower in str(book.get('year', '')))
            ]
        
        # Sort by author, then title
        books.sort(key=lambda b: (
            b.get('author', '').lower(),
            b.get('title', '').lower()
        ))
        
        # Apply pagination if needed
        if limit:
            start = (page - 1) * limit
            books = books[start:start + limit]
        
        return books
    
    def get_book(self, book_id):
        """Get a specific book by ID, using SQLite if available"""
        # Try SQLite first if enabled
        if self.database_service.use_sqlite:
            try:
                book = self.database_service.get_book(book_id)
                if book:
                    logger.info(f"Retrieved book {book_id} from SQLite")
                    return book
            except Exception as e:
                logger.warning(f"SQLite query failed for book {book_id}, falling back to JSON: {e}")
        
        # Fallback to JSON method
        logger.info(f"Using JSON fallback for get_book {book_id}")
        return self._get_book_from_json(book_id)
    
    def _get_book_from_json(self, book_id):
        """Get a specific book by ID from JSON (original method as fallback)"""
        library = self.load_library()
        summary = library.get('books', {}).get(book_id)
        if not summary:
            return None

        # Try to load per-book metadata.json first
        folder_name = summary.get('folder_name', book_id)
        book_dir = Path(self.config.BOOKS_PATH) / folder_name
        metadata_file = book_dir / 'metadata.json'
        
        if metadata_file.exists():
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    book_metadata = json.load(f)
                logger.info(f"Loaded metadata from {metadata_file}: contributor = {book_metadata.get('contributor')}")
                # Use the metadata.json directly, just ensure ID is set
                book_metadata['id'] = book_id
                return book_metadata
            except Exception as e:
                logger.warning(f"Failed to load per-book metadata for {book_id}: {e}")
                # Fallback to summary
                return summary
        else:
            logger.info(f"No metadata file found at {metadata_file}, using library summary")
            return summary
    
    def update_book(self, book_id, metadata):
        """Update book metadata in both SQLite and JSON systems"""
        # Update in SQLite if enabled
        if self.database_service.use_sqlite:
            try:
                success = self.database_service.update_book(book_id, metadata)
                if success:
                    logger.info(f"Updated book {book_id} in SQLite")
                else:
                    logger.warning(f"Failed to update book {book_id} in SQLite")
            except Exception as e:
                logger.error(f"Error updating book {book_id} in SQLite: {e}")
        
        # Always update JSON as backup
        library = self.load_library()
        if book_id not in library.get('books', {}):
            raise ValueError(f"Book {book_id} not found")

        # Merge new metadata into library record first so folder computation uses latest values
        library_record = library['books'][book_id]
        library_record.update(metadata)

        old_folder = library_record.get('folder_name', book_id)
        new_folder = self._compute_folder_name(library_record)

        # Only perform expensive rename if the canonical name has changed
        if new_folder != old_folder:
            final_folder = self._rename_book_assets(old_folder, new_folder)
            # Update paths inside library record after physical move
            library_record['folder_name'] = final_folder
            library_record['path'] = f"books/{final_folder}"

        # Also update per-book metadata.json if it exists (post-rename path accounted for)
        folder_name = library_record.get('folder_name', book_id)
        book_dir = Path(self.config.BOOKS_PATH) / folder_name
        metadata_file = book_dir / 'metadata.json'
        if metadata_file.exists():
            try:
                with open(metadata_file, 'r', encoding='utf-8') as fh:
                    per_book_meta = json.load(fh)
                per_book_meta.update(metadata)
                # Ensure folder_name stays consistent
                per_book_meta['folder_name'] = folder_name
                with open(metadata_file, 'w', encoding='utf-8') as fh:
                    json.dump(per_book_meta, fh, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"Failed to update per-book metadata for {book_id}: {e}")

        # Finally, persist library.json
        self.save_library(library)
        logger.info(f"Updated book {book_id}")
        return library_record
    
    def delete_book(self, book_id):
        """Delete a book from both SQLite and JSON systems"""
        # Delete from SQLite if enabled
        if self.database_service.use_sqlite:
            try:
                success = self.database_service.delete_book(book_id)
                if success:
                    logger.info(f"Deleted book {book_id} from SQLite")
                else:
                    logger.warning(f"Failed to delete book {book_id} from SQLite")
            except Exception as e:
                logger.error(f"Error deleting book {book_id} from SQLite: {e}")
        
        # Delete from JSON system
        library = self.load_library()
        
        if book_id not in library.get('books', {}):
            raise ValueError(f"Book {book_id} not found")
        
        # Remove from library
        book = library['books'].pop(book_id)
        
        # Update total count
        library['metadata']['total_books'] = len(library['books'])
        
        # Save library
        self.save_library(library)
        
        # Remove book files/folder from disk
        try:
            folder_name = book.get('folder_name', book_id)
            book_dir = Path(self.config.BOOKS_PATH) / folder_name
            if book_dir.exists():
                import shutil
                shutil.rmtree(book_dir)
                logger.info(f"Deleted book folder {book_dir}")
            else:
                # If individual files in root path, attempt delete those
                for ext in ['.pdf', '.epub', '.mobi', '.azw', '.azw3', '.djvu', '.djv']:
                    f = Path(self.config.BOOKS_PATH)/f"{folder_name}{ext}"
                    if f.exists():
                        f.unlink()
                        logger.info(f"Deleted file {f}")
        except Exception as e:
            logger.warning(f"Failed to delete files for book {book_id}: {e}")
        
        logger.info(f"Deleted book {book_id}")
        return book
    
    def get_library_stats(self):
        """Get library statistics"""
        # Try SQLite first if enabled
        if self.database_service.use_sqlite:
            try:
                sqlite_count = self.database_service.count_books()
                if sqlite_count > 0:
                    return {
                        'total_books': sqlite_count,
                        'source': 'sqlite'
                    }
            except Exception as e:
                logger.warning(f"SQLite stats failed, falling back to JSON: {e}")
        
        # Fallback to JSON
        library = self.load_library()
        books = library.get('books', {})
        
        return {
            'total_books': len(books),
            'unique_authors': len(set(
                book.get('author', 'Unknown') 
                for book in books.values()
            )),
            'books_with_isbn': len([
                book for book in books.values() 
                if book.get('isbn')
            ]),
            'version': library.get('metadata', {}).get('version', '2.0'),
            'source': 'json'
        }
    
    def enable_sqlite(self):
        """Enable SQLite mode"""
        self.database_service.enable_sqlite()
        logger.info("SQLite mode enabled in BookService")
    
    def disable_sqlite(self):
        """Disable SQLite mode (rollback to JSON)"""
        self.database_service.disable_sqlite()
        logger.info("SQLite mode disabled in BookService, using JSON fallback")
    
    def extract_text(self, book_id):
        """Extract text from book using OCR"""
        try:
            # Get book metadata
            book = self.get_book(book_id)
            if not book:
                return {"success": False, "error": "Book not found"}
            
            # Create text service instance
            from services.text_service import TextService
            text_service = TextService(self.config)
            
            # Find the PDF file
            folder_name = book.get("folder_name", book_id)
            book_dir = Path(self.config.BOOKS_PATH) / folder_name
            
            # Look for PDF files
            pdf_files = list(book_dir.glob("*.pdf")) if book_dir.exists() else []
            
            # If not found in folder, look in library root
            if not pdf_files:
                direct_pdf = Path(self.config.BOOKS_PATH) / f"{folder_name}.pdf"
                if direct_pdf.exists():
                    pdf_file = direct_pdf
                else:
                    return {"success": False, "error": "No PDF file found for this book"}
            else:
                pdf_file = pdf_files[0]
            
            logger.info(f"Extracting text from: {pdf_file}")
            
            # Use the dedicated full text extraction method
            result = text_service.extract_full_text(pdf_file, save_to_file=True)
            
            if not result['success']:
                return {
                    "success": False, 
                    "error": f"Could not extract meaningful text from PDF: {result.get('text', 'Unknown error')}"
                }
            
            return {
                "success": True,
                "filename": result['filename'],
                "text_length": result['text_length'],
                "word_count": len(result['text'].split()),
                "method": result['method'],
                "message": f"Text extracted successfully using {result['method']} to {result['filename']}"
            }
            
        except Exception as e:
            logger.error(f"Error extracting text from book {book_id}: {e}")
            return {"success": False, "error": str(e)}
    
    def enhanced_isbn_lookup(self, isbn: str) -> dict:
        """Enhanced ISBN lookup with multiple sources"""
        try:
            import isbnlib
            
            # Clean ISBN
            isbn = isbnlib.canonical(isbn)
            if not isbnlib.is_isbn10(isbn) and not isbnlib.is_isbn13(isbn):
                return {}
            
            # Try multiple sources
            sources = ['openl', 'goob', 'wiki']
            metadata = {}
            
            for source in sources:
                try:
                    source_metadata = isbnlib.meta(isbn, service=source)
                    if source_metadata:
                        metadata.update(source_metadata)
                        break
                except Exception as e:
                    logger.debug(f"ISBN lookup failed for source {source}: {e}")
                    continue
            
            if metadata:
                # Normalize field names
                normalized = {}
                field_mapping = {
                    'Title': 'title',
                    'Authors': 'author',
                    'Year': 'year',
                    'Publisher': 'publisher',
                    'ISBN-13': 'isbn',
                    'ISBN-10': 'isbn_10'
                }
                
                for old_key, new_key in field_mapping.items():
                    if old_key in metadata:
                        normalized[new_key] = metadata[old_key]
                
                # Handle authors list
                if 'author' in normalized and isinstance(normalized['author'], list):
                    normalized['author'] = ', '.join(normalized['author'])
                
                return normalized
            
            return {}
            
        except Exception as e:
            logger.error(f"Enhanced ISBN lookup failed: {e}")
            return {}
    
    def _clean_for_filename(self, s: str, max_length: int = 50) -> str:
        """Clean string for use in filename"""
        import re
        if not s:
            return 'Unknown'
        cleaned = re.sub(r'[^\w\s\-]', '', s)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        cleaned = cleaned.replace(' ', '_')
        return cleaned[:max_length]
    
    def _compute_folder_name(self, metadata: dict) -> str:
        """Compute canonical folder name from metadata"""
        author = self._clean_for_filename(str(metadata.get('author', 'Unknown_Author')).split(',')[0], 30)
        title = self._clean_for_filename(metadata.get('title', 'Unknown_Title'), 40)
        year = str(metadata.get('year', 'Unknown_Year'))
        ident = metadata.get('isbn') or 'no_id'
        return f"{author}_{title}_{year}_{ident}"
    
    def _rename_book_assets(self, old_folder: str, new_folder: str) -> str:
        """Rename book folder and contained files"""
        import shutil
        from pathlib import Path
        
        old_dir = Path(self.config.BOOKS_PATH) / old_folder
        new_dir = Path(self.config.BOOKS_PATH) / new_folder
        
        if not old_dir.exists():
            logger.warning(f"Old folder doesn't exist: {old_dir}")
            return new_folder
        
        # Ensure target folder is unique
        suffix = 1
        final_new_folder = new_folder
        while new_dir.exists():
            final_new_folder = f"{new_folder}_{suffix}"
            new_dir = Path(self.config.BOOKS_PATH) / final_new_folder
            suffix += 1
        
        try:
            old_dir.rename(new_dir)
            logger.info(f"Renamed folder: {old_folder} -> {final_new_folder}")
            
            # Rename internal files prefixed with old folder name
            for f in new_dir.iterdir():
                if f.is_file() and f.name.startswith(old_folder):
                    new_name = f.name.replace(old_folder, final_new_folder, 1)
                    f.rename(new_dir / new_name)
                    logger.info(f"Renamed file: {f.name} -> {new_name}")
            
            return final_new_folder
            
        except Exception as e:
            logger.error(f"Failed to rename folder {old_folder}: {e}")
            return old_folder 