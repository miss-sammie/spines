"""
Database Service for Spines 2.0
Handles SQLite database operations with safe migration from JSON
"""
import sqlite3
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any
from utils.logging import get_logger

logger = get_logger(__name__)

class DatabaseService:
    def __init__(self, config):
        self.config = config
        self.db_path = config.DATA_PATH / 'library.db'
        self.use_sqlite = False  # Feature flag for safe migration
        
        # Initialize database if it doesn't exist
        if not self.db_path.exists():
            self._create_database()
    
    def _create_database(self):
        """Create SQLite database with proper schema"""
        logger.info(f"Creating SQLite database at {self.db_path}")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create books table
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
        logger.info("SQLite database created successfully")
    
    def _json_to_sqlite_value(self, value: Any) -> str:
        """Convert Python value to SQLite-compatible JSON string"""
        if value is None:
            return None
        if isinstance(value, (list, dict)):
            return json.dumps(value, ensure_ascii=False)
        return str(value)
    
    def _sqlite_to_json_value(self, value: str, field_type: str = 'text') -> Any:
        """Convert SQLite value back to Python object"""
        if value is None:
            return None
        if field_type in ['contributor', 'read_by', 'tags', 'files']:
            try:
                return json.loads(value) if value else []
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSON for {field_type}: {value}")
                return []
        return value
    
    def get_books(self, page: int = 1, limit: Optional[int] = None, search: Optional[str] = None) -> List[Dict]:
        """Get books from SQLite database"""
        if not self.use_sqlite or not self.db_path.exists():
            return []
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        cursor = conn.cursor()
        
        # Build query
        query = "SELECT * FROM books"
        params = []
        
        if search:
            query += " WHERE title LIKE ? OR author LIKE ? OR contributor LIKE ? OR tags LIKE ?"
            search_term = f"%{search}%"
            params.extend([search_term, search_term, search_term, search_term])
        
        # Add ordering
        query += " ORDER BY author COLLATE NOCASE, title COLLATE NOCASE"
        
        # Add pagination
        if limit:
            offset = (page - 1) * limit
            query += f" LIMIT {limit} OFFSET {offset}"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        # Convert to dict format
        books = []
        for row in rows:
            book = dict(row)
            # Convert JSON fields back to Python objects
            book['contributor'] = self._sqlite_to_json_value(book['contributor'], 'contributor')
            book['read_by'] = self._sqlite_to_json_value(book['read_by'], 'read_by')
            book['tags'] = self._sqlite_to_json_value(book['tags'], 'tags')
            book['files'] = self._sqlite_to_json_value(book['files'], 'files')
            books.append(book)
        
        conn.close()
        return books
    
    def get_book(self, book_id: str) -> Optional[Dict]:
        """Get a specific book from SQLite database"""
        if not self.use_sqlite or not self.db_path.exists():
            return None
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM books WHERE id = ?", (book_id,))
        row = cursor.fetchone()
        
        if row:
            book = dict(row)
            # Convert JSON fields back to Python objects
            book['contributor'] = self._sqlite_to_json_value(book['contributor'], 'contributor')
            book['read_by'] = self._sqlite_to_json_value(book['read_by'], 'read_by')
            book['tags'] = self._sqlite_to_json_value(book['tags'], 'tags')
            book['files'] = self._sqlite_to_json_value(book['files'], 'files')
            conn.close()
            return book
        
        conn.close()
        return None
    
    def update_book(self, book_id: str, metadata: Dict) -> bool:
        """Update a book in SQLite database"""
        if not self.use_sqlite or not self.db_path.exists():
            return False
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Prepare update data
        update_data = {}
        for key, value in metadata.items():
            if key in ['contributor', 'read_by', 'tags', 'files']:
                update_data[key] = self._json_to_sqlite_value(value)
            else:
                update_data[key] = value
        
        update_data['updated_at'] = 'CURRENT_TIMESTAMP'
        
        # Build UPDATE query
        set_clause = ', '.join([f"{k} = ?" for k in update_data.keys()])
        query = f"UPDATE books SET {set_clause} WHERE id = ?"
        params = list(update_data.values()) + [book_id]
        
        try:
            cursor.execute(query, params)
            conn.commit()
            success = cursor.rowcount > 0
            conn.close()
            return success
        except Exception as e:
            logger.error(f"Error updating book {book_id}: {e}")
            conn.close()
            return False
    
    def insert_book(self, book_data: Dict) -> bool:
        """Insert a new book into SQLite database"""
        if not self.use_sqlite or not self.db_path.exists():
            return False
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Prepare insert data
        insert_data = {}
        for key, value in book_data.items():
            if key in ['contributor', 'read_by', 'tags', 'files']:
                insert_data[key] = self._json_to_sqlite_value(value)
            else:
                insert_data[key] = value
        
        # Build INSERT query
        columns = ', '.join(insert_data.keys())
        placeholders = ', '.join(['?' for _ in insert_data])
        query = f"INSERT OR REPLACE INTO books ({columns}) VALUES ({placeholders})"
        
        try:
            cursor.execute(query, list(insert_data.values()))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error inserting book {book_data.get('id')}: {e}")
            conn.close()
            return False
    
    def delete_book(self, book_id: str) -> bool:
        """Delete a book from SQLite database"""
        if not self.use_sqlite or not self.db_path.exists():
            return False
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("DELETE FROM books WHERE id = ?", (book_id,))
            conn.commit()
            success = cursor.rowcount > 0
            conn.close()
            return success
        except Exception as e:
            logger.error(f"Error deleting book {book_id}: {e}")
            conn.close()
            return False
    
    def count_books(self) -> int:
        """Count total books in SQLite database"""
        if not self.use_sqlite or not self.db_path.exists():
            return 0
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM books")
        count = cursor.fetchone()[0]
        conn.close()
        
        return count
    
    def enable_sqlite(self):
        """Enable SQLite mode (safe migration feature flag)"""
        self.use_sqlite = True
        logger.info("SQLite mode enabled")
    
    def disable_sqlite(self):
        """Disable SQLite mode (rollback to JSON)"""
        self.use_sqlite = False
        logger.info("SQLite mode disabled, falling back to JSON") 