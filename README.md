# spines

*a library service hosted on whisper and hal’s homelab*

 
when couples move in together, sometimes they merge their book shelves. what would it feel like to take our piles of dusty pdfs held hostage in proprietary apps, and made a space where they could be held with more care. 

the software is janky and vibe coded, but it made the difficult task of normalizing file names and gathering metadata extremely fluid

the result is a cleanly organized folder of our books, with library and book level metadata stored in JSON files, all of which can easily migrate to more stable future interfaces. 

right now it is hosted on a tailnet, so only friends who are members of the network can access the site. 

we dream of hosting a webserver feeling more like hosting a guest. serving files like serving cake.

xoxo hwwh

## Quick Start

### 1. Build and start the server

```bash
docker-compose build
docker-compose up
```

Your spines library will be accessible at `http://localhost:8888`

### 2. Add books through the web interface

**Drag & Drop**: Simply drag PDF files directly into your browser window. They'll be processed automatically and added to your library. This creates a folder with a normalized filename for the PDF, which changes in real time as you add metadata like author and ISBN. 

**Manual Review Queue**: After processing, books enter a review queue where you can:
- Verify auto-detected metadata (title, author, year, ISBN)
- Set media type (book, article, zine, etc.)
- Add contributors and tags
- Mark reading status



### 3. Or use the CLI for batch processing

```bash
# Extract metadata from a directory of PDFs
docker exec -it spines-server python3 -m src.cli extract /app/books --contributor="hal"

# Or from another directory (mount it in docker-compose.yml first)
docker exec -it spines-server python3 -m src.cli extract /path/to/pdfs --contributor="whisper"
```

## Current Features

✅ **Web-Based Book Management**
- Drag-and-drop PDF upload directly in browser
- Automatic metadata extraction using PyPDF2 and Calibre
- Manual review queue for metadata verification
- Real-time processing status updates

✅ **Automated Batch Processing**
- ISBN detection with strategic page scanning
- Robust text extraction with PyPDF2 fallback

✅ **Library Interface**
- Real-time search and filtering
- Responsive grid layout with book cards
- Individual book detail pages with full PDF viewing


## CLI Usage 

### Process books from command line
```bash
docker exec -it spines-server python3 -m src.cli extract /app/books --contributor="your_name"
```

### Interactive metadata editor
```bash
docker exec -it spines-server python3 -m src.cli edit
```


### Generate static site
```bash
docker exec -it spines-server python3 -m src.cli generate --output-dir /app/static --title "our library"
```

## Docker Setup

The container uses these volumes:
- `./test_books:/app/books` - Your PDF library
- `spines_data:/app/data` - Metadata and database

To use your own PDF collection, edit `docker-compose.yml`:

```yaml
volumes:
  - /path/to/your/real/books:/app/books:ro  # ro = read-only
  - spines_data:/app/data
```

## Directory Structure

```
/app/
├── books/           # Organized PDF library
│   └── {book_id}/
│       ├── original.pdf
│       ├── metadata.json
│       └── ocr_text.txt      # Full document text
├── temp/            # Processing queue
├── data/
│   └── library.json  # Master index
└── static/           # Generated site assets
```

## Processing Pipeline

1. **Upload**: Drag PDFs into browser or use CLI
2. **Temp Processing**: Files processed in temp directory
3. **Metadata Extraction**: Auto-detect title, author, year, ISBN, media type
4. **Review Queue**: Manual verification and enhancement of metadata
5. **Library Integration**: Clean files moved to organized books directory
6. **Text Extraction**: Full document text extracted for search

## Coming Soon (Phase 2)

- **OCR Highlight Detection**: Identify and preserve highlighted passages
- **Multi-Copy Support**: Handle duplicate books with different contributors
- **Enhanced Export**: Individual book folders with complete metadata
- **Social Features**: Comments, check-out system, collaborative annotations

## Dependencies

The Docker container includes:
- **Calibre** - Core ebook processing
- **Tesseract** - OCR engine (Phase 2)
- **Python 3** with Flask, PyPDF2, isbnlib
- **PDF.js** - In-browser PDF rendering

- Books as objects, not lists
- Fast, direct interactions

---

*spines is software made with love and for love* 
