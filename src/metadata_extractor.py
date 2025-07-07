"""
spines metadata extractor
extracts metadata from PDFs and generates JSON files
follows ebooktools escalation procedure: basic -> calibre -> OCR
"""

import os
import json
import hashlib
from pathlib import Path
from datetime import datetime
import PyPDF2
import isbnlib
import re
from typing import Dict, Optional, List, Tuple
import magic
import subprocess
import tempfile
import shutil
from dataclasses import dataclass
from enum import Enum
from difflib import SequenceMatcher
import requests
import time
from services.book_service import BookService
from services.text_service import TextService
from utils.logging import get_logger

# Add pytesseract import
try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False
    print("⚠️ pytesseract not available - OCR text extraction will be limited")

# Add PIL for image processing
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("⚠️ PIL not available - OCR will use command line tools only")

logger = get_logger(__name__)


class MediaType(Enum):
    """Simple media types - keep it minimal"""
    BOOK = "book"                # Books and most documents
    WEB = "web"                  # Web-based resources with URL
    UNKNOWN = "unknown"          # Unclassified


class ExtractionMethod(Enum):
    """Metadata extraction methods in order of escalation"""
    BASIC = "basic"              # PyPDF2 + simple text extraction
    CALIBRE = "calibre"          # Calibre ebook-meta
    CALIBRE_CONVERT = "calibre_convert"  # Calibre convert to txt
    OCR_PARTIAL = "ocr_partial"  # OCR first/last pages only
    OCR_FULL = "ocr_full"        # Full OCR (last resort)


@dataclass
class ExtractionResult:
    """Result of metadata extraction attempt"""
    method: ExtractionMethod
    success: bool
    metadata: Dict
    confidence: float  # 0.0 to 1.0
    isbn_found: bool
    text_extracted: bool
    error: Optional[str] = None


class MetadataExtractor:
    def __init__(self, config, book_service=None, text_service=None):
        self.config = config
        self.library_path = Path(config.BOOKS_PATH)
        self.data_path = Path(config.DATA_PATH)
        self.library_json_path = self.data_path / "library.json"
        self.ocr_queue_path = self.data_path / "ocr_queue.json"
        self.review_queue_path = self.data_path / "review_queue.json"
        
        # Inject services
        self.book_service = book_service or BookService(config)
        self.text_service = text_service or TextService(config)
        
        # Create directories if they don't exist
        self.library_path.mkdir(exist_ok=True)
        self.data_path.mkdir(exist_ok=True)
        
        # Load or create library index
        self.library_index = self.load_library_index()
        
        # OCR settings (following ebooktools defaults)
        self.ocr_enabled = False
        self.ocr_first_pages = 7
        self.ocr_last_pages = 3
        self.ocr_command = "tesseract"  # Can be customized
        
        # A more forgiving regex for finding potential ISBNs.
        # It looks for an optional ISBN/SBN prefix, then captures a sequence of 10 or 13 digits
        # with flexible separators. The result is then cleaned and validated.
        self.isbn_regex = r'(?:ISBN|SBN)?[-\s—–:]{0,3}(((?:\d[-\s—–]*){9}[\dxX])|((?:\d[-\s—–]*){12}\d))'
        
        # Confidence thresholds
        self.min_confidence_auto_accept = 0.7  # Lower threshold - we were being too strict
        self.min_confidence_suggest_ocr = 0.4  # Reasonable threshold for suggesting OCR
        self.min_confidence_auto_process = 0.8  # High confidence for automatic processing
        
        # Multi-copy similarity thresholds
        self.title_similarity_threshold = 0.85  # Levenshtein ratio for titles
        self.author_similarity_threshold = 0.90  # Levenshtein ratio for authors
    
    def load_library_index(self) -> Dict:
        """Load existing library index or create new one"""
        if self.library_json_path.exists():
            with open(self.library_json_path, 'r', encoding='utf-8') as f:
                index = json.load(f)
                # Migrate old format if needed
                if "metadata" not in index:
                    index["metadata"] = {
                        "version": "1.1",
                        "created": index.get("created", datetime.now().isoformat()),
                        "last_updated": datetime.now().isoformat(),
                        "last_scan": 0,  # Unix timestamp
                        "total_books": len(index.get("books", {})),
                        "library_path": str(self.library_path),
                        "contributors": [],  # List of all contributors who have added books
                        "readers": []  # List of all people who have read books
                    }
                
                # One-time fix for corrupted contributor data
                if not index["metadata"].get("contributor_fix_applied", False):
                    self._fix_corrupted_contributors(index)
                    index["metadata"]["contributor_fix_applied"] = True
                    # Save the updated index directly here since self.library_index isn't set yet
                    with open(self.library_json_path, 'w', encoding='utf-8') as f:
                        json.dump(index, f, indent=2, ensure_ascii=False)
                    
                return index
        return {
            "metadata": {
                "version": "1.1",
                "created": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
                "last_scan": 0,  # Unix timestamp
                "total_books": 0,
                "library_path": str(self.library_path),
                "contributors": [],  # List of all contributors who have added books
                "readers": []  # List of all people who have read books
            },
            "books": {}
        }
    
    def save_library_index(self):
        """Save library index to disk with updated metadata"""
        self.library_index["metadata"]["last_updated"] = datetime.now().isoformat()
        self.library_index["metadata"]["total_books"] = len(self.library_index["books"])
        
        with open(self.library_json_path, 'w', encoding='utf-8') as f:
            json.dump(self.library_index, f, indent=2, ensure_ascii=False)
    
    def refresh_library_index(self):
        """Reload library index from disk to pick up external changes (like deletions)"""
        self.library_index = self.load_library_index()
    
    def update_last_scan(self):
        """Update the last scan timestamp"""
        import time
        self.library_index["metadata"]["last_scan"] = time.time()
        self.save_library_index()
    
    def add_contributor(self, contributor: str):
        """Add a contributor to the global list if not already present"""
        if contributor and contributor.strip():
            contributor = contributor.strip()
            contributors = self.library_index["metadata"].get("contributors", [])
            if contributor not in contributors:
                contributors.append(contributor)
                self.library_index["metadata"]["contributors"] = sorted(contributors)
                print(f"➕ Added new contributor: {contributor}")
    
    def add_readers(self, readers: list):
        """Add readers to the global list if not already present"""
        if readers:
            current_readers = self.library_index["metadata"].get("readers", [])
            for reader in readers:
                if reader and reader.strip():
                    reader = reader.strip()
                    if reader not in current_readers:
                        current_readers.append(reader)
                        print(f"📖 Added new reader: {reader}")
            self.library_index["metadata"]["readers"] = sorted(current_readers)
    
    def _fix_corrupted_contributors(self, index: Dict):
        """One-time fix for contributor data that was split into individual characters"""
        print("🔧 Applying one-time fix for corrupted contributor data...")
        fixed_count = 0
        
        all_contributors = set()
        all_readers = set()
        
        # Go through each book
        for book_id, book_info in index.get("books", {}).items():
            folder_name = book_info.get("folder_name", book_id)
            book_dir = self.library_path / folder_name
            metadata_file = book_dir / "metadata.json"
            
            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                    
                    changed = False
                    
                    # Fix contributor field
                    contributor = metadata.get("contributor", [])
                    if isinstance(contributor, str):
                        # Convert string to list
                        if contributor:
                            metadata["contributor"] = [contributor]
                            all_contributors.add(contributor)
                            changed = True
                        else:
                            metadata["contributor"] = []
                    elif isinstance(contributor, list) and contributor:
                        # Check if it's character-split (all single characters)
                        if all(len(c) == 1 for c in contributor if isinstance(c, str)):
                            original_name = ''.join(contributor)
                            metadata["contributor"] = [original_name]
                            all_contributors.add(original_name)
                            print(f"🔧 Fixed character-split contributor: {contributor} -> [{original_name}]")
                            changed = True
                            fixed_count += 1
                        else:
                            # Clean up empty entries
                            cleaned = [c for c in contributor if c and c.strip()]
                            if cleaned != contributor:
                                metadata["contributor"] = cleaned
                                changed = True
                            for c in cleaned:
                                all_contributors.add(c)
                    
                    # Fix read_by field
                    read_by = metadata.get("read_by", [])
                    if isinstance(read_by, list) and read_by:
                        if all(len(r) == 1 for r in read_by if isinstance(r, str)):
                            original_name = ''.join(read_by)
                            metadata["read_by"] = [original_name]
                            all_readers.add(original_name)
                            print(f"🔧 Fixed character-split reader: {read_by} -> [{original_name}]")
                            changed = True
                            fixed_count += 1
                        else:
                            cleaned = [r for r in read_by if r and r.strip()]
                            if cleaned != read_by:
                                metadata["read_by"] = cleaned
                                changed = True
                            for r in cleaned:
                                all_readers.add(r)
                    
                    # Save if changed
                    if changed:
                        with open(metadata_file, 'w', encoding='utf-8') as f:
                            json.dump(metadata, f, indent=2, ensure_ascii=False)
                
                except Exception as e:
                    print(f"⚠️ Error fixing {metadata_file}: {e}")
        
        # Update global lists
        index["metadata"]["contributors"] = sorted(list(all_contributors))
        index["metadata"]["readers"] = sorted(list(all_readers))
        
        if fixed_count > 0:
            print(f"✅ Fixed {fixed_count} corrupted contributor/reader entries")
        else:
            print("✅ No corrupted data found")
        
        # Update the passed index object (will be saved by caller)
        # Don't call save_library_index() here as self.library_index isn't set yet
    
    def get_files_needing_scan(self) -> tuple:
        """Get files that need scanning based on modification time vs last scan"""
        import time
        
        last_scan_time = self.library_index["metadata"]["last_scan"]
        new_files = []
        modified_files = []
        
        # Find all supported ebook files in the library path (not in subdirectories)
        supported_extensions = ['.pdf', '.epub', '.mobi', '.azw', '.azw3', '.djvu', '.djv']
        
        for ext in supported_extensions:
            for ebook_file in self.library_path.glob(f"*{ext}"):
                if ebook_file.is_file():
                    mtime = ebook_file.stat().st_mtime
                    
                    # Check if this file is already processed
                    is_processed = False
                    file_book_id = None
                    
                    # Look through existing books to see if this file is already processed
                    for book_id, book_info in self.library_index["books"].items():
                        folder_name = book_info.get("folder_name", book_id)
                        book_dir = self.library_path / folder_name
                        
                        # Check if this matches an existing book by checking metadata
                        if book_dir.exists():
                            try:
                                metadata_file = book_dir / "metadata.json"
                                if metadata_file.exists():
                                    with open(metadata_file, 'r') as f:
                                        metadata = json.load(f)
                                        
                                        # Check if original filename matches
                                        if metadata.get("original_filename") == ebook_file.name:
                                            is_processed = True
                                            file_book_id = book_id
                                            print(f"✅ File already processed: {ebook_file.name} -> {folder_name}")
                                            break
                            except Exception as e:
                                print(f"⚠️ Error checking {book_dir}: {e}")
                                pass
                    
                    if not is_processed:
                        # File is new - add it regardless of scan time for now
                        new_files.append(ebook_file)
                        print(f"🆕 New file detected: {ebook_file.name}")
                    elif mtime > last_scan_time:
                        # File is processed but was modified since last scan
                        modified_files.append((ebook_file, file_book_id))
                        print(f"📝 Modified file detected: {ebook_file.name}")
        
        return new_files, modified_files
    
    def generate_book_id(self, file_path: str) -> str:
        """Generate unique ID for book based on file hash"""
        with open(file_path, 'rb') as f:
            file_hash = hashlib.md5(f.read()).hexdigest()[:12]
        return file_hash
    
    def extract_metadata_with_escalation(self, pdf_path: Path) -> ExtractionResult:
        """
        Extract metadata using escalation procedure
        Python approach: basic -> calibre -> calibre convert -> OCR (first/last pages) -> OCR queue
        """
        print(f"🔍 Starting metadata extraction for: {pdf_path.name}")
        
        results = []
        
        # Method 1: Basic extraction (PyPDF2 + simple text)
        try:
            result = self._extract_basic_metadata(pdf_path)
            results.append(result)
            print(f"  📄 Basic extraction: confidence={result.confidence:.2f}, isbn={result.isbn_found}")
            
            if result.confidence >= self.min_confidence_auto_accept:
                print(f"  ✅ High confidence result from basic extraction")
                return result
                
        except Exception as e:
            print(f"  ⚠️ Basic extraction failed: {e}")
        
        # Method 2: Calibre ebook-meta
        try:
            result = self._extract_calibre_metadata(pdf_path)
            results.append(result)
            print(f"  📚 Calibre extraction: confidence={result.confidence:.2f}, isbn={result.isbn_found}")
            
            if result.confidence >= self.min_confidence_auto_accept:
                print(f"  ✅ High confidence result from Calibre")
                return result
                
        except Exception as e:
            print(f"  ⚠️ Calibre extraction failed: {e}")
        
        # Method 3: Calibre convert to text (more thorough text extraction)
        try:
            result = self._extract_calibre_convert_metadata(pdf_path)
            results.append(result)
            print(f"  🔄 Calibre convert: confidence={result.confidence:.2f}, isbn={result.isbn_found}")
            
            if result.confidence >= self.min_confidence_auto_accept:
                print(f"  ✅ High confidence result from Calibre convert")
                return result
                
        except Exception as e:
            print(f"  ⚠️ Calibre convert failed: {e}")
        
        # Find the best result so far
        best_result = max(results, key=lambda r: r.confidence) if results else None
        
        # If confidence is still low, we'll send it to the review queue. No more auto-OCR.
        if not best_result or best_result.confidence < self.min_confidence_auto_process:
            print(f"  📋 Low confidence ({best_result.confidence:.2f} if best_result else 'no results'), will send to review queue.")
            
            # If all methods failed, create a fallback result to send to the review queue
            if not best_result:
                best_result = ExtractionResult(
                    method=ExtractionMethod.BASIC,
                    success=False,
                    metadata=self._get_fallback_metadata(pdf_path),
                    confidence=0.1,
                    isbn_found=False,
                    text_extracted=False,
                    error="All extraction methods failed"
                )
            
            # The calling function (process_book_in_temp) will handle adding to the review queue.
            # We just return the best result we found, even if it's low confidence.
            return best_result

        # If we reach here, it means we have a result with sufficient confidence
        print(f"  ✅ Sufficient confidence result from {best_result.method.value} (confidence: {best_result.confidence:.2f}).")
        return best_result
    
    def _extract_basic_metadata(self, pdf_path: Path) -> ExtractionResult:
        """Basic metadata extraction using PyPDF2"""
        metadata = self._get_fallback_metadata(pdf_path)
        isbn_found = False
        text_extracted = False
        confidence = 0.2  # Base confidence for filename-based metadata
        
        try:
            with open(pdf_path, 'rb') as f:
                pdf = PyPDF2.PdfReader(f)
                
                # Extract page count
                metadata["pages"] = len(pdf.pages)
                
                # Extract PDF metadata
                if pdf.metadata:
                    if pdf.metadata.title and pdf.metadata.title.strip():
                        metadata["title"] = pdf.metadata.title.strip()
                        confidence += 0.2
                    if pdf.metadata.author and pdf.metadata.author.strip():
                        metadata["author"] = pdf.metadata.author.strip()
                        confidence += 0.2
                    if pdf.metadata.creation_date:
                        year = pdf.metadata.creation_date.year
                        if 1900 <= year <= datetime.now().year:
                            metadata["year"] = year
                            confidence += 0.1
                
                # Use improved text extraction for thorough ISBN search
                # Check first 15 pages for ISBN (copyright page, back cover info, etc.)
                text = self._extract_text_for_isbn_search(pdf, max_pages=15)
                text_extracted = bool(text)
                
                # Look for ISBN in extracted text FIRST (before expensive full text extraction)
                if text:
                    isbn = self._find_isbn_in_text(text)
                    if isbn:
                        metadata["isbn"] = isbn
                        isbn_found = True
                        confidence += 0.3
                        print(f"📚 Found ISBN via basic extraction: {isbn}")
                        
                        # Try to enhance metadata with ISBN lookup via BookService
                        isbn_metadata = self.book_service.enhanced_isbn_lookup(isbn)
                        if isbn_metadata:
                            # ISBN data is ALWAYS better than filename-based fallback data
                            original_title = metadata.get('title', '')
                            
                            # If title is just the filename, replace it completely
                            if (original_title == pdf_path.stem or 
                                '_' in original_title or 
                                len(original_title.split()) > 8):
                                metadata['title'] = isbn_metadata.get('title', original_title)
                                print(f"📚 Replaced filename title with: {isbn_metadata.get('title', 'N/A')}")
                            elif isbn_metadata.get('title'):
                                metadata['title'] = isbn_metadata.get('title')
                                print(f"📚 Updated title with: {isbn_metadata.get('title', 'N/A')}")
                            
                            # Always prefer ISBN author and year
                            if isbn_metadata.get('author'):
                                metadata['author'] = isbn_metadata.get('author')
                            if isbn_metadata.get('year'):
                                metadata['year'] = isbn_metadata.get('year')
                            if isbn_metadata.get('publisher'):
                                metadata['publisher'] = isbn_metadata.get('publisher')
                            
                            confidence += 0.5  # ISBN lookup is VERY valuable
                            print(f"📚 Enhanced with ISBN lookup: {isbn_metadata.get('title', 'N/A')}")
                
                # OPTIMIZATION: Only do full text extraction if we have high confidence or need it
                # Skip full text extraction if we found a good ISBN and have decent metadata
                should_extract_full_text = (
                    not isbn_found or  # No ISBN found, might need full text for other extraction methods
                    confidence < 0.7   # Low confidence, full text might help
                )
                
                if should_extract_full_text and text_extracted:
                    print(f"💡 Extracting full text for future use (ISBN: {isbn_found}, confidence: {confidence:.2f})...")
                    try:
                        # Use the new TextService
                        full_text_result = self.text_service.extract_full_text(pdf_path, save_to_file=False)
                        if full_text_result['success']:
                            # Save the full text to a temp file next to the PDF for later use
                            temp_txt_path = pdf_path.with_suffix('.txt')
                            with open(temp_txt_path, 'w', encoding='utf-8') as f:
                                f.write(full_text_result['text'])
                            print(f"  💾 Saved full text to temp file: {temp_txt_path.name} ({full_text_result['text_length']} chars)")
                    except Exception as e:
                        print(f"  ⚠️ Could not save temp text file: {e}")
                else:
                    print(f"⚡ Skipping full text extraction (ISBN: {isbn_found}, confidence: {confidence:.2f})")
                
        except Exception as e:
            return ExtractionResult(
                method=ExtractionMethod.BASIC,
                success=False,
                metadata=metadata,
                confidence=0.1,
                isbn_found=False,
                text_extracted=False,
                error=str(e)
            )
        
        return ExtractionResult(
            method=ExtractionMethod.BASIC,
            success=True,
            metadata=metadata,
            confidence=min(confidence, 1.0),
            isbn_found=isbn_found,
            text_extracted=text_extracted
        )
    
    def _extract_calibre_metadata(self, pdf_path: Path) -> ExtractionResult:
        """Extract metadata using Calibre's ebook-meta command"""
        metadata = self._get_fallback_metadata(pdf_path)
        confidence = 0.2  # Base confidence for Calibre
        isbn_found = False
        
        try:
            # Use Calibre's ebook-meta command
            result = subprocess.run([
                'ebook-meta', str(pdf_path)
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0 and result.stdout:
                # Parse the output
                lines = result.stdout.split('\n')
                for line in lines:
                    line = line.strip()
                    if line.startswith('Title'):
                        title = line.split(':', 1)[1].strip()
                        if title and title != 'Unknown' and title != pdf_path.stem:
                            metadata['title'] = title
                            confidence += 0.2
                    elif line.startswith('Author(s)'):
                        author = line.split(':', 1)[1].strip()
                        if author and author != 'Unknown':
                            metadata['author'] = author
                            confidence += 0.2
                    elif line.startswith('Published'):
                        pub_info = line.split(':', 1)[1].strip()
                        year_match = re.search(r'\b(19|20)\d{2}\b', pub_info)
                        if year_match:
                            metadata['year'] = int(year_match.group())
                            confidence += 0.1
                    elif 'ISBN' in line:
                        isbn_match = re.search(self.isbn_regex, line)
                        if isbn_match:
                            raw_isbn = isbn_match.group(1).strip()
                            isbn = re.sub(r'[-\s—–]', '', raw_isbn)
                            if isbnlib.is_isbn13(isbn) or isbnlib.is_isbn10(isbn):
                                metadata['isbn'] = isbn
                                isbn_found = True
                                confidence += 0.3
                
                # If we found an ISBN, try to enhance with lookup
                if isbn_found and metadata.get('isbn'):
                    print(f"📚 Found ISBN via Calibre: {metadata['isbn']}")
                    isbn_metadata = self.book_service.enhanced_isbn_lookup(metadata['isbn'])
                    if isbn_metadata:
                        # ISBN data is ALWAYS better than filename-based data
                        # Only keep Calibre data if it's actually from PDF metadata, not filename
                        original_title = metadata.get('title', '')
                        original_author = metadata.get('author', '')
                        
                        # If title looks like a filename (contains underscores, dashes, etc), replace it
                        if ('_' in original_title or '-' in original_title or 
                            original_title == pdf_path.stem or 
                            len(original_title.split()) > 8):  # Very long titles are usually filenames
                            metadata['title'] = isbn_metadata.get('title', original_title)
                            print(f"📚 Replaced filename-based title with: {isbn_metadata.get('title', 'N/A')}")
                        elif isbn_metadata.get('title'):
                            metadata['title'] = isbn_metadata.get('title')
                            print(f"📚 Updated title with: {isbn_metadata.get('title', 'N/A')}")
                        
                        # Always use ISBN author if available (more reliable than filename parsing)
                        if isbn_metadata.get('author'):
                            metadata['author'] = isbn_metadata.get('author')
                            print(f"📚 Updated author with: {isbn_metadata.get('author', 'N/A')}")
                        
                        # Always use ISBN year and publisher if available
                        if isbn_metadata.get('year'):
                            metadata['year'] = isbn_metadata.get('year')
                        if isbn_metadata.get('publisher'):
                            metadata['publisher'] = isbn_metadata.get('publisher')
                        
                        confidence += 0.4  # ISBN lookup is VERY valuable
                        print(f"📚 Enhanced with ISBN lookup: {isbn_metadata.get('title', 'N/A')}")
                
                return ExtractionResult(
                    method=ExtractionMethod.CALIBRE,
                    success=True,
                    metadata=metadata,
                    confidence=min(confidence, 1.0),
                    isbn_found=isbn_found,
                    text_extracted=True
                )
                
        except Exception as e:
            print(f"Calibre extraction failed: {e}")
            
        return ExtractionResult(
            method=ExtractionMethod.CALIBRE,
            success=False,
            metadata=metadata,
            confidence=0.1,
            isbn_found=False,
            text_extracted=False,
            error=str(e) if 'e' in locals() else "Calibre command failed"
        )
    

    
    def _extract_calibre_convert_metadata(self, pdf_path: Path) -> ExtractionResult:
        """Extract metadata by converting PDF to text with Calibre"""
        metadata = self._get_fallback_metadata(pdf_path)
        confidence = 0.2
        
        try:
            with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as tmp_file:
                tmp_path = tmp_file.name
            
            # Convert PDF to text using Calibre
            result = subprocess.run([
                'ebook-convert', str(pdf_path), tmp_path
            ], capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0 and os.path.exists(tmp_path):
                with open(tmp_path, 'r', encoding='utf-8', errors='ignore') as f:
                    text = f.read()
                
                os.unlink(tmp_path)  # Clean up
                
                if text and len(text.strip()) > 100:  # Meaningful text extracted
                    confidence += 0.3
                    
                    # Look for ISBN in the full text with improved search
                    isbn = self._find_isbn_in_text(text)
                    isbn_found = False
                    
                    if isbn:
                        metadata["isbn"] = isbn
                        isbn_found = True
                        confidence += 0.3
                        
                        # Enhance with ISBN lookup
                        isbn_metadata = self.book_service.enhanced_isbn_lookup(isbn)
                        if isbn_metadata:
                            metadata.update(isbn_metadata)
                            confidence += 0.2
                    
                    return ExtractionResult(
                        method=ExtractionMethod.CALIBRE_CONVERT,
                        success=True,
                        metadata=metadata,
                        confidence=min(confidence, 1.0),
                        isbn_found=isbn_found,
                        text_extracted=True
                    )
                else:
                    # Text conversion succeeded but no meaningful content
                    return ExtractionResult(
                        method=ExtractionMethod.CALIBRE_CONVERT,
                        success=False,
                        metadata=metadata,
                        confidence=0.1,
                        isbn_found=False,
                        text_extracted=False,
                        error="No meaningful text extracted from conversion"
                    )
            else:
                # Conversion failed
                return ExtractionResult(
                    method=ExtractionMethod.CALIBRE_CONVERT,
                    success=False,
                    metadata=metadata,
                    confidence=0.1,
                    isbn_found=False,
                    text_extracted=False,
                    error=f"Calibre conversion failed with exit code {result.returncode}"
                )
            
        except Exception as e:
            return ExtractionResult(
                method=ExtractionMethod.CALIBRE_CONVERT,
                success=False,
                metadata=metadata,
                confidence=0.1,
                isbn_found=False,
                text_extracted=False,
                error=str(e)
            )
    
    def _extract_text_for_isbn_search(self, pdf: PyPDF2.PdfReader, max_pages: int = 15) -> str:
        """Extract text from strategic pages for ISBN detection"""
        total_pages = len(pdf.pages)
        text_parts = []
        
        # Strategy: Check pages where ISBNs are most likely to appear
        # 1. First few pages (title page, copyright page)
        # 2. Last few pages (back cover, publication info)
        # 3. A couple pages from the middle (sometimes has publication info)
        
        pages_to_check = set()
        
        # First 8 pages (covers title page, copyright, table of contents)
        for i in range(min(8, total_pages)):
            pages_to_check.add(i)
        
        # Last 5 pages (back cover, publication info)
        for i in range(max(0, total_pages - 5), total_pages):
            pages_to_check.add(i)
        
        # A couple pages from the middle (sometimes has publication info)
        if total_pages > 20:
            middle = total_pages // 2
            pages_to_check.add(middle)
            pages_to_check.add(middle + 1)
        
        # Limit to max_pages to avoid excessive processing
        pages_to_check = sorted(list(pages_to_check))[:max_pages]
        
        print(f"🔍 Searching for ISBN in pages: {pages_to_check}")
        
        for page_num in pages_to_check:
            try:
                page_text = pdf.pages[page_num].extract_text()
                if page_text and page_text.strip():
                    # Look for ISBN patterns in this page specifically
                    if 'isbn' in page_text.lower() or re.search(r'\b97[89]\d{10}\b', page_text):
                        text_parts.append(f"--- Page {page_num + 1} (ISBN search) ---\n{page_text}")
                        print(f"  📚 Page {page_num + 1}: Found potential ISBN content")
                    else:
                        # Still include the text but with less priority
                        text_parts.append(page_text)
            except Exception as e:
                print(f"  ⚠️ Could not extract text from page {page_num + 1}: {e}")
                continue
        
        combined_text = '\n\n'.join(text_parts)
        print(f"✅ Extracted {len(combined_text)} characters for ISBN search from {len(pages_to_check)} pages")
        return combined_text
    
    def _find_isbn_in_text(self, text: str) -> Optional[str]:
        """Find and validate ISBN in text with improved detection"""
        print(f"🔍 Searching for ISBN in {len(text)} characters of text...")
        
        # This regex is more forgiving and captures sequences of 10 or 13 digits,
        # allowing for various separators. It's designed to find candidates
        # which are then cleaned and validated.
        # It looks for an optional ISBN/SBN prefix, then captures the number.
        isbn_candidate_regex = r'(?:ISBN|SBN)?[-\s—–:]{0,3}(((?:\d[-\s—–]*){9}[\dxX])|((?:\d[-\s—–]*){12}\d))'
        
        # A second, simpler pattern for numbers without a clear prefix,
        # but structured like an ISBN (e.g., inside parenthesis or on its own line).
        isbn_structure_regex = r'\b(((?:\d[-\s—–]*){9}[\dxX])|((?:\d[-\s—–]*){12}\d))\b'

        isbn_patterns = [
            isbn_candidate_regex,
            isbn_structure_regex
        ]
        
        all_matches = []
        for i, pattern in enumerate(isbn_patterns):
            # finditer is better for overlapping matches and getting match objects
            for match in re.finditer(pattern, text, re.IGNORECASE):
                # The actual number is in the first main capturing group
                captured_string = match.group(1)
                if captured_string:
                    all_matches.append(captured_string.strip())

        if all_matches:
            print(f"  🔍 Found {len(all_matches)} potential ISBN candidates: {all_matches[:5]}{'...' if len(all_matches) > 5 else ''}")

        # Sort matches by priority (longer ISBNs first, then by position in text)
        unique_matches = list(set(all_matches))
        unique_matches.sort(key=lambda x: (-len(re.sub(r'[-\s—–]', '', x)), text.find(x)))
        
        print(f"  📋 Checking {len(unique_matches)} unique matches: {unique_matches}")
        
        for i, match in enumerate(unique_matches):
            # Clean the ISBN
            isbn = re.sub(r'[-\s—–]', '', match)
            print(f"  🔍 Candidate {i+1}: '{match}' → cleaned: '{isbn}' (length: {len(isbn)})")
            
            # Validate ISBN
            if len(isbn) == 10 or len(isbn) == 13:
                is_isbn13 = isbnlib.is_isbn13(isbn)
                is_isbn10 = isbnlib.is_isbn10(isbn)
                print(f"    📚 ISBN validation: is_isbn13={is_isbn13}, is_isbn10={is_isbn10}")
                
                if is_isbn13 or is_isbn10:
                    # Additional blacklist check (from ebooktools)
                    blacklist_pattern = r'^(0123456789|([0-9xX])\2{9})$'
                    is_blacklisted = re.match(blacklist_pattern, isbn)
                    print(f"    🔍 Blacklist check: {'REJECTED' if is_blacklisted else 'OK'}")
                    
                    if not is_blacklisted:
                        print(f"✅ Found valid ISBN: {isbn}")
                        return isbn
                    else:
                        print(f"⚠️ Rejected blacklisted ISBN: {isbn}")
                else:
                    # Sometimes cleaning reveals a non-ISBN number.
                    # e.g., a 12-digit number that isn't a valid format.
                    # isbnlib will handle this.
                    print(f"    ❌ Invalid ISBN format according to isbnlib")
            else:
                print(f"    ❌ Incorrect length after cleaning (need 10 or 13 digits)")
        
        print(f"❌ No valid ISBN found in text (checked {len(all_matches)} total matches)")
        return None
    
    def _get_fallback_metadata(self, file_path: Path) -> Dict:
        """Get basic metadata from filename and file stats"""
        file_extension = file_path.suffix.lower()
        
        # Determine file type
        if file_extension == '.pdf':
            file_type = 'pdf'
        elif file_extension in ['.epub', '.mobi', '.azw', '.azw3']:
            file_type = 'ebook'
        elif file_extension in ['.djvu', '.djv']:
            file_type = 'djvu'
        elif file_extension in ['.txt', '.rtf']:
            file_type = 'text'
        else:
            file_type = 'unknown'
        
        metadata = {
            "title": file_path.stem,
            "author": "Unknown",
            "year": None,
            "isbn": None,
            "issn": None,
            "url": None,
            "publisher": None,
            "pages": 0,
            "file_size": file_path.stat().st_size,
            "file_type": file_type,
            "media_type": MediaType.UNKNOWN.value
        }
        
        # Apply enhanced media type detection even to fallback metadata
        metadata["media_type"] = self.detect_media_type(metadata)
        
        return metadata
    
    def add_to_ocr_queue(self, pdf_path: Path, reason: str = "low_confidence") -> None:
        """Add a book to the OCR processing queue"""
        queue = self.load_ocr_queue()
        
        book_entry = {
            "path": str(pdf_path),
            "filename": pdf_path.name,
            "reason": reason,
            "added": datetime.now().isoformat(),
            "status": "pending"
        }
        
        # Avoid duplicates
        existing = [item for item in queue if item["path"] == str(pdf_path)]
        if not existing:
            queue.append(book_entry)
            self.save_ocr_queue(queue)
            print(f"➕ Added to OCR queue: {pdf_path.name} (reason: {reason})")
    
    def load_ocr_queue(self) -> List[Dict]:
        """Load OCR processing queue"""
        if self.ocr_queue_path.exists():
            with open(self.ocr_queue_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    
    def save_ocr_queue(self, queue: List[Dict]) -> None:
        """Save OCR processing queue"""
        with open(self.ocr_queue_path, 'w', encoding='utf-8') as f:
            json.dump(queue, f, indent=2, ensure_ascii=False)
    
    def process_ocr_queue(self, progress_callback=None) -> List[str]:
        """Process books in the OCR queue with progress tracking"""
        queue = self.load_ocr_queue()
        pending_items = [item for item in queue if item["status"] == "pending"]
        
        if not pending_items:
            print("📋 OCR queue is empty")
            return []
        
        processed_ids = []
        total = len(pending_items)
        
        print(f"🔍 Processing {total} items in OCR queue...")
        
        for i, item in enumerate(pending_items):
            if progress_callback:
                progress_callback(i, total, item["filename"])
            
            try:
                pdf_path = Path(item["path"])
                if pdf_path.exists():
                    # Try OCR extraction
                    result = self._extract_ocr_metadata(pdf_path)
                    
                    if result.success and result.confidence > 0.5:
                        # Process the book with OCR metadata
                        book_id = self.process_book_with_metadata(pdf_path, result.metadata)
                        if book_id:
                            processed_ids.append(book_id)
                            item["status"] = "completed"
                            item["completed"] = datetime.now().isoformat()
                            print(f"  ✅ OCR success: {pdf_path.name}")
                        else:
                            item["status"] = "failed"
                            print(f"  ❌ Processing failed: {pdf_path.name}")
                    else:
                        item["status"] = "failed"
                        item["error"] = result.error or "OCR extraction failed"
                        print(f"  ❌ OCR failed: {pdf_path.name}")
                else:
                    item["status"] = "missing"
                    print(f"  ⚠️ File not found: {item['path']}")
                    
            except Exception as e:
                item["status"] = "error"
                item["error"] = str(e)
                print(f"  💥 Error processing {item['filename']}: {e}")
        
        # Save updated queue
        self.save_ocr_queue(queue)
        
        if progress_callback:
            progress_callback(total, total, "Complete")
        
        return processed_ids
    
    def _extract_ocr_metadata(self, pdf_path: Path, full_ocr: bool = False) -> ExtractionResult:
        """Extract metadata using OCR (Tesseract)"""
        metadata = self._get_fallback_metadata(pdf_path)
        confidence = 0.1
        
        try:
            # Convert PDF pages to images, then OCR using TextService
            text = self.text_service._simple_ocr_extraction(pdf_path)
            
            if text and len(text.strip()) > 50:
                confidence += 0.4
                
                # Look for ISBN in OCR text
                isbn = self._find_isbn_in_text(text)
                isbn_found = False
                
                if isbn:
                    metadata["isbn"] = isbn
                    isbn_found = True
                    confidence += 0.3
                    
                    # Enhance with ISBN lookup
                    isbn_metadata = self.book_service.enhanced_isbn_lookup(isbn)
                    if isbn_metadata:
                        metadata.update(isbn_metadata)
                        confidence += 0.2
                
                method = ExtractionMethod.OCR_FULL if full_ocr else ExtractionMethod.OCR_PARTIAL
                
                return ExtractionResult(
                    method=method,
                    success=True,
                    metadata=metadata,
                    confidence=min(confidence, 1.0),
                    isbn_found=isbn_found,
                    text_extracted=True
                )
                
        except Exception as e:
            method = ExtractionMethod.OCR_FULL if full_ocr else ExtractionMethod.OCR_PARTIAL
            return ExtractionResult(
                method=method,
                success=False,
                metadata=metadata,
                confidence=0.1,
                isbn_found=False,
                text_extracted=False,
                error=str(e)
            )
    

    
    def extract_and_structure_text(self, file_path: Path):
        """
        Main public method to extract, normalize, and structure text from a file.
        This method will be called when a new file is detected.
        """
        # Implement the logic to extract, normalize, and structure text from the file
        pass
    
    def process_book_with_multi_copy_detection(self, file_path: Path, metadata: Dict, contributor: str = "unknown") -> Optional[str]:
        """Process a book with given metadata, including multi-copy detection"""
        # Generate book ID
        book_id = self.generate_book_id(str(file_path))
        
        # Ensure file_type is set (needed for library index)
        if "file_type" not in metadata:
            file_extension = file_path.suffix.lower()
            if file_extension == '.pdf':
                metadata["file_type"] = 'pdf'
            elif file_extension in ['.epub', '.mobi', '.azw', '.azw3']:
                metadata["file_type"] = 'ebook'
            elif file_extension in ['.djvu', '.djv']:
                metadata["file_type"] = 'djvu'
            elif file_extension in ['.txt', '.rtf']:
                metadata["file_type"] = 'text'
            else:
                metadata["file_type"] = 'unknown'
        
        # Ensure media_type is set if not already present
        if "media_type" not in metadata:
            metadata["media_type"] = self.detect_media_type(metadata)
        
        # Add additional fields
        metadata.update({
            "id": book_id,
            "original_filename": file_path.name,
            "contributor": [contributor] if contributor else [],
            "date_added": datetime.now().isoformat(),
            "read_by": [],
            "tags": metadata.get("tags", []),
            "notes": metadata.get("notes", "")
        })
        
        # Check for similar books (multi-copy detection)
        similar_books = self.find_similar_books(metadata)
        copy_action = metadata.get('_copy_action', 'auto')
        
        if similar_books:
            print(f"🔍 Found {len(similar_books)} similar book(s) during review approval")
            for similar in similar_books[:3]:  # Show top 3
                print(f"  📚 {similar['similarity_type']}: {similar['metadata'].get('title', 'Unknown')} "
                      f"(confidence: {similar['confidence']:.2f})")
            
            should_create_separate_copy = False
            
            if copy_action == 'separate_copy':
                should_create_separate_copy = True
                print(f"  🆕 User chose to create separate copy")
            elif copy_action == 'add_to_existing':
                should_create_separate_copy = False
                print(f"  📚 User chose to add to existing book")
                # Find the best match to add to
                best_match = similar_books[0]
                existing_book_id = best_match['book_id']
                print(f"  ➕ Adding contributor '{contributor}' to existing book: {existing_book_id}")
                # We'll add the contributor to the existing book instead of creating new
                return self._add_contributor_to_existing_book(existing_book_id, contributor, file_path)
            else:  # auto
                # Check if any similar book has different contributors
                for similar in similar_books:
                    existing_contributors = similar['metadata'].get('contributor', [])
                    if contributor not in existing_contributors:
                        should_create_separate_copy = True
                        print(f"  🆕 Different contributor '{contributor}' - will create separate copy")
                        break
            
            if should_create_separate_copy:
                # Add contributor name to filename to distinguish copies
                metadata['copy_suffix'] = f"_{contributor}_copy"
                print(f"  📁 Adding copy suffix: {metadata['copy_suffix']}")
                
                # Generate a new unique book ID for this contributor copy
                book_id = f"{book_id}_{contributor}"
                metadata['id'] = book_id
                print(f"  🆔 New book ID for contributor copy: {book_id}")
            
            # Handle the duplicates/related copies
            metadata = self.handle_potential_duplicate(metadata, similar_books)
        
        # Clean up the internal copy action flag
        if '_copy_action' in metadata:
            del metadata['_copy_action']
        
        # Track this contributor globally
        if contributor:
            self.add_contributor(contributor)
        
        # Generate normalized folder name
        folder_name = self.normalize_filename(metadata)
        
        # Create book directory with normalized name
        book_dir = self.library_path / folder_name
        book_dir.mkdir(exist_ok=True)
        
        # Generate normalized filename and move the original file
        file_extension = file_path.suffix.lower()
        new_filename = f"{folder_name}{file_extension}"
        new_file_path = book_dir / new_filename
        
        # Move and rename the original file (no duplication)
        if not new_file_path.exists():
            shutil.move(str(file_path), str(new_file_path))
            print(f"  → Moved and renamed to: {folder_name}/{new_filename}")
        
        # Update metadata with new paths
        metadata.update({
            "folder_name": folder_name,
            "filename": new_filename,
            "folder_path": str(book_dir.relative_to(self.library_path.parent))
        })
        
        # For backwards compatibility with PDFs
        if file_extension == '.pdf':
            metadata["pdf_filename"] = new_filename
        
        # Save metadata
        metadata_path = book_dir / "metadata.json"
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        # Update library index
        self.library_index["books"][book_id] = {
            "id": book_id,
            "title": metadata["title"],
            "author": metadata["author"],
            "year": metadata["year"],
            "isbn": metadata["isbn"],
            "folder_name": folder_name,
            "path": str(book_dir.relative_to(self.library_path.parent)),
            "date_added": metadata["date_added"],
            "extraction_confidence": metadata.get("extraction_confidence", 0.5),
            "file_type": metadata["file_type"]
        }
        
        # CRITICAL: Save the library index to disk!
        self.save_library_index()
        print(f"✅ Book successfully processed from review queue: {metadata['title']}")
        
        # Automatically extract full text for PDFs (part of review approval)
        if file_extension == '.pdf':
            print(f"📄 Setting up text extraction for review approval...")
            
            # Check if we have a temp text file from metadata extraction
            temp_txt_path = file_path.with_suffix('.txt')
            final_txt_path = book_dir / f"{folder_name}.txt"
            
            if temp_txt_path.exists():
                # Move the temp text file to the final location
                try:
                    shutil.move(str(temp_txt_path), str(final_txt_path))
                    print(f"  ✅ Moved existing text file from temp: {final_txt_path.name}")
                    
                    # Update metadata with text info
                    if final_txt_path.exists():
                        text_length = len(final_txt_path.read_text(encoding='utf-8'))
                        metadata_path = book_dir / "metadata.json"
                        if metadata_path.exists():
                            try:
                                with open(metadata_path, 'r', encoding='utf-8') as f:
                                    book_metadata = json.load(f)
                                book_metadata.update({
                                    'text_extracted': datetime.now().isoformat(),
                                    'text_filename': f"{folder_name}.txt",
                                    'text_length': text_length,
                                    'text_extraction_method': 'moved_from_temp'
                                })
                                with open(metadata_path, 'w', encoding='utf-8') as f:
                                    json.dump(book_metadata, f, indent=2, ensure_ascii=False)
                                print(f"  ✅ Updated metadata with moved text info")
                            except Exception as e:
                                print(f"  ⚠️ Could not update metadata: {e}")
                                
                except Exception as e:
                    print(f"  ⚠️ Could not move temp text file: {e}")
                    # Fall back to fresh extraction
                    temp_txt_path = None
            
            if not final_txt_path.exists():
                # No temp file existed or move failed - extract fresh
                print(f"  📄 No temp text file found, extracting fresh...")
                try:
                    text_result = self.text_service.extract_full_text(new_file_path, save_to_file=True)
                    if text_result['success']:
                        print(f"  ✅ Text extraction successful: {text_result['text_length']} characters using {text_result['method']}")
                    else:
                        print(f"  ⚠️ Text extraction failed: {text_result.get('text', 'Unknown error')}")
                except Exception as e:
                    print(f"  ⚠️ Text extraction error: {e}")
        
        return book_id

    def process_book_with_metadata(self, pdf_path: Path, metadata: Dict, contributor: str = "unknown") -> Optional[str]:
        """Process a book with pre-extracted metadata"""
        # Similar to process_book but uses provided metadata
        if not pdf_path.exists() or pdf_path.suffix.lower() != '.pdf':
            print(f"Skipping {pdf_path}: not a valid PDF")
            return None
        
        # Generate book ID
        book_id = self.generate_book_id(str(pdf_path))
        
        # Skip if already processed
        if book_id in self.library_index["books"]:
            print(f"📚 Book already processed: {pdf_path.name}")
            return book_id
        
        print(f"Processing with metadata: {pdf_path.name}")
        
        # Add additional fields to provided metadata
        metadata.update({
            "id": book_id,
            "original_filename": pdf_path.name,
            "contributor": [contributor] if contributor else [],
            "date_added": datetime.now().isoformat(),
            "read_by": [],
            "tags": [],
            "notes": ""
        })
        
        # Apply enhanced media type detection
        metadata["media_type"] = self.detect_media_type(metadata)
        
        # Add contextual metadata based on media type
        metadata = self.add_contextual_metadata(metadata)
        
        # Check for similar books (multi-copy detection)
        similar_books = self.find_similar_books(metadata)
        if similar_books:
            print(f"🔍 Found {len(similar_books)} similar book(s)")
            for similar in similar_books[:3]:  # Show top 3
                print(f"  📚 {similar['similarity_type']}: {similar['metadata'].get('title', 'Unknown')} "
                      f"(confidence: {similar['confidence']:.2f})")
            
            # Handle the duplicates/related copies
            metadata = self.handle_potential_duplicate(metadata, similar_books)
        
        # Track contributor
        if contributor:
            self.add_contributor(contributor)
        
        # Generate normalized folder name
        folder_name = self.normalize_filename(metadata)
        
        # Create book directory
        book_dir = self.library_path / folder_name
        book_dir.mkdir(exist_ok=True)
        
        # Move and rename PDF
        pdf_filename = f"{folder_name}.pdf"
        new_pdf_path = book_dir / pdf_filename
        
        if not new_pdf_path.exists():
            shutil.move(str(pdf_path), str(new_pdf_path))
            print(f"  → Moved to: {folder_name}/{pdf_filename}")
        
        # Update metadata with paths
        metadata.update({
            "folder_name": folder_name,
            "pdf_filename": pdf_filename,
            "folder_path": str(book_dir.relative_to(self.library_path.parent))
        })
        
        # Save metadata
        metadata_path = book_dir / "metadata.json"
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        # Update library index
        self.library_index["books"][book_id] = {
            "id": book_id,
            "title": metadata["title"],
            "author": metadata["author"],
            "year": metadata["year"],
            "isbn": metadata["isbn"],
            "folder_name": folder_name,
            "path": str(book_dir.relative_to(self.library_path.parent)),
            "date_added": metadata["date_added"]
        }
        
        # CRITICAL: Save the library index to disk!
        self.save_library_index()
        print(f"✅ Book successfully added to library: {metadata['title']}")
        
        # Automatically extract full text for PDFs (part of processing flow)
        print(f"📄 Setting up text extraction for processing...")
        
        # Check if we have a temp text file from metadata extraction
        temp_txt_path = pdf_path.with_suffix('.txt')
        final_txt_path = book_dir / f"{folder_name}.txt"
        
        if temp_txt_path.exists():
            # Move the temp text file to the final location
            try:
                shutil.move(str(temp_txt_path), str(final_txt_path))
                print(f"  ✅ Moved existing text file from temp: {final_txt_path.name}")
                
                # Update metadata with text info
                if final_txt_path.exists():
                    text_length = len(final_txt_path.read_text(encoding='utf-8'))
                    metadata.update({
                        'text_extracted': datetime.now().isoformat(),
                        'text_filename': f"{folder_name}.txt",
                        'text_length': text_length,
                        'text_extraction_method': 'moved_from_temp'
                    })
                    print(f"  ✅ Updated metadata with moved text info")
                    
            except Exception as e:
                print(f"  ⚠️ Could not move temp text file: {e}")
                # Fall back to fresh extraction
                temp_txt_path = None
        
        if not final_txt_path.exists():
            # No temp file existed or move failed - extract fresh
            print(f"  📄 No temp text file found, extracting fresh...")
            try:
                text_result = self.text_service.extract_full_text(new_pdf_path, save_to_file=True)
                if text_result['success']:
                    print(f"  ✅ Text extraction successful: {text_result['text_length']} characters using {text_result['method']}")
                else:
                    print(f"  ⚠️ Text extraction failed: {text_result.get('text', 'Unknown error')}")
            except Exception as e:
                print(f"  ⚠️ Text extraction error: {e}")
        
        return book_id

    def extract_pdf_metadata(self, pdf_path: Path) -> Dict:
        """Extract metadata from PDF file using escalation procedure"""
        result = self.extract_metadata_with_escalation(pdf_path)
        
        # If confidence is low, add to OCR queue for later processing
        if result.confidence < self.min_confidence_suggest_ocr:
            self.add_to_ocr_queue(pdf_path, f"low_confidence_{result.confidence:.2f}")
        
        return result.metadata

    def enhanced_isbn_lookup(self, isbn: str) -> Dict:
        """Enhanced ISBN lookup that tries multiple sources"""
        print(f"📚 Looking up ISBN: {isbn}")
        
        # Try isbnlib first (covers Open Library, Google Books, etc.)
        try:
            # Clean the ISBN
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
                        print(f"  ✅ Found metadata via {provider}: {meta.get('Title', 'N/A')}")
                        
                        # Convert to our format
                        result = {}
                        if meta.get('Title'):
                            result['title'] = meta['Title']
                        if meta.get('Authors'):
                            # Join multiple authors with comma
                            result['author'] = ', '.join(meta['Authors'])
                        if meta.get('Year'):
                            result['year'] = int(meta['Year'])
                        if meta.get('Publisher'):
                            result['publisher'] = meta['Publisher']
                        
                        return result
                        
                except Exception as e:
                    print(f"  ⚠️ {provider} lookup failed: {e}")
                    continue
            
            print(f"  ❌ No results from isbnlib providers")
            
        except Exception as e:
            print(f"  💥 ISBN lookup failed completely: {e}")
        
        return {}

    def add_contextual_metadata(self, metadata: Dict) -> Dict:
        """Simplified contextual metadata - just handle web URLs properly"""
        media_type = metadata.get("media_type", MediaType.UNKNOWN.value)
        
        # For web resources, ensure URL is properly formatted
        if media_type == MediaType.WEB.value:
            url = metadata.get("url", "")
            if url and not url.startswith(("http://", "https://")):
                metadata["url"] = f"https://{url}"
        
        return metadata

    def normalize_filename(self, metadata: Dict) -> str:
        """Generate normalized filename from metadata following AUTHOR - Title - Year - ISBN convention"""
        # Clean strings for filename use
        def clean_for_filename(s: str, max_length: int = 50) -> str:
            # Remove special characters, keep alphanumeric, spaces, hyphens
            cleaned = re.sub(r'[^\w\s\-]', '', s)
            # Replace multiple spaces with single space
            cleaned = re.sub(r'\s+', ' ', cleaned).strip()
            # Replace spaces with underscores
            cleaned = cleaned.replace(' ', '_')
            return cleaned[:max_length]
        
        # Build filename components  
        author = clean_for_filename(metadata.get("author", "Unknown_Author").split(',')[0], 30)
        title = clean_for_filename(metadata.get("title", "Unknown_Title"), 40)
        year = str(metadata.get("year", "Unknown_Year"))
        
        # Get identifier based on media type
        media_type = metadata.get("media_type", MediaType.UNKNOWN.value)
        if media_type == MediaType.BOOK.value and metadata.get("isbn"):
            identifier = metadata.get("isbn")
        elif media_type == MediaType.WEB.value and metadata.get("url"):
            # Use domain from URL as identifier
            import urllib.parse
            parsed = urllib.parse.urlparse(metadata.get("url", ""))
            identifier = parsed.netloc.replace(".", "_") if parsed.netloc else "no_url"
        else:
            identifier = "no_id"
        
        # Create the filename: AUTHOR - Title - Year - Identifier
        filename = f"{author}_{title}_{year}_{identifier}"
        
        # Add copy suffix if this is a multi-contributor copy
        if metadata.get('copy_suffix'):
            filename += metadata['copy_suffix']
        
        return filename
    
    def process_book(self, file_path: Path, contributor: str = "unknown") -> Optional[str]:
        """Process a single book and extract metadata using escalation"""
        if not file_path.exists():
            print(f"Skipping {file_path}: file does not exist")
            return None
        
        # Check if it's a supported file type
        file_extension = file_path.suffix.lower()
        supported_extensions = ['.pdf', '.epub', '.mobi', '.azw', '.azw3', '.djvu', '.djv']
        
        if file_extension not in supported_extensions:
            print(f"Skipping {file_path}: unsupported file type {file_extension}")
            return None
        
        # Generate book ID
        book_id = self.generate_book_id(str(file_path))
        
        # Check if already processed by this contributor (same hash + same contributor)
        if book_id in self.library_index["books"]:
            # Load the existing book's metadata to check contributor
            existing_book_info = self.library_index["books"][book_id]
            folder_name = existing_book_info.get("folder_name", book_id)
            book_dir = self.library_path / folder_name
            metadata_file = book_dir / "metadata.json"
            
            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r') as f:
                        existing_metadata = json.load(f)
                        existing_contributors = existing_metadata.get("contributor", [])
                        
                        if contributor in existing_contributors:
                            print(f"📚 Book already processed by this contributor (by hash): {file_path.name}")
                            return book_id
                        else:
                            print(f"🔍 Same file but different contributor ({contributor} vs {existing_contributors}) - will create separate copy")
                            # CRITICAL FIX: Generate unique book ID for different contributor
                            book_id = f"{book_id}_{contributor}"
                            print(f"🆔 Generated unique book ID for contributor: {book_id}")
                except:
                    # If we can't read metadata, assume it's the same contributor
                    print(f"📚 Book already processed (by hash): {file_path.name}")
                    return book_id
            else:
                print(f"📚 Book already processed (by hash): {file_path.name}")
                return book_id
        
        # Check if a book with this original filename already exists by the SAME contributor
        for existing_id, book_info in self.library_index["books"].items():
            folder_name = book_info.get("folder_name", existing_id)
            book_dir = self.library_path / folder_name
            metadata_file = book_dir / "metadata.json"
            
            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r') as f:
                        existing_metadata = json.load(f)
                        if (existing_metadata.get("original_filename") == file_path.name and 
                            contributor in existing_metadata.get("contributor", [])):
                            print(f"📚 Book already processed by this contributor: {file_path.name}")
                            return existing_id
                except:
                    pass
        
        print(f"Processing: {file_path.name}")
        
        # Extract metadata using escalation procedure
        if file_extension == '.pdf':
            result = self.extract_metadata_with_escalation(file_path)
        else:
            # For non-PDF files, use Calibre-based extraction
            result = self._extract_ebook_metadata(file_path)
        
        # If extraction returned None, it means the file was added to review queue
        if result is None:
            print(f"📋 File added to review queue: {file_path.name}")
            return None
        
        metadata = result.metadata
        
        # Add additional fields
        metadata.update({
            "id": book_id,
            "original_filename": file_path.name,
            "contributor": [contributor] if contributor else [],
            "date_added": datetime.now().isoformat(),
            "read_by": [],
            "tags": [],
            "notes": "",
            "extraction_method": result.method.value,
            "extraction_confidence": result.confidence
        })
        
        # Apply enhanced media type detection
        metadata["media_type"] = self.detect_media_type(metadata)
        
        # Add contextual metadata based on media type
        metadata = self.add_contextual_metadata(metadata)
        
        # Check for similar books (multi-copy detection)
        similar_books = self.find_similar_books(metadata)
        if similar_books:
            print(f"🔍 Found {len(similar_books)} similar book(s)")
            for similar in similar_books[:3]:  # Show top 3
                print(f"  📚 {similar['similarity_type']}: {similar['metadata'].get('title', 'Unknown')} "
                      f"(confidence: {similar['confidence']:.2f})")
            
            # Check if any similar book has different contributors
            should_create_separate_copy = False
            for similar in similar_books:
                existing_contributors = similar['metadata'].get('contributor', [])
                if contributor not in existing_contributors:
                    should_create_separate_copy = True
                    print(f"  🆕 Different contributor '{contributor}' - will create separate copy")
                    break
            
            if should_create_separate_copy:
                # Add contributor name to filename to distinguish copies
                metadata['copy_suffix'] = f"_{contributor}_copy"
                print(f"  📁 Adding copy suffix: {metadata['copy_suffix']}")
                
                # Note: book_id already modified earlier if needed for contributor collision
            
            # Handle the duplicates/related copies
            metadata = self.handle_potential_duplicate(metadata, similar_books)
        
        # Track this contributor globally
        if contributor:
            self.add_contributor(contributor)
        
        # Generate normalized folder name
        folder_name = self.normalize_filename(metadata)
        
        # Create book directory with normalized name
        book_dir = self.library_path / folder_name
        book_dir.mkdir(exist_ok=True)
        
        # Generate normalized filename and move the original file
        new_filename = f"{folder_name}{file_extension}"
        new_file_path = book_dir / new_filename
        
        # Move and rename the original file (no duplication)
        if not new_file_path.exists():
            shutil.move(str(file_path), str(new_file_path))
            print(f"  → Moved and renamed to: {folder_name}/{new_filename}")
        
        # Update metadata with new paths
        metadata.update({
            "folder_name": folder_name,
            "filename": new_filename,
            "folder_path": str(book_dir.relative_to(self.library_path.parent))
        })
        
        # For backwards compatibility with PDFs
        if file_extension == '.pdf':
            metadata["pdf_filename"] = new_filename
        
        # Save metadata
        metadata_path = book_dir / "metadata.json"
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        # Update library index
        self.library_index["books"][book_id] = {
            "id": book_id,
            "title": metadata["title"],
            "author": metadata["author"],
            "year": metadata["year"],
            "isbn": metadata["isbn"],
            "folder_name": folder_name,
            "path": str(book_dir.relative_to(self.library_path.parent)),
            "date_added": metadata["date_added"],
            "extraction_confidence": result.confidence,
            "file_type": metadata["file_type"]
        }
        
        # CRITICAL: Save the library index to disk!
        self.save_library_index()
        print(f"✅ Book successfully processed: {metadata['title']}")
        
        # Automatically extract full text for PDFs (part of upload flow)
        if file_extension == '.pdf':
            print(f"📄 Setting up text extraction for upload flow...")
            
            # Check if we have a temp text file from metadata extraction
            temp_txt_path = file_path.with_suffix('.txt')
            final_txt_path = book_dir / f"{folder_name}.txt"
            
            if temp_txt_path.exists():
                # Move the temp text file to the final location
                try:
                    shutil.move(str(temp_txt_path), str(final_txt_path))
                    print(f"  ✅ Moved existing text file from temp: {final_txt_path.name}")
                    
                    # Update metadata with text info
                    if final_txt_path.exists():
                        text_length = len(final_txt_path.read_text(encoding='utf-8'))
                        metadata_path = book_dir / "metadata.json"
                        if metadata_path.exists():
                            try:
                                with open(metadata_path, 'r', encoding='utf-8') as f:
                                    book_metadata = json.load(f)
                                book_metadata.update({
                                    'text_extracted': datetime.now().isoformat(),
                                    'text_filename': f"{folder_name}.txt",
                                    'text_length': text_length,
                                    'text_extraction_method': 'moved_from_temp'
                                })
                                with open(metadata_path, 'w', encoding='utf-8') as f:
                                    json.dump(book_metadata, f, indent=2, ensure_ascii=False)
                                print(f"  ✅ Updated metadata with moved text info")
                            except Exception as e:
                                print(f"  ⚠️ Could not update metadata: {e}")
                                
                except Exception as e:
                    print(f"  ⚠️ Could not move temp text file: {e}")
                    # Fall back to fresh extraction
                    temp_txt_path = None
            
            if not final_txt_path.exists():
                # No temp file existed or move failed - extract fresh
                print(f"  📄 No temp text file found, extracting fresh...")
                try:
                    text_result = self.text_service.extract_full_text(new_file_path, save_to_file=True)
                    if text_result['success']:
                        print(f"  ✅ Text extraction successful: {text_result['text_length']} characters using {text_result['method']}")
                    else:
                        print(f"  ⚠️ Text extraction failed: {text_result.get('text', 'Unknown error')}")
                except Exception as e:
                    print(f"  ⚠️ Text extraction error: {e}")
        
        return book_id
    
    def _extract_ebook_metadata(self, file_path: Path) -> ExtractionResult:
        """Extract metadata from non-PDF ebook files using Calibre"""
        metadata = self._get_fallback_metadata(file_path)
        confidence = 0.4  # Base confidence for ebook files (better than PDFs usually)
        
        try:
            # Use Calibre's ebook-meta command
            result = subprocess.run([
                'ebook-meta', str(file_path)
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0 and result.stdout:
                isbn_found = False
                
                # Parse the output
                lines = result.stdout.split('\n')
                for line in lines:
                    line = line.strip()
                    if line.startswith('Title'):
                        title = line.split(':', 1)[1].strip()
                        if title and title != 'Unknown' and title != file_path.stem:
                            metadata['title'] = title
                            confidence += 0.2
                    elif line.startswith('Author(s)'):
                        author = line.split(':', 1)[1].strip()
                        if author and author != 'Unknown':
                            metadata['author'] = author
                            confidence += 0.2
                    elif line.startswith('Published'):
                        pub_info = line.split(':', 1)[1].strip()
                        year_match = re.search(r'\b(19|20)\d{2}\b', pub_info)
                        if year_match:
                            metadata['year'] = int(year_match.group())
                            confidence += 0.1
                    elif 'ISBN' in line:
                        isbn_match = re.search(self.isbn_regex, line)
                        if isbn_match:
                            raw_isbn = isbn_match.group(1).strip()
                            isbn = re.sub(r'[-\s—–]', '', raw_isbn)
                            if isbnlib.is_isbn13(isbn) or isbnlib.is_isbn10(isbn):
                                metadata['isbn'] = isbn
                                isbn_found = True
                                confidence += 0.3
                                
                                # Enhance with ISBN lookup
                                isbn_metadata = self.book_service.enhanced_isbn_lookup(isbn)
                                if isbn_metadata:
                                    metadata.update(isbn_metadata)
                                    confidence += 0.2
                
                return ExtractionResult(
                    method=ExtractionMethod.CALIBRE,
                    success=True,
                    metadata=metadata,
                    confidence=min(confidence, 1.0),
                    isbn_found=isbn_found,
                    text_extracted=True
                )
                
        except Exception as e:
            return ExtractionResult(
                method=ExtractionMethod.CALIBRE,
                success=False,
                metadata=metadata,
                confidence=0.2,  # Still better than complete failure
                isbn_found=False,
                text_extracted=False,
                error=str(e)
            )

    def scan_directory(self, directory: Path, contributor: str = "unknown") -> List[str]:
        """Scan directory for PDFs and process them"""
        processed_ids = []
        
        # Use the new file detection system
        new_files, modified_files = self.get_files_needing_scan()
        
        print(f"Found {len(new_files)} new files and {len(modified_files)} modified files")
        
        # Process new files
        for pdf_path in new_files:
            book_id = self.process_book(pdf_path, contributor)
            if book_id:
                processed_ids.append(book_id)
        
        # Process modified files (re-extract metadata)
        for pdf_path, existing_book_id in modified_files:
            print(f"Re-processing modified file: {pdf_path.name}")
            # Remove from index and re-process
            if existing_book_id in self.library_index["books"]:
                del self.library_index["books"][existing_book_id]
            
            book_id = self.process_book(pdf_path, contributor)
            if book_id:
                processed_ids.append(book_id)
        
        # Update last scan time
        self.update_last_scan()
        
        return processed_ids
    
    def get_ocr_queue_summary(self) -> Dict:
        """Get summary of OCR queue status"""
        queue = self.load_ocr_queue()
        
        summary = {
            "total": len(queue),
            "pending": len([item for item in queue if item["status"] == "pending"]),
            "completed": len([item for item in queue if item["status"] == "completed"]),
            "failed": len([item for item in queue if item["status"] == "failed"]),
            "missing": len([item for item in queue if item["status"] == "missing"]),
            "error": len([item for item in queue if item["status"] == "error"])
        }
        
        return summary
    
    def get_low_confidence_books(self, threshold: float = 0.5) -> List[Dict]:
        """Get books that were processed with low confidence and might benefit from OCR"""
        low_confidence_books = []
        
        for book_id, book_info in self.library_index["books"].items():
            confidence = book_info.get("extraction_confidence", 1.0)  # Default to high confidence for old books
            
            if confidence < threshold:
                folder_name = book_info.get("folder_name", book_id)
                book_dir = self.library_path / folder_name
                metadata_file = book_dir / "metadata.json"
                
                if metadata_file.exists():
                    try:
                        with open(metadata_file, 'r') as f:
                            metadata = json.load(f)
                            
                        low_confidence_books.append({
                            "book_id": book_id,
                            "title": metadata.get("title", "Unknown"),
                            "author": metadata.get("author", "Unknown"),
                            "confidence": confidence,
                            "extraction_method": metadata.get("extraction_method", "unknown"),
                            "path": str(book_dir / metadata.get("pdf_filename", ""))
                        })
                    except:
                        pass
        
        return sorted(low_confidence_books, key=lambda x: x["confidence"])

    def add_to_review_queue(self, file_path: Path, metadata: Dict, extraction_result: ExtractionResult, reason: str = "needs_review") -> None:
        """Add a book to the manual review queue (legacy method - files should already be in temp)"""
        print(f"⚠️ Using legacy add_to_review_queue method for {file_path.name}")
        
        # This method is now mainly for files that are already processed but need review
        # For new uploads, use _add_to_review_queue_from_temp instead
        queue = self.load_review_queue()
        
        review_entry = {
            "id": self.generate_book_id(str(file_path)),
            "path": str(file_path),  # This might be books directory for legacy calls
            "filename": file_path.name,
            "extracted_metadata": metadata,
            "extraction_method": extraction_result.method.value,
            "extraction_confidence": extraction_result.confidence,
            "isbn_found": extraction_result.isbn_found,
            "reason": reason,
            "added": datetime.now().isoformat(),
            "status": "pending_review"
        }
        
        # Avoid duplicates
        existing = [item for item in queue if item["path"] == str(file_path)]
        if not existing:
            queue.append(review_entry)
            self.save_review_queue(queue)
            print(f"📋 Added to review queue: {file_path.name} (reason: {reason})")
    
    def load_review_queue(self) -> List[Dict]:
        """Load manual review queue"""
        if self.review_queue_path.exists():
            with open(self.review_queue_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    
    def save_review_queue(self, queue: List[Dict]) -> None:
        """Save manual review queue"""
        with open(self.review_queue_path, 'w', encoding='utf-8') as f:
            json.dump(queue, f, indent=2, ensure_ascii=False)
    
    def approve_from_review_queue(self, review_id: str, updated_metadata: Dict, contributor: str = "unknown") -> Optional[str]:
        """Process a book from review queue with approved/corrected metadata"""
        queue = self.load_review_queue()
        
        # Find the item
        item = None
        for i, entry in enumerate(queue):
            if entry["id"] == review_id:
                item = entry
                break
        
        if not item:
            print(f"Review item not found: {review_id}")
            return None
        
        temp_file_path = Path(item["path"])
        if not temp_file_path.exists():
            print(f"File no longer exists in temp: {temp_file_path}")
            # Mark as missing
            item["status"] = "file_missing"
            self.save_review_queue(queue)
            return None
        
        # Ensure required fields are set
        if "file_type" not in updated_metadata:
            updated_metadata["file_type"] = "pdf"  # Default for most uploads
        if "media_type" not in updated_metadata:
            updated_metadata["media_type"] = self.detect_media_type(updated_metadata)
        
        print(f"✅ Approving from review queue: {temp_file_path.name}")
        print(f"   Moving from temp to books directory...")
        
        # Process with the approved metadata - this will move file from temp to books
        book_id = self.process_book_with_multi_copy_detection(temp_file_path, updated_metadata, contributor)
        
        if book_id:
            # Remove from review queue
            queue = [entry for entry in queue if entry["id"] != review_id]
            self.save_review_queue(queue)
            print(f"✅ Processed and moved from temp: {temp_file_path.name}")
            # Refresh last scan timestamp so UI immediately reflects the new book
            try:
                self.update_last_scan()
            except Exception as _e:
                print(f"⚠️ Could not update last_scan metadata: {_e}")
            return book_id
        else:
            # Mark as failed
            item["status"] = "processing_failed"
            self.save_review_queue(queue)
            print(f"❌ Failed to process from review queue: {temp_file_path.name}")
            return None
    
    def get_review_queue_summary(self) -> Dict:
        """Get summary of review queue status"""
        queue = self.load_review_queue()
        
        summary = {
            "total": len(queue),
            "pending_review": len([item for item in queue if item["status"] == "pending_review"]),
            "file_missing": len([item for item in queue if item["status"] == "file_missing"]),
            "processing_failed": len([item for item in queue if item["status"] == "processing_failed"])
        }
        
        return summary

    def reject_from_review_queue(self, review_id: str, reason: str = "user_rejected") -> bool:
        """Reject and remove a book from review queue without processing"""
        queue = self.load_review_queue()
        
        # Find and remove the item
        for i, entry in enumerate(queue):
            if entry["id"] == review_id:
                temp_file_path = Path(entry["path"])
                filename = entry["filename"]
                
                # Remove the item from queue
                del queue[i]
                self.save_review_queue(queue)
                
                # Delete the temp file and any associated text file since it was rejected
                try:
                    if temp_file_path.exists():
                        temp_file_path.unlink()
                        print(f"🗑️ Deleted temp file: {filename}")
                    
                    # Also delete any temp text file
                    temp_txt_path = temp_file_path.with_suffix('.txt')
                    if temp_txt_path.exists():
                        temp_txt_path.unlink()
                        print(f"🗑️ Deleted temp text file: {temp_txt_path.name}")
                        
                except Exception as e:
                    print(f"⚠️ Could not delete temp files for {filename}: {e}")
                
                print(f"🗑️ Rejected from review queue: {filename} (reason: {reason})")
                return True
        
        print(f"Review item not found: {review_id}")
        return False

    def detect_media_type(self, metadata: Dict) -> str:
        """Simple media type detection - defaults to BOOK unless clearly something else"""
        title = (metadata.get("title") or "").lower()
        filename = (metadata.get("original_filename") or "").lower()
        
        # EXPLICIT indicators only - be very conservative
        
        # Has ISSN = definitely an article/journal
        if metadata.get("issn"):
            return MediaType.BOOK.value
        
        # Has URL but no ISBN = web resource
        if metadata.get("url") and not metadata.get("isbn"):
            return MediaType.WEB.value
        
        # Everything else is a BOOK (including things with ISBN, existing items, etc.)
        return MediaType.BOOK.value
    
    def find_similar_books(self, metadata: Dict) -> List[Dict]:
        """Find books that might be copies or similar editions"""
        candidates = []
        target_title = (metadata.get("title") or "").lower().strip()
        target_author = (metadata.get("author") or "").lower().strip()
        target_isbn = metadata.get("isbn", "")
        
        if not target_title or not target_author:
            return candidates
        
        for book_id, book_info in self.library_index["books"].items():
            # Skip if it's the same book (in case we're updating)
            if book_info.get("id") == metadata.get("id"):
                continue
                
            # Load the book's metadata
            folder_name = book_info.get("folder_name", book_id)
            book_dir = self.library_path / folder_name
            metadata_file = book_dir / "metadata.json"
            
            if not metadata_file.exists():
                continue
                
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    existing_metadata = json.load(f)
                
                existing_title = (existing_metadata.get("title") or "").lower().strip()
                existing_author = (existing_metadata.get("author") or "").lower().strip()
                existing_isbn = existing_metadata.get("isbn", "")
                
                # Exact ISBN match = definitely the same book
                if target_isbn and existing_isbn and target_isbn == existing_isbn:
                    candidates.append({
                        "book_id": book_id,
                        "metadata": existing_metadata,
                        "similarity_type": "exact_isbn",
                        "confidence": 1.0
                    })
                    continue
                
                # Calculate title similarity
                title_similarity = SequenceMatcher(None, target_title, existing_title).ratio()
                author_similarity = SequenceMatcher(None, target_author, existing_author).ratio()
                
                # High similarity on both title and author
                if (title_similarity >= self.title_similarity_threshold and 
                    author_similarity >= self.author_similarity_threshold):
                    
                    confidence = (title_similarity + author_similarity) / 2
                    similarity_type = "high_similarity"
                    
                    # Even higher confidence if one has ISBN and they're very similar
                    if target_isbn or existing_isbn:
                        confidence = min(confidence + 0.1, 1.0)
                        similarity_type = "likely_duplicate"
                    
                    candidates.append({
                        "book_id": book_id,
                        "metadata": existing_metadata,
                        "similarity_type": similarity_type,
                        "confidence": confidence,
                        "title_similarity": title_similarity,
                        "author_similarity": author_similarity
                    })
                    
            except Exception as e:
                print(f"⚠️ Error checking similarity for {book_id}: {e}")
                continue
        
        # Sort by confidence (highest first)
        candidates.sort(key=lambda x: x["confidence"], reverse=True)
        return candidates
    
    def handle_potential_duplicate(self, metadata: Dict, similar_books: List[Dict]) -> Dict:
        """Handle when we find potential duplicates - update metadata with multi-copy info"""
        if not similar_books:
            return metadata
        
        # Add related copies information
        metadata["related_copies"] = []
        
        for similar in similar_books:
            copy_info = {
                "book_id": similar["book_id"],
                "similarity_type": similar["similarity_type"],
                "confidence": similar["confidence"],
                "contributor": similar["metadata"].get("contributor", []),
                "folder_name": similar["metadata"].get("folder_name"),
                "isbn": similar["metadata"].get("isbn"),
                "year": similar["metadata"].get("year"),
                "publisher": similar["metadata"].get("publisher")
            }
            metadata["related_copies"].append(copy_info)
            
            # Also update the existing book to reference this new copy
            self._add_related_copy_to_existing(similar["book_id"], {
                "book_id": metadata.get("id"),
                "similarity_type": similar["similarity_type"],
                "confidence": similar["confidence"],
                "contributor": metadata.get("contributor", []),
                "folder_name": metadata.get("folder_name"),
                "isbn": metadata.get("isbn"),
                "year": metadata.get("year"),
                "publisher": metadata.get("publisher")
            })
        
        return metadata
    
    def _add_contributor_to_existing_book(self, existing_book_id: str, contributor: str, file_path: Path) -> str:
        """Add a contributor to an existing book instead of creating a separate copy"""
        try:
            book_info = self.library_index["books"].get(existing_book_id)
            if not book_info:
                print(f"⚠️ Existing book not found: {existing_book_id}")
                return None
                
            folder_name = book_info.get("folder_name", existing_book_id)
            book_dir = self.library_path / folder_name
            metadata_file = book_dir / "metadata.json"
            
            if not metadata_file.exists():
                print(f"⚠️ Metadata file not found for: {existing_book_id}")
                return None
                
            with open(metadata_file, 'r', encoding='utf-8') as f:
                existing_metadata = json.load(f)
            
            # Add contributor if not already present
            contributors = existing_metadata.get("contributor", [])
            if contributor not in contributors:
                contributors.append(contributor)
                existing_metadata["contributor"] = contributors
                print(f"  ➕ Added contributor '{contributor}' to existing book")
                
                # Save updated metadata
                with open(metadata_file, 'w', encoding='utf-8') as f:
                    json.dump(existing_metadata, f, indent=2, ensure_ascii=False)
                
                # Track this contributor globally
                self.add_contributor(contributor)
                
                # Remove the uploaded file since we're not creating a new copy
                if file_path.exists():
                    file_path.unlink()
                    print(f"  🗑️ Removed duplicate file: {file_path.name}")
                
                return existing_book_id
            else:
                print(f"  ⚠️ Contributor '{contributor}' already exists for this book")
                # Remove the duplicate file
                if file_path.exists():
                    file_path.unlink()
                    print(f"  🗑️ Removed duplicate file: {file_path.name}")
                return existing_book_id
                    
        except Exception as e:
            print(f"⚠️ Error adding contributor to existing book {existing_book_id}: {e}")
            return None

    def _add_related_copy_to_existing(self, existing_book_id: str, new_copy_info: Dict):
        """Add related copy info to an existing book's metadata"""
        try:
            book_info = self.library_index["books"].get(existing_book_id)
            if not book_info:
                return
                
            folder_name = book_info.get("folder_name", existing_book_id)
            book_dir = self.library_path / folder_name
            metadata_file = book_dir / "metadata.json"
            
            if not metadata_file.exists():
                return
                
            with open(metadata_file, 'r', encoding='utf-8') as f:
                existing_metadata = json.load(f)
            
            if "related_copies" not in existing_metadata:
                existing_metadata["related_copies"] = []
            
            # Check if this copy is already listed
            existing_ids = [copy.get("book_id") for copy in existing_metadata["related_copies"]]
            if new_copy_info["book_id"] not in existing_ids:
                existing_metadata["related_copies"].append(new_copy_info)
                
                # Save updated metadata
                with open(metadata_file, 'w', encoding='utf-8') as f:
                    json.dump(existing_metadata, f, indent=2, ensure_ascii=False)
                    
        except Exception as e:
            print(f"⚠️ Error updating related copy for {existing_book_id}: {e}")

    def process_book_in_temp(self, temp_file_path: Path, contributor: str = "unknown", progress_callback=None) -> Optional[Dict]:
        """
        Process a book from temp directory - either auto-process or add to review queue
        Returns dict with status info instead of just book_id
        """
        print(f"🔄 Processing book from temp: {temp_file_path.name}")
        
        try:
            # FIRST: Refresh library index to pick up any external changes (like deletions)
            self.refresh_library_index()
            
            # SECOND: Check for duplicates by hash BEFORE doing any expensive processing
            book_id = self.generate_book_id(str(temp_file_path))
            
            # DEBUG: Add detailed logging for hash checking
            print(f"🔍 DUPLICATE CHECK DEBUG:")
            print(f"   File: {temp_file_path.name}")
            print(f"   Generated hash: {book_id}")
            print(f"   Library has {len(self.library_index['books'])} total books")
            print(f"   Checking if {book_id} exists in library...")
            
            # Check if already processed by this contributor (same hash + same contributor)
            if book_id in self.library_index["books"]:
                print(f"   ✅ HASH MATCH FOUND! Book {book_id} exists in library")
                # Load the existing book's metadata to check contributor
                existing_book_info = self.library_index["books"][book_id]
                folder_name = existing_book_info.get("folder_name", book_id)
                book_dir = self.library_path / folder_name
                metadata_file = book_dir / "metadata.json"
                
                if metadata_file.exists():
                    try:
                        with open(metadata_file, 'r') as f:
                            existing_metadata = json.load(f)
                            existing_contributors = existing_metadata.get("contributor", [])
                            
                            if contributor in existing_contributors:
                                print(f"📚 DUPLICATE: Book already processed by this contributor (by hash): {temp_file_path.name}")
                                print(f"   ⚠️  This file should go to review queue with duplicate flag!")
                                
                                # Add to review queue with duplicate flag instead of auto-rejecting
                                # This gives the user a chance to review and decide
                                duplicate_metadata = {
                                    "title": existing_metadata.get("title", "Unknown"),
                                    "author": existing_metadata.get("author", "Unknown"),
                                    "year": existing_metadata.get("year", "Unknown"),
                                    "isbn": existing_metadata.get("isbn", ""),
                                    "file_type": temp_file_path.suffix.lower()[1:],  # Remove the dot
                                    "media_type": "book",
                                    "duplicate_of": book_id,
                                    "existing_contributors": existing_contributors
                                }
                                
                                # Create a fake extraction result for the review queue
                                duplicate_result = ExtractionResult(
                                    method=ExtractionMethod.BASIC,
                                    success=True,
                                    metadata=duplicate_metadata,
                                    confidence=1.0,  # High confidence since we know it's a duplicate
                                    isbn_found=bool(existing_metadata.get("isbn")),
                                    text_extracted=False
                                )
                                
                                review_id = self._add_to_review_queue_from_temp(
                                    temp_file_path, 
                                    duplicate_metadata, 
                                    duplicate_result, 
                                    reason=f"duplicate_file_same_contributor_{contributor}"
                                )
                                
                                if review_id:
                                    return {"status": "review_queue", "review_id": review_id, "reason": "duplicate_detected"}
                                else:
                                    return {"status": "failed", "error": "duplicate_review_queue_failed"}
                            else:
                                print(f"🔍 Same file hash but different contributor ({contributor} vs {existing_contributors})")
                                print(f"   📋 Will add to review queue for manual decision on multi-copy handling")
                                
                                # Add to review queue for multi-contributor decision
                                multicopy_metadata = {
                                    "title": existing_metadata.get("title", "Unknown"),
                                    "author": existing_metadata.get("author", "Unknown"),
                                    "year": existing_metadata.get("year", "Unknown"),
                                    "isbn": existing_metadata.get("isbn", ""),
                                    "file_type": temp_file_path.suffix.lower()[1:],
                                    "media_type": "book",
                                    "potential_multicopy_of": book_id,
                                    "existing_contributors": existing_contributors,
                                    "new_contributor": contributor
                                }
                                
                                multicopy_result = ExtractionResult(
                                    method=ExtractionMethod.BASIC,
                                    success=True,
                                    metadata=multicopy_metadata,
                                    confidence=1.0,
                                    isbn_found=bool(existing_metadata.get("isbn")),
                                    text_extracted=False
                                )
                                
                                review_id = self._add_to_review_queue_from_temp(
                                    temp_file_path,
                                    multicopy_metadata,
                                    multicopy_result,
                                    reason=f"same_file_different_contributor_{contributor}"
                                )
                                
                                if review_id:
                                    return {"status": "review_queue", "review_id": review_id, "reason": "multicopy_detected"}
                                else:
                                    return {"status": "failed", "error": "multicopy_review_queue_failed"}
                    except Exception as e:
                        print(f"⚠️ Error reading existing metadata: {e}")
                        # If we can't read metadata, assume it's the same contributor and flag as duplicate
                        print(f"📚 DUPLICATE: Book already processed (by hash, metadata read failed): {temp_file_path.name}")
                        
                        fallback_metadata = {
                            "title": "Unknown (metadata read failed)",
                            "author": "Unknown",
                            "year": "Unknown",
                            "isbn": "",
                            "file_type": temp_file_path.suffix.lower()[1:],
                            "media_type": "book",
                            "duplicate_of": book_id,
                            "existing_contributors": ["unknown"]
                        }
                        
                        fallback_result = ExtractionResult(
                            method=ExtractionMethod.BASIC,
                            success=True,
                            metadata=fallback_metadata,
                            confidence=0.8,
                            isbn_found=False,
                            text_extracted=False
                        )
                        
                        review_id = self._add_to_review_queue_from_temp(
                            temp_file_path,
                            fallback_metadata,
                            fallback_result,
                            reason=f"duplicate_file_metadata_error"
                        )
                        
                        if review_id:
                            return {"status": "review_queue", "review_id": review_id, "reason": "duplicate_with_error"}
                        else:
                            return {"status": "failed", "error": "duplicate_error_review_queue_failed"}
                else:
                    print(f"📚 DUPLICATE: Book already processed (by hash, no metadata file): {temp_file_path.name}")
                    # No metadata file exists but book ID is in index - flag as duplicate
                    orphan_metadata = {
                        "title": existing_book_info.get("title", "Unknown"),
                        "author": existing_book_info.get("author", "Unknown"),
                        "year": existing_book_info.get("year", "Unknown"),
                        "isbn": existing_book_info.get("isbn", ""),
                        "file_type": temp_file_path.suffix.lower()[1:],
                        "media_type": "book",
                        "duplicate_of": book_id,
                        "existing_contributors": ["unknown"]
                    }
                    
                    orphan_result = ExtractionResult(
                        method=ExtractionMethod.BASIC,
                        success=True,
                        metadata=orphan_metadata,
                        confidence=0.6,
                        isbn_found=bool(existing_book_info.get("isbn")),
                        text_extracted=False
                    )
                    
                    review_id = self._add_to_review_queue_from_temp(
                        temp_file_path,
                        orphan_metadata,
                        orphan_result,
                        reason=f"duplicate_file_orphaned_entry"
                    )
                    
                    if review_id:
                        return {"status": "review_queue", "review_id": review_id, "reason": "duplicate_orphaned"}
                    else:
                        return {"status": "failed", "error": "duplicate_orphaned_review_queue_failed"}
            
            # If we get here, it's not a duplicate by hash - proceed with normal metadata extraction
            print(f"✅ No hash duplicate found - proceeding with metadata extraction")
            
            if progress_callback: progress_callback("extracting_metadata")
            
            # DEBUG: Show a few sample hashes from the library for comparison
            if len(self.library_index['books']) > 0:
                sample_hashes = list(self.library_index['books'].keys())[:3]
                print(f"   📋 Sample library hashes for comparison: {sample_hashes}")
            else:
                print(f"   📭 Library index is empty!")
            
            # Extract metadata using escalation procedure
            extraction_result = self.extract_metadata_with_escalation(temp_file_path)
            
            if not extraction_result:
                print(f"❌ Failed to extract metadata from {temp_file_path.name}")
                if progress_callback: progress_callback("failed")
                return {"status": "failed", "error": "metadata_extraction_failed"}
            
            # Add contextual metadata
            metadata = self.add_contextual_metadata(extraction_result.metadata)
            metadata["contributor"] = [contributor] if contributor != "unknown" else []
            metadata["extraction_method"] = extraction_result.method.value
            metadata["extraction_confidence"] = extraction_result.confidence
            
            # Decision: auto-process or review queue?
            if (extraction_result.confidence >= self.min_confidence_auto_process and 
                (extraction_result.isbn_found or extraction_result.method == ExtractionMethod.CALIBRE)):
                
                # High confidence + ISBN or from Calibre = auto-process
                print(f"✅ High confidence ({extraction_result.confidence:.2f}) - auto-processing")
                if progress_callback: progress_callback("processing")
                
                # Move file from temp to books directory and process
                book_id = self.process_book_with_multi_copy_detection(temp_file_path, metadata, contributor)
                
                if book_id:
                    if progress_callback: progress_callback("success")
                    return {"status": "processed", "book_id": book_id}
                else:
                    if progress_callback: progress_callback("failed")
                    return {"status": "failed", "error": "processing_failed"}
            
            else:
                # Add to review queue, file stays in temp
                print(f"📋 Adding to review queue (confidence: {extraction_result.confidence:.2f})")
                if progress_callback: progress_callback("review_queue")
                
                review_id = self._add_to_review_queue_from_temp(temp_file_path, metadata, extraction_result)
                
                if review_id:
                    return {"status": "review_queue", "review_id": review_id}
                else:
                    if progress_callback: progress_callback("failed")
                    return {"status": "failed", "error": "review_queue_failed"}
                    
        except Exception as e:
            print(f"❌ Error processing {temp_file_path.name}: {e}")
            if progress_callback: progress_callback("failed")
            return {"status": "failed", "error": str(e)}
    
    def _add_to_review_queue_from_temp(self, temp_file_path: Path, metadata: Dict, extraction_result: ExtractionResult, reason: str = None) -> Optional[str]:
        """Add a book to review queue, keeping file in temp directory"""
        queue = self.load_review_queue()
        
        review_id = self.generate_book_id(str(temp_file_path))
        
        # Use provided reason or default based on confidence
        if reason is None:
            reason = f"moderate_confidence_{extraction_result.confidence:.2f}"
        
        review_entry = {
            "id": review_id,
            "path": str(temp_file_path),  # Points to temp directory
            "filename": temp_file_path.name,
            "extracted_metadata": metadata,
            "extraction_method": extraction_result.method.value,
            "extraction_confidence": extraction_result.confidence,
            "isbn_found": extraction_result.isbn_found,
            "reason": reason,
            "added": datetime.now().isoformat(),
            "status": "pending_review"
        }
        
        # Avoid duplicates
        existing = [item for item in queue if item["path"] == str(temp_file_path)]
        if not existing:
            queue.append(review_entry)
            self.save_review_queue(queue)
            print(f"📋 Added to review queue from temp: {temp_file_path.name}")
            return review_id
        else:
            print(f"⚠️ File already in review queue: {temp_file_path.name}")
            return existing[0]["id"]

    def cleanup_temp_files(self) -> Dict:
        """Clean up temp files that are no longer in review queue"""
        # Get temp directory path
        if Path("/app").exists():
            temp_base = Path("/app/temp")
        else:
            temp_base = self.library_path.parent / "temp"
        
        if not temp_base.exists():
            return {"cleaned": 0, "errors": 0}
        
        # Get list of files currently in review queue
        queue = self.load_review_queue()
        queue_files = {Path(item["path"]) for item in queue}
        
        cleaned = 0
        errors = 0
        
        # Check all files in temp directory
        for temp_file in temp_base.iterdir():
            if temp_file.is_file():
                if temp_file not in queue_files:
                    # File is not in review queue, safe to remove
                    try:
                        temp_file.unlink()
                        print(f"🧹 Cleaned up orphaned temp file: {temp_file.name}")
                        cleaned += 1
                    except Exception as e:
                        print(f"⚠️ Could not clean up {temp_file.name}: {e}")
                        errors += 1
        
        print(f"🧹 Temp cleanup complete: {cleaned} files cleaned, {errors} errors")
        return {"cleaned": cleaned, "errors": errors}


if __name__ == "__main__":
    # Test the extractor
    extractor = MetadataExtractor()
    print("Metadata extractor initialized")
    print(f"Library path: {extractor.library_path}")
    print(f"Data path: {extractor.data_path}")