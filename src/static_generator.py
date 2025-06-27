"""
spines static site generator
Generates a minimal, hypercard-inspired HTML interface
"""

import json
from pathlib import Path
from datetime import datetime
from jinja2 import Template


class StaticGenerator:
    def __init__(self, library_path: str = "./books", data_path: str = "./data"):
        self.library_path = Path(library_path)
        self.data_path = Path(data_path)
        self.library_json_path = self.data_path / "library.json"
    
    def load_library_index(self):
        """Load library index"""
        if self.library_json_path.exists():
            with open(self.library_json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"books": {}}
    
    def load_book_metadata(self, book_id: str):
        """Load full metadata for a specific book"""
        metadata = None
        book_dir = None
        
        # First try to find by book_id (old method)
        book_dir = self.library_path / book_id
        metadata_file = book_dir / "metadata.json"
        
        if metadata_file.exists():
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
        else:
            # If not found, try to find by looking through library index
            library_index = self.load_library_index()
            if book_id in library_index.get('books', {}):
                book_info = library_index['books'][book_id]
                if 'folder_name' in book_info:
                    # New method: use folder_name
                    book_dir = self.library_path / book_info['folder_name']
                    metadata_file = book_dir / "metadata.json"
                    if metadata_file.exists():
                        with open(metadata_file, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
        
        if metadata and book_dir:
            # Check if text has been extracted (look for .txt file)
            folder_name = metadata.get('folder_name', book_id)
            txt_file = book_dir / f"{folder_name}.txt"
            metadata['text_extracted'] = txt_file.exists()
            
            # Also check if metadata indicates text extraction
            if not metadata['text_extracted'] and metadata.get('text_filename'):
                # Check if the specified text file exists
                text_file_path = book_dir / metadata['text_filename']
                metadata['text_extracted'] = text_file_path.exists()
        
        return metadata
    
    def generate_site(self, output_dir: Path, site_title: str = "spines library"):
        """Generate the complete static site"""
        output_dir.mkdir(exist_ok=True, parents=True)
        
        # Load library data
        library_index = self.load_library_index()
        
        # Collect all book metadata
        books = []
        for book_id in library_index.get('books', {}):
            metadata = self.load_book_metadata(book_id)
            if metadata:
                books.append(metadata)
        
        # Sort books by author, then title
        books.sort(key=lambda b: (b.get('author', '').lower(), b.get('title', '').lower()))
        
        # Generate main index
        self.generate_index(output_dir, books, site_title)
        
        # Generate CSS
        self.generate_css(output_dir)
        
        # Generate book detail pages
        for book in books:
            self.generate_book_page(output_dir, book)
    
    def generate_index(self, output_dir: Path, books: list, site_title: str):
        """Generate the main index page"""
        
        template = Template("""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ site_title }}</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <div class="container">
        <header>
            <h1>{{ site_title }}</h1>
            <p class="subtitle">{{ book_count }} books</p>
        </header>
        
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
                 data-tags="{{ book.tags|join(' ')|lower }}"
                 data-read="{{ 'read' if book.read_by else 'unread' }}"
                 data-year="{{ book.year or '0' }}"
                 data-date-added="{{ book.date_added or '1900-01-01' }}"
                 data-pages="{{ book.pages or '0' }}">
                
                <div class="book-spine">
                    <div class="book-title">{{ book.title }}</div>
                    <div class="book-author">{{ book.author }}</div>
                    <div class="book-year">{{ book.year or '' }}</div>
                </div>
                
                <div class="book-meta">
                    {% if book.read_by %}
                    <div class="read-status">read by: {{ book.read_by|join(', ') }}</div>
                    {% endif %}
                    {% if book.tags %}
                    <div class="tags">{{ book.tags|join(', ') }}</div>
                    {% endif %}
                    <div class="pages">{{ book.pages }} pages</div>
                </div>
                
                <a href="book_{{ book.id }}.html" class="book-link">view</a>
            </div>
        {% endfor %}
        </main>
        
        <footer>
            <p>generated {{ generation_time }} by spines</p>
        </footer>
    </div>
    
    <script>
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
        document.getElementById('sortField').addEventListener('change', sortBooks);
        document.getElementById('sortOrder').addEventListener('change', sortBooks);
        
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
        
        document.getElementById('search').addEventListener('input', function(e) {
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
    </script>
</body>
</html>""")
        
        html = template.render(
            site_title=site_title,
            books=books,
            book_count=len(books),
            generation_time=datetime.now().strftime("%Y-%m-%d %H:%M")
        )
        
        with open(output_dir / "index.html", 'w', encoding='utf-8') as f:
            f.write(html)
    
    def generate_css(self, output_dir: Path):
        """Generate hypercard-inspired CSS"""
        
        css = """/* spines - hypercard inspired book library */

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

h1 {
    font-size: 24px;
    font-weight: bold;
    margin-bottom: 5px;
}

.subtitle {
    font-size: 14px;
    color: #666;
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
    flex: 1;
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
    background: white;
    padding: 15px;
    position: relative;
    min-height: 150px;
    display: flex;
    flex-direction: column;
}

.book-spine {
    flex: 1;
    margin-bottom: 10px;
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

.book-meta {
    font-size: 10px;
    color: #666;
    margin-bottom: 10px;
}

.book-meta div {
    margin-bottom: 2px;
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

footer {
    border: 2px solid black;
    padding: 15px;
    background: white;
    text-align: center;
    font-size: 10px;
    color: #666;
}

/* Book detail page styles */
.book-detail {
    border: 2px solid black;
    background: white;
    padding: 20px;
    margin-bottom: 20px;
}

.book-detail h2 {
    font-size: 18px;
    margin-bottom: 10px;
}

.metadata-grid {
    display: grid;
    grid-template-columns: 120px 1fr;
    gap: 10px 20px;
    margin: 20px 0;
}

.metadata-label {
    font-weight: bold;
}

.back-link {
    border: 1px solid black;
    background: white;
    padding: 5px 15px;
    text-decoration: none;
    color: black;
    font-size: 12px;
    display: inline-block;
}

.back-link:hover {
    background: black;
    color: white;
}
"""
        
        with open(output_dir / "style.css", 'w', encoding='utf-8') as f:
            f.write(css)
    
    def generate_book_page(self, output_dir: Path, book: dict):
        """Generate individual book detail page"""
        
        template = Template("""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ book.title }} - spines</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <div class="container">
        <header>
            <a href="index.html" class="back-link">← back to library</a>
        </header>
        
        <div class="book-detail">
            <h2>{{ book.title }}</h2>
            
            <div class="metadata-grid">
                <div class="metadata-label">author:</div>
                <div>{{ book.author }}</div>
                
                {% if book.year %}
                <div class="metadata-label">year:</div>
                <div>{{ book.year }}</div>
                {% endif %}
                
                {% if book.isbn %}
                <div class="metadata-label">isbn:</div>
                <div>{{ book.isbn }}</div>
                {% endif %}
                
                <div class="metadata-label">pages:</div>
                <div>{{ book.pages }}</div>
                
                <div class="metadata-label">file size:</div>
                <div>{{ "%.1f"|format(book.file_size / 1024 / 1024) }} MB</div>
                
                {% if book.contributor %}
                <div class="metadata-label">contributed by:</div>
                <div>{{ book.contributor }}</div>
                {% endif %}
                
                {% if book.read_by %}
                <div class="metadata-label">read by:</div>
                <div>{{ book.read_by|join(', ') }}</div>
                {% endif %}
                
                {% if book.tags %}
                <div class="metadata-label">tags:</div>
                <div>{{ book.tags|join(', ') }}</div>
                {% endif %}
                
                <div class="metadata-label">added:</div>
                <div>{{ book.date_added[:10] }}</div>
            </div>
            
            {% if book.notes %}
            <div class="metadata-grid">
                <div class="metadata-label">notes:</div>
                <div>{{ book.notes }}</div>
            </div>
            {% endif %}
        </div>
        
        <footer>
            <p>generated {{ generation_time }} by spines</p>
        </footer>
    </div>
</body>
</html>""")
        
        html = template.render(
            book=book,
            generation_time=datetime.now().strftime("%Y-%m-%d %H:%M")
        )
        
        filename = f"book_{book['id']}.html"
        with open(output_dir / filename, 'w', encoding='utf-8') as f:
            f.write(html) 