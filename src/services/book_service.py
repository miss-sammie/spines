"""
Book Service for Spines 2.0
Business logic for book operations
"""
import json
from pathlib import Path
from utils.logging import get_logger
from flask import current_app

logger = get_logger(__name__)

class BookService:
    def __init__(self, config):
        self.config = config
        self.library_file = config.get_library_metadata_path()
        
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
        """Get books with optional pagination and filtering, loading full metadata from individual files"""
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
        """Get a specific book by ID, loading from per-book metadata.json if available"""
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
        """Update book metadata in both library.json and per-book metadata.json.

        If a change to author, title, year or isbn would alter the canonical folder
        name, this method will also rename the folder and contained files so the
        on-disk layout stays in sync with the metadata.
        """
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
        """Delete a book"""
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
            'version': library.get('metadata', {}).get('version', '2.0')
        }
    
    def extract_text(self, book_id):
        """Extract text from book using OCR"""
        try:
            # Get book metadata
            book = self.get_book(book_id)
            if not book:
                return {"success": False, "error": "Book not found"}
            
            text_service = current_app.text_service
            
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
            logger.exception(f"Error extracting text from book {book_id}")
            return {"success": False, "error": f"Text extraction failed: {str(e)}"}

    def enhanced_isbn_lookup(self, isbn: str) -> dict:
        """Enhanced ISBN lookup that tries multiple sources"""
        logger.info(f"📚 Looking up ISBN: {isbn}")
        
        # Try isbnlib first (covers Open Library, Google Books, etc.)
        try:
            # Clean the ISBN
            import isbnlib
            clean_isbn = isbn.replace('-', '').replace(' ', '')
            
            # Try multiple isbnlib providers in order
            providers = ['default', 'openl', 'goob']  # openlibrary, google books
            
            for provider in providers:
                try:
                    if provider == 'default':
                        meta = isbnlib.meta(clean_isbn)
                    else:
                        meta = isbnlib.meta(clean_isbn, service=provider)
                    
                    if meta:
                        logger.info(f"  ✅ Found metadata via {provider}: {meta.get('Title', 'N/A')}")
                        
                        # Convert to our format
                        result = {}
                        if meta.get('Title'):
                            result['title'] = meta['Title']
                        if meta.get('Authors'):
                            result['author'] = ', '.join(meta['Authors'])
                        if meta.get('Year'):
                            result['year'] = int(meta['Year'])
                        if meta.get('Publisher'):
                            result['publisher'] = meta['Publisher']
                        
                        return result
                        
                except Exception as e:
                    logger.warning(f"  ⚠️ {provider} lookup failed: {e}")
                    continue
            
            logger.info(f"  ❌ No results from isbnlib providers")
            
        except Exception as e:
            logger.error(f"  💥 ISBN lookup failed completely: {e}")
        
        return {} 

    def _clean_for_filename(self, s: str, max_length: int = 50) -> str:
        """Utility to sanitise a string so it can be safely used in a filename."""
        import re
        if not s:
            return "Unknown"
        # Remove any character that is not alphanumeric, whitespace, hyphen or underscore
        cleaned = re.sub(r'[^\w\s\-]', '', s)
        # Collapse whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        # Replace spaces with underscores
        cleaned = cleaned.replace(' ', '_')
        return cleaned[:max_length]

    def _compute_folder_name(self, metadata: dict) -> str:
        """Re-compute the canonical folder / base filename for a book based on current metadata.

        It mirrors the logic in MetadataExtractor.normalize_filename so both CLI and
        web edits stay consistent without importing that heavy module here.
        """
        author   = self._clean_for_filename(str(metadata.get('author', 'Unknown_Author')).split(',')[0], 30)
        title    = self._clean_for_filename(str(metadata.get('title',  'Unknown_Title')), 40)
        year     = str(metadata.get('year', 'Unknown_Year'))
        media_id = metadata.get('isbn') or 'no_id'
        return f"{author}_{title}_{year}_{media_id}"

    def _rename_book_assets(self, old_folder: str, new_folder: str) -> str:
        """Physically rename the on-disk folder and contained files.

        If the target folder already exists we will append a numerical suffix
        to avoid collisions (foldername_1, _2, ...).
        """
        from pathlib import Path
        import shutil, os

        books_root = Path(self.config.BOOKS_PATH)
        old_dir    = books_root / old_folder
        if not old_dir.exists():
            # Might be a legacy layout with files at root – bail out for safety.
            logger.warning(f"Old folder '{old_dir}' not found. Skipping physical rename.")
            return

        # Ensure new folder name is unique
        new_dir = books_root / new_folder
        if new_dir.exists():
            suffix = 1
            while (books_root / f"{new_folder}_{suffix}").exists():
                suffix += 1
            new_folder = f"{new_folder}_{suffix}"
            new_dir = books_root / new_folder

        logger.info(f"Renaming book folder '{old_dir.name}' -> '{new_dir.name}'")
        old_dir.rename(new_dir)

        # Rename files inside the folder that start with the old prefix
        for f in new_dir.iterdir():
            if f.is_file() and f.name.startswith(old_folder):
                new_name = f.name.replace(old_folder, new_folder, 1)
                f.rename(new_dir / new_name)

        # Also attempt to rename any orphaned root-level files (rare)
        for ext in ['.pdf', '.epub', '.mobi', '.azw', '.azw3', '.djvu', '.djv', '.txt']:
            legacy_file = books_root / f"{old_folder}{ext}"
            if legacy_file.exists():
                legacy_file.rename(books_root / f"{new_folder}{ext}")

        # Update metadata.json inside the folder, if present
        meta_path = new_dir / 'metadata.json'
        if meta_path.exists():
            try:
                with open(meta_path, 'r', encoding='utf-8') as fh:
                    meta = json.load(fh)
                meta['folder_name'] = new_folder
                # Update common filename fields if present
                for key in ['filename', 'pdf_filename', 'text_filename']:
                    if key in meta and meta[key]:
                        base, ext = os.path.splitext(meta[key])
                        meta[key] = f"{new_folder}{ext}"
                with open(meta_path, 'w', encoding='utf-8') as fh:
                    json.dump(meta, fh, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"Failed to update inner metadata.json after rename: {e}")

        return new_folder  # Return the possibly suffixed final folder name 