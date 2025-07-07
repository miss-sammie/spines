# Spines 1.0 → 2.0 Function Migration Plan

*Surgical extraction of 5,418 lines into elegant, purposeful modules*

## Migration Strategy Overview

We're taking a **function-by-function approach**, carefully extracting each piece of functionality from the monolithic `web_server.py` and placing it in its architecturally correct home. This ensures:

- **Zero functionality loss** - Every feature preserved
- **Clean separation of concerns** - Each module has a single responsibility
- **Maintainable codebase** - Easy to understand and extend
- **Testable components** - Each service can be tested in isolation

## Function Mapping Table

| v1.0 Function | v1.0 Line | New Location | v2.0 Function | Status |
|---------------|-----------|--------------|---------------|---------|
| `check_for_changes()` | 15 | `services/file_service.py` | `FileService.check_for_changes()` | ⏳ |
| `index()` | 86 | `routes/main.py` | `index()` | ✅ |
| `book_detail()` | 1468 | `routes/main.py` | `book_detail()` | ✅ |
| `update_book()` | 2761 | `api/books.py` | `update_book()` | ✅ |
| `delete_book()` | 3001 | `api/books.py` | `delete_book()` | ✅ |
| `serve_book_file()` | 3037 | `api/books.py` | `serve_book_file()` | ✅ |
| `extract_text_from_book()` | 3096 | `api/books.py` | `extract_text()` | ✅ |
| `api_books()` | 3147 | `api/books.py` | `get_books()` | ✅ |
| `api_library_metadata()` | 3154 | `api/library.py` | `get_library_metadata()` | ✅ |
| `process_files()` | 3161 | `api/files.py` | `process_files()` | ⏳ |
| `process_files_stream()` | 3217 | `api/files.py` | `process_files_stream()` | ⏳ |
| `upload_files()` | 3325 | `api/files.py` | `upload_files()` | ✅ |
| `get_ocr_queue()` | 3415 | `api/ocr.py` | `get_ocr_queue()` | ✅ |
| `add_to_ocr_queue()` | 3436 | `api/ocr.py` | `add_to_ocr_queue()` | ✅ |
| `process_ocr_queue()` | 3471 | `api/ocr.py` | `process_ocr_queue()` | ✅ |
| `ocr_management()` | 3491 | `routes/admin.py` | `ocr_management()` | ✅ |
| `get_review_queue()` | 4368 | `api/review.py` | `get_review_queue()` | ✅ |
| `approve_review_item()` | 4387 | `api/review.py` | `approve_review()` | ✅ |
| `get_review_pdf()` | 4417 | `api/review.py` | `get_review_pdf()` | ✅ |
| `review_queue_page()` | 4449 | `routes/admin.py` | `review_queue_page()` | ⏳ |
| `get_similar_books_for_review()` | 5295 | `api/review.py` | `get_similar_books()` | ✅ |
| `reject_review_item()` | 5337 | `api/review.py` | `reject_review()` | ✅ |
| `cleanup_temp_files()` | 5361 | `api/files.py` | `cleanup_temp()` | ⏳ |
| `isbn_lookup()` | 5380 | `api/library.py` | `isbn_lookup()` | ⏳ |

## Implementation Phase Plan

### Phase 1: Missing API Modules ⚙️

#### Create `api/review.py`
```python
"""
Review Queue API - Managing metadata review workflow
"""
from flask import Blueprint, request, jsonify, send_file
from services.review_service import ReviewService
from utils.auth import require_write_access

review_api = Blueprint('review_api', __name__)

@review_api.route('/review-queue')
def get_review_queue():
    """Get pending review items"""
    # Extract logic from line 4368 of v1.0
    
@review_api.route('/review-queue/<review_id>/approve', methods=['POST'])
@require_write_access
def approve_review(review_id):
    """Approve review item with metadata"""
    # Extract logic from line 4387 of v1.0
    
@review_api.route('/review-queue/<review_id>/reject', methods=['POST'])
@require_write_access
def reject_review(review_id):
    """Reject review item"""
    # Extract logic from line 5337 of v1.0
    
@review_api.route('/review-queue/<review_id>/pdf')
def get_review_pdf(review_id):
    """Get PDF for review item"""
    # Extract logic from line 4417 of v1.0
    
@review_api.route('/review-queue/<review_id>/similar-books')
def get_similar_books(review_id):
    """Get similar books for review item"""
    # Extract logic from line 5295 of v1.0
```

#### Create `api/ocr.py`
```python
"""
OCR API - Optical Character Recognition management
"""
from flask import Blueprint, request, jsonify
from services.ocr_service import OCRService
from utils.auth import require_write_access

ocr_api = Blueprint('ocr_api', __name__)

@ocr_api.route('/ocr-queue')
def get_ocr_queue():
    """Get OCR processing queue"""
    # Extract logic from line 3415 of v1.0
    
@ocr_api.route('/ocr-queue', methods=['POST'])
@require_write_access
def add_to_ocr_queue():
    """Add book to OCR queue"""
    # Extract logic from line 3436 of v1.0
    
@ocr_api.route('/ocr-queue/process', methods=['POST'])
@require_write_access
def process_ocr_queue():
    """Process OCR queue"""
    # Extract logic from line 3471 of v1.0
```

### Phase 2: Enhanced API Modules 🚀

#### Enhance `api/books.py`
```python
# Add missing functions:

@books_api.route('/books/<book_id>/file')
def serve_book_file(book_id):
    """Serve book file for download/viewing"""
    # Extract logic from line 3037 of v1.0
    
@books_api.route('/books/<book_id>/extract-text', methods=['POST'])
@require_write_access
def extract_text(book_id):
    """Extract text from book using OCR"""
    # Extract logic from line 3096 of v1.0
```

#### Enhance `api/files.py`
```python
# Add missing functions:

@files_api.route('/process-files', methods=['POST'])
@require_write_access
def process_files():
    """Process uploaded files"""
    # Extract logic from line 3161 of v1.0
    
@files_api.route('/process-files-stream')
def process_files_stream():
    """Stream processing progress"""
    # Extract logic from line 3217 of v1.0
    
@files_api.route('/cleanup-temp', methods=['POST'])
@require_write_access
def cleanup_temp():
    """Clean up temporary files"""
    # Extract logic from line 5361 of v1.0
```

#### Enhance `api/library.py`
```python
# Add missing functions:

@library_api.route('/isbn-lookup', methods=['POST'])
def isbn_lookup():
    """Look up book metadata by ISBN"""
    # Extract logic from line 5380 of v1.0
```

### Phase 3: Service Layer Creation 🏗️

#### Create `services/review_service.py`
```python
"""
Review Service - Business logic for metadata review workflow
"""
from pathlib import Path
import json
from datetime import datetime
from utils.logging import get_logger

logger = get_logger(__name__)

class ReviewService:
    def __init__(self, config):
        self.config = config
        self.review_queue_path = Path(config.DATA_PATH) / 'review_queue.json'
    
    def get_review_queue(self):
        """Get all pending review items"""
        # Business logic extracted from v1.0
        
    def approve_review(self, review_id, approved_metadata):
        """Approve review item and update library"""
        # Business logic extracted from v1.0
        
    def reject_review(self, review_id, reason):
        """Reject review item"""
        # Business logic extracted from v1.0
        
    def get_review_item(self, review_id):
        """Get specific review item"""
        # Business logic extracted from v1.0
        
    def get_similar_books(self, review_id):
        """Find similar books for review comparison"""
        # Business logic extracted from v1.0
```

#### Create `services/ocr_service.py`
```python
"""
OCR Service - Optical Character Recognition processing
"""
from pathlib import Path
import json
from datetime import datetime
from utils.logging import get_logger

logger = get_logger(__name__)

class OCRService:
    def __init__(self, config):
        self.config = config
        self.ocr_queue_path = Path(config.DATA_PATH) / 'ocr_queue.json'
    
    def get_ocr_queue(self):
        """Get OCR processing queue"""
        # Business logic extracted from v1.0
        
    def add_to_ocr_queue(self, book_id, pages=None):
        """Add book to OCR processing queue"""
        # Business logic extracted from v1.0
        
    def process_ocr_queue(self, max_items=None):
        """Process items in OCR queue"""
        # Business logic extracted from v1.0
        
    def get_ocr_status(self, job_id):
        """Get OCR processing status"""
        # New functionality for better UX
```

#### Enhance `services/file_service.py`
```python
# Add missing methods:

def check_for_changes(self):
    """Check for new or modified files"""
    # Extract logic from line 15 of v1.0
    
def process_files(self, file_paths, contributor):
    """Process uploaded files with metadata extraction"""
    # Extract logic from v1.0 with job queue support
    
def cleanup_temp_files(self):
    """Clean up temporary files"""
    # Extract logic from v1.0
```

### Phase 4: Frontend Component Extraction 🎨

#### Extract CSS to `static/css/`
- `base.css` - Core styles, typography, layout
- `components.css` - Book cards, upload zones, progress bars
- `admin.css` - Admin interface styles
- `animations.css` - Transitions and effects

#### Extract JavaScript to `static/js/components/`
- `BookGrid.js` - Book grid display and filtering
- `UploadZone.js` - File upload with drag-and-drop
- `ProcessingQueue.js` - File processing progress
- `ReviewQueue.js` - Review queue interface
- `SearchFilters.js` - Search and filtering
- `CloudSky.js` - p5.js background animation

### Phase 5: Template Modularization 📄

#### Create `static/templates/`
- `base.html` - Base template structure
- `index.html` - Main library page
- `book-detail.html` - Individual book page
- `admin/` - Admin interface templates
  - `review-queue.html`
  - `ocr-management.html`
- `components/` - Reusable template fragments
  - `book-card.html`
  - `upload-zone.html`
  - `search-filters.html`

## Extraction Methodology

For each function, we'll:

1. **Identify Dependencies** - What imports, utilities, and data does it need?
2. **Extract Core Logic** - Pull out the business logic from Flask route handling
3. **Create Service Method** - Move business logic to appropriate service class
4. **Create API Endpoint** - Clean Flask route that calls service method
5. **Add Error Handling** - Proper error responses and logging
6. **Add Authentication** - Access control decorators where needed
7. **Write Tests** - Unit tests for service methods and integration tests for APIs

## Example: Extracting `isbn_lookup()`

### v1.0 Code (line 5380):
```python
@app.route('/api/isbn-lookup', methods=['POST'])
def isbn_lookup():
    data = request.get_json()
    isbn = data.get('isbn', '').strip()
    
    if not isbn:
        return jsonify({'error': 'ISBN required'}), 400
    
    # Complex ISBN lookup logic...
    # 50+ lines of implementation
```

### v2.0 Refactored:

**Service Layer** (`services/library_service.py`):
```python
class LibraryService:
    def lookup_isbn(self, isbn):
        """Look up book metadata by ISBN"""
        if not isbn or not isbn.strip():
            raise ValueError("ISBN required")
        
        # Complex ISBN lookup logic moved here
        # Testable, reusable business logic
        return metadata
```

**API Layer** (`api/library.py`):
```python
@library_api.route('/isbn-lookup', methods=['POST'])
def isbn_lookup():
    """Look up book metadata by ISBN"""
    try:
        data = request.get_json()
        isbn = data.get('isbn', '').strip()
        
        service = LibraryService(current_app.config['SPINES_CONFIG'])
        metadata = service.lookup_isbn(isbn)
        
        return jsonify(metadata)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.exception("ISBN lookup failed")
        return jsonify({'error': 'Lookup failed'}), 500
```

## Migration Verification

After each function migration:

- [ ] **Functionality Test** - Does it work the same as v1.0?
- [ ] **Error Handling** - Are errors handled gracefully?
- [ ] **Logging** - Are operations properly logged?
- [ ] **Authentication** - Are access controls in place?
- [ ] **Performance** - Is it as fast or faster than v1.0?

## Success Metrics

- **Lines of Code**: Reduce `web_server.py` from 5,418 to < 100 lines
- **Function Count**: Distribute 20+ functions across 8+ modules
- **Maintainability**: Each module < 500 lines, single responsibility
- **Testability**: 80%+ test coverage on service layer
- **Performance**: No degradation in response times

---

*This surgical refactoring preserves every beautiful function while giving them proper architectural homes* 🏗️✨ 