"""
Schema migration script for spines
Simplifies complex metadata back to clean, minimal schema
"""

import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List
import re
import isbnlib
from src.metadata_extractor import MediaType


class SchemaMigrator:
    def __init__(self, library_path: str = "./books", data_path: str = "./data"):
        self.library_path = Path(library_path)
        self.data_path = Path(data_path)
        self.library_json_path = self.data_path / "library.json"
        
        # Load library index
        self.library_index = self.load_library_index()
        
    def load_library_index(self) -> Dict:
        """Load existing library index"""
        if self.library_json_path.exists():
            with open(self.library_json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"metadata": {}, "books": {}}
    
    def save_library_index(self):
        """Save updated library index"""
        with open(self.library_json_path, 'w', encoding='utf-8') as f:
            json.dump(self.library_index, f, indent=2, ensure_ascii=False)
    
    def detect_simple_media_type(self, metadata: Dict) -> str:
        """Simple media type detection - just book, web, or unknown"""
        # Has URL but no ISBN = web resource
        if metadata.get("url") and not metadata.get("isbn"):
            return MediaType.WEB.value
        
        # Everything else is a BOOK (including things with ISBN, articles, journals, etc.)
        return MediaType.BOOK.value
    
    def clean_metadata(self, metadata: Dict) -> Dict:
        """Remove complex metadata fields, keeping only essential ones"""
        # Essential fields to keep
        essential_fields = {
            'id', 'title', 'author', 'year', 'isbn', 'original_filename',
            'contributor', 'date_added', 'read_by', 'tags', 'notes',
            'extraction_method', 'extraction_confidence', 'folder_name',
            'filename', 'folder_path', 'pdf_filename', 'file_type', 'pages',
            'publisher', 'related_copies', 'media_type', 'file_size'
        }
        
        # Keep URL only for web resources
        if metadata.get("media_type") == MediaType.WEB.value:
            essential_fields.add('url')
        
        # Create cleaned metadata with only essential fields
        cleaned = {}
        for field in essential_fields:
            if field in metadata:
                cleaned[field] = metadata[field]
        
        return cleaned
    
    def migrate_book_metadata(self, book_id: str, book_info: Dict, dry_run: bool = True) -> bool:
        """Migrate a single book's metadata to simplified schema"""
        try:
            # Get current folder
            folder_name = book_info.get("folder_name", book_id)
            book_dir = self.library_path / folder_name
            
            if not book_dir.exists():
                print(f"⚠️ Skipping {book_id}: folder not found at {book_dir}")
                return False
            
            # Load current metadata
            metadata_file = book_dir / "metadata.json"
            if not metadata_file.exists():
                print(f"⚠️ Skipping {book_id}: no metadata.json found")
                return False
            
            with open(metadata_file, 'r', encoding='utf-8') as f:
                original_metadata = json.load(f)
            
            # Detect simple media type
            media_type = self.detect_simple_media_type(original_metadata)
            
            # Clean the metadata
            cleaned_metadata = self.clean_metadata(original_metadata)
            cleaned_metadata["media_type"] = media_type
            
            # Add missing file_size if not present
            if "file_size" not in cleaned_metadata:
                # Try to calculate from the actual file
                try:
                    pdf_filename = cleaned_metadata.get("pdf_filename") or cleaned_metadata.get("filename")
                    if pdf_filename:
                        file_path = book_dir / pdf_filename
                        if file_path.exists():
                            cleaned_metadata["file_size"] = file_path.stat().st_size
                            print(f"    Added file_size: {cleaned_metadata['file_size']} bytes")
                except Exception as e:
                    print(f"    Could not calculate file_size: {e}")
                    cleaned_metadata["file_size"] = None
            
            # Check if anything actually changed
            complex_fields = [
                'issn', 'journal', 'volume', 'issue', 'venue', 'accessed_date'
            ]
            
            had_complex_fields = any(field in original_metadata for field in complex_fields)
            media_type_changed = original_metadata.get("media_type") != media_type
            
            if not had_complex_fields and not media_type_changed:
                print(f"✅ {book_id}: already clean")
                return True
            
            if dry_run:
                print(f"🧹 Would clean: {folder_name}")
                if had_complex_fields:
                    removed_fields = [f for f in complex_fields if f in original_metadata]
                    print(f"    Remove fields: {', '.join(removed_fields)}")
                if media_type_changed:
                    print(f"    Update media type: {original_metadata.get('media_type', 'none')} → {media_type}")
                return True
            
            # Actually update the metadata
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(cleaned_metadata, f, indent=2, ensure_ascii=False)
            
            print(f"🧹 Cleaned: {folder_name}")
            if had_complex_fields:
                removed_fields = [f for f in complex_fields if f in original_metadata]
                print(f"    Removed fields: {', '.join(removed_fields)}")
            if media_type_changed:
                print(f"    Updated media type: {original_metadata.get('media_type', 'none')} → {media_type}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error cleaning {book_id}: {e}")
            return False
    
    def run_migration(self, dry_run: bool = True) -> Dict:
        """Run the metadata cleanup migration"""
        print(f"🧹 Starting metadata cleanup (dry_run={dry_run})")
        print(f"📚 Found {len(self.library_index['books'])} books to check")
        
        results = {
            "total": len(self.library_index['books']),
            "cleaned": 0,
            "skipped": 0,
            "errors": 0,
            "changes": []
        }
        
        if dry_run:
            print("🔍 DRY RUN - No actual changes will be made")
        
        for book_id, book_info in self.library_index["books"].items():
            folder_name = book_info.get("folder_name", book_id)
            book_dir = self.library_path / folder_name
            
            if not book_dir.exists():
                results["errors"] += 1
                continue
            
            metadata_file = book_dir / "metadata.json"
            if not metadata_file.exists():
                results["errors"] += 1
                continue
            
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                
                # Check what would change
                complex_fields = ['issn', 'journal', 'volume', 'issue', 'venue', 'accessed_date']
                had_complex_fields = any(field in metadata for field in complex_fields)
                
                old_media_type = metadata.get("media_type", "unknown")
                new_media_type = self.detect_simple_media_type(metadata)
                media_type_changed = old_media_type != new_media_type
                
                if had_complex_fields or media_type_changed:
                    if dry_run:
                        change_info = {
                            "book_id": book_id,
                            "folder_name": folder_name,
                            "title": metadata.get("title", "Unknown"),
                            "old_media_type": old_media_type,
                            "new_media_type": new_media_type,
                            "complex_fields_removed": [f for f in complex_fields if f in metadata]
                        }
                        results["changes"].append(change_info)
                    
                    success = self.migrate_book_metadata(book_id, book_info, dry_run)
                    if success:
                        results["cleaned"] += 1
                    else:
                        results["errors"] += 1
                else:
                    results["skipped"] += 1
                    
            except Exception as e:
                print(f"❌ Error processing {book_id}: {e}")
                results["errors"] += 1
        
        if not dry_run and results["cleaned"] > 0:
            # Save updated library index
            self.library_index["metadata"]["last_updated"] = datetime.now().isoformat()
            self.library_index["metadata"]["schema_version"] = "2.0_simplified"
            self.save_library_index()
            
            print(f"✅ Cleanup complete: {results['cleaned']} cleaned, {results['errors']} errors")
        
        return results


def main():
    """Run migration from command line"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Migrate spines library to new schema')
    parser.add_argument('--library-path', default='./books', help='Path to books directory')
    parser.add_argument('--data-path', default='./data', help='Path to data directory')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be changed without making changes')
    parser.add_argument('--force', action='store_true', help='Apply changes (required for actual migration)')
    
    args = parser.parse_args()
    
    if not args.dry_run and not args.force:
        print("❌ Must specify either --dry-run or --force")
        return
    
    migrator = SchemaMigrator(args.library_path, args.data_path)
    results = migrator.run_migration(dry_run=args.dry_run)
    
    print(f"\n📊 Migration Summary:")
    print(f"  Total books: {results['total']}")
    print(f"  Cleaned: {results['cleaned']}")
    print(f"  Skipped: {results['skipped']}")
    print(f"  Errors: {results['errors']}")
    
    if results.get("changes"):
        print(f"\n📋 Proposed changes:")
        for change in results["changes"][:10]:  # Show first 10
            print(f"  {change['folder_name']} ({change['old_media_type']} → {change['new_media_type']})")
        if len(results["changes"]) > 10:
            print(f"  ... and {len(results['changes']) - 10} more")


if __name__ == "__main__":
    main() 