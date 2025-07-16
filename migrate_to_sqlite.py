#!/usr/bin/env python3
"""
Safe Migration Script: JSON to SQLite
Migrates all book data from JSON files to SQLite database with new files parameter
"""
import json
import hashlib
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional
import sys

def calculate_file_hash(file_path: Path) -> str:
    """Calculate SHA256 hash of a file"""
    hash_sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_sha256.update(chunk)
    return hash_sha256.hexdigest()

def discover_book_files(book_dir: Path, book_id: str) -> List[Dict]:
    """Discover all files associated with a book and create file objects"""
    files = []
    supported_exts = ['.pdf', '.epub', '.mobi', '.azw', '.azw3', '.djvu', '.djv', '.txt']
    
    if not book_dir.exists():
        return files
    
    # Look for files in the book directory
    for file_path in book_dir.iterdir():
        if file_path.is_file() and file_path.suffix.lower() in supported_exts:
            file_hash = calculate_file_hash(file_path)
            file_obj = {
                'hash': file_hash,
                'filename': file_path.name,
                'url': f'/api/books/{book_id}/file?filename={file_path.name}',
                'type': file_path.suffix.lower().strip('.'),
                'size': file_path.stat().st_size
            }
            files.append(file_obj)
    
    # Also check for legacy files directly in books root
    books_root = book_dir.parent
    for ext in supported_exts:
        legacy_file = books_root / f"{book_dir.name}{ext}"
        if legacy_file.exists():
            file_hash = calculate_file_hash(legacy_file)
            file_obj = {
                'hash': file_hash,
                'filename': legacy_file.name,
                'url': f'/api/books/{book_id}/file?filename={legacy_file.name}',
                'type': ext.strip('.'),
                'size': legacy_file.stat().st_size
            }
            files.append(file_obj)
    
    return files

def load_library_json(data_path: Path) -> Dict:
    """Load the main library.json file"""
    library_file = data_path / 'library.json'
    if not library_file.exists():
        print(f"❌ Library file not found: {library_file}")
        return {'books': {}}
    
    try:
        with open(library_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error loading library.json: {e}")
        return {'books': {}}

def load_book_metadata(books_path: Path, book_id: str, folder_name: str) -> Optional[Dict]:
    """Load full metadata for a specific book"""
    book_dir = books_path / folder_name
    metadata_file = book_dir / 'metadata.json'
    
    if not metadata_file.exists():
        print(f"⚠️ No metadata file found for {book_id}: {metadata_file}")
        return None
    
    try:
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # Discover and add files
        files = discover_book_files(book_dir, book_id)
        metadata['files'] = files
        
        return metadata
    except Exception as e:
        print(f"❌ Error loading metadata for {book_id}: {e}")
        return None

def create_sqlite_database(db_path: Path):
    """Create SQLite database with proper schema"""
    print(f"🔧 Creating SQLite database at {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create books table with all possible fields from metadata
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS books (
            id TEXT PRIMARY KEY,
            title TEXT,
            author TEXT,
            year INTEGER,
            isbn TEXT,
            publisher TEXT,
            media_type TEXT DEFAULT 'book',
            contributor TEXT,  -- JSON array as text
            read_by TEXT,      -- JSON array as text
            tags TEXT,         -- JSON array as text
            notes TEXT,
            folder_name TEXT,
            date_added TEXT,
            original_filename TEXT,
            file_type TEXT,
            file_size INTEGER,
            pages INTEGER,
            url TEXT,
            extraction_method TEXT,
            extraction_confidence REAL,
            metadata_json TEXT, -- Full JSON for complex fields
            files TEXT,        -- JSON array of file objects with hash and url
            filename TEXT,     -- Legacy field from metadata
            pdf_filename TEXT, -- Legacy field from metadata
            folder_path TEXT,  -- Legacy field from metadata
            text_extracted BOOLEAN,
            text_filename TEXT,
            text_length INTEGER,
            text_extraction_method TEXT,
            contributor_manually_edited BOOLEAN,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create indexes for performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_books_author ON books(author)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_books_title ON books(title)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_books_year ON books(year)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_books_media_type ON books(media_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_books_contributor ON books(contributor)')
    
    conn.commit()
    conn.close()
    print("✅ SQLite database created successfully")

def migrate_books_to_sqlite(data_path: Path, books_path: Path, db_path: Path) -> Dict:
    """Migrate all books from JSON to SQLite"""
    print("🚀 Starting migration from JSON to SQLite...")
    
    # Load library data
    library_data = load_library_json(data_path)
    book_summaries = library_data.get('books', {})
    
    if not book_summaries:
        print("⚠️ No books found in library.json")
        return {'success': False, 'migrated': 0, 'errors': []}
    
    print(f"📚 Found {len(book_summaries)} books to migrate")
    
    # Create database
    create_sqlite_database(db_path)
    
    # Connect to SQLite
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    migrated_count = 0
    errors = []
    
    for book_id, summary in book_summaries.items():
        try:
            folder_name = summary.get('folder_name', book_id)
            
            # Load full metadata
            metadata = load_book_metadata(books_path, book_id, folder_name)
            if not metadata:
                errors.append(f"Could not load metadata for {book_id}")
                continue
            
            # Ensure ID is set
            metadata['id'] = book_id
            
            # Prepare data for SQLite
            allowed_fields = [
                'id', 'title', 'author', 'year', 'isbn', 'publisher', 'media_type',
                'contributor', 'read_by', 'tags', 'notes', 'folder_name', 'date_added',
                'original_filename', 'file_type', 'file_size', 'pages', 'url',
                'extraction_method', 'extraction_confidence', 'metadata_json', 'files',
                'filename', 'pdf_filename', 'folder_path', 'text_extracted',
                'text_filename', 'text_length', 'text_extraction_method',
                'contributor_manually_edited'
            ]
            insert_data = {}
            for key, value in metadata.items():
                if key not in allowed_fields:
                    continue  # Ignore unknown fields like 'issn'
                if key in ['contributor', 'read_by', 'tags', 'files']:
                    insert_data[key] = json.dumps(value, ensure_ascii=False) if value else '[]'
                elif key in ['text_extracted', 'contributor_manually_edited']:
                    insert_data[key] = 1 if value else 0
                else:
                    insert_data[key] = value
            
            # Build INSERT query
            columns = ', '.join(insert_data.keys())
            placeholders = ', '.join(['?' for _ in insert_data])
            query = f"INSERT OR REPLACE INTO books ({columns}) VALUES ({placeholders})"
            
            cursor.execute(query, list(insert_data.values()))
            migrated_count += 1
            
            if migrated_count % 10 == 0:
                print(f"📖 Migrated {migrated_count}/{len(book_summaries)} books...")
                
        except Exception as e:
            error_msg = f"Error migrating {book_id}: {e}"
            print(f"❌ {error_msg}")
            errors.append(error_msg)
    
    conn.commit()
    conn.close()
    
    print(f"✅ Migration completed: {migrated_count} books migrated")
    if errors:
        print(f"⚠️ {len(errors)} errors occurred")
        for error in errors[:5]:  # Show first 5 errors
            print(f"   - {error}")
        if len(errors) > 5:
            print(f"   ... and {len(errors) - 5} more errors")
    
    return {
        'success': migrated_count > 0,
        'migrated': migrated_count,
        'total': len(book_summaries),
        'errors': errors
    }

def verify_migration(data_path: Path, db_path: Path) -> bool:
    """Verify that migration was successful"""
    print("🔍 Verifying migration...")
    
    # Count books in JSON
    library_data = load_library_json(data_path)
    json_count = len(library_data.get('books', {}))
    
    # Count books in SQLite
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM books")
    sqlite_count = cursor.fetchone()[0]
    conn.close()
    
    print(f"📊 JSON books: {json_count}")
    print(f"📊 SQLite books: {sqlite_count}")
    
    if json_count == sqlite_count:
        print("✅ Migration verification successful!")
        return True
    else:
        print("❌ Migration verification failed - counts don't match")
        return False

def main():
    """Main migration function"""
    print("🔧 Safe Migration: JSON to SQLite")
    print("=" * 50)
    
    # Determine paths
    script_dir = Path(__file__).parent
    data_path = script_dir / 'data'
    books_path = script_dir / 'books'
    db_path = data_path / 'library.db'
    
    print(f"📁 Data path: {data_path}")
    print(f"📁 Books path: {books_path}")
    print(f"📁 Database path: {db_path}")
    
    # Check if paths exist
    if not data_path.exists():
        print(f"❌ Data directory not found: {data_path}")
        return False
    
    if not books_path.exists():
        print(f"❌ Books directory not found: {books_path}")
        return False
    
    # Check if database already exists
    if db_path.exists():
        print(f"⚠️ Database already exists: {db_path}")
        response = input("Do you want to overwrite it? (y/N): ")
        if response.lower() != 'y':
            print("Migration cancelled")
            return False
        db_path.unlink()  # Remove existing database
    
    # Perform migration
    result = migrate_books_to_sqlite(data_path, books_path, db_path)
    
    if result['success']:
        # Verify migration
        if verify_migration(data_path, db_path):
            print("\n🎉 Migration completed successfully!")
            print("\n📋 Next steps:")
            print("1. Update BookService to use SQLite:")
            print("   - Set use_sqlite = True in DatabaseService")
            print("2. Test the application")
            print("3. If everything works, you can remove JSON files later")
            print("\n🔄 To rollback:")
            print("   - Set use_sqlite = False in DatabaseService")
            print("   - Delete library.db file")
            return True
        else:
            print("\n❌ Migration verification failed")
            return False
    else:
        print("\n❌ Migration failed")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1) 