"""
spines web server
Simple Flask app for serving the book library
"""

from flask import Flask, render_template_string, send_from_directory, jsonify, request, Response
import json
import os
import time
from pathlib import Path
from datetime import datetime
from src.metadata_extractor import MetadataExtractor
from src.static_generator import StaticGenerator


def check_for_changes(library_path="./books", data_path="./data"):
    """Check for new or modified PDFs using the enhanced metadata extractor"""
    from src.metadata_extractor import MetadataExtractor
    
    extractor = MetadataExtractor(library_path, data_path)
    new_files, modified_files = extractor.get_files_needing_scan()
    
    # Get last scan time from library metadata
    last_scan_time = extractor.library_index["metadata"]["last_scan"]
    
    return new_files, modified_files, last_scan_time


def create_app(library_path="./books", data_path="./data"):
    """Create Flask application"""
    import os
    
    # Determine static folder path
    possible_static_dirs = [
        os.path.join(os.path.dirname(__file__), '..', 'static'),  # Development
        '/app/static',  # Docker
        './static',  # Current directory
    ]
    
    static_folder = None
    for static_dir in possible_static_dirs:
        if os.path.exists(static_dir):
            static_folder = static_dir
            print(f"Found static folder: {static_folder}")
            break
    
    if static_folder:
        app = Flask(__name__, static_folder=static_folder, static_url_path='/static')
        print(f"Using static folder: {static_folder}")
    else:
        app = Flask(__name__)
        print("No static folder found")
    
    app.config['library_path'] = library_path
    app.config['data_path'] = data_path
    
    # Check for changes on startup
    new_files, modified_files, last_scan_time = check_for_changes(library_path, data_path)
    
    if new_files or modified_files:
        print("\n" + "="*60)
        print("📚 SPINES LIBRARY CHANGES DETECTED")
        print("="*60)
        
        if new_files:
            print(f"🆕 {len(new_files)} new files:")
            for f in new_files[:5]:  # Show first 5
                print(f"   • {f.name}")
            if len(new_files) > 5:
                print(f"   ... and {len(new_files) - 5} more")
        
        if modified_files:
            print(f"📝 {len(modified_files)} modified files:")
            for f, _ in modified_files[:5]:  # Show first 5 (f is the file, _ is the book_id)
                print(f"   • {f.name}")
            if len(modified_files) > 5:
                print(f"   ... and {len(modified_files) - 5} more")
        
        print("\nTo process these changes, run:")
        print("docker exec -it spines-server python3 -m src.cli extract /app/books --contributor=\"your_name\"")
        print("="*60 + "\n")
    else:
        print("📚 No new or modified PDFs detected")
    

    @app.route('/')
    def index():
        """Main library page"""
        from flask import make_response
        
        # Check for changes again on page load
        new_files, modified_files, _ = check_for_changes(library_path, data_path)
        
        # Generate static site on the fly for now
        generator = StaticGenerator(library_path, data_path)
        
        # Load library data
        library_index = generator.load_library_index()
        
        # Collect all book metadata
        books = []
        for book_id in library_index.get('books', {}):
            metadata = generator.load_book_metadata(book_id)
            if metadata:
                books.append(metadata)
        
        # Sort books by author, then title
        books.sort(key=lambda b: (b.get('author', '').lower(), b.get('title', '').lower()))
        
        # Check review queue status
        from src.metadata_extractor import MetadataExtractor
        extractor = MetadataExtractor(library_path, data_path)
        review_summary = extractor.get_review_queue_summary()
        
        # Include change notification and upload zone in template
        changes_notice = ""
        if new_files or modified_files:
            total_changes = len(new_files) + len(modified_files)
            changes_notice = f"""
            <div class="changes-notice">
                <strong>📚 {total_changes} file{'s' if total_changes != 1 else ''} need processing</strong>
                <br>
                <button class="process-button" onclick="processFiles()">process now</button>
                <span class="process-status" id="processStatus"></span>
                <div class="process-progress" id="processProgress" style="display: none;">
                    <div class="progress-bar">
                        <div class="progress-fill" id="processProgressFill"></div>
                    </div>
                    <div class="progress-details" id="progressDetails"></div>
                    <div class="file-list" id="fileList"></div>
                </div>
            </div>
            """
        
        # Add review queue notice if there are items waiting
        review_notice = ""
        if review_summary['pending_review'] > 0:
            review_notice = f"""
            <div class="review-notice">
                <strong>📋 {review_summary['pending_review']} book{'s' if review_summary['pending_review'] != 1 else ''} need manual review</strong>
                <br>
                <a href="/review-queue" class="review-link">review metadata →</a>
            </div>
            """
        
        # Always show upload zone
        upload_zone = """
        <div class="upload-zone" id="uploadZone">
            <div class="upload-content">
                <div class="upload-icon">📚</div>
                <div class="upload-text">
                    <strong>Drop PDF files here to add to library</strong>
                    <br>
                    <small>or <button class="browse-button" onclick="document.getElementById('fileInput').click()">browse files</button></small>
                </div>
                <input type="file" id="fileInput" multiple accept=".pdf,.epub,.mobi,.azw,.azw3,.djvu,.djv" style="display: none;">
            </div>
            <div class="upload-progress" id="uploadProgress" style="display: none;">
                <div class="progress-bar">
                    <div class="progress-fill" id="progressFill"></div>
                </div>
                <div class="upload-status" id="uploadStatus">Uploading...</div>
            </div>
        </div>
        """
        
        # Render template with cache busting
        template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>spines</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/p5.js/1.7.0/p5.min.js"></script>
    <style>
/* spines - hal and whisper's pdf library */

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
    background: #f0f0f0;
    color: #000;
    line-height: 1.4;
    font-size: 12px;
    margin: 0;
    padding: 0;
    overflow-x: hidden;
}

#cloudSky {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    z-index: 1;
    pointer-events: none;
}

.container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 20px;
    position: relative;
    z-index: 2;
}

header {
    border: 2px solid black;
    padding: 20px;
    margin-bottom: 20px;
    background: white;
}

.header-content {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.header-left h1 {
    font-size: 24px;
    font-weight: bold;
    margin-bottom: 5px;
}

.header-left .subtitle {
    font-size: 14px;
    color: #666;
}

.header-right {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    flex-shrink: 0;
    min-width: 0;
}

.header-right label {
    font-weight: bold;
    flex-shrink: 0;
}

.header-right input {
    border: 1px solid black;
    padding: 4px 8px;
    font-family: inherit;
    font-size: 12px;
    width: 120px;
    min-width: 80px;
    max-width: 150px;
}

/* Mobile header adjustments */
@media (max-width: 768px) {
    .header-content {
        flex-direction: column;
        align-items: flex-start;
        gap: 10px;
    }
    
    .header-right {
        width: 100%;
        justify-content: flex-start;
    }
    
    .header-right input {
        flex: 1;
        max-width: 200px;
    }
}

@media (max-width: 480px) {
    .header-right {
        flex-wrap: wrap;
    }
    
    .header-right input {
        width: 100%;
        max-width: none;
    }
}

.changes-notice {
    border: 2px solid #ff6600;
    background: #fff3e0;
    padding: 15px;
    margin-bottom: 20px;
    font-size: 12px;
}

.changes-notice code {
    background: #f0f0f0;
    padding: 2px 4px;
    font-family: inherit;
    border: 1px solid #ccc;
}

.process-button {
    border: 2px solid #006600;
    background: #006600;
    color: white;
    padding: 8px 16px;
    font-family: inherit;
    font-size: 12px;
    cursor: pointer;
    margin-left: 10px;
    font-weight: bold;
}

.process-button:hover {
    background: #004400;
}

.process-button:disabled {
    background: #ccc;
    border-color: #ccc;
    cursor: not-allowed;
}

.process-status {
    margin-left: 10px;
    font-weight: bold;
}

.review-notice {
    border: 2px solid #0066cc;
    background: #f0f8ff;
    padding: 15px;
    margin-bottom: 20px;
    font-size: 12px;
}

.review-link {
    color: #0066cc;
    text-decoration: none;
    font-weight: bold;
    margin-left: 10px;
}

.review-link:hover {
    text-decoration: underline;
}

.process-progress {
    margin-top: 15px;
    border: 1px solid #ccc;
    background: #f8f8f8;
    padding: 10px;
}

.progress-bar {
    border: 1px solid black;
    height: 20px;
    background: white;
    margin-bottom: 10px;
}

.progress-fill {
    height: 100%;
    background: #0066cc;
    transition: width 0.3s ease;
    width: 0%;
}

.progress-details {
    font-size: 11px;
    margin-bottom: 10px;
    font-weight: bold;
}

.file-list {
    max-height: 200px;
    overflow-y: auto;
    border: 1px solid #ddd;
    background: white;
    padding: 5px;
}

.file-item {
    padding: 3px 0;
    font-size: 10px;
    border-bottom: 1px solid #eee;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.file-item:last-child {
    border-bottom: none;
}

.file-name {
    flex: 1;
    margin-right: 10px;
    word-break: break-all;
}

.file-status {
    font-weight: bold;
    padding: 1px 4px;
    font-size: 9px;
}

.file-status.processing {
    color: #0066cc;
}

.file-status.success {
    color: #006600;
}

.file-status.failed {
    color: #cc0000;
}

.file-status.error {
    color: #cc0000;
}

.filters {
    border: 2px solid black;
    padding: 15px;
    margin-bottom: 20px;
    background: white;
    display: flex;
    flex-direction: column;
    gap: 15px;
}

#search {
    border: 1px solid black;
    padding: 5px 10px;
    font-family: inherit;
    font-size: 12px;
}

.sort-controls {
    display: flex;
    align-items: center;
    gap: 10px;
}

.sort-controls label {
    font-weight: bold;
}

.sort-controls select {
    padding: 5px;
    border: 1px solid black;
    font-family: inherit;
    font-size: 12px;
    background: white;
}



.book-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 20px;
    margin-bottom: 40px;
}

.book-card {
    border: 2px solid black;
    background: #ffffff8f;
    padding: 15px;
    position: relative;
    min-height: 150px;
    display: flex;
    flex-direction: column;
    transition: background-color 0.2s;
}

.book-card:hover {
    background: #f8f8f8;
}

.book-card.editing {
    border-color: #0066cc;
    background: #f8f8ff;
}

.book-spine {
    flex: 1;
    margin-bottom: 10px;
}

.book-title, .book-author, .book-year, .book-isbn {
    cursor: pointer;
    padding: 2px;
    border: 1px solid transparent;
}

.book-title:hover, .book-author:hover, .book-year:hover, .book-isbn:hover {
    background: #f0f0f0;
    border-color: #ccc;
}

.book-title {
    font-weight: bold;
    font-size: 14px;
    margin-bottom: 5px;
    line-height: 1.2;
}

.book-author {
    font-size: 12px;
    margin-bottom: 3px;
    color: #333;
}

.book-year {
    font-size: 11px;
    color: #666;
}

.book-isbn {
    font-size: 10px;
    color: #666;
    font-style: italic;
}

.book-meta {
    font-size: 10px;
    color: #666;
    margin-bottom: 10px;
}

.book-meta div {
    margin-bottom: 2px;
}

.contributor {
    color: #0066cc !important;
    font-weight: bold;
}

.related-copies {
    color: #666 !important;
    font-style: italic;
}

.read-status {
    color: #006600 !important;
    font-weight: bold;
}

.tags {
    font-style: italic;
}

.book-link {
    position: absolute;
    top: 10px;
    right: 10px;
    border: 1px solid black;
    background: white;
    padding: 3px 8px;
    text-decoration: none;
    color: black;
    font-size: 10px;
}

.book-link:hover {
    background: black;
    color: white;
}



.edit-controls {
    position: absolute;
    bottom: 10px;
    right: 10px;
    display: none;
}

.book-card.editing .edit-controls {
    display: block;
}

.edit-controls button {
    border: 1px solid black;
    background: white;
    padding: 2px 6px;
    font-family: inherit;
    font-size: 9px;
    cursor: pointer;
    margin-left: 2px;
}

.edit-controls button:hover {
    background: #e0e0e0;
}

.edit-controls .save {
    background: #006600;
    color: white;
}

.edit-controls .cancel {
    background: #cc0000;
    color: white;
}

.editable-input {
    border: 1px solid #0066cc;
    background: white;
    font-family: inherit;
    font-size: inherit;
    color: inherit;
    width: 100%;
    padding: 1px 3px;
}

footer {
    border: 2px solid black;
    padding: 15px;
    background: white;
    text-align: center;
    font-size: 10px;
    color: #666;
}

.empty-state {
    border: 2px solid black;
    background: white;
    padding: 40px;
    text-align: center;
    margin: 20px 0;
}

.cli-hint {
    font-family: inherit;
    background: #f8f8f8;
    padding: 10px;
    margin: 10px 0;
    border: 1px solid #ccc;
}

.loading {
    opacity: 0.6;
    pointer-events: none;
}

.upload-zone {
    border: 2px dashed #666;
    background: white;
    padding: 30px;
    margin-bottom: 20px;
    text-align: center;
    transition: all 0.3s ease;
}

.upload-zone.drag-over {
    border-color: #0066cc;
    background: #f8f8ff;
}

.upload-content {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
}

.upload-icon {
    font-size: 48px;
    opacity: 0.6;
}

.upload-text {
    font-size: 14px;
}

.upload-text small {
    font-size: 12px;
    color: #666;
}

.browse-button {
    border: 1px solid #0066cc;
    background: white;
    color: #0066cc;
    padding: 2px 8px;
    font-family: inherit;
    font-size: 12px;
    cursor: pointer;
    text-decoration: underline;
}

.browse-button:hover {
    background: #0066cc;
    color: white;
}

.upload-progress {
    margin-top: 20px;
}

.progress-bar {
    width: 100%;
    height: 20px;
    border: 1px solid black;
    background: white;
    margin-bottom: 10px;
}

.progress-fill {
    height: 100%;
    background: #0066cc;
    width: 0%;
    transition: width 0.3s ease;
}

.upload-status {
    font-size: 12px;
    font-weight: bold;
}
    </style>
</head>
<body>
    <div id="cloudSky"></div>
    <div class="container">
        <header>
            <div class="header-content">
                <div class="header-left">
                    <h1>spines</h1>
                    <p class="subtitle">{{ books|length }} books</p>
                </div>
                <div class="header-right">
                    <a href="/ocr-management" style="margin-right: 15px; color: #0066cc; text-decoration: none; font-size: 12px;">🔍 OCR Management</a>
                    <label for="contributor">contributor:</label>
                    <input type="text" id="contributor" placeholder="your name" value="">
                </div>
            </div>
        </header>
        
        {{ changes_notice|safe }}
        
        {{ review_notice|safe }}
        
        {{ upload_zone|safe }}
        
        {% if books %}
        <div class="filters">
            <div class="sort-controls">
                <label>sort by:</label>
                <select id="sortField">
                    <option value="author">author</option>
                    <option value="title">title</option>
                    <option value="year">year</option>
                    <option value="date_added">date added</option>
                    <option value="pages">pages</option>
                </select>
                <select id="sortOrder">
                    <option value="asc">asc</option>
                    <option value="desc">desc</option>
                </select>
            </div>
            <input type="text" id="search" placeholder="search titles, authors, tags... (try: read:, unread:, tag:)">
        </div>
        
        <main class="book-grid" id="bookGrid">
        {% for book in books %}
            <div class="book-card" 
                 data-title="{{ book.title|lower }}" 
                 data-author="{{ book.author|lower }}"
                 data-tags="{{ (book.tags or [])|join(' ')|lower }}"
                 data-read="{{ 'read' if book.read_by else 'unread' }}"
                 data-year="{{ book.year or '0' }}"
                 data-date-added="{{ book.date_added or '1900-01-01' }}"
                 data-pages="{{ book.pages or '0' }}"
                 onclick="navigateToBook('{{ book.id }}')"
                 style="cursor: pointer;">
                
                <div class="book-spine">
                    <div class="book-title">{{ book.title }}</div>
                    <div class="book-author">{{ book.author }}</div>
                    <div class="book-year">{{ book.year or '' }}</div>
                </div>
                
                <div class="book-meta">
                    {% if book.contributor %}
                    <div class="contributor">contributed by: {{ book.contributor|join(', ') }}</div>
                    {% endif %}
                    {% if book.related_copies %}
                    <div class="related-copies">also contributed by: 
                        {% for copy in book.related_copies[:3] %}
                            {% if copy.contributor %}{{ copy.contributor|join(', ') }}{% endif %}{% if not loop.last %}, {% endif %}
                        {% endfor %}
                        {% if book.related_copies|length > 3 %}...{% endif %}
                    </div>
                    {% endif %}
                    {% if book.read_by %}
                    <div class="read-status">read by: {{ book.read_by|join(', ') }}</div>
                    {% endif %}
                    {% if book.tags %}
                    <div class="tags">{{ book.tags|join(', ') }}</div>
                    {% endif %}
                    <div class="pages">{{ book.pages }} pages</div>
                </div>
                

            </div>
        {% endfor %}
        </main>
        {% else %}
        <div class="empty-state">
            <h2>no books yet</h2>
            <p>To add books to your library, use the CLI:</p>
            <div class="cli-hint">
                docker exec -it spines-server python3 -m src.cli extract /app/books --contributor="your_name"
            </div>
        </div>
        {% endif %}
        
        <footer>
            <p>we love you!</p>
        </footer>
    </div>
    
    <script>
        // Load saved contributor name and setup autocomplete
        document.addEventListener('DOMContentLoaded', async function() {
            const savedContributor = localStorage.getItem('spines_contributor');
            if (savedContributor) {
                document.getElementById('contributor').value = savedContributor;
            }
            
            // Check if metadata was updated and show refresh notification
            checkForMetadataUpdates();
            
            // Restore scroll position if returning from book detail page
            restoreScrollPosition();
            
            // Load library metadata for contributor autocomplete
            try {
                const response = await fetch('/api/library-metadata');
                if (response.ok) {
                    const metadata = await response.json();
                    if (metadata.contributors && metadata.contributors.length > 0) {
                        const contributorInput = document.getElementById('contributor');
                        contributorInput.setAttribute('list', 'contributors-list');
                        
                        // Create datalist
                        const datalist = document.createElement('datalist');
                        datalist.id = 'contributors-list';
                        metadata.contributors.forEach(contributor => {
                            const option = document.createElement('option');
                            option.value = contributor;
                            datalist.appendChild(option);
                        });
                        document.body.appendChild(datalist);
                    }
                }
            } catch (error) {
                console.error('Failed to load contributors:', error);
            }
        });
        
        // Save contributor name when changed
        document.getElementById('contributor')?.addEventListener('input', function(e) {
            localStorage.setItem('spines_contributor', e.target.value);
        });
        
        // Scroll position management for navigation between pages
        function saveScrollPosition() {
            const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
            localStorage.setItem('spines_scroll_position', scrollTop.toString());
            console.log('📍 Saved scroll position:', scrollTop);
        }
        
        function restoreScrollPosition() {
            const savedPosition = localStorage.getItem('spines_scroll_position');
            if (savedPosition && savedPosition !== '0') {
                const scrollTop = parseInt(savedPosition, 10);
                console.log('📍 Restoring scroll position:', scrollTop);
                
                // Smooth scroll to the saved position
                window.scrollTo({
                    top: scrollTop,
                    behavior: 'smooth'
                });
                
                // Clear the saved position after restoring
                localStorage.removeItem('spines_scroll_position');
            }
        }
        
        function navigateToBook(bookId) {
            // Save current scroll position before navigating
            saveScrollPosition();
            
            // Navigate to book detail page
            window.location.href = `/book/${bookId}`;
        }
        
        function checkForMetadataUpdates() {
            const metadataUpdated = localStorage.getItem('spines_metadata_updated');
            if (metadataUpdated === 'true') {
                // Clear the flag
                localStorage.removeItem('spines_metadata_updated');
                
                // Show a subtle notification that data was updated
                showUpdateNotification();
            }
        }
        
        function showUpdateNotification() {
            // Create a temporary notification
            const notification = document.createElement('div');
            notification.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                background: #e8f5e8;
                border: 2px solid #006600;
                color: #006600;
                padding: 10px 15px;
                font-family: inherit;
                font-size: 12px;
                z-index: 1000;
                border-radius: 0;
            `;
            notification.textContent = '✅ Book metadata updated';
            
            document.body.appendChild(notification);
            
            // Remove notification after 3 seconds
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 3000);
        }
        
        async function processFiles() {
            const contributorInput = document.getElementById('contributor');
            // Auto-populate contributor field if empty but name is saved
            if (!contributorInput.value.trim()) {
                const savedContributor = localStorage.getItem('spines_contributor');
                if (savedContributor) {
                    contributorInput.value = savedContributor;
                }
            }
            const contributor = contributorInput.value.trim() || 'anonymous';
            const processButton = document.querySelector('.process-button');
            const processStatus = document.getElementById('processStatus');
            const processProgress = document.getElementById('processProgress');
            const progressFill = document.getElementById('processProgressFill');
            const progressDetails = document.getElementById('progressDetails');
            const fileList = document.getElementById('fileList');
            
            // Disable button and show processing status
            processButton.disabled = true;
            processButton.textContent = 'processing...';
            processStatus.textContent = '⏳ Starting file processing...';
            processStatus.style.color = '#0066cc';
            processProgress.style.display = 'block';
            progressFill.style.width = '0%';
            progressDetails.textContent = 'Initializing...';
            fileList.innerHTML = '';
            
            try {
                // Use Server-Sent Events for real-time progress
                const eventSource = new EventSource(`/api/process-files-stream?contributor=${encodeURIComponent(contributor)}`);
                
                eventSource.onmessage = function(event) {
                    const data = JSON.parse(event.data);
                    
                    switch(data.type) {
                        case 'ping':
                            progressDetails.textContent = `Connection established, starting...`;
                            break;
                            
                        case 'start':
                            progressDetails.textContent = `Processing ${data.total_files} files...`;
                            break;
                            
                        case 'progress':
                            const percent = Math.round((data.current_file / data.total_files) * 100);
                            progressFill.style.width = `${percent}%`;
                            progressDetails.textContent = `Processing file ${data.current_file} of ${data.total_files} (${percent}%)`;
                            
                            // Add or update file in list
                            let fileItem = document.getElementById(`file-${data.current_file}`);
                            if (!fileItem) {
                                fileItem = document.createElement('div');
                                fileItem.className = 'file-item';
                                fileItem.id = `file-${data.current_file}`;
                                fileList.appendChild(fileItem);
                            }
                            
                            fileItem.innerHTML = `
                                <span class="file-name">${data.filename}</span>
                                <span class="file-status ${data.status}">${data.status === 'processing' ? '⏳' : '🔄'} ${data.status}</span>
                            `;
                            
                            // Scroll to show current file
                            fileItem.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                            break;
                            
                        case 'file_complete':
                            const fileItem2 = document.getElementById(`file-${data.current_file}`);
                            if (fileItem2) {
                                let statusIcon = '✅';
                                let statusText = 'success';
                                if (data.status === 'failed') {
                                    statusIcon = '❌';
                                    statusText = 'failed';
                                } else if (data.status === 'error') {
                                    statusIcon = '💥';
                                    statusText = 'error';
                                }
                                
                                fileItem2.innerHTML = `
                                    <span class="file-name">${data.filename}</span>
                                    <span class="file-status ${data.status}">${statusIcon} ${statusText}</span>
                                `;
                            }
                            break;
                            
                        case 'complete':
                            progressFill.style.width = '100%';
                            progressDetails.textContent = `✅ Completed! Processed ${data.processed_count} files.`;
                            processStatus.textContent = `✅ Processed ${data.processed_count} files!`;
                            processStatus.style.color = '#006600';
                            
                            eventSource.close();
                            
                            // Refresh page after a moment to show new books
                            setTimeout(() => {
                                window.location.reload();
                            }, 3000);
                            break;
                            
                        case 'error':
                            progressDetails.textContent = `❌ Error: ${data.error}`;
                            processStatus.textContent = `❌ Error: ${data.error}`;
                            processStatus.style.color = '#cc0000';
                            processButton.disabled = false;
                            processButton.textContent = 'process now';
                            eventSource.close();
                            break;
                    }
                };
                
                eventSource.onerror = function(event) {
                    console.log('SSE connection error, falling back to regular processing');
                    eventSource.close();
                    
                    // Fallback to regular processing
                    fallbackProcessFiles(contributor, processButton, processStatus, progressDetails, progressFill);
                };
                
            } catch (error) {
                console.log('SSE setup error, falling back to regular processing');
                fallbackProcessFiles(contributor, processButton, processStatus, progressDetails, progressFill);
            }
        }
        
        async function fallbackProcessFiles(contributor, processButton, processStatus, progressDetails, progressFill) {
            try {
                progressDetails.textContent = 'Using fallback processing method...';
                progressFill.style.width = '50%';
                
                const response = await fetch('/api/process-files', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ contributor: contributor })
                });
                
                if (response.ok) {
                    const result = await response.json();
                    progressFill.style.width = '100%';
                    progressDetails.textContent = `✅ Completed! Processed ${result.processed_count} files.`;
                    processStatus.textContent = `✅ Processed ${result.processed_count} files!`;
                    processStatus.style.color = '#006600';
                    
                    // Refresh page after a moment to show new books
                    setTimeout(() => {
                        window.location.reload();
                    }, 3000);
                } else {
                    const error = await response.json();
                    progressDetails.textContent = `❌ Error: ${error.error}`;
                    processStatus.textContent = `❌ Error: ${error.error}`;
                    processStatus.style.color = '#cc0000';
                    processButton.disabled = false;
                    processButton.textContent = 'process now';
                }
            } catch (error) {
                progressDetails.textContent = `❌ Network error: ${error.message}`;
                processStatus.textContent = `❌ Network error: ${error.message}`;
                processStatus.style.color = '#cc0000';
                processButton.disabled = false;
                processButton.textContent = 'process now';
            }
        }
        
        function sortBooks() {
            const sortField = document.getElementById('sortField').value;
            const sortOrder = document.getElementById('sortOrder').value;
            const bookGrid = document.getElementById('bookGrid');
            const cards = Array.from(bookGrid.children);
            
            cards.sort((a, b) => {
                let aValue, bValue;
                
                switch(sortField) {
                    case 'author':
                        aValue = a.dataset.author;
                        bValue = b.dataset.author;
                        break;
                    case 'title':
                        aValue = a.dataset.title;
                        bValue = b.dataset.title;
                        break;
                    case 'year':
                        aValue = parseInt(a.dataset.year);
                        bValue = parseInt(b.dataset.year);
                        break;
                    case 'date_added':
                        aValue = new Date(a.dataset.dateAdded);
                        bValue = new Date(b.dataset.dateAdded);
                        break;
                    case 'pages':
                        aValue = parseInt(a.dataset.pages);
                        bValue = parseInt(b.dataset.pages);
                        break;
                    default:
                        aValue = a.dataset.author;
                        bValue = b.dataset.author;
                }
                
                if (typeof aValue === 'string') {
                    aValue = aValue.toLowerCase();
                    bValue = bValue.toLowerCase();
                }
                
                let comparison = 0;
                if (aValue < bValue) comparison = -1;
                if (aValue > bValue) comparison = 1;
                
                return sortOrder === 'desc' ? -comparison : comparison;
            });
            
            // Remove all cards and re-add them in sorted order
            cards.forEach(card => bookGrid.removeChild(card));
            cards.forEach(card => bookGrid.appendChild(card));
        }
        
        // Add event listeners for sort controls
        document.getElementById('sortField')?.addEventListener('change', sortBooks);
        document.getElementById('sortOrder')?.addEventListener('change', sortBooks);
        
        function parseSearchQuery(query) {
            const filters = {
                readStatus: null,
                tags: [],
                general: []
            };
            
            const terms = query.toLowerCase().split(/\s+/).filter(term => term.length > 0);
            
            terms.forEach(term => {
                if (term === 'read:' || term.startsWith('read:')) {
                    filters.readStatus = 'read';
                } else if (term === 'unread:' || term.startsWith('unread:')) {
                    filters.readStatus = 'unread';
                } else if (term.startsWith('tag:')) {
                    const tagValue = term.substring(4);
                    if (tagValue) filters.tags.push(tagValue);
                } else {
                    filters.general.push(term);
                }
            });
            
            return filters;
        }
        
        document.getElementById('search')?.addEventListener('input', function(e) {
            const query = e.target.value.trim();
            const cards = document.querySelectorAll('.book-card');
            
            if (!query) {
                // Show all cards when search is empty
                cards.forEach(card => {
                    card.style.display = 'block';
                });
                return;
            }
            
            const filters = parseSearchQuery(query);
            
            cards.forEach(card => {
                const title = card.dataset.title || '';
                const author = card.dataset.author || '';
                const tags = card.dataset.tags || '';
                const readStatus = card.dataset.read;
                
                let matches = true;
                
                // Check read status filter
                if (filters.readStatus && readStatus !== filters.readStatus) {
                    matches = false;
                }
                
                // Check tag filters
                if (matches && filters.tags.length > 0) {
                    const bookTags = tags.split(' ').filter(tag => tag.length > 0);
                    matches = filters.tags.every(filterTag => 
                        bookTags.some(bookTag => bookTag.includes(filterTag))
                    );
                }
                
                // Check general search terms
                if (matches && filters.general.length > 0) {
                    const searchableText = `${title} ${author} ${tags}`;
                    matches = filters.general.every(term => 
                        searchableText.includes(term)
                    );
                }
                
                card.style.display = matches ? 'block' : 'none';
            });
        });
        
        // Drag and drop functionality
        const uploadZone = document.getElementById('uploadZone');
        const fileInput = document.getElementById('fileInput');
        
        if (uploadZone && fileInput) {
            // Prevent default drag behaviors
            ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
                uploadZone.addEventListener(eventName, preventDefaults, false);
                document.body.addEventListener(eventName, preventDefaults, false);
            });
            
            // Highlight drop area when item is dragged over it
            ['dragenter', 'dragover'].forEach(eventName => {
                uploadZone.addEventListener(eventName, highlight, false);
            });
            
            ['dragleave', 'drop'].forEach(eventName => {
                uploadZone.addEventListener(eventName, unhighlight, false);
            });
            
            // Handle dropped files
            uploadZone.addEventListener('drop', handleDrop, false);
            
            // Handle file input change
            fileInput.addEventListener('change', function(e) {
                handleFiles(e.target.files);
            });
        }
        
        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }
        
        function highlight(e) {
            uploadZone.classList.add('drag-over');
        }
        
        function unhighlight(e) {
            uploadZone.classList.remove('drag-over');
        }
        
        function handleDrop(e) {
            const dt = e.dataTransfer;
            const files = dt.files;
            handleFiles(files);
        }
        
        async function handleFiles(files) {
            const contributorInput = document.getElementById('contributor');
            // Auto-populate contributor field if empty but name is saved
            if (!contributorInput.value.trim()) {
                const savedContributor = localStorage.getItem('spines_contributor');
                if (savedContributor) {
                    contributorInput.value = savedContributor;
                }
            }
            const contributor = contributorInput.value.trim() || 'anonymous';
            
            // Filter for PDF files only
            const pdfFiles = Array.from(files).filter(file => 
                file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')
            );
            
            if (pdfFiles.length === 0) {
                alert('Please select PDF files only.');
                return;
            }
            
            // Show upload progress
            const uploadContent = document.querySelector('.upload-content');
            const uploadProgress = document.getElementById('uploadProgress');
            const progressFill = document.getElementById('progressFill');
            const uploadStatus = document.getElementById('uploadStatus');
            
            uploadContent.style.display = 'none';
            uploadProgress.style.display = 'block';
            
            try {
                const formData = new FormData();
                pdfFiles.forEach(file => {
                    formData.append('files', file);
                });
                formData.append('contributor', contributor);
                
                const response = await fetch('/api/upload-files', {
                    method: 'POST',
                    body: formData
                });
                
                if (response.ok) {
                    const result = await response.json();
                    progressFill.style.width = '100%';
                    uploadStatus.textContent = `✅ Uploaded ${result.uploaded_count} files successfully!`;
                    
                    // Refresh page after a moment
                    setTimeout(() => {
                        window.location.reload();
                    }, 2000);
                } else {
                    const error = await response.json();
                    uploadStatus.textContent = `❌ Upload failed: ${error.error}`;
                    uploadStatus.style.color = '#cc0000';
                }
            } catch (error) {
                uploadStatus.textContent = `❌ Upload failed: ${error.message}`;
                uploadStatus.style.color = '#cc0000';
            }
            
            // Reset upload zone after a delay
            setTimeout(() => {
                uploadContent.style.display = 'flex';
                uploadProgress.style.display = 'none';
                progressFill.style.width = '0%';
                uploadStatus.textContent = 'Uploading...';
                uploadStatus.style.color = '';
            }, 3000);
        }
        
        // Cloud Sky Animation
        let cloudSketch = function(p) {
            let clouds = [];
            let cloudImg = null;
            let imageLoaded = false;
            const numClouds = 8;

            p.setup = async function() {
                try {
                    p.createCanvas(p.windowWidth, p.windowHeight);
                    
                    // Load cloud image
                    try {
                        cloudImg = await new Promise((resolve, reject) => {
                            p.loadImage('/static/cloud.png', resolve, reject);
                        });
                        imageLoaded = true;
                        console.log('Cloud image loaded successfully');
                    } catch (err) {
                        console.warn('Could not load cloud image, continuing without clouds:', err);
                        imageLoaded = false;
                    }
                    
                    // Initialize clouds with random positions
                    for (let i = 0; i < numClouds; i++) {
                        clouds.push({
                            x: p.random(-200, p.width + 200),
                            y: p.random(50, p.height - 200),
                            scale: p.random(0.3, 0.8),
                            speed: p.random(0.2, 0.6),
                            alpha: p.random(100, 180)
                        });
                    }
                } catch (err) {
                    console.error('Error in cloud sky setup:', err);
                }
            };

            p.draw = function() {
                try {
                    // Soft blue sky gradient
                    for (let y = 0; y < p.height; y++) {
                        const inter = p.map(y, 0, p.height, 0, 1);
                        const c = p.lerpColor(
                            p.color(135, 206, 235), // Light sky blue
                            p.color(176, 224, 230), // Powder blue
                            inter
                        );
                        p.stroke(c);
                        p.line(0, y, p.width, y);
                    }

                    // Draw and animate clouds only if image is loaded
                    if (imageLoaded && cloudImg) {
                        clouds.forEach((cloud) => {
                            p.push();
                            p.translate(cloud.x, cloud.y);
                            p.scale(cloud.scale);
                            p.tint(255, cloud.alpha);
                            
                            p.image(cloudImg, -cloudImg.width / 2, -cloudImg.height / 2);
                            
                            p.pop();

                            // Move cloud from right to left
                            cloud.x -= cloud.speed;

                            // Reset cloud position when it goes off screen
                            if (cloud.x < -300) {
                                cloud.x = p.width + 200;
                                cloud.y = p.random(50, p.height - 200);
                                cloud.scale = p.random(0.3, 0.8);
                                cloud.speed = p.random(0.2, 0.6);
                                cloud.alpha = p.random(100, 180);
                            }
                        });
                    }
                } catch (err) {
                    console.error('Error in cloud sky draw:', err);
                }
            };

            p.windowResized = function() {
                try {
                    p.resizeCanvas(p.windowWidth, p.windowHeight);
                } catch (err) {
                    console.error('Error in cloud sky windowResized:', err);
                }
            };
        };

        // Create the cloud sky instance
        new p5(cloudSketch, 'cloudSky');

    </script>
</body>
</html>"""
        
        # Render template with cache control headers to ensure fresh data
        response = make_response(render_template_string(template, books=books, changes_notice=changes_notice, review_notice=review_notice, upload_zone=upload_zone))
        
        # Prevent caching to ensure metadata updates are reflected immediately
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        
        return response
    
    @app.route('/book/<book_id>')
    def book_detail(book_id):
        """Individual book detail page with comprehensive editing capabilities"""
        generator = StaticGenerator(library_path, data_path)
        metadata = generator.load_book_metadata(book_id)
        
        if not metadata:
            return "Book not found", 404
        
        # Enhanced book detail template with comprehensive editing
        template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ book.title }} - spines</title>
    <style>
/* Enhanced reading experience with seamless PDF background */
body {
    font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
    background: #f0f0f0;
    color: #000;
    line-height: 1.4;
    font-size: 12px;
    margin: 0;
    padding: 0;
    overflow-x: hidden;
}

/* PDF Pages Container - flows with document */
.pdf-pages-container {
    width: 100%;
    background: #fff;
    padding: 0;
    margin: 0;
}

.pdf-page {
    display: block;
    max-width: 100%;
    margin: 0 auto 1px auto; /* Tiny gap between pages */
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

/* Content flows naturally with document */
.content-container {
    max-width: 800px;
    margin: 0 auto;
    padding: 20px;
    position: relative;
    z-index: 10;
}

/* Mobile responsive adjustments */
@media (max-width: 480px) {
    .content-container {
        padding: 10px;
    }
    
    body {
        font-size: 14px; /* Slightly larger for touch */
    }
    
    .metadata-grid {
        grid-template-columns: 1fr;
        gap: 5px 0;
    }
    
    .metadata-label {
        font-size: 11px;
        color: #666;
        margin-bottom: 2px;
    }
    
    .add-select {
        width: 100% !important;
        max-width: none;
    }
    
    .save-status {
        bottom: 10px !important;
        right: 10px !important;
        font-size: 12px;
    }
    
    .collapse-toggle {
        top: 8px;
        right: 8px;
        width: 20px;
        height: 20px;
        font-size: 12px;
    }
}

.book-detail {
    border: 2px solid black;
    background: rgba(255, 255, 255, 0.95);
    backdrop-filter: blur(2px);
    padding: 20px;
    margin-bottom: 20px;
    transition: all 0.3s ease;
    position: sticky;
    top: 70px; /* Space for back button (20px top + ~35px height + 15px gap) */
    z-index: 100;
}

.book-detail.collapsed {
    transform: translateY(calc(-100% + 60px)); /* Show just the title and button */
    box-shadow: 0 4px 8px rgba(0,0,0,0.1);
}

.book-detail.collapsed .metadata-content {
    display: none;
}

.book-detail.collapsed .functions-section {
    display: none;
}

/* Collapse toggle - top right corner like window minimize */
.collapse-toggle {
    position: absolute;
    right: 10px;
    top: 10px;
    width: 24px;
    height: 24px;
    background: rgba(255, 255, 255, 0.9);
    border: 1px solid black;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    font-weight: bold;
    transition: all 0.3s ease;
    z-index: 101;
}

.collapse-toggle:hover {
    background: rgba(0, 0, 0, 0.1);
}

@media (max-width: 480px) {
    .book-detail {
        padding: 15px;
    }
}

.metadata-grid {
    display: grid;
    grid-template-columns: 140px 1fr;
    gap: 10px 20px;
    margin: 20px 0;
}

.metadata-label {
    font-weight: bold;
    align-self: start;
}

.metadata-value {
    cursor: pointer;
    padding: 2px 4px;
    border: 1px solid transparent;
    min-height: 16px;
    word-wrap: break-word;
    overflow-wrap: break-word;
    hyphens: auto;
    
    /* Better touch targets on mobile */
    min-height: 24px;
    display: flex;
    align-items: center;
}

.metadata-value:hover {
    background: #f0f0f0;
    border-color: #ccc;
}

/* Touch device improvements */
@media (hover: none) {
    .metadata-value {
        min-height: 32px; /* Larger touch targets */
        padding: 6px 8px;
    }
    
    .metadata-value:not(.readonly) {
        background: #f8f8f8;
        border: 1px solid #ddd;
    }
}

.metadata-value.editing {
    background: #f8f8ff;
    border-color: #0066cc;
}

.metadata-input, .metadata-textarea {
    border: 1px solid #0066cc;
    background: white;
    font-family: inherit;
    font-size: inherit;
    color: inherit;
    width: 100%;
    padding: 2px 4px;
}

.metadata-textarea {
    min-height: 60px;
    resize: vertical;
}

.back-link {
    border: 1px solid black;
    background: rgba(255, 255, 255, 0.95);
    backdrop-filter: blur(2px);
    padding: 5px 15px;
    text-decoration: none;
    color: black;
    font-size: 12px;
    display: inline-block;
    margin-bottom: 20px;
    position: sticky;
    top: 20px;
    z-index: 99; /* Just below metadata card */
}

.back-link:hover {
    background: black;
    color: white;
}

.save-status {
    position: fixed;
    bottom: 20px;
    right: 20px;
    padding: 8px 12px;
    border: 1px solid black;
    background: white;
    font-family: inherit;
    font-size: 11px;
    z-index: 1000;
}

.metadata-value:focus {
    outline: 2px solid black;
    outline-offset: -2px;
}

.metadata-value:not(.readonly):hover {
    background: #f8f8f8;
    cursor: text;
}

.metadata-input, .metadata-textarea {
    border: 2px solid black;
    background: white;
    font-family: inherit;
    font-size: inherit;
    padding: 2px 4px;
    outline: none;
    width: 100%;
    box-sizing: border-box;
}

.metadata-input:focus, .metadata-textarea:focus {
    border-color: #0066cc;
}

.metadata-textarea {
    min-height: 60px;
    resize: vertical;
}

.feedback {
    position: fixed;
    top: 20px;
    right: 20px;
    padding: 10px 15px;
    border: 2px solid black;
    font-family: inherit;
    font-size: 12px;
    z-index: 1000;
}

.feedback.success { background: #e8f5e8; }
.feedback.error { background: #ffe8e8; }
.feedback.info { background: #e8f0ff; }

.loading {
    opacity: 0.6;
    pointer-events: none;
}

.readonly {
    color: #666;
    cursor: default;
}

.readonly:hover {
    background: transparent;
    border-color: transparent;
}

.metadata-list {
    min-height: 20px;
}

.add-select {
    border: 1px solid black;
    background: white;
    font-family: inherit;
    font-size: 12px;
    padding: 4px 8px;
    margin-bottom: 8px;
    width: 200px;
    max-width: 100%;
}

.list-items {
    line-height: 1.6;
}

.list-item {
    margin-bottom: 4px;
    font-size: 12px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    word-wrap: break-word;
    overflow-wrap: break-word;
}

.remove-item {
    margin-left: 8px;
    cursor: pointer;
    color: black;
    font-weight: bold;
    padding: 2px 6px;
    flex-shrink: 0;
    border: 1px solid transparent;
    
    /* Better touch target */
    min-width: 24px;
    min-height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
}

.remove-item:hover {
    background: black;
    color: white;
    border-color: black;
}

/* Touch-friendly remove buttons */
@media (hover: none) {
    .remove-item {
        min-width: 32px;
        min-height: 32px;
        background: #f0f0f0;
        border: 1px solid #ccc;
    }
    
    .remove-item:active {
        background: black;
        color: white;
    }
}

.functions-section {
    margin-top: 30px;
    padding-top: 20px;
    border-top: 1px solid #ccc;
}

.section-title {
    font-size: 14px;
    font-weight: bold;
    margin-bottom: 15px;
    text-transform: lowercase;
}

.function-buttons {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
}

.function-button {
    border: 1px solid black;
    background: white;
    padding: 8px 16px;
    font-family: inherit;
    font-size: 12px;
    cursor: pointer;
    font-weight: normal;
    display: flex;
    align-items: center;
    gap: 6px;
}

.function-button:hover {
    background: #f0f0f0;
}

.function-button.delete {
    border-color: #cc0000;
    color: #cc0000;
}

.function-button.delete:hover {
    background: #cc0000;
    color: white;
}

.related-copies-list {
    background: #f8f8f8;
    border: 1px solid #ddd;
    padding: 10px;
    margin-top: 5px;
}

.related-copy {
    margin-bottom: 10px;
    padding: 8px;
    border: 1px solid #ccc;
    background: white;
    font-size: 11px;
    line-height: 1.4;
}

.related-copy:last-child {
    margin-bottom: 0;
}

.clickable-copy {
    cursor: pointer;
    transition: all 0.2s ease;
}

.clickable-copy:hover {
    background: #f0f8ff;
    border-color: #0066cc;
    transform: translateY(-1px);
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.copy-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 4px;
}

.copy-header strong {
    color: #0066cc;
    text-transform: capitalize;
}

.confidence {
    color: #666;
    font-size: 10px;
}

.view-copy {
    color: #0066cc;
    font-size: 10px;
    opacity: 0;
    transition: opacity 0.2s ease;
}

.clickable-copy:hover .view-copy {
    opacity: 1;
}

.copy-detail {
    margin: 2px 0;
    color: #444;
}

.current-copy-indicator {
    background: #e8f0ff;
    border: 1px solid #0066cc;
    padding: 8px 12px;
    margin: 10px 0 20px 0;
    font-size: 11px;
    color: #0066cc;
}

.copy-count {
    color: #666;
    font-style: italic;
}

.copy-navigation {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.copy-nav-button {
    border: 1px solid #0066cc;
    background: white;
    padding: 10px 12px;
    font-family: inherit;
    font-size: 11px;
    cursor: pointer;
    text-align: left;
    color: #0066cc;
    line-height: 1.3;
}

.copy-nav-button:hover {
    background: #e8f0ff;
}

.copy-nav-button small {
    color: #666;
    font-size: 9px;
}
    </style>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js"></script>
</head>
<body>
    <!-- Content flows naturally -->
    <div class="content-container">
        <a href="/" class="back-link" onclick="navigateBackToLibrary(event)">← back to library</a>
            
            <div class="book-detail" id="bookDetail">
                <div class="collapse-toggle" id="collapseToggle" onclick="toggleMetadata()">–</div>
                
                <h2 class="metadata-value" data-field="title">{{ book.title }}</h2>
                
                <div class="metadata-content">
        {% if book.related_copies %}
        <div class="current-copy-indicator">
            📚 viewing copy contributed by: {{ book.contributor|join(', ') if book.contributor else 'unknown' }}
            <span class="copy-count">({{ book.related_copies|length + 1 }} copies total)</span>
        </div>
        {% endif %}
        
        <div class="metadata-grid">
            <div class="metadata-label">author:</div>
            <div class="metadata-value" data-field="author">{{ book.author }}</div>
            
            <div class="metadata-label">year:</div>
            <div class="metadata-value" data-field="year">{{ book.year or 'click to add' }}</div>
            
            <div class="metadata-label">media type:</div>
            <div class="metadata-value" data-field="media_type" data-select="true">{{ book.media_type or 'book' }}</div>
            
            <div class="metadata-label">isbn:</div>
            <div class="metadata-value" data-field="isbn">{{ book.isbn or 'click to add' }}</div>
            
            <div class="metadata-label url-field" style="display: none;">url:</div>
            <div class="metadata-value url-field" data-field="url" style="display: none;">{{ book.url or 'click to add' }}</div>
            
            <div class="metadata-label">contributors:</div>
            <div class="metadata-list" data-field="contributor">
                <select class="add-select" onchange="addFromSelect(this)" data-list="contributors">
                    <option value="">add contributor...</option>
                </select>
                <div class="list-items">
                    {% for contributor in book.contributor or [] %}
                    <div class="list-item">
                        {{ contributor }}
                        <span class="remove-item" onclick="removeListItem(this)">×</span>
                    </div>
                    {% endfor %}
                </div>
            </div>
            
            <div class="metadata-label">tags:</div>
            <div class="metadata-value" data-field="tags">{{ (book.tags or [])|join(', ') or 'click to add tags' }}</div>
            
            <div class="metadata-label">read by:</div>
            <div class="metadata-list" data-field="read_by">
                <select class="add-select" onchange="addFromSelect(this)" data-list="readers">
                    <option value="">add reader...</option>
                </select>
                <div class="list-items">
                    {% for reader in book.read_by or [] %}
                    <div class="list-item">
                        {{ reader }}
                        <span class="remove-item" onclick="removeListItem(this)">×</span>
                    </div>
                    {% endfor %}
                </div>
            </div>
            
            <div class="metadata-label">notes:</div>
            <div class="metadata-value" data-field="notes" data-multiline="true">{{ book.notes or 'click to add notes' }}</div>
            
            <div class="metadata-label">pages:</div>
            <div class="readonly">{{ book.pages }}</div>
            
            <div class="metadata-label">file size:</div>
            <div class="readonly">{% if book.file_size %}{{ "%.1f"|format(book.file_size / 1024 / 1024) }} MB{% else %}unknown{% endif %}</div>
            
            <div class="metadata-label">added:</div>
            <div class="readonly">{{ book.date_added[:10] }}</div>
            
            {% if book.publisher %}
            <div class="metadata-label">publisher:</div>
            <div class="metadata-value" data-field="publisher">{{ book.publisher }}</div>
            {% endif %}
            
            {% if book.related_copies %}
            <div class="metadata-label">related copies:</div>
            <div class="readonly related-copies-list">
                {% for copy in book.related_copies %}
                <div class="related-copy clickable-copy" onclick="window.location.href='/book/{{ copy.book_id }}'">
                    <div class="copy-header">
                        <strong>{{ copy.similarity_type|replace('_', ' ') }}</strong> 
                        <span class="confidence">({{ "%.0f"|format(copy.confidence * 100) }}% match)</span>
                        <span class="view-copy">→ view this copy</span>
                    </div>
                    {% if copy.contributor %}<div class="copy-detail">contributed by: {{ copy.contributor|join(', ') }}</div>{% endif %}
                    {% if copy.isbn and copy.isbn != book.isbn %}<div class="copy-detail">ISBN: {{ copy.isbn }}</div>{% endif %}
                    {% if copy.year and copy.year != book.year %}<div class="copy-detail">Year: {{ copy.year }}</div>{% endif %}
                    {% if copy.publisher and copy.publisher != book.publisher %}<div class="copy-detail">Publisher: {{ copy.publisher }}</div>{% endif %}
                </div>
                {% endfor %}
            </div>
            {% endif %}
        </div>
        </div> <!-- Close metadata-content -->
        
        <div class="functions-section">
            <h3 class="section-title">functions</h3>
            <div class="function-buttons">
                <button class="function-button" onclick="openFile('{{ book.id }}')">
                    📖 open file
                </button>
                <button class="function-button" onclick="extractText('{{ book.id }}')">
                    {% if book.text_extracted %}📄 re-extract text{% else %}🔍 extract text{% endif %}
                </button>
                <button class="function-button delete" onclick="deleteBook('{{ book.id }}', '{{ book.title|replace("'", "\\'") }}')">
                    🗑️ delete book
                </button>
            </div>
            
            {% if book.related_copies %}
            <h3 class="section-title" style="margin-top: 20px;">other copies</h3>
            <div class="copy-navigation">
                {% for copy in book.related_copies %}
                <button class="copy-nav-button" onclick="window.location.href='/book/{{ copy.book_id }}'">
                    📄 {{ copy.contributor|join(', ') if copy.contributor else 'unknown contributor' }}
                    {% if copy.isbn and copy.isbn != book.isbn %}<br><small>ISBN: {{ copy.isbn }}</small>{% endif %}
                </button>
                {% endfor %}
            </div>
            {% endif %}
        </div>
        
        <div class="save-status" id="saveStatus" style="display: none;">
            💾 saving...
        </div>
    </div> <!-- Close book-detail -->
    </div> <!-- Close content-container -->
    
    <!-- PDF Pages Container - flows after metadata -->
    <div class="pdf-pages-container" id="pdfPagesContainer">
        <div id="loadingStatus" style="text-align: center; padding: 40px; font-family: monospace; color: #666;">
            📄 loading pdf pages...
        </div>
    </div>
    
    <script>
        const bookId = '{{ book.id }}';
        let currentlyEditing = null;
        let editableFields = [];
        let currentFieldIndex = -1;
        let libraryMetadata = {};
        let saveTimeout = null;
        let metadataCollapsed = false;
        
        // Toggle metadata visibility
        function toggleMetadata() {
            const bookDetail = document.getElementById('bookDetail');
            const collapseToggle = document.getElementById('collapseToggle');
            
            metadataCollapsed = !metadataCollapsed;
            
            if (metadataCollapsed) {
                bookDetail.classList.add('collapsed');
                collapseToggle.textContent = '+';
            } else {
                bookDetail.classList.remove('collapsed');
                collapseToggle.textContent = '–';
            }
        }
        
        // Navigation function to preserve scroll position
        function navigateBackToLibrary(event) {
            event.preventDefault();
            
            // Check if there are unsaved changes
            if (currentlyEditing) {
                if (!confirm('You have unsaved changes. Are you sure you want to leave?')) {
                    return;
                }
            }
            
            // Force browser cache refresh by adding timestamp parameter
            const timestamp = new Date().getTime();
            window.location.href = `/?t=${timestamp}`;
        }
        
        // Load library metadata for autocomplete
        async function loadLibraryMetadata() {
            try {
                const response = await fetch('/api/library-metadata');
                if (response.ok) {
                    libraryMetadata = await response.json();
                    setupAutocomplete();
                }
            } catch (error) {
                console.error('Failed to load library metadata:', error);
            }
        }
        
        // Setup autocomplete select options
        function setupAutocomplete() {
            if (libraryMetadata.contributors) {
                populateSelect('contributors', libraryMetadata.contributors);
            }
            if (libraryMetadata.readers) {
                populateSelect('readers', libraryMetadata.readers);
            }
        }
        
        function populateSelect(type, options) {
            const selects = document.querySelectorAll(`select[data-list="${type}"]`);
            selects.forEach(select => {
                // Clear existing options except the first one
                while (select.children.length > 1) {
                    select.removeChild(select.lastChild);
                }
                
                // Add options
                options.forEach(option => {
                    const optionElement = document.createElement('option');
                    optionElement.value = option;
                    optionElement.textContent = option;
                    select.appendChild(optionElement);
                });
            });
        }
        
        // Load metadata on page load
        loadLibraryMetadata();
        
        // Load and render PDF pages
        loadPDFPages();
        
        // Setup media type handling and field navigation
        setupFieldNavigation();
        setupMediaTypeHandling();
        
        function setupFieldNavigation() {
            // Build list of editable fields in order
            editableFields = Array.from(document.querySelectorAll('.metadata-value:not(.readonly)'));
            
            editableFields.forEach((field, index) => {
                field.setAttribute('tabindex', '0');
                field.setAttribute('data-field-index', index);
            });
        }
        
        function showSaveStatus(message = '💾 saving...') {
            const status = document.getElementById('saveStatus');
            status.textContent = message;
            status.style.display = 'block';
        }
        
        function hideSaveStatus() {
            const status = document.getElementById('saveStatus');
            status.style.display = 'none';
        }
        
        // Make metadata values editable on click/tap or focus
        document.addEventListener('click', function(e) {
            if (e.target.classList.contains('metadata-value') && !e.target.classList.contains('readonly')) {
                startEditing(e.target);
            }
        });
        
        // Touch event handling for mobile
        document.addEventListener('touchstart', function(e) {
            if (e.target.classList.contains('metadata-value') && !e.target.classList.contains('readonly')) {
                // Add visual feedback for touch
                e.target.style.background = '#e8f0ff';
            }
        });
        
        document.addEventListener('touchend', function(e) {
            if (e.target.classList.contains('metadata-value') && !e.target.classList.contains('readonly')) {
                // Remove visual feedback
                setTimeout(() => {
                    if (!currentlyEditing) {
                        e.target.style.background = '';
                    }
                }, 100);
            }
        });
        
        // Handle keyboard navigation
        document.addEventListener('keydown', function(e) {
            // Global tab navigation when not editing
            if (!currentlyEditing && e.key === 'Tab') {
                e.preventDefault();
                navigateToNextField(e.shiftKey);
            }
        });
        
        function navigateToNextField(backwards = false) {
            if (editableFields.length === 0) return;
            
            if (currentFieldIndex === -1) {
                currentFieldIndex = 0;
            } else {
                currentFieldIndex = backwards 
                    ? (currentFieldIndex - 1 + editableFields.length) % editableFields.length
                    : (currentFieldIndex + 1) % editableFields.length;
            }
            
            const nextField = editableFields[currentFieldIndex];
            nextField.focus();
        }
        
        function setupMediaTypeHandling() {
            // Show appropriate fields based on current media type
            updateFieldsForMediaType();
        }
        
        function updateFieldsForMediaType() {
            const mediaTypeElement = document.querySelector('[data-field="media_type"]');
            const currentType = mediaTypeElement ? mediaTypeElement.textContent.trim() : 'book';
            
            // Hide all contextual fields first
            document.querySelectorAll('.url-field').forEach(el => {
                el.style.display = 'none';
            });
            
            // Show relevant fields based on media type
            if (currentType === 'web') {
                document.querySelectorAll('.url-field').forEach(el => {
                    el.style.display = '';
                });
            }
        }
        
        function startEditing(element) {
            if (currentlyEditing) return;
            
            currentlyEditing = element;
            currentFieldIndex = parseInt(element.dataset.fieldIndex);
            
            const field = element.dataset.field;
            const isMultiline = element.dataset.multiline === 'true';
            const isSelect = element.dataset.select === 'true';
            const originalValue = element.textContent.trim();
            
            // Create input or select
            let input;
            if (isSelect && field === 'media_type') {
                input = document.createElement('select');
                input.className = 'metadata-input';
                
                // Add media type options
                const mediaTypes = ['book', 'web', 'unknown'];
                mediaTypes.forEach(type => {
                    const option = document.createElement('option');
                    option.value = type;
                    option.textContent = type;
                    if (type === originalValue) {
                        option.selected = true;
                    }
                    input.appendChild(option);
                });
            } else {
                input = document.createElement(isMultiline ? 'textarea' : 'input');
                if (!isMultiline) input.type = 'text';
                input.className = isMultiline ? 'metadata-textarea' : 'metadata-input';
            }
            
            // Add autocomplete for specific fields
            if (field === 'contributor' && libraryMetadata.contributors) {
                input.setAttribute('list', 'contributors-list');
                addDatalist('contributors-list', libraryMetadata.contributors);
            } else if (field === 'read_by' && libraryMetadata.readers) {
                input.setAttribute('list', 'readers-list');
                addDatalist('readers-list', libraryMetadata.readers);
            }
            
            // Set value, handling placeholder text
            const placeholders = {
                'year': 'click to add',
                'isbn': 'click to add', 
                'url': 'click to add',
                'contributor': 'click to add contributors',
                'tags': 'click to add tags',
                'read_by': 'click to add readers',
                'notes': 'click to add notes'
            };
            
            const placeholder = placeholders[field];
            input.value = (originalValue === placeholder) ? '' : originalValue;
            
            // Replace element with input
            element.style.display = 'none';
            element.parentNode.insertBefore(input, element.nextSibling);
            input.focus();
            if (!isMultiline && !isSelect) input.select();
            
            // Handle input events
            function finishEditing(saveChanges = true) {
                if (!currentlyEditing) return;
                
                const newValue = isSelect ? input.value : input.value.trim();
                const displayValue = newValue || placeholder || '';
                
                element.textContent = displayValue;
                element.style.display = '';
                input.remove();
                currentlyEditing = null;
                
                if (saveChanges && newValue !== originalValue) {
                    saveFieldValue(field, newValue);
                }
            }
            
            // Keyboard handling
            input.addEventListener('keydown', function(e) {
                if (e.key === 'Enter' && !isMultiline) {
                    e.preventDefault();
                    finishEditing(true);
                    // Move to next field after save
                    setTimeout(() => navigateToNextField(), 100);
                } else if (e.key === 'Tab') {
                    e.preventDefault();
                    finishEditing(true);
                    // Tab navigation handled by global listener
                    setTimeout(() => navigateToNextField(e.shiftKey), 100);
                } else if (e.key === 'Escape') {
                    e.preventDefault();
                    finishEditing(false); // Don't save changes
                }
            });
            
            // Auto-save on blur (when clicking elsewhere) 
            // Longer timeout for mobile to handle touch events properly
            input.addEventListener('blur', function() {
                setTimeout(() => {
                    if (currentlyEditing === element) {
                        finishEditing(true);
                    }
                }, 150);
            });
            
            // Also save on input change for better mobile UX
            let inputTimeout;
            input.addEventListener('input', function() {
                clearTimeout(inputTimeout);
                inputTimeout = setTimeout(() => {
                    // Visual feedback that auto-save is happening
                    showSaveStatus('💾 auto-saving...');
                }, 1000);
            });
            
            // Special handling for select elements
            if (isSelect) {
                input.addEventListener('change', function() {
                    finishEditing(true);
                });
            }
        }
        
        async function saveFieldValue(field, value) {
            // Clear any existing save timeout
            if (saveTimeout) {
                clearTimeout(saveTimeout);
            }
            
            // Show save status
            showSaveStatus();
            
            // Process the value
            let processedValue = value;
            
            // Handle special field types
            if (field === 'year' && value) {
                processedValue = parseInt(value) || null;
            } else if (field === 'tags' && typeof value === 'string' && value) {
                // Split tags by comma and clean them
                processedValue = value.split(',').map(tag => tag.trim()).filter(tag => tag);
            }
            // For list fields (contributor, read_by), value is already an array
            
            // Build the data object for this single field
            const data = {};
            data[field] = processedValue;
            
            try {
                const response = await fetch(`/api/books/${bookId}`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(data)
                });
                
                if (response.ok) {
                    showSaveStatus('✅ saved');
                    
                    // Mark that metadata has been updated (for cache invalidation)
                    localStorage.setItem('spines_metadata_updated', 'true');
                    
                    // Check if ISBN was added for metadata lookup
                    if (field === 'isbn' && value) {
                        showSaveStatus('📚 fetching metadata...');
                        setTimeout(() => window.location.reload(), 2000);
                        return;
                    }
                    
                    // Handle media type changes
                    if (field === 'media_type') {
                        setTimeout(() => {
                            updateFieldsForMediaType();
                        }, 100);
                    }
                    
                    // Hide save status after a moment
                    setTimeout(() => {
                        hideSaveStatus();
                    }, 1500);
                    
                } else {
                    const error = await response.json();
                    showSaveStatus(`❌ error: ${error.error}`);
                    setTimeout(() => {
                        hideSaveStatus();
                    }, 3000);
                }
            } catch (error) {
                showSaveStatus(`❌ network error`);
                setTimeout(() => {
                    hideSaveStatus();
                }, 3000);
            }
        }
        
        function addDatalist(id, options) {
            // Remove existing datalist if it exists
            const existing = document.getElementById(id);
            if (existing) existing.remove();
            
            // Create new datalist
            const datalist = document.createElement('datalist');
            datalist.id = id;
            
            options.forEach(option => {
                const optionElement = document.createElement('option');
                optionElement.value = option;
                datalist.appendChild(optionElement);
            });
            
            document.body.appendChild(datalist);
        }
        
        function addFromSelect(select) {
            const value = select.value.trim();
            if (!value) return;
            
            const metadataList = select.parentElement;
            const listItems = metadataList.querySelector('.list-items');
            
            // Check if already exists
            const existing = Array.from(listItems.querySelectorAll('.list-item')).find(item => 
                item.textContent.replace('×', '').trim() === value
            );
            if (existing) {
                select.value = '';
                return;
            }
            
            // Create new list item
            const listItem = document.createElement('div');
            listItem.className = 'list-item';
            listItem.innerHTML = `${value}<span class="remove-item" onclick="removeListItem(this)">×</span>`;
            
            listItems.appendChild(listItem);
            
            // Reset select
            select.value = '';
            
            // Mark as changed for save
            markListChanged(metadataList);
        }
        
        function removeListItem(span) {
            const listItem = span.parentElement;
            const metadataList = listItem.closest('.metadata-list');
            
            listItem.remove();
            markListChanged(metadataList);
        }
        
        function markListChanged(metadataList) {
            // Auto-save list changes
            const field = metadataList.dataset.field;
            if (field) {
                const items = [];
                const listItems = metadataList.querySelectorAll('.list-item');
                listItems.forEach(item => {
                    const text = item.textContent.replace('×', '').trim();
                    if (text) items.push(text);
                });
                
                // Mark that metadata will be updated
                localStorage.setItem('spines_metadata_updated', 'true');
                
                saveFieldValue(field, items);
            }
        }
        
        function showFeedback(message, type) {
            const feedback = document.createElement('div');
            feedback.className = `feedback ${type}`;
            feedback.textContent = message;
            
            document.body.appendChild(feedback);
            
            setTimeout(() => {
                if (feedback.parentNode) {
                    feedback.parentNode.removeChild(feedback);
                }
            }, 3000);
        }
        
        function openFile(bookId) {
            // Open the PDF file in a new tab
            window.open(`/api/books/${bookId}/file`, '_blank');
        }
        
        async function extractText(bookId) {
            // Extract text from PDF using OCR
            try {
                showSaveStatus('🔍 extracting text...');
                
                const response = await fetch(`/api/books/${bookId}/extract-text`, {
                    method: 'POST'
                });
                
                if (response.ok) {
                    const result = await response.json();
                    showSaveStatus('✅ text extracted');
                    showFeedback(`📄 Text extracted to ${result.filename}`, 'success');
                    
                    // Hide save status after a moment
                    setTimeout(() => {
                        hideSaveStatus();
                    }, 2000);
                } else {
                    const error = await response.json();
                    showSaveStatus(`❌ extraction failed`);
                    showFeedback(`❌ Text extraction failed: ${error.error}`, 'error');
                    setTimeout(() => {
                        hideSaveStatus();
                    }, 3000);
                }
            } catch (error) {
                showSaveStatus(`❌ network error`);
                showFeedback(`❌ Network error: ${error.message}`, 'error');
                setTimeout(() => {
                    hideSaveStatus();
                }, 3000);
            }
        }
        
        // PDF.js setup and page rendering
        async function loadPDFPages() {
            try {
                // Set up PDF.js worker
                pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
                
                const loadingTask = pdfjsLib.getDocument(`/api/books/${bookId}/file`);
                const pdf = await loadingTask.promise;
                
                const container = document.getElementById('pdfPagesContainer');
                const loadingStatus = document.getElementById('loadingStatus');
                
                // Update loading status
                loadingStatus.textContent = `📄 rendering ${pdf.numPages} pages...`;
                
                // Render pages progressively
                for (let pageNum = 1; pageNum <= pdf.numPages; pageNum++) {
                    // Add a small delay to keep UI responsive
                    if (pageNum > 1) {
                        await new Promise(resolve => setTimeout(resolve, 10));
                    }
                    
                    const page = await pdf.getPage(pageNum);
                    const canvas = document.createElement('canvas');
                    const context = canvas.getContext('2d');
                    
                    // Get device pixel ratio for crisp rendering on high-DPI displays
                    const devicePixelRatio = window.devicePixelRatio || 1;
                    
                    // Calculate scale for responsive rendering
                    const viewport = page.getViewport({ scale: 1 });
                    const containerWidth = container.clientWidth || 800;
                    const baseScale = Math.min(1.8, containerWidth / viewport.width);
                    
                    // Scale for both responsive sizing AND device pixel density
                    const renderScale = baseScale * devicePixelRatio;
                    const scaledViewport = page.getViewport({ scale: renderScale });
                    
                    // Set canvas backing store size (actual pixel dimensions)
                    canvas.height = scaledViewport.height;
                    canvas.width = scaledViewport.width;
                    
                    // Set canvas CSS size (visual dimensions)
                    const displayWidth = scaledViewport.width / devicePixelRatio;
                    const displayHeight = scaledViewport.height / devicePixelRatio;
                    canvas.style.width = displayWidth + 'px';
                    canvas.style.height = displayHeight + 'px';
                    
                    canvas.className = 'pdf-page';
                    canvas.style.opacity = '0';
                    canvas.style.transition = 'opacity 0.3s ease';
                    
                    const renderContext = {
                        canvasContext: context,
                        viewport: scaledViewport
                    };
                    
                    // Insert before loading status first
                    container.insertBefore(canvas, loadingStatus);
                    
                    // Render and fade in
                    await page.render(renderContext).promise;
                    canvas.style.opacity = '1';
                    
                    // Update progress
                    loadingStatus.textContent = `📄 rendered ${pageNum}/${pdf.numPages} pages...`;
                }
                
                // Hide loading status
                loadingStatus.style.display = 'none';
                
            } catch (error) {
                console.error('Error loading PDF:', error);
                document.getElementById('loadingStatus').textContent = '❌ failed to load pdf';
            }
        }
        
        async function deleteBook(bookId, bookTitle) {
            if (!confirm(`Are you sure you want to delete "${bookTitle}"?\n\nThis will permanently delete the book and all its files from the server.`)) {
                return;
            }
            
            try {
                const response = await fetch(`/api/books/${bookId}`, {
                    method: 'DELETE'
                });
                
                if (response.ok) {
                    const result = await response.json();
                    showFeedback(`✅ ${result.message}`, 'success');
                    
                    // Redirect to main library after successful deletion
                    setTimeout(() => {
                        window.location.href = '/';
                    }, 2000);
                } else {
                    const error = await response.json();
                    showFeedback(`❌ Failed to delete book: ${error.error}`, 'error');
                }
            } catch (error) {
                showFeedback(`❌ Network error: ${error.message}`, 'error');
            }
        }
    </script>
</body>
</html>"""
        
        return render_template_string(template, book=metadata)
    
    @app.route('/api/books/<book_id>', methods=['PUT'])
    def update_book(book_id):
        """Update book metadata"""
        from src.metadata_extractor import MetadataExtractor
        
        try:
            data = request.get_json()
            extractor = MetadataExtractor(library_path, data_path)
            generator = StaticGenerator(library_path, data_path)
            
            # Load current metadata
            current_metadata = generator.load_book_metadata(book_id)
            if not current_metadata:
                return jsonify({"error": "Book not found"}), 404
            
            # Check if ISBN was actually changed and needs lookup
            isbn_changed = False
            original_isbn = current_metadata.get('isbn')
            new_isbn = data.get('isbn')
            
            # Check if ISSN was added/changed and needs lookup
            issn_changed = False
            original_issn = current_metadata.get('issn')
            new_issn = data.get('issn')
            issn_metadata_fetched = current_metadata.get('issn_metadata_fetched', False)
            
            # Only fetch ISBN metadata if:
            # 1. The ISBN field was actually included in this update, AND
            # 2. The ISBN value is different from what we had before, AND
            # 3. We're adding an ISBN where none existed before, AND
            # 4. We haven't already fetched ISBN metadata for this book
            isbn_metadata_fetched = current_metadata.get('isbn_metadata_fetched', False)
            
            if ('isbn' in data and 
                new_isbn != original_isbn and
                new_isbn and 
                original_isbn in [None, '', 'no_isbn', 'click to add'] and
                not isbn_metadata_fetched):
                isbn_changed = True
                print(f"🔍 ISBN added for the first time: {new_isbn}")
            
            # Similar logic for ISSN
            if ('issn' in data and 
                new_issn != original_issn and
                new_issn and 
                original_issn in [None, '', 'no_issn', 'click to add'] and
                not issn_metadata_fetched):
                issn_changed = True
                print(f"🔍 ISSN added for the first time: {new_issn}")
            
            # Track which fields the user is manually editing
            # Mark fields as manually edited if they're being changed by the user
            if 'title' in data and data['title'] != current_metadata.get('title'):
                current_metadata['title_manually_edited'] = True
                print(f"🖋️ Title manually edited: {data['title']}")
            
            if 'author' in data and data['author'] != current_metadata.get('author'):
                current_metadata['author_manually_edited'] = True
                print(f"🖋️ Author manually edited: {data['author']}")
            
            if 'year' in data and data['year'] != current_metadata.get('year'):
                current_metadata['year_manually_edited'] = True
                print(f"🖋️ Year manually edited: {data['year']}")
            
            # For contributor, compare as lists
            current_contributors = current_metadata.get('contributor', [])
            new_contributors = data.get('contributor', [])
            if 'contributor' in data and new_contributors != current_contributors:
                current_metadata['contributor_manually_edited'] = True
                print(f"🖋️ Contributors manually edited: {new_contributors}")
            
            # Update metadata with user changes FIRST (before ISBN lookup)
            current_metadata.update(data)
            
            # Track contributors and readers globally
            if 'contributor' in data and data['contributor']:
                # contributor is already processed as a list in the frontend
                contributors = data['contributor'] if isinstance(data['contributor'], list) else [data['contributor']]
                for contributor in contributors:
                    if contributor and contributor.strip():
                        extractor.add_contributor(contributor.strip())
            
            if 'read_by' in data and data['read_by']:
                # read_by should be a list
                readers = data['read_by'] if isinstance(data['read_by'], list) else [data['read_by']]
                extractor.add_readers(readers)
            
            # If ISBN was added for the first time, try to fetch additional metadata
            if isbn_changed:
                try:
                    # Use the enhanced ISBN lookup
                    isbn_metadata = extractor.enhanced_isbn_lookup(new_isbn)
                    
                    if isbn_metadata:
                        # Define placeholder/poor quality values that should be replaced
                        title_placeholders = ['Unknown', 'unknown_title', '', None]
                        author_placeholders = ['Unknown', 'unknown_author', '', None]
                        
                        # Only update title if it hasn't been manually edited yet
                        title_manually_edited = current_metadata.get('title_manually_edited', False)
                        if isbn_metadata.get('title') and not title_manually_edited:
                            current_metadata['title'] = isbn_metadata['title']
                            print(f"📚 Updated title: {isbn_metadata['title']}")
                        elif title_manually_edited:
                            print(f"📚 Skipping title update - user has manually edited it")
                        
                        # Only update author if it hasn't been manually edited yet
                        author_manually_edited = current_metadata.get('author_manually_edited', False)
                        if isbn_metadata.get('author') and not author_manually_edited:
                            current_metadata['author'] = isbn_metadata['author']
                            print(f"👤 Updated author: {isbn_metadata['author']}")
                        elif author_manually_edited:
                            print(f"👤 Skipping author update - user has manually edited it")
                        
                        # Only update year if it hasn't been manually edited yet
                        year_manually_edited = current_metadata.get('year_manually_edited', False)
                        if isbn_metadata.get('year') and not year_manually_edited:
                            current_metadata['year'] = isbn_metadata['year']
                            print(f"📅 Updated year: {isbn_metadata['year']}")
                        elif year_manually_edited:
                            print(f"📅 Skipping year update - user has manually edited it")
                        
                        # Add publisher if available and not set
                        if (isbn_metadata.get('publisher') and 
                            not current_metadata.get('publisher')):
                            current_metadata['publisher'] = isbn_metadata['publisher']
                            print(f"🏢 Added publisher: {isbn_metadata['publisher']}")
                        
                        # Mark that we've fetched ISBN metadata
                        current_metadata['isbn_metadata_fetched'] = True
                        print(f"✅ ISBN metadata fetch completed for: {new_isbn}")
                    else:
                        print(f"⚠️ No metadata found for ISBN: {new_isbn}")
                        # Still mark as fetched so we don't try again
                        current_metadata['isbn_metadata_fetched'] = True
                        
                except Exception as e:
                    print(f"Enhanced ISBN lookup failed: {e}")
                    # Fallback to simple isbnlib lookup
                    try:
                        import isbnlib
                        if isbnlib.is_isbn13(new_isbn) or isbnlib.is_isbn10(new_isbn):
                            isbn_meta = isbnlib.meta(new_isbn)
                            if isbn_meta:
                                if isbn_meta.get('Title'):
                                    current_metadata['title'] = isbn_meta['Title']
                                if isbn_meta.get('Authors'):
                                    current_metadata['author'] = ', '.join(isbn_meta['Authors'])
                                if isbn_meta.get('Year'):
                                    current_metadata['year'] = int(isbn_meta['Year'])
                                
                                print(f"📚 Fallback lookup found: {isbn_meta.get('Title', 'N/A')}")
                    except Exception as e2:
                        print(f"Fallback ISBN lookup also failed: {e2}")
            
            # If ISSN was added for the first time, try to fetch additional metadata
            if issn_changed:
                try:
                    # Use the enhanced ISSN lookup
                    issn_metadata = extractor.enhanced_issn_lookup(new_issn)
                    
                    if issn_metadata:
                        # Only update fields that haven't been manually edited
                        title_manually_edited = current_metadata.get('title_manually_edited', False)
                        if issn_metadata.get('title') and not title_manually_edited:
                            current_metadata['title'] = issn_metadata['title']
                            print(f"📰 Updated journal title: {issn_metadata['title']}")
                        
                        # Add publisher if available and not set
                        if (issn_metadata.get('publisher') and 
                            not current_metadata.get('publisher')):
                            current_metadata['publisher'] = issn_metadata['publisher']
                            print(f"🏢 Added journal publisher: {issn_metadata['publisher']}")
                        
                        # Add subjects if available
                        if issn_metadata.get('subjects'):
                            current_metadata['subjects'] = issn_metadata['subjects']
                            print(f"🏷️ Added subjects: {issn_metadata['subjects']}")
                        
                        # Mark that we've fetched ISSN metadata
                        current_metadata['issn_metadata_fetched'] = True
                        print(f"✅ ISSN metadata fetch completed for: {new_issn}")
                    else:
                        print(f"⚠️ No metadata found for ISSN: {new_issn}")
                        current_metadata['issn_metadata_fetched'] = True
                        
                except Exception as e:
                    print(f"ISSN lookup failed: {e}")
                    current_metadata['issn_metadata_fetched'] = True
            
            # Check if we need to rename folder/files
            old_folder_name = current_metadata.get('folder_name', book_id)
            new_folder_name = extractor.normalize_filename(current_metadata)
            
            needs_rename = old_folder_name != new_folder_name
            
            if needs_rename:
                # Rename folder and files
                old_path = Path(library_path) / old_folder_name
                new_path = Path(library_path) / new_folder_name
                
                if old_path.exists() and not new_path.exists():
                    old_path.rename(new_path)
                    
                    # Update PDF filename too
                    old_pdf = new_path / f"{old_folder_name}.pdf"
                    new_pdf = new_path / f"{new_folder_name}.pdf"
                    if old_pdf.exists():
                        old_pdf.rename(new_pdf)
                    
                    # Update metadata paths
                    current_metadata.update({
                        'folder_name': new_folder_name,
                        'pdf_filename': f"{new_folder_name}.pdf",
                        'folder_path': str(new_path.relative_to(Path(library_path).parent))
                    })
                    
                    print(f"📁 Renamed: {old_folder_name} → {new_folder_name}")
            
            # Save updated metadata
            metadata_path = Path(library_path) / current_metadata['folder_name'] / "metadata.json"
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(current_metadata, f, indent=2, ensure_ascii=False)
            
            # Update library index
            extractor.library_index["books"][book_id].update({
                "title": current_metadata["title"],
                "author": current_metadata["author"],
                "year": current_metadata["year"],
                "isbn": current_metadata["isbn"],
                "folder_name": current_metadata["folder_name"]
            })
            extractor.save_library_index()
            
            return jsonify(current_metadata)
            
        except Exception as e:
            print(f"Error updating book: {e}")
            return jsonify({"error": str(e)}), 500
    
    @app.route('/api/books/<book_id>', methods=['DELETE'])
    def delete_book(book_id):
        """Delete a book and all its associated files"""
        try:
            from src.metadata_extractor import MetadataExtractor
            extractor = MetadataExtractor(library_path, data_path)
            
            # Check if book exists
            if book_id not in extractor.library_index["books"]:
                return jsonify({"error": "Book not found"}), 404
            
            book_info = extractor.library_index["books"][book_id]
            folder_name = book_info.get("folder_name", book_id)
            book_dir = Path(library_path) / folder_name
            
            # Delete the book folder and all its contents
            if book_dir.exists():
                import shutil
                shutil.rmtree(book_dir)
                print(f"🗑️ Deleted book folder: {folder_name}")
            
            # Remove from library index
            del extractor.library_index["books"][book_id]
            extractor.save_library_index()
            
            print(f"🗑️ Deleted book from library: {book_info.get('title', 'Unknown')}")
            
            return jsonify({
                "success": True,
                "message": f"Book '{book_info.get('title', 'Unknown')}' deleted successfully"
            })
            
        except Exception as e:
            print(f"Error deleting book: {e}")
            return jsonify({"error": str(e)}), 500
    
    @app.route('/api/books/<book_id>/file')
    def serve_book_file(book_id):
        """Serve the PDF file for a book"""
        try:
            from src.metadata_extractor import MetadataExtractor
            extractor = MetadataExtractor(library_path, data_path)
            
            # Check if book exists
            if book_id not in extractor.library_index["books"]:
                return "Book not found", 404
            
            book_info = extractor.library_index["books"][book_id]
            folder_name = book_info.get("folder_name", book_id)
            
            # First try looking in the organized folder structure
            book_dir = Path(library_path) / folder_name
            pdf_files = list(book_dir.glob("*.pdf")) if book_dir.exists() else []
            
            # If not found in folder, look directly in the library path
            if not pdf_files:
                # Try to find the file directly in library_path using the folder_name as filename
                direct_pdf = Path(library_path) / f"{folder_name}.pdf"
                if direct_pdf.exists():
                    book_file = direct_pdf
                    book_dir = Path(library_path)  # Set directory to library root
                else:
                    # Try other ebook formats in library root
                    ebook_files = []
                    for ext in ['.pdf', '.epub', '.mobi', '.azw', '.azw3', '.djvu', '.djv']:
                        potential_file = Path(library_path) / f"{folder_name}{ext}"
                        if potential_file.exists():
                            ebook_files.append(potential_file)
                    
                    if not ebook_files:
                        return "No readable file found for this book", 404
                    
                    # Use the first ebook file found
                    book_file = ebook_files[0]
                    book_dir = Path(library_path)  # Set directory to library root
            else:
                # Use the first PDF file from organized folder
                book_file = pdf_files[0]
            
            # Debug logging
            print(f"📖 Serving file: {book_file}")
            print(f"📁 From directory: {book_dir}")
            print(f"📄 File exists: {book_file.exists()}")
            
            # Serve the file
            return send_from_directory(
                str(book_dir),  # Convert Path to string
                book_file.name,
                as_attachment=False  # Display in browser instead of downloading
            )
            
        except Exception as e:
            print(f"Error serving book file: {e}")
            return f"Error serving file: {str(e)}", 500
    
    @app.route('/api/books/<book_id>/extract-text', methods=['POST'])
    def extract_text_from_book(book_id):
        """Extract text from a book's PDF and save to txt file"""
        try:
            from src.metadata_extractor import MetadataExtractor
            from datetime import datetime
            extractor = MetadataExtractor(library_path, data_path)
            
            # Check if book exists
            if book_id not in extractor.library_index["books"]:
                return jsonify({"error": "Book not found"}), 404
            
            book_info = extractor.library_index["books"][book_id]
            folder_name = book_info.get("folder_name", book_id)
            book_dir = Path(library_path) / folder_name
            
            # Find the PDF file
            pdf_files = list(book_dir.glob("*.pdf")) if book_dir.exists() else []
            
            # If not found in folder, look in library root
            if not pdf_files:
                direct_pdf = Path(library_path) / f"{folder_name}.pdf"
                if direct_pdf.exists():
                    pdf_file = direct_pdf
                    book_dir = Path(library_path)
                else:
                    return jsonify({"error": "No PDF file found for this book"}), 404
            else:
                pdf_file = pdf_files[0]
            
            print(f"🔍 Extracting text from: {pdf_file}")
            
            # Use the dedicated full text extraction method
            result = extractor.extract_full_text(pdf_file, save_to_file=True)
            
            if not result['success']:
                return jsonify({"error": f"Could not extract meaningful text from PDF: {result.get('text', 'Unknown error')}"}), 400
            
            return jsonify({
                "success": True,
                "filename": result['filename'],
                "text_length": result['text_length'],
                "word_count": len(result['text'].split()),
                "method": result['method'],
                "message": f"Text extracted successfully using {result['method']} to {result['filename']}"
            })
            
        except Exception as e:
            print(f"Error extracting text from book {book_id}: {e}")
            return jsonify({"error": f"Text extraction failed: {str(e)}"}), 500
    
    @app.route('/api/books')
    def api_books():
        """API endpoint for book data"""
        generator = StaticGenerator(library_path, data_path)
        library_index = generator.load_library_index()
        return jsonify(library_index.get('books', {}))
    
    @app.route('/api/library-metadata')
    def api_library_metadata():
        """API endpoint for library metadata including contributors and readers"""
        generator = StaticGenerator(library_path, data_path)
        library_index = generator.load_library_index()
        return jsonify(library_index.get('metadata', {}))
    
    @app.route('/api/process-files', methods=['POST'])
    def process_files():
        """Process new/modified files via API"""
        try:
            data = request.get_json()
            contributor = data.get('contributor', 'anonymous')
            
            from src.metadata_extractor import MetadataExtractor
            extractor = MetadataExtractor(library_path, data_path)
            
            # Get files that need processing
            new_files, modified_files = extractor.get_files_needing_scan()
            total_files = len(new_files) + len(modified_files)
            
            if total_files == 0:
                return jsonify({
                    "success": True,
                    "processed_count": 0,
                    "processed_books": [],
                    "message": "No files need processing"
                })
            
            # Process files with progress tracking
            processed_ids = []
            
            # Process new files
            for i, pdf_path in enumerate(new_files):
                print(f"Processing new file {i+1}/{len(new_files)}: {pdf_path.name}")
                book_id = extractor.process_book(pdf_path, contributor)
                if book_id:
                    processed_ids.append(book_id)
            
            # Process modified files
            for i, (pdf_path, existing_book_id) in enumerate(modified_files):
                print(f"Processing modified file {i+1}/{len(modified_files)}: {pdf_path.name}")
                # Remove from index and re-process
                if existing_book_id in extractor.library_index["books"]:
                    del extractor.library_index["books"][existing_book_id]
                
                book_id = extractor.process_book(pdf_path, contributor)
                if book_id:
                    processed_ids.append(book_id)
            
            # Update scan time
            extractor.update_last_scan()
            
            return jsonify({
                "success": True,
                "processed_count": len(processed_ids),
                "processed_books": processed_ids
            })
            
        except Exception as e:
            print(f"Error processing files: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route('/api/process-files-stream')
    def process_files_stream():
        """Process files with real-time progress updates via Server-Sent Events"""
        from flask import Response
        import json
        import time
        import sys
        
        # Get contributor BEFORE creating the generator (while request context is active)
        contributor = request.args.get('contributor', 'anonymous')
        
        def generate_progress():
            try:
                print("📡 Starting SSE stream for file processing")
                
                # Send initial ping to test connection
                yield f"data: {json.dumps({'type': 'ping', 'message': 'Connection established'})}\n\n"
                time.sleep(0.1)  # Small delay to ensure message is sent
                
                print(f"📡 Processing files for contributor: {contributor}")
                
                from src.metadata_extractor import MetadataExtractor
                extractor = MetadataExtractor(library_path, data_path)
                
                # Get files that need processing
                new_files, modified_files = extractor.get_files_needing_scan()
                total_files = len(new_files) + len(modified_files)
                
                print(f"📡 Found {total_files} files to process")
                
                if total_files == 0:
                    yield f"data: {json.dumps({'type': 'complete', 'processed_count': 0, 'message': 'No files need processing'})}\n\n"
                    return
                
                yield f"data: {json.dumps({'type': 'start', 'total_files': total_files})}\n\n"
                time.sleep(0.1)  # Small delay to ensure message is sent
                
                processed_ids = []
                current_file = 0
                
                # Process new files
                for pdf_path in new_files:
                    current_file += 1
                    print(f"📡 Processing file {current_file}/{total_files}: {pdf_path.name}")
                    
                    yield f"data: {json.dumps({'type': 'progress', 'current_file': current_file, 'total_files': total_files, 'filename': pdf_path.name, 'status': 'processing'})}\n\n"
                    sys.stdout.flush()  # Force flush
                    
                    try:
                        book_id = extractor.process_book(pdf_path, contributor)
                        if book_id:
                            processed_ids.append(book_id)
                            yield f"data: {json.dumps({'type': 'file_complete', 'current_file': current_file, 'filename': pdf_path.name, 'book_id': book_id, 'status': 'success'})}\n\n"
                        else:
                            yield f"data: {json.dumps({'type': 'file_complete', 'current_file': current_file, 'filename': pdf_path.name, 'status': 'failed'})}\n\n"
                    except Exception as e:
                        print(f"📡 Error processing {pdf_path.name}: {e}")
                        yield f"data: {json.dumps({'type': 'file_complete', 'current_file': current_file, 'filename': pdf_path.name, 'status': 'error', 'error': str(e)})}\n\n"
                    
                    sys.stdout.flush()  # Force flush after each file
                
                # Process modified files
                for pdf_path, existing_book_id in modified_files:
                    current_file += 1
                    print(f"📡 Reprocessing file {current_file}/{total_files}: {pdf_path.name}")
                    
                    yield f"data: {json.dumps({'type': 'progress', 'current_file': current_file, 'total_files': total_files, 'filename': pdf_path.name, 'status': 'reprocessing'})}\n\n"
                    sys.stdout.flush()  # Force flush
                    
                    try:
                        # Remove from index and re-process
                        if existing_book_id in extractor.library_index["books"]:
                            del extractor.library_index["books"][existing_book_id]
                        
                        book_id = extractor.process_book(pdf_path, contributor)
                        if book_id:
                            processed_ids.append(book_id)
                            yield f"data: {json.dumps({'type': 'file_complete', 'current_file': current_file, 'filename': pdf_path.name, 'book_id': book_id, 'status': 'success'})}\n\n"
                        else:
                            yield f"data: {json.dumps({'type': 'file_complete', 'current_file': current_file, 'filename': pdf_path.name, 'status': 'failed'})}\n\n"
                    except Exception as e:
                        print(f"📡 Error reprocessing {pdf_path.name}: {e}")
                        yield f"data: {json.dumps({'type': 'file_complete', 'current_file': current_file, 'filename': pdf_path.name, 'status': 'error', 'error': str(e)})}\n\n"
                    
                    sys.stdout.flush()  # Force flush after each file
                
                # Update scan time
                extractor.update_last_scan()
                
                print(f"📡 Completed processing {len(processed_ids)} files")
                yield f"data: {json.dumps({'type': 'complete', 'processed_count': len(processed_ids), 'processed_books': processed_ids})}\n\n"
                
            except Exception as e:
                print(f"📡 SSE stream error: {e}")
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
        
        # Set proper headers for SSE
        response = Response(generate_progress(), 
                          content_type='text/event-stream',
                          headers={
                              'Cache-Control': 'no-cache',
                              'Connection': 'keep-alive',
                              'Access-Control-Allow-Origin': '*',
                              'Access-Control-Allow-Headers': 'Cache-Control'
                          })
        
        return response
    
    @app.route('/api/upload-files', methods=['POST'])
    def upload_files():
        """Handle file uploads via drag and drop or file input"""
        try:
            from werkzeug.utils import secure_filename
            import tempfile
            import shutil
            
            contributor = request.form.get('contributor', 'anonymous')
            uploaded_files = request.files.getlist('files')
            
            if not uploaded_files:
                return jsonify({"error": "No files provided"}), 400
            
            # Create temp directory for processing (inside Docker container or local)
            if os.path.exists("/app"):
                # Running in Docker - create temp directory inside container
                temp_base = Path("/app/temp")
            else:
                # Running locally
                temp_base = Path(library_path).parent / "temp"
            
            temp_base.mkdir(exist_ok=True)
            
            saved_files = []
            
            for file in uploaded_files:
                if file and file.filename:
                    filename_lower = file.filename.lower()
                    supported_extensions = ['.pdf', '.epub', '.mobi', '.azw', '.azw3', '.djvu', '.djv']
                    
                    if any(filename_lower.endswith(ext) for ext in supported_extensions):
                        # Secure the filename
                        filename = secure_filename(file.filename)
                        
                        # Save to temp directory (not main books directory)
                        file_path = temp_base / filename
                        
                        # Handle duplicate names by adding a counter
                        counter = 1
                        original_path = file_path
                        while file_path.exists():
                            name_part = original_path.stem
                            suffix = original_path.suffix
                            file_path = temp_base / f"{name_part}_{counter}{suffix}"
                            counter += 1
                        
                        file.save(str(file_path))
                        saved_files.append(file_path)
                        print(f"📁 Uploaded to temp: {file_path.name}")
            
            if not saved_files:
                return jsonify({"error": "No valid ebook files were uploaded"}), 400
            
            # Process the uploaded files from temp directory
            from src.metadata_extractor import MetadataExtractor
            extractor = MetadataExtractor(library_path, data_path)
            
            processed_ids = []
            review_queue_ids = []
            
            for file_path in saved_files:
                # Process book but keep file in temp until approved
                result = extractor.process_book_in_temp(file_path, contributor)
                
                if result and result.get('status') == 'processed':
                    # Book was auto-processed (high confidence)
                    processed_ids.append(result['book_id'])
                    # File was moved from temp to books directory by process_book_in_temp
                elif result and result.get('status') == 'review_queue':
                    # Book was added to review queue, file stays in temp
                    review_queue_ids.append(result['review_id'])
                # If result is None or failed, file stays in temp for manual cleanup
            
            # Update scan time
            extractor.update_last_scan()
            
            return jsonify({
                "success": True,
                "uploaded_count": len(saved_files),
                "processed_count": len(processed_ids),
                "review_queue_count": len(review_queue_ids),
                "processed_books": processed_ids,
                "review_queue_items": review_queue_ids
            })
            
        except Exception as e:
            print(f"Error uploading files: {e}")
            return jsonify({"error": str(e)}), 500
    
    @app.route('/api/ocr-queue')
    def get_ocr_queue():
        """Get OCR queue status and summary"""
        try:
            from src.metadata_extractor import MetadataExtractor
            extractor = MetadataExtractor(library_path, data_path)
            
            queue = extractor.load_ocr_queue()
            summary = extractor.get_ocr_queue_summary()
            
            return jsonify({
                "queue": queue,
                "summary": summary
            })
            
        except Exception as e:
            print(f"Error getting OCR queue: {e}")
            return jsonify({"error": str(e)}), 500
    
    # Removed low confidence books endpoint - replaced with search functionality
    
    @app.route('/api/add-to-ocr-queue', methods=['POST'])
    def add_to_ocr_queue():
        """Add books to OCR queue"""
        try:
            from src.metadata_extractor import MetadataExtractor
            extractor = MetadataExtractor(library_path, data_path)
            
            data = request.get_json()
            book_ids = data.get('book_ids', [])
            reason = data.get('reason', 'manual_request')
            
            added_count = 0
            for book_id in book_ids:
                # Find the book's PDF path
                if book_id in extractor.library_index["books"]:
                    book_info = extractor.library_index["books"][book_id]
                    folder_name = book_info.get("folder_name", book_id)
                    book_dir = Path(library_path) / folder_name
                    
                    # Find PDF file in the book directory
                    pdf_files = list(book_dir.glob("*.pdf"))
                    if pdf_files:
                        pdf_path = pdf_files[0]  # Take the first PDF
                        extractor.add_to_ocr_queue(pdf_path, reason)
                        added_count += 1
            
            return jsonify({
                "success": True,
                "added_count": added_count
            })
            
        except Exception as e:
            print(f"Error adding to OCR queue: {e}")
            return jsonify({"error": str(e)}), 500
    
    @app.route('/api/process-ocr-queue', methods=['POST'])
    def process_ocr_queue():
        """Process OCR queue with progress tracking"""
        try:
            from src.metadata_extractor import MetadataExtractor
            extractor = MetadataExtractor(library_path, data_path)
            
            # Simple progress tracking for now - could be enhanced with WebSockets
            processed_ids = extractor.process_ocr_queue()
            
            return jsonify({
                "success": True,
                "processed_count": len(processed_ids),
                "processed_books": processed_ids
            })
            
        except Exception as e:
            print(f"Error processing OCR queue: {e}")
            return jsonify({"error": str(e)}), 500
    
    @app.route('/ocr-management')
    def ocr_management():
        """OCR queue management page"""
        template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OCR Management - spines</title>
    <style>
/* spines - hypercard inspired book library */

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
    background: #f0f0f0;
    color: #000;
    line-height: 1.4;
    font-size: 12px;
}

.container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 20px;
}

header {
    border: 2px solid black;
    padding: 20px;
    margin-bottom: 20px;
    background: white;
}

.header-content {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.header-left h1 {
    font-size: 24px;
    font-weight: bold;
    margin-bottom: 5px;
}

.header-left .subtitle {
    font-size: 14px;
    color: #666;
}

.nav-links {
    display: flex;
    gap: 15px;
}

.nav-links a {
    color: #0066cc;
    text-decoration: none;
    font-size: 12px;
}

.nav-links a:hover {
    text-decoration: underline;
}

.section {
    border: 2px solid black;
    background: white;
    padding: 20px;
    margin-bottom: 20px;
}

.section-title {
    font-size: 16px;
    font-weight: bold;
    margin-bottom: 15px;
    padding-bottom: 5px;
    border-bottom: 1px solid #ccc;
}

.queue-summary {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 15px;
    margin-bottom: 20px;
}

.stat-card {
    border: 1px solid black;
    padding: 10px;
    text-align: center;
    background: #f8f8f8;
}

.stat-number {
    font-size: 18px;
    font-weight: bold;
    margin-bottom: 3px;
}

.stat-label {
    font-size: 10px;
    color: #666;
    text-transform: uppercase;
}

.stat-card.pending {
    background: #fff3e0;
    border-color: #ff6600;
}

.stat-card.completed {
    background: #e8f5e8;
    border-color: #006600;
}

.stat-card.failed {
    background: #ffe8e8;
    border-color: #cc0000;
}

.controls {
    display: flex;
    gap: 10px;
    margin-bottom: 20px;
    align-items: center;
}

.btn {
    border: 2px solid black;
    background: white;
    padding: 8px 16px;
    font-family: inherit;
    font-size: 12px;
    cursor: pointer;
    font-weight: bold;
}

.btn:hover {
    background: #e0e0e0;
}

.btn.primary {
    background: #0066cc;
    color: white;
    border-color: #0066cc;
}

.btn.primary:hover {
    background: #004499;
}

.btn.danger {
    background: #cc0000;
    color: white;
    border-color: #cc0000;
}

.btn.danger:hover {
    background: #990000;
}

.btn:disabled {
    background: #ccc;
    color: #666;
    border-color: #ccc;
    cursor: not-allowed;
}

.progress-bar {
    border: 1px solid black;
    height: 20px;
    background: white;
    margin: 10px 0;
    display: none;
}

.progress-fill {
    height: 100%;
    background: #0066cc;
    transition: width 0.3s ease;
    width: 0%;
}

.book-list {
    border: 1px solid #ccc;
    background: white;
    max-height: 400px;
    overflow-y: auto;
}

.book-item {
    padding: 10px;
    border-bottom: 1px solid #eee;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.book-item:last-child {
    border-bottom: none;
}

.book-info {
    flex: 1;
}

.book-title {
    font-weight: bold;
    margin-bottom: 2px;
}

.book-meta {
    font-size: 10px;
    color: #666;
}

.confidence-badge {
    padding: 2px 6px;
    font-size: 10px;
    border: 1px solid;
    margin-left: 10px;
}

.confidence-low {
    background: #ffe8e8;
    border-color: #cc0000;
    color: #cc0000;
}

.confidence-medium {
    background: #fff3e0;
    border-color: #ff6600;
    color: #ff6600;
}

.confidence-high {
    background: #e8f5e8;
    border-color: #006600;
    color: #006600;
}

.book-actions {
    display: flex;
    gap: 5px;
}

.book-actions button {
    border: 1px solid black;
    background: white;
    padding: 3px 8px;
    font-family: inherit;
    font-size: 10px;
    cursor: pointer;
}

.book-actions button:hover {
    background: #e0e0e0;
}

.book-actions button.primary {
    background: #0066cc;
    color: white;
    border-color: #0066cc;
}

.book-actions button.primary:hover {
    background: #004499;
}

.status-pending {
    color: #ff6600;
}

.status-completed {
    color: #006600;
}

.status-failed {
    color: #cc0000;
}

.loading {
    opacity: 0.6;
    pointer-events: none;
}

.feedback {
    position: fixed;
    top: 20px;
    right: 20px;
    padding: 10px 15px;
    border: 2px solid;
    background: white;
    font-size: 12px;
    z-index: 1000;
}

.feedback.success {
    border-color: #006600;
    color: #006600;
    background: #e8f5e8;
}

.feedback.error {
    border-color: #cc0000;
    color: #cc0000;
    background: #ffe8e8;
}

.feedback.info {
    border-color: #0066cc;
    color: #0066cc;
    background: #e8f3ff;
}

.search-control {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 15px;
}

.search-control input {
    border: 2px solid black;
    padding: 8px 12px;
    font-family: inherit;
    font-size: 12px;
    flex: 1;
    min-width: 300px;
}

.search-control input:focus {
    outline: none;
    border-color: #0066cc;
}

.bulk-actions {
    padding: 10px;
    background: #f8f8f8;
    border-bottom: 1px solid #ccc;
    display: flex;
    gap: 10px;
    align-items: center;
}

.select-all {
    margin-right: 10px;
}

.selected-count {
    color: #666;
    font-size: 10px;
}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="header-content">
                <div class="header-left">
                    <h1>Text Extraction Management</h1>
                    <div class="subtitle">OCR Processing & Text Extraction Queue</div>
                </div>
                <div class="nav-links">
                    <a href="/" onclick="navigateBackToLibrary(event)">← back to library</a>
                    <a href="/ocr-management">OCR Management</a>
                </div>
            </div>
        </header>

        <!-- OCR Queue Status -->
        <div class="section">
            <div class="section-title">OCR Queue Status</div>
            <div class="queue-summary" id="queueSummary">
                <!-- Will be populated by JavaScript -->
            </div>
            
            <div class="controls">
                <button class="btn primary" id="processQueueBtn" onclick="processOCRQueue()">
                    🔍 Process OCR Queue
                </button>
                <button class="btn primary" onclick="extractTextFromAllBooks()">
                    📄 Extract Text from All Books
                </button>
                <button class="btn" onclick="refreshData()">
                    🔄 Refresh
                </button>
                <div class="progress-bar" id="progressBar">
                    <div class="progress-fill" id="progressFill"></div>
                </div>
                <span id="progressText"></span>
            </div>
        </div>

        <!-- Book Search and Queue -->
        <div class="section">
            <div class="section-title">Search Books for Text Extraction</div>
            <div class="search-control">
                <input type="text" id="bookSearchInput" placeholder="Search by title, author, or contributor..." onchange="searchBooks()" oninput="searchBooks()">
                <button class="btn" onclick="searchBooks()">🔍 Search</button>
                <button class="btn" onclick="loadAllBooks()">📚 Show All Books</button>
            </div>
            
            <div class="book-list" id="searchResults">
                <div class="book-item">Use the search above to find books for text extraction</div>
            </div>
        </div>

        <!-- OCR Queue Items -->
        <div class="section">
            <div class="section-title">OCR Queue Items</div>
            <div class="book-list" id="ocrQueueItems">
                <!-- Will be populated by JavaScript -->
            </div>
        </div>
    </div>

    <script>
        let ocrData = { queue: [], summary: {} };

        // Navigation function for cache busting
        function navigateBackToLibrary(event) {
            event.preventDefault();
            const timestamp = new Date().getTime();
            window.location.href = `/?t=${timestamp}`;
        }
        
        // Load data on page load
        document.addEventListener('DOMContentLoaded', function() {
            refreshData();
            
            // Add keyboard shortcuts
            document.getElementById('bookSearchInput').addEventListener('keydown', function(e) {
                if (e.key === 'Enter') {
                    searchBooks();
                }
            });
        });

        async function refreshData() {
            await loadOCRQueue();
        }

        async function loadOCRQueue() {
            try {
                const response = await fetch('/api/ocr-queue');
                ocrData = await response.json();
                
                renderQueueSummary();
                renderQueueItems();
            } catch (error) {
                showFeedback('Error loading OCR queue: ' + error.message, 'error');
            }
        }

        let allBooks = {};
        let searchResults = [];

        async function loadAllBooks() {
            try {
                const response = await fetch('/api/books');
                allBooks = await response.json();
                
                // Convert to array and show all books
                searchResults = Object.keys(allBooks).map(bookId => ({
                    book_id: bookId,
                    ...allBooks[bookId]
                }));
                
                renderSearchResults();
                showFeedback(`📚 Loaded ${searchResults.length} books`, 'info');
            } catch (error) {
                showFeedback('Error loading books: ' + error.message, 'error');
            }
        }

        function searchBooks() {
            const query = document.getElementById('bookSearchInput').value.toLowerCase().trim();
            
            if (!query) {
                document.getElementById('searchResults').innerHTML = '<div class="book-item">Use the search above to find books for text extraction</div>';
                return;
            }
            
            if (Object.keys(allBooks).length === 0) {
                // Load books first if not loaded
                loadAllBooks().then(() => searchBooks());
                return;
            }
            
            // Search through books
            searchResults = Object.keys(allBooks).map(bookId => ({
                book_id: bookId,
                ...allBooks[bookId]
            })).filter(book => {
                const title = (book.title || '').toLowerCase();
                const author = (book.author || '').toLowerCase();
                
                return title.includes(query) || 
                       author.includes(query) || 
                       (book.contributor && book.contributor.some(c => c.toLowerCase().includes(query)));
            });
            
            renderSearchResults();
            showFeedback(`🔍 Found ${searchResults.length} books matching "${query}"`, 'info');
        }

        function renderQueueSummary() {
            const summary = ocrData.summary;
            const summaryEl = document.getElementById('queueSummary');
            
            summaryEl.innerHTML = `
                <div class="stat-card">
                    <div class="stat-number">${summary.total || 0}</div>
                    <div class="stat-label">Total</div>
                </div>
                <div class="stat-card pending">
                    <div class="stat-number">${summary.pending || 0}</div>
                    <div class="stat-label">Pending</div>
                </div>
                <div class="stat-card completed">
                    <div class="stat-number">${summary.completed || 0}</div>
                    <div class="stat-label">Completed</div>
                </div>
                <div class="stat-card failed">
                    <div class="stat-number">${summary.failed || 0}</div>
                    <div class="stat-label">Failed</div>
                </div>
            `;

            // Enable/disable process button
            const processBtn = document.getElementById('processQueueBtn');
            processBtn.disabled = (summary.pending || 0) === 0;
        }

        function renderSearchResults() {
            const container = document.getElementById('searchResults');
            
            if (searchResults.length === 0) {
                container.innerHTML = '<div class="book-item">No books found matching your search.</div>';
                return;
            }

            const bulkActions = `
                <div class="bulk-actions">
                    <label class="select-all">
                        <input type="checkbox" onchange="toggleSelectAll(this, 'search-results')"> Select All
                    </label>
                    <button class="btn" onclick="addSelectedToOCRQueue('search-results')">
                        Add Selected to OCR Queue
                    </button>
                    <button class="btn primary" onclick="extractTextFromSelected('search-results')">
                        🔍 Extract Text from Selected
                    </button>
                    <span class="selected-count" id="searchresultsSelected">0 selected</span>
                </div>
            `;

            const bookItems = searchResults.map(book => {
                // Check if book already has text extracted
                const hasTextExtracted = book.text_extracted ? '📄' : '';
                
                return `
                    <div class="book-item">
                        <input type="checkbox" class="book-select search-results" data-book-id="${book.book_id}" onchange="updateSelectedCount('search-results')">
                        <div class="book-info">
                            <div class="book-title">${hasTextExtracted} ${book.title}</div>
                            <div class="book-meta">
                                by ${book.author} • 
                                ${book.year || 'Unknown year'} • 
                                ${book.contributor ? `Contributed by: ${Array.isArray(book.contributor) ? book.contributor.join(', ') : book.contributor}` : 'No contributor'}
                            </div>
                        </div>
                        <div class="book-actions">
                            <button onclick="addSingleToOCRQueue('${book.book_id}')">Add to OCR</button>
                            <button onclick="extractTextFromBook('${book.book_id}')" class="primary">🔍 Extract Text</button>
                            <a href="/book/${book.book_id}" target="_blank">
                                <button>View</button>
                            </a>
                        </div>
                    </div>
                `;
            }).join('');

            container.innerHTML = bulkActions + bookItems;
        }

        function renderQueueItems() {
            const queue = ocrData.queue;
            const container = document.getElementById('ocrQueueItems');
            
            if (queue.length === 0) {
                container.innerHTML = '<div class="book-item">OCR queue is empty.</div>';
                return;
            }

            const queueItems = queue.map(item => {
                const statusClass = `status-${item.status}`;
                const statusText = item.status.charAt(0).toUpperCase() + item.status.slice(1);
                
                return `
                    <div class="book-item">
                        <div class="book-info">
                            <div class="book-title">${item.filename}</div>
                            <div class="book-meta">
                                Added: ${new Date(item.added).toLocaleDateString()} • 
                                Reason: ${item.reason} • 
                                <span class="${statusClass}">${statusText}</span>
                                ${item.error ? ` • Error: ${item.error}` : ''}
                                ${item.completed ? ` • Completed: ${new Date(item.completed).toLocaleDateString()}` : ''}
                            </div>
                        </div>
                    </div>
                `;
            }).join('');

            container.innerHTML = queueItems;
        }

        async function processOCRQueue() {
            const processBtn = document.getElementById('processQueueBtn');
            const progressBar = document.getElementById('progressBar');
            const progressFill = document.getElementById('progressFill');
            const progressText = document.getElementById('progressText');

            try {
                processBtn.disabled = true;
                progressBar.style.display = 'block';
                progressText.textContent = 'Processing OCR queue...';

                const response = await fetch('/api/process-ocr-queue', {
                    method: 'POST'
                });

                const result = await response.json();

                if (result.success) {
                    showFeedback(`✅ OCR processing completed! ${result.processed_count} books processed.`, 'success');
                    progressFill.style.width = '100%';
                    progressText.textContent = `Completed: ${result.processed_count} books processed`;
                    
                    // Refresh data
                    setTimeout(refreshData, 1000);
                } else {
                    throw new Error(result.error || 'OCR processing failed');
                }

            } catch (error) {
                showFeedback('Error processing OCR queue: ' + error.message, 'error');
                progressText.textContent = 'Error occurred';
            } finally {
                processBtn.disabled = false;
                setTimeout(() => {
                    progressBar.style.display = 'none';
                    progressFill.style.width = '0%';
                    progressText.textContent = '';
                }, 3000);
            }
        }

        async function addSingleToOCRQueue(bookId) {
            try {
                const response = await fetch('/api/add-to-ocr-queue', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        book_ids: [bookId],
                        reason: 'manual_request'
                    })
                });

                const result = await response.json();
                
                if (result.success) {
                    showFeedback('✅ Book added to OCR queue', 'success');
                    refreshData();
                } else {
                    throw new Error(result.error);
                }
            } catch (error) {
                showFeedback('Error adding book to OCR queue: ' + error.message, 'error');
            }
        }

        function toggleSelectAll(checkbox, className) {
            const checkboxes = document.querySelectorAll(`.book-select.${className}`);
            checkboxes.forEach(cb => cb.checked = checkbox.checked);
            updateSelectedCount(className);
        }

        function updateSelectedCount(className) {
            const selected = document.querySelectorAll(`.book-select.${className}:checked`);
            const countElId = className === 'search-results' ? 'searchresultsSelected' : `${className.replace('-', '')}Selected`;
            const countEl = document.getElementById(countElId);
            if (countEl) {
                countEl.textContent = `${selected.length} selected`;
            }
        }

        async function addSelectedToOCRQueue(className) {
            const selected = document.querySelectorAll(`.book-select.${className}:checked`);
            const bookIds = Array.from(selected).map(cb => cb.dataset.bookId);
            
            if (bookIds.length === 0) {
                showFeedback('Please select at least one book', 'error');
                return;
            }

            try {
                const response = await fetch('/api/add-to-ocr-queue', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        book_ids: bookIds,
                        reason: 'bulk_manual_request'
                    })
                });

                const result = await response.json();
                
                if (result.success) {
                    showFeedback(`✅ ${result.added_count} books added to OCR queue`, 'success');
                    refreshData();
                } else {
                    throw new Error(result.error);
                }
            } catch (error) {
                showFeedback('Error adding books to OCR queue: ' + error.message, 'error');
            }
        }

        async function extractTextFromBook(bookId) {
            try {
                showFeedback('🔍 Extracting text...', 'info');
                
                const response = await fetch(`/api/books/${bookId}/extract-text`, {
                    method: 'POST'
                });
                
                const result = await response.json();
                
                if (result.success) {
                    showFeedback(`✅ Text extracted: ${result.text_length} characters saved to ${result.filename}`, 'success');
                } else {
                    throw new Error(result.error);
                }
            } catch (error) {
                showFeedback('❌ Text extraction failed: ' + error.message, 'error');
            }
        }

        async function extractTextFromSelected(className) {
            const selected = document.querySelectorAll(`.book-select.${className}:checked`);
            const bookIds = Array.from(selected).map(cb => cb.dataset.bookId);
            
            if (bookIds.length === 0) {
                showFeedback('Please select at least one book', 'error');
                return;
            }

            let completed = 0;
            let failed = 0;
            
            showFeedback(`🔍 Starting text extraction for ${bookIds.length} books...`, 'info');
            
            // Process books sequentially to avoid overwhelming the server
            for (const bookId of bookIds) {
                try {
                    const response = await fetch(`/api/books/${bookId}/extract-text`, {
                        method: 'POST'
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        completed++;
                        console.log(`✅ Extracted text from book ${bookId}: ${result.text_length} characters`);
                    } else {
                        failed++;
                        console.error(`❌ Failed to extract text from book ${bookId}: ${result.error}`);
                    }
                } catch (error) {
                    failed++;
                    console.error(`❌ Error extracting text from book ${bookId}: ${error.message}`);
                }
            }
            
            showFeedback(`📄 Text extraction complete! ${completed} successful, ${failed} failed`, completed > 0 ? 'success' : 'error');
        }

        async function extractTextFromAllBooks() {
            if (!confirm('This will attempt to extract text from ALL books in your library. This may take a while. Continue?')) {
                return;
            }
            
            try {
                showFeedback('🔍 Starting bulk text extraction...', 'info');
                
                // Get all books first
                const booksResponse = await fetch('/api/books');
                const books = await booksResponse.json();
                const bookIds = Object.keys(books);
                
                if (bookIds.length === 0) {
                    showFeedback('No books found in library', 'error');
                    return;
                }
                
                let completed = 0;
                let failed = 0;
                let skipped = 0;
                
                // Process books with progress updates
                for (let i = 0; i < bookIds.length; i++) {
                    const bookId = bookIds[i];
                    const book = books[bookId];
                    
                    try {
                        const response = await fetch(`/api/books/${bookId}/extract-text`, {
                            method: 'POST'
                        });
                        
                        const result = await response.json();
                        
                        if (result.success) {
                            completed++;
                        } else {
                            if (result.error.includes('No PDF file found')) {
                                skipped++;
                            } else {
                                failed++;
                            }
                        }
                        
                        // Update progress
                        if ((i + 1) % 5 === 0) {
                            showFeedback(`📄 Progress: ${i + 1}/${bookIds.length} books processed (${completed} successful)`, 'info');
                        }
                        
                    } catch (error) {
                        failed++;
                    }
                }
                
                showFeedback(`🎉 Bulk text extraction complete! ${completed} successful, ${failed} failed, ${skipped} skipped (no PDF)`, 'success');
                
            } catch (error) {
                showFeedback('❌ Bulk extraction failed: ' + error.message, 'error');
            }
        }

        function showFeedback(message, type) {
            const feedback = document.createElement('div');
            feedback.className = `feedback ${type}`;
            feedback.textContent = message;
            
            document.body.appendChild(feedback);
            
            setTimeout(() => {
                if (feedback.parentNode) {
                    feedback.parentNode.removeChild(feedback);
                }
            }, 5000);
        }
    </script>
</body>
</html>"""
        
        return render_template_string(template)

    @app.route('/api/review-queue')
    def get_review_queue():
        """Get review queue status and items"""
        try:
            from src.metadata_extractor import MetadataExtractor
            extractor = MetadataExtractor(library_path, data_path)
            
            queue = extractor.load_review_queue()
            summary = extractor.get_review_queue_summary()
            
            return jsonify({
                "queue": queue,
                "summary": summary
            })
            
        except Exception as e:
            print(f"Error getting review queue: {e}")
            return jsonify({"error": str(e)}), 500
    
    @app.route('/api/review-queue/<review_id>/approve', methods=['POST'])
    def approve_review_item(review_id):
        """Approve and process a review queue item with corrected metadata"""
        try:
            from src.metadata_extractor import MetadataExtractor
            extractor = MetadataExtractor(library_path, data_path)
            
            data = request.get_json()
            updated_metadata = data.get('metadata', {})
            contributor = data.get('contributor', 'anonymous')
            copy_action = data.get('copy_action', 'auto')  # 'auto', 'separate_copy', 'add_to_existing'
            
            # Store the copy action preference in metadata for processing
            updated_metadata['_copy_action'] = copy_action
            
            book_id = extractor.approve_from_review_queue(review_id, updated_metadata, contributor)
            
            if book_id:
                return jsonify({
                    "success": True,
                    "book_id": book_id,
                    "message": "Book processed successfully"
                })
            else:
                return jsonify({"error": "Failed to process book"}), 500
            
        except Exception as e:
            print(f"Error approving review item: {e}")
            return jsonify({"error": str(e)}), 500
    
    @app.route('/api/review-queue/<review_id>/pdf')
    def get_review_pdf(review_id):
        """Serve PDF file for review queue item"""
        try:
            from src.metadata_extractor import MetadataExtractor
            extractor = MetadataExtractor(library_path, data_path)
            
            queue = extractor.load_review_queue()
            item = None
            for entry in queue:
                if entry["id"] == review_id:
                    item = entry
                    break
            
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
            print(f"Error serving review PDF: {e}")
            return "Error serving PDF", 500

    @app.route('/review-queue')
    def review_queue_page():
        """Review queue management page"""
        template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Review Queue - spines</title>
    <style>
/* spines - hypercard inspired review queue */

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
    background: #f0f0f0;
    color: #000;
    line-height: 1.4;
    font-size: 12px;
}

.container {
    max-width: 1400px;
    margin: 0 auto;
    padding: 20px;
}

header {
    border: 2px solid black;
    padding: 20px;
    margin-bottom: 20px;
    background: white;
}

.header-content {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.header-left h1 {
    font-size: 24px;
    font-weight: bold;
    margin-bottom: 5px;
}

.header-left .subtitle {
    font-size: 14px;
    color: #666;
}

.nav-links {
    display: flex;
    gap: 15px;
}

.nav-links a {
    color: #0066cc;
    text-decoration: none;
    font-size: 12px;
}

.nav-links a:hover {
    text-decoration: underline;
}

.queue-summary {
    border: 2px solid black;
    background: white;
    padding: 20px;
    margin-bottom: 20px;
}

.summary-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 15px;
}

.stat-card {
    border: 1px solid black;
    padding: 10px;
    text-align: center;
    background: #f8f8f8;
}

.stat-number {
    font-size: 18px;
    font-weight: bold;
    margin-bottom: 3px;
}

.stat-label {
    font-size: 10px;
    color: #666;
    text-transform: uppercase;
}

.review-items {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(600px, 1fr));
    gap: 20px;
}

.review-item {
    border: 2px solid black;
    background: white;
    padding: 20px;
    position: relative;
}

.review-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 15px;
    padding-bottom: 10px;
    border-bottom: 1px solid #ccc;
}

.review-title {
    font-weight: bold;
    font-size: 14px;
    margin-bottom: 5px;
}

.review-meta {
    font-size: 10px;
    color: #666;
}

.review-actions {
    display: flex;
    gap: 8px;
}

.btn {
    border: 1px solid black;
    background: white;
    padding: 4px 8px;
    font-family: inherit;
    font-size: 10px;
    cursor: pointer;
}

.btn:hover {
    background: #f0f0f0;
}

.btn.primary {
    background: #0066cc;
    color: white;
    border-color: #0066cc;
}

.metadata-editor {
    display: grid;
    grid-template-columns: 80px 1fr;
    gap: 8px 15px;
    margin-bottom: 15px;
}

.metadata-label {
    font-weight: bold;
    font-size: 11px;
}

.metadata-input {
    border: 1px solid #ccc;
    padding: 4px 6px;
    font-family: inherit;
    font-size: 11px;
    width: 100%;
}

.metadata-input:focus {
    border-color: #0066cc;
    outline: none;
}

.pdf-preview {
    width: 100%;
    height: 400px;
    border: 1px solid #ccc;
    margin-bottom: 15px;
}

.process-controls {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-top: 15px;
    border-top: 1px solid #ccc;
}

.contributor-input {
    border: 1px solid black;
    padding: 4px 8px;
    font-family: inherit;
    font-size: 11px;
    width: 120px;
}

.process-btn {
    border: 2px solid #006600;
    background: #006600;
    color: white;
    padding: 8px 16px;
    font-family: inherit;
    font-size: 12px;
    cursor: pointer;
    font-weight: bold;
}

.process-btn:hover {
    background: #004400;
}

.process-btn:disabled {
    background: #ccc;
    border-color: #ccc;
    cursor: not-allowed;
}

.action-buttons {
    display: flex;
    gap: 10px;
    align-items: center;
}

.reject-btn {
    border: 2px solid #cc0000;
    background: white;
    color: #cc0000;
    padding: 8px 16px;
    font-family: inherit;
    font-size: 12px;
    cursor: pointer;
    font-weight: bold;
}

.reject-btn:hover {
    background: #cc0000;
    color: white;
}

.reject-btn:disabled {
    background: #ccc;
    border-color: #ccc;
    color: #666;
    cursor: not-allowed;
}

.loading {
    opacity: 0.6;
    pointer-events: none;
}

.feedback {
    position: fixed;
    top: 20px;
    right: 20px;
    padding: 10px 15px;
    border: 2px solid;
    background: white;
    font-size: 12px;
    z-index: 1000;
}

.feedback.success {
    border-color: #006600;
    color: #006600;
    background: #e8f5e8;
}

.feedback.error {
    border-color: #cc0000;
    color: #cc0000;
    background: #ffe8e8;
}

.empty-state {
    border: 2px solid black;
    background: white;
    padding: 40px;
    text-align: center;
}

.empty-state h2 {
    margin-bottom: 10px;
}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="header-content">
                <div class="header-left">
                    <h1>review queue</h1>
                    <div class="subtitle">manual review for uncertain metadata</div>
                </div>
                <div class="nav-links">
                    <a href="/" onclick="navigateBackToLibrary(event)">← back to library</a>
                    <a href="/ocr-management">ocr queue</a>
                </div>
            </div>
        </header>
        
        <div class="queue-summary">
            <div class="summary-grid" id="summaryGrid">
                <!-- Will be populated by JavaScript -->
            </div>
        </div>
        
        <div class="review-items" id="reviewItems">
            <!-- Will be populated by JavaScript -->
        </div>
        
        <div class="empty-state" id="emptyState" style="display: none;">
            <h2>no items need review</h2>
            <p>All books are either processed automatically or in the OCR queue.</p>
        </div>
    </div>
    
    <script>
        let reviewQueue = [];
        
        // Navigation function for cache busting
        function navigateBackToLibrary(event) {
            event.preventDefault();
            const timestamp = new Date().getTime();
            window.location.href = `/?t=${timestamp}`;
        }
        
        async function loadReviewQueue() {
            try {
                const response = await fetch('/api/review-queue');
                if (response.ok) {
                    const data = await response.json();
                    reviewQueue = data.queue;
                    displaySummary(data.summary);
                    displayReviewItems(data.queue);
                } else {
                    showFeedback('Failed to load review queue', 'error');
                }
            } catch (error) {
                showFeedback(`Network error: ${error.message}`, 'error');
            }
        }
        
        function displaySummary(summary) {
            const grid = document.getElementById('summaryGrid');
            grid.innerHTML = `
                <div class="stat-card">
                    <div class="stat-number">${summary.total}</div>
                    <div class="stat-label">total items</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">${summary.pending_review}</div>
                    <div class="stat-label">pending review</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">${summary.file_missing}</div>
                    <div class="stat-label">missing files</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">${summary.processing_failed}</div>
                    <div class="stat-label">failed</div>
                </div>
            `;
        }
        
        function displayReviewItems(queue) {
            const container = document.getElementById('reviewItems');
            const emptyState = document.getElementById('emptyState');
            
            const pendingItems = queue.filter(item => item.status === 'pending_review');
            
            if (pendingItems.length === 0) {
                container.style.display = 'none';
                emptyState.style.display = 'block';
                return;
            }
            
            container.style.display = 'grid';
            emptyState.style.display = 'none';
            
            container.innerHTML = pendingItems.map(item => `
                <div class="review-item" id="item-${item.id}">
                    <div class="review-header">
                        <div>
                            <div class="review-title">${item.filename}</div>
                            <div class="review-meta">
                                confidence: ${(item.extraction_confidence * 100).toFixed(0)}% • 
                                method: ${item.extraction_method} • 
                                isbn: ${item.isbn_found ? '✅' : '❌'} • 
                                reason: ${item.reason}
                            </div>
                        </div>
                        <div class="review-actions">
                            <button class="btn" onclick="previewPdf('${item.id}')">📄 preview</button>
                        </div>
                    </div>
                    
                    <iframe class="pdf-preview" id="preview-${item.id}" style="display: none;"></iframe>
                    
                    <div class="metadata-editor" id="editor-${item.id}">
                        <div class="metadata-label">media type:</div>
                        <select class="metadata-input" data-field="media_type" onchange="updateReviewFields('${item.id}')">
                            <option value="book" ${(item.extracted_metadata.media_type || 'book') === 'book' ? 'selected' : ''}>book</option>
                            <option value="web" ${(item.extracted_metadata.media_type || 'book') === 'web' ? 'selected' : ''}>web</option>
                            <option value="unknown" ${(item.extracted_metadata.media_type || 'book') === 'unknown' ? 'selected' : ''}>unknown</option>
                        </select>
                        
                        <div class="metadata-label">title:</div>
                        <input type="text" class="metadata-input" data-field="title" value="${item.extracted_metadata.title || ''}" />
                        
                        <div class="metadata-label">author:</div>
                        <input type="text" class="metadata-input" data-field="author" value="${item.extracted_metadata.author || ''}" />
                        
                        <div class="metadata-label">year:</div>
                        <input type="number" class="metadata-input" data-field="year" value="${item.extracted_metadata.year || ''}" />
                        
                        <!-- ISBN for books -->
                        <div class="metadata-label isbn-field">isbn:</div>
                        <div class="isbn-field" style="display: flex; gap: 5px; align-items: center;">
                            <input type="text" class="metadata-input" data-field="isbn" value="${item.extracted_metadata.isbn || ''}" 
                                   onkeypress="if(event.key==='Enter') recheckIsbn('${item.id}')" />
                            <button class="btn" onclick="recheckIsbn('${item.id}')" title="Recheck ISBN">🔍</button>
                        </div>
                        
                        <!-- URL for web resources -->
                        <div class="metadata-label url-field" style="display: none;">url:</div>
                        <input type="url" class="metadata-input url-field" data-field="url" value="${item.extracted_metadata.url || ''}" style="display: none;" />
                    </div>
                    
                                         <div class="process-controls">
                         <div>
                             <label>contributor:</label>
                             <input type="text" class="contributor-input" value="anonymous" />
                         </div>
                         <div class="action-buttons">
                             <button class="reject-btn" onclick="rejectItem('${item.id}')">
                                 🗑️ reject
                             </button>
                             <button class="process-btn" onclick="approveItem('${item.id}')">
                                 ✅ approve & process
                             </button>
                         </div>
                     </div>
                </div>
            `).join('');
            
            // Update fields for each item based on current media type
            pendingItems.forEach(item => {
                updateReviewFields(item.id);
            });
            
            // Auto-populate contributor fields with saved name after DOM is ready
            setTimeout(populateContributorFields, 200);
        }
        
        function updateReviewFields(itemId) {
            const editor = document.getElementById(`editor-${itemId}`);
            const mediaTypeSelect = editor.querySelector('[data-field="media_type"]');
            const mediaType = mediaTypeSelect.value;
            
            // Hide all contextual fields first
            editor.querySelectorAll('.url-field').forEach(el => {
                el.style.display = 'none';
            });
            
            // Show relevant fields based on media type
            if (mediaType === 'web') {
                editor.querySelectorAll('.url-field').forEach(el => {
                    el.style.display = '';
                });
            }
            
            // Show ISBN for most types except web
            const isbnFields = editor.querySelectorAll('.isbn-field');
            if (mediaType === 'web') {
                isbnFields.forEach(el => el.style.display = 'none');
            } else {
                isbnFields.forEach(el => el.style.display = '');
            }
        }
        
        function populateContributorFields() {
            const savedContributor = localStorage.getItem('spines_contributor');
            if (savedContributor && savedContributor.trim()) {
                const contributorInputs = document.querySelectorAll('.contributor-input');
                contributorInputs.forEach(input => {
                    if (input.value.trim() === 'anonymous') {
                        input.value = savedContributor;
                    }
                });
            }
        }
        
        function previewPdf(reviewId) {
            const preview = document.getElementById(`preview-${reviewId}`);
            if (preview.style.display === 'none') {
                preview.src = `/api/review-queue/${reviewId}/pdf`;
                preview.style.display = 'block';
            } else {
                preview.style.display = 'none';
            }
        }
        
                 async function approveItem(reviewId) {
             const itemElement = document.getElementById(`item-${reviewId}`);
             const inputs = itemElement.querySelectorAll('.metadata-input');
             const contributorInput = itemElement.querySelector('.contributor-input');
             
             // Collect metadata from all inputs
             const metadata = {};
             console.log('Collecting metadata for approval...');
             
             inputs.forEach(input => {
                 const field = input.dataset.field;
                 if (field) {
                     // Always collect core fields, only check visibility for contextual fields
                     const coreFields = ['media_type', 'title', 'author', 'year', 'isbn', 'url'];
                     const isVisible = input.offsetParent !== null;
                     const isCore = coreFields.includes(field);
                     
                     if (isCore || isVisible) {
                         let value = input.value.trim();
                         
                         if (field === 'year' && value) {
                             value = parseInt(value) || null;
                         }
                         
                         metadata[field] = value || null;
                         console.log(`Collected ${field}: ${value}`);
                     }
                 }
             });
             
             console.log('Final metadata to submit:', metadata);
             
             const contributor = contributorInput.value.trim() || 'anonymous';
             
             // Check for similar books first
             try {
                 itemElement.classList.add('loading');
                 
                 const similarResponse = await fetch(`/api/review-queue/${reviewId}/similar-books`);
                 let copyAction = 'auto';
                 
                 if (similarResponse.ok) {
                     const similarData = await similarResponse.json();
                     
                     if (similarData.has_matches) {
                         // Show copy options dialog
                         copyAction = await showCopyOptionsDialog(similarData.similar_books, contributor);
                         if (!copyAction) {
                             // User cancelled
                             itemElement.classList.remove('loading');
                             return;
                         }
                     }
                 }
                 
                 // Proceed with approval
                 const response = await fetch(`/api/review-queue/${reviewId}/approve`, {
                     method: 'POST',
                     headers: {
                         'Content-Type': 'application/json'
                     },
                     body: JSON.stringify({
                         metadata: metadata,
                         contributor: contributor,
                         copy_action: copyAction
                     })
                 });
                 
                 if (response.ok) {
                     const result = await response.json();
                     showFeedback(`✅ ${result.message}`, 'success');
                     
                     // Mark that metadata has been updated (for cache invalidation)
                     localStorage.setItem('spines_metadata_updated', 'true');
                     
                     // Remove item from display
                     itemElement.remove();
                     
                     // Reload queue to update summary
                     setTimeout(() => {
                         loadReviewQueue();
                     }, 1000);
                 } else {
                     const error = await response.json();
                     showFeedback(`❌ ${error.error}`, 'error');
                 }
             } catch (error) {
                 showFeedback(`❌ Network error: ${error.message}`, 'error');
             } finally {
                 itemElement.classList.remove('loading');
             }
         }
         
         async function showCopyOptionsDialog(similarBooks, contributor) {
             return new Promise((resolve) => {
                 // Create modal dialog
                 const modal = document.createElement('div');
                 modal.style.cssText = `
                     position: fixed;
                     top: 0;
                     left: 0;
                     width: 100%;
                     height: 100%;
                     background: rgba(0,0,0,0.5);
                     display: flex;
                     align-items: center;
                     justify-content: center;
                     z-index: 1000;
                 `;
                 
                 const dialog = document.createElement('div');
                 dialog.style.cssText = `
                     background: white;
                     border: 2px solid black;
                     padding: 20px;
                     max-width: 600px;
                     max-height: 80vh;
                     overflow-y: auto;
                     font-family: inherit;
                 `;
                 
                 dialog.innerHTML = `
                     <h3 style="margin: 0 0 15px 0;">Similar books found</h3>
                     <p style="margin: 0 0 15px 0; font-size: 12px; color: #666;">
                         This book appears similar to existing books in your library. 
                         Choose how to handle it:
                     </p>
                     
                     <div style="border: 1px solid #ccc; padding: 10px; margin-bottom: 15px; max-height: 200px; overflow-y: auto;">
                         ${similarBooks.map(book => `
                             <div style="padding: 5px 0; border-bottom: 1px solid #eee;">
                                 <strong>${book.title}</strong> by ${book.author} (${book.year || 'unknown year'})
                                 <br><small style="color: #666;">
                                     Contributors: ${book.contributors.join(', ') || 'none'} • 
                                     Confidence: ${(book.confidence * 100).toFixed(0)}% • 
                                     Type: ${book.similarity_type}
                                 </small>
                             </div>
                         `).join('')}
                     </div>
                     
                     <div style="margin-bottom: 20px;">
                         <label style="display: block; margin-bottom: 8px; font-weight: bold;">
                             <input type="radio" name="copyAction" value="separate_copy" checked style="margin-right: 5px;">
                             Create separate copy for "${contributor}"
                         </label>
                         <small style="color: #666; margin-left: 20px; display: block;">
                             Creates a new copy with your annotations/highlights separate from existing copies
                         </small>
                         
                         <label style="display: block; margin: 15px 0 8px 0; font-weight: bold;">
                             <input type="radio" name="copyAction" value="add_to_existing" style="margin-right: 5px;">
                             Add to existing book
                         </label>
                         <small style="color: #666; margin-left: 20px; display: block;">
                             Adds "${contributor}" as a contributor to the most similar existing book
                         </small>
                         
                         <label style="display: block; margin: 15px 0 8px 0; font-weight: bold;">
                             <input type="radio" name="copyAction" value="auto" style="margin-right: 5px;">
                             Auto-decide
                         </label>
                         <small style="color: #666; margin-left: 20px; display: block;">
                             Let the system decide based on contributor differences
                         </small>
                     </div>
                     
                     <div style="display: flex; gap: 10px; justify-content: flex-end;">
                         <button id="cancelBtn" style="border: 1px solid black; background: white; padding: 8px 16px; cursor: pointer;">
                             Cancel
                         </button>
                         <button id="okBtn" style="border: 2px solid #006600; background: #006600; color: white; padding: 8px 16px; cursor: pointer;">
                             Proceed
                         </button>
                     </div>
                 `;
                 
                 modal.appendChild(dialog);
                 document.body.appendChild(modal);
                 
                 // Handle buttons
                 dialog.querySelector('#cancelBtn').onclick = () => {
                     document.body.removeChild(modal);
                     resolve(null); // null = cancelled
                 };
                 
                 dialog.querySelector('#okBtn').onclick = () => {
                     const selectedAction = dialog.querySelector('input[name="copyAction"]:checked').value;
                     document.body.removeChild(modal);
                     resolve(selectedAction);
                 };
                 
                 // Close on background click
                 modal.onclick = (e) => {
                     if (e.target === modal) {
                         document.body.removeChild(modal);
                         resolve(null);
                     }
                 };
             });
         }
         
         async function rejectItem(reviewId) {
             const item = reviewQueue.find(item => item.id === reviewId);
             const filename = item ? item.filename : 'this item';
             
             if (!confirm(`Are you sure you want to reject "${filename}"?\n\nThis will remove it from the queue without adding it to your library.`)) {
                 return;
             }
             
             const itemElement = document.getElementById(`item-${reviewId}`);
             
             try {
                 itemElement.classList.add('loading');
                 
                 const response = await fetch(`/api/review-queue/${reviewId}/reject`, {
                     method: 'POST',
                     headers: {
                         'Content-Type': 'application/json'
                     },
                     body: JSON.stringify({
                         reason: 'user_rejected'
                     })
                 });
                 
                 if (response.ok) {
                     const result = await response.json();
                     showFeedback(`🗑️ ${result.message}`, 'success');
                     
                     // Remove item from display
                     itemElement.remove();
                     
                     // Reload queue to update summary
                     setTimeout(() => {
                         loadReviewQueue();
                     }, 1000);
                 } else {
                     const error = await response.json();
                     showFeedback(`❌ ${error.error}`, 'error');
                 }
             } catch (error) {
                 showFeedback(`❌ Network error: ${error.message}`, 'error');
             } finally {
                 itemElement.classList.remove('loading');
             }
         }
        
        async function recheckIsbn(itemId) {
            const editor = document.getElementById(`editor-${itemId}`);
            const isbnInput = editor.querySelector('[data-field="isbn"]');
            const isbn = isbnInput.value.trim();
            
            if (!isbn) {
                showFeedback('Please enter an ISBN first', 'error');
                return;
            }
            
            const recheckBtn = editor.querySelector('button[onclick*="recheckIsbn"]');
            const originalText = recheckBtn.innerHTML;
            
            try {
                recheckBtn.innerHTML = '⏳';
                recheckBtn.disabled = true;
                
                const response = await fetch('/api/isbn-lookup', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ isbn: isbn })
                });
                
                if (response.ok) {
                    const data = await response.json();
                    
                    if (data.found) {
                        // Update form fields with ISBN data
                        const titleInput = editor.querySelector('[data-field="title"]');
                        const authorInput = editor.querySelector('[data-field="author"]');
                        const yearInput = editor.querySelector('[data-field="year"]');
                        
                        if (data.metadata.title && titleInput) {
                            titleInput.value = data.metadata.title;
                        }
                        if (data.metadata.author && authorInput) {
                            authorInput.value = data.metadata.author;
                        }
                        if (data.metadata.year && yearInput) {
                            yearInput.value = data.metadata.year;
                        }
                        
                        showFeedback(`✅ Updated metadata from ISBN: ${data.metadata.title}`, 'success');
                    } else {
                        showFeedback('📚 No metadata found for this ISBN', 'info');
                    }
                } else {
                    const error = await response.json();
                    showFeedback(`❌ ISBN lookup failed: ${error.error}`, 'error');
                }
            } catch (error) {
                showFeedback(`❌ Network error: ${error.message}`, 'error');
            } finally {
                recheckBtn.innerHTML = originalText;
                recheckBtn.disabled = false;
            }
        }
        
        function showFeedback(message, type) {
            const feedback = document.createElement('div');
            feedback.className = `feedback ${type}`;
            feedback.textContent = message;
            
            document.body.appendChild(feedback);
            
            setTimeout(() => {
                if (feedback.parentNode) {
                    feedback.parentNode.removeChild(feedback);
                }
            }, 3000);
        }
        

        
        // Load queue on page load
        loadReviewQueue();
    </script>
</body>
</html>"""
        
        return render_template_string(template)

    @app.route('/api/review-queue/<review_id>/similar-books', methods=['GET'])
    def get_similar_books_for_review(review_id):
        """Get similar books for a review queue item to show copy options"""
        try:
            from src.metadata_extractor import MetadataExtractor
            extractor = MetadataExtractor(library_path, data_path)
            
            queue = extractor.load_review_queue()
            item = None
            for entry in queue:
                if entry["id"] == review_id:
                    item = entry
                    break
            
            if not item:
                return jsonify({"error": "Review item not found"}), 404
            
            # Find similar books using the extracted metadata
            similar_books = extractor.find_similar_books(item["extracted_metadata"])
            
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
            
            return jsonify({
                "similar_books": similar_data,
                "has_matches": len(similar_data) > 0
            })
            
        except Exception as e:
            print(f"Error finding similar books: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route('/api/review-queue/<review_id>/reject', methods=['POST'])
    def reject_review_item(review_id):
        """Reject and discard a review queue item without processing"""
        try:
            from src.metadata_extractor import MetadataExtractor
            extractor = MetadataExtractor(library_path, data_path)
            
            data = request.get_json() or {}
            reason = data.get('reason', 'user_rejected')
            
            success = extractor.reject_from_review_queue(review_id, reason)
            
            if success:
                return jsonify({
                    "success": True,
                    "message": "Item rejected and removed from queue"
                })
            else:
                return jsonify({"error": "Review item not found"}), 404
            
        except Exception as e:
            print(f"Error rejecting review item: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route('/api/cleanup-temp', methods=['POST'])
    def cleanup_temp_files():
        """Clean up orphaned temp files"""
        try:
            from src.metadata_extractor import MetadataExtractor
            extractor = MetadataExtractor(library_path, data_path)
            
            result = extractor.cleanup_temp_files()
            
            return jsonify({
                "success": True,
                "cleaned": result["cleaned"],
                "errors": result["errors"]
            })
            
        except Exception as e:
            print(f"Error cleaning up temp files: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route('/api/isbn-lookup', methods=['POST'])
    def isbn_lookup():
        """Look up metadata for an ISBN"""
        try:
            from src.metadata_extractor import MetadataExtractor
            extractor = MetadataExtractor(library_path, data_path)
            
            data = request.get_json()
            isbn = data.get('isbn', '').strip()
            
            if not isbn:
                return jsonify({"error": "ISBN is required"}), 400
            
            # Use the existing enhanced ISBN lookup method
            isbn_metadata = extractor.enhanced_isbn_lookup(isbn)
            
            if isbn_metadata and isbn_metadata.get('title'):
                return jsonify({
                    "found": True,
                    "metadata": {
                        "title": isbn_metadata.get('title'),
                        "author": isbn_metadata.get('author'),
                        "year": isbn_metadata.get('year'),
                        "publisher": isbn_metadata.get('publisher'),
                        "isbn": isbn
                    }
                })
            else:
                return jsonify({
                    "found": False,
                    "message": "No metadata found for this ISBN"
                })
            
        except Exception as e:
            print(f"Error looking up ISBN: {e}")
            return jsonify({"error": str(e)}), 500

    return app 
    return app 