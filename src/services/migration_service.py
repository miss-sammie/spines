"""
Migration service for importing Spines 1.0 data
"""
import json
import shutil
from pathlib import Path
from datetime import datetime
from utils.logging import get_logger
from services.book_service import BookService

logger = get_logger(__name__)

class MigrationService:
    def __init__(self, config):
        self.config = config
        self.migration_log = []
        self.book_service = BookService(config)
        
    def import_from_v1(self, v1_books_path=None, v1_data_path=None):
        """Import library from Spines 1.0"""
        logger.info("Starting migration from Spines 1.0")
        
        # Use config paths if not provided
        v1_books_path = v1_books_path or self.config.V1_BOOKS_PATH
        v1_data_path = v1_data_path or self.config.V1_DATA_PATH
        
        try:
            # Load v1 data
            v1_data = self._load_v1_data(v1_data_path)
            
            # Migrate books directory
            books_migrated = self._migrate_books_directory(v1_books_path)
            
            # Migrate metadata
            metadata_migrated = self._migrate_metadata(v1_data)
            
            # Validate migration
            self._validate_migration()
            
            logger.info("Migration completed successfully")
            return {
                'success': True,
                'books_migrated': books_migrated,
                'metadata_migrated': metadata_migrated,
                'log': self.migration_log
            }
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'log': self.migration_log
            }
    
    def _load_v1_data(self, v1_data_path):
        """Load v1 library data"""
        v1_data_path = Path(v1_data_path)
        
        # Try migration export first
        export_file = v1_data_path / 'migration-export.json'
        if export_file.exists():
            logger.info(f"Found migration export: {export_file}")
            with open(export_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        # Try direct library file
        library_files = [
            'library.json',
            'spines-metadata-062725',  # Your specific file
            'library-index.json'
        ]
        
        for filename in library_files:
            library_file = v1_data_path / filename
            if library_file.exists():
                logger.info(f"Found library file: {library_file}")
                with open(library_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Wrap in migration format if needed
                    if 'library_metadata' not in data:
                        return {
                            'export_timestamp': datetime.now().isoformat(),
                            'spines_version': '1.0',
                            'library_metadata': data
                        }
                    return data
        
        raise FileNotFoundError(f"No library data found in {v1_data_path}")
    
    def _migrate_books_directory(self, v1_books_path):
        """Copy books directory structure"""
        v1_books = Path(v1_books_path)
        v2_books = Path(self.config.BOOKS_PATH)
        
        if not v1_books.exists():
            logger.warning(f"V1 books directory not found: {v1_books}")
            return 0
        
        logger.info(f"Copying books from {v1_books} to {v2_books}")
        
        # Backup existing v2 books if they exist
        if v2_books.exists() and any(v2_books.iterdir()):
            backup_path = v2_books.parent / f"books-backup-{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.move(str(v2_books), str(backup_path))
            logger.info(f"Backed up existing books to {backup_path}")
        
        # Copy v1 books to v2
        shutil.copytree(str(v1_books), str(v2_books), dirs_exist_ok=True)
        
        # Count migrated books
        book_dirs = [d for d in v2_books.iterdir() if d.is_dir()]
        books_count = len(book_dirs)
        
        self.migration_log.append(f"Copied {books_count} book directories")
        logger.info(f"Migrated {books_count} book directories")
        
        return books_count
    
    def _migrate_metadata(self, v1_data):
        """Convert v1 metadata to v2 format"""
        v1_library = v1_data.get('library_metadata', {})
        
        # Create v2 library structure
        v2_library = {
            'metadata': {
                'version': '2.0',
                'migrated_from': '1.0',
                'migration_date': datetime.now().isoformat(),
                'original_created': v1_library.get('metadata', {}).get('created'),
                'original_version': v1_library.get('metadata', {}).get('version'),
                'total_books': v1_library.get('metadata', {}).get('total_books', 0),
                'library_path': 'books',
                'contributors': v1_library.get('metadata', {}).get('contributors', []),
                'readers': v1_library.get('metadata', {}).get('readers', []),
                'schema_version': '2.0_migrated'
            },
            'books': {}
        }
        
        # Convert individual book metadata
        v1_books = v1_library.get('books', {})
        migrated_count = 0
        
        for book_id, book_data in v1_books.items():
            try:
                v2_library['books'][book_id] = self._convert_book_metadata(book_data)
                migrated_count += 1
            except Exception as e:
                logger.warning(f"Failed to migrate book {book_id}: {e}")
                self.migration_log.append(f"Failed to migrate book {book_id}: {e}")
        
        # Update total count
        v2_library['metadata']['total_books'] = migrated_count
        
        # Save migrated library
        self.book_service.save_library(v2_library)
        
        self.migration_log.append(f"Migrated metadata for {migrated_count} books")
        logger.info(f"Migrated metadata for {migrated_count} books")
        
        return migrated_count
    
    def _convert_book_metadata(self, v1_book):
        """Convert individual book metadata to v2 format"""
        # Keep all existing fields and add migration tracking
        v2_book = dict(v1_book)
        v2_book.update({
            'migrated_from_v1': True,
            'migration_date': datetime.now().isoformat()
        })
        
        # Ensure required fields exist
        if 'id' not in v2_book and 'book_id' in v2_book:
            v2_book['id'] = v2_book['book_id']
        
        return v2_book
    
    def _validate_migration(self):
        """Validate that migration was successful"""
        v2_books_dir = Path(self.config.BOOKS_PATH)
        
        # Check books directory
        if not v2_books_dir.exists():
            raise Exception("Books directory not found after migration")
        
        # Check library metadata
        library = self.book_service.load_library()
        if not library.get('books'):
            logger.warning("No books found in migrated library metadata")
        
        # Count directories vs metadata
        book_dirs = len([d for d in v2_books_dir.iterdir() if d.is_dir()])
        metadata_books = len(library.get('books', {}))
        
        if book_dirs != metadata_books:
            logger.warning(f"Count mismatch: {book_dirs} directories, {metadata_books} metadata entries")
            self.migration_log.append(f"Count mismatch: {book_dirs} directories, {metadata_books} metadata entries")
        else:
            self.migration_log.append(f"Validation successful: {book_dirs} books migrated")
        
        logger.info(f"Migration validation: {book_dirs} directories, {metadata_books} metadata entries")
    
    def get_migration_status(self):
        """Check if migration has been run"""
        library = self.book_service.load_library()
        metadata = library.get('metadata', {})
        
        return {
            'has_migrated': metadata.get('migrated_from') == '1.0',
            'migration_date': metadata.get('migration_date'),
            'original_version': metadata.get('original_version'),
            'total_books': metadata.get('total_books', 0)
        }
    
    def create_migration_export(self, output_path=None):
        """Create a migration export from current v1 data (for backup)"""
        if not output_path:
            output_path = self.config.V1_DATA_PATH / 'migration-export.json'
        
        try:
            # Load current v1 library
            v1_data = self._load_v1_data(self.config.V1_DATA_PATH)
            
            # Create export with metadata
            export_data = {
                'export_timestamp': datetime.now().isoformat(),
                'spines_version': '1.0',
                'migration_target': '2.0',
                'library_metadata': v1_data.get('library_metadata', v1_data)
            }
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, default=str, ensure_ascii=False)
            
            logger.info(f"Migration export created: {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Failed to create migration export: {e}")
            raise 