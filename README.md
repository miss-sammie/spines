# spines

*a library service hosted on whisper and hal’s homelab*
![Screenshot 2025-06-28 113947](https://github.com/user-attachments/assets/41e2d73c-e59a-4230-ae39-8edfd3c361ac)

when couples move in together, sometimes they merge their book shelves. what would it feel like to take our piles of dusty pdfs held hostage in proprietary apps, and made a space where they could be held with more care. 

the first version of this software, now at [spines-0.1](https://github.com/miss-sammie/spines-0.1) was extremely janky and vibe coded (like a 6000 line Python file where all Javascript templates are encoded as strings), but it made the difficult task of normalizing file names and gathering metadata extremely fluid. 

the result is a cleanly organized folder of our books, with library and book level metadata stored in JSON files, all of which can easily migrate to more ~~stable~~ expansive future interfaces. 

this is where we started thinking of a practice we call *orange peel software*

we eat the data, and discard the wrapper. if we leave the data better than we found it each time we make a new tool, the software can be ephemeral. 

so, yes, this version is also vibe coded, and also it is much more sensibly architected, with neat separation of concerns and lovely encapsulated components. we look forward to adding more tools to enable study as a form of collective play.  

right now spines it is hosted on a tailnet, so only friends who are members of the network can access the site. 

we dream of hosting a webserver feeling more like hosting a guest. serving files like serving cake.

xoxo hwwh

## Quick Start

### 1. Build and start the server

```bash
docker-compose build
docker-compose up
```

Your spines library will be accessible at `http://localhost:8890`

### 2. Add books through the web interface
![Screenshot 2025-06-28 120122](https://github.com/user-attachments/assets/16227ea9-0b27-4f69-81ed-f1156e1ed9b8)


**Drag & Drop**: Simply drag PDF, EPUB, and other ebook files directly into your browser window. They'll be processed automatically and added to your library.

**Manual Review Queue**: After processing, books enter a review queue where you can:
- Verify auto-detected metadata (title, author, year, ISBN)
- Preview the cover and first few pages
- Add contributors, tags, and notes
- Handle potential duplicates or merge new files as additional copies of existing books.



## Current Features

**Web-Based Book Management**
- Drag-and-drop upload for multiple file types (PDF, EPUB, etc.)
- Automatic metadata extraction using Calibre's `ebook-meta`
- A manual review queue for verifying metadata and handling duplicates.
- Real-time processing status updates via websockets.

**Flexible Library Model**
- **Multi-copy support**: Merge different file formats or editions under a single canonical book record.
- Track contributors for each copy.
- Inline, on-the-fly editing of book metadata directly from the library view.

**Library Interface**
- Real-time search, sorting, and filtering.
- Responsive grid layout with book cards.
- Individual book detail pages with full metadata and file access.


## Docker Setup

The `docker-compose.yml` is set up for local development with hot-reloading.
The container uses these primary volumes:
- `./books:/app/books` - Your ebook library.
- `./data:/app/data` - Metadata and database files.
- `./logs:/app/logs` - Application logs.

To use your own ebook collection, you can place it in the `books` directory, or drag it into the upload window on the main page. Actually, now that I think of it, not super sure what will happen if you just dump your pdfs into the books folder. 

```yaml
volumes:
  # Books library
  - ./books:/app/books:rw
  # Data persistence
  - ./data:/app/data:rw
  - ./logs:/app/logs:rw
  # For development: mount source code for hot reload
  - ./src:/app/src:rw
  - ./static:/app/static:rw
```

## Directory Structure

```
.
├── books/           # Organized ebook library (managed by the application)
│   └── {book_id}/
│       ├── {file_hash}.pdf
│       └── metadata.json
├── data/            # Persistent data files
│   ├── library.json   # Master index of all books
│   └── review.json    # Items awaiting review
├── logs/            # Application logs
├── src/             # Python backend source code (Flask, services, etc.)
├── static/          # Frontend assets (CSS, JS, HTML templates)
├── temp/            # Staging area for uploaded files
├── Dockerfile       # Instructions to build the Docker image
└── docker-compose.yml # Docker service configuration
```

## Processing Pipeline

1. **Upload**: Drag files into the browser.
2. **Temp Processing**: Files are uploaded to a temporary directory.
3. **Metadata Extraction**: Core metadata is extracted using Calibre.
4. **Review Queue**: The file appears in the review queue for manual verification, enhancement, and duplicate handling.
5. **Library Integration**: On approval, the book is moved to the permanent library folder and its metadata is saved.
6. **Text Extraction**: Full text is extracted on demand for search or analysis.

## Core Ideas

- **Multi-Copy Support**: Handle duplicate books by different contributors or in different formats.
- **Enhanced Export**: Create self-contained book folders with metadata.
- **OCR Integration**: Use Tesseract for text extraction from image-based PDFs.
- **Social Features**: Room to grow into comments, check-outs, and collaborative annotations.

## Dependencies

The Docker container includes:
- **Calibre** - Core ebook processing and metadata extraction.
- **Tesseract** - OCR engine.
- **Python 3** with Flask, PyPDF2, isbnlib, and watchdog for hot-reloading.
- **PDF.js** - In-browser PDF rendering.

- Books as objects, not lists
- Fast, direct interactions

---

*spines is software made with love and for love*
