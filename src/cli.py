"""
spines CLI interface
Provides command-line tools for organizing and managing ebook libraries
"""

import click
import os
from pathlib import Path
from src.metadata_extractor import MetadataExtractor
from src.static_generator import StaticGenerator


@click.group()
@click.option('--library-path', default='./books', help='Path to book library')
@click.option('--data-path', default='./data', help='Path to data directory')
@click.pass_context
def cli(ctx, library_path, data_path):
    """spines - a hypercard-inspired book server"""
    ctx.ensure_object(dict)
    ctx.obj['library_path'] = library_path
    ctx.obj['data_path'] = data_path


@cli.command()
@click.argument('source_directory', type=click.Path(exists=True))
@click.option('--contributor', default='unknown', help='Name of person contributing these books')
@click.option('--recursive', '-r', is_flag=True, help='Scan subdirectories recursively')
@click.pass_context
def extract(ctx, source_directory, contributor, recursive):
    """Extract metadata from PDFs in a directory"""
    extractor = MetadataExtractor(
        library_path=ctx.obj['library_path'],
        data_path=ctx.obj['data_path']
    )
    
    source_path = Path(source_directory)
    click.echo(f"Scanning {source_path} for PDFs...")
    
    if recursive:
        pdf_files = list(source_path.rglob("*.pdf"))
    else:
        pdf_files = list(source_path.glob("*.pdf"))
    
    if not pdf_files:
        click.echo("No PDF files found!")
        return
    
    click.echo(f"Found {len(pdf_files)} PDF files")
    
    with click.progressbar(pdf_files, label='Processing books') as bar:
        processed = 0
        for pdf_path in bar:
            book_id = extractor.process_book(pdf_path, contributor)
            if book_id:
                processed += 1
    
    click.echo(f"Processed {processed} books successfully")
    extractor.save_library_index()


@cli.command()
@click.pass_context
def edit(ctx):
    """Interactive metadata editor"""
    extractor = MetadataExtractor(
        library_path=ctx.obj['library_path'],
        data_path=ctx.obj['data_path']
    )
    
    if not extractor.library_index['books']:
        click.echo("No books in library. Run 'extract' first.")
        return
    
    click.echo("=== spines metadata editor ===")
    click.echo("Available commands: list, edit <id>, read <id> <user>, tag <id> <tags>, quit")
    
    while True:
        try:
            command = click.prompt("\nspines> ", type=str).strip().split()
            
            if not command:
                continue
                
            cmd = command[0].lower()
            
            if cmd in ['quit', 'q', 'exit']:
                break
            elif cmd == 'list':
                for book_id, book_info in extractor.library_index['books'].items():
                    click.echo(f"{book_id[:8]}: {book_info['author']} - {book_info['title']} ({book_info.get('year', 'unknown')})")
            elif cmd == 'edit' and len(command) > 1:
                book_id = command[1]
                edit_book_metadata(extractor, book_id)
            elif cmd == 'read' and len(command) > 2:
                book_id = command[1]
                user = command[2]
                mark_as_read(extractor, book_id, user)
            elif cmd == 'tag' and len(command) > 2:
                book_id = command[1]
                tags = command[2:]
                add_tags(extractor, book_id, tags)
            else:
                click.echo("Unknown command. Try: list, edit <id>, read <id> <user>, tag <id> <tags>, quit")
                
        except KeyboardInterrupt:
            break
        except Exception as e:
            click.echo(f"Error: {e}")
    
    extractor.save_library_index()
    click.echo("Goodbye!")


def edit_book_metadata(extractor, book_id):
    """Edit metadata for a specific book"""
    # Find matching book ID (allow partial matches)
    matching_ids = [bid for bid in extractor.library_index['books'].keys() if bid.startswith(book_id)]
    
    if not matching_ids:
        click.echo(f"No book found with ID starting with {book_id}")
        return
    
    if len(matching_ids) > 1:
        click.echo(f"Multiple matches: {', '.join(matching_ids[:5])}")
        return
    
    book_id = matching_ids[0]
    book_dir = extractor.library_path / book_id
    metadata_file = book_dir / "metadata.json"
    
    if not metadata_file.exists():
        click.echo(f"Metadata file not found for {book_id}")
        return
    
    import json
    with open(metadata_file, 'r', encoding='utf-8') as f:
        metadata = json.load(f)
    
    click.echo(f"\nEditing: {metadata['title']}")
    click.echo(f"Current author: {metadata['author']}")
    
    new_title = click.prompt("Title", default=metadata['title'])
    new_author = click.prompt("Author", default=metadata['author'])
    new_year = click.prompt("Year", default=metadata.get('year', ''), type=int, show_default=False)
    
    metadata['title'] = new_title
    metadata['author'] = new_author
    metadata['year'] = new_year if new_year else None
    
    # Save updated metadata
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    # Update library index
    extractor.library_index['books'][book_id].update({
        'title': new_title,
        'author': new_author,
        'year': new_year
    })
    
    click.echo("Metadata updated!")


def mark_as_read(extractor, book_id, user):
    """Mark a book as read by a user"""
    matching_ids = [bid for bid in extractor.library_index['books'].keys() if bid.startswith(book_id)]
    
    if not matching_ids:
        click.echo(f"No book found with ID starting with {book_id}")
        return
    
    book_id = matching_ids[0]
    book_dir = extractor.library_path / book_id
    metadata_file = book_dir / "metadata.json"
    
    import json
    with open(metadata_file, 'r', encoding='utf-8') as f:
        metadata = json.load(f)
    
    if 'read_by' not in metadata:
        metadata['read_by'] = []
    
    if user not in metadata['read_by']:
        metadata['read_by'].append(user)
        
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        click.echo(f"Marked as read by {user}")
    else:
        click.echo(f"Already marked as read by {user}")


def add_tags(extractor, book_id, tags):
    """Add tags to a book"""
    matching_ids = [bid for bid in extractor.library_index['books'].keys() if bid.startswith(book_id)]
    
    if not matching_ids:
        click.echo(f"No book found with ID starting with {book_id}")
        return
    
    book_id = matching_ids[0]
    book_dir = extractor.library_path / book_id
    metadata_file = book_dir / "metadata.json"
    
    import json
    with open(metadata_file, 'r', encoding='utf-8') as f:
        metadata = json.load(f)
    
    if 'tags' not in metadata:
        metadata['tags'] = []
    
    for tag in tags:
        if tag not in metadata['tags']:
            metadata['tags'].append(tag)
    
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    click.echo(f"Added tags: {', '.join(tags)}")


@cli.command()
@click.option('--output-dir', default='./static', help='Output directory for static site')
@click.option('--title', default='spines library', help='Site title')
@click.pass_context
def generate(ctx, output_dir, title):
    """Generate static HTML site"""
    generator = StaticGenerator(
        library_path=ctx.obj['library_path'],
        data_path=ctx.obj['data_path']
    )
    
    output_path = Path(output_dir)
    click.echo(f"Generating static site in {output_path}")
    
    generator.generate_site(output_path, title)
    click.echo("Static site generated!")


@cli.command()
@click.option('--host', default='0.0.0.0', help='Host to bind to')
@click.option('--port', default=8888, help='Port to bind to')
@click.pass_context
def serve(ctx, host, port):
    """Start the web server"""
    from src.web_server import create_app
    
    app = create_app(
        library_path=ctx.obj['library_path'],
        data_path=ctx.obj['data_path']
    )
    
    click.echo(f"Starting spines server on {host}:{port}")
    app.run(host=host, port=port, debug=True)


@cli.command()
@click.option('--dry-run', is_flag=True, help='Show what would be changed without making changes')
@click.option('--force', is_flag=True, help='Apply changes (required for actual migration)')
@click.pass_context
def migrate(ctx, dry_run, force):
    """Migrate library to new filename format and add media type support"""
    if not dry_run and not force:
        click.echo("❌ Must specify either --dry-run or --force")
        return
    
    from src.migrate_schema import SchemaMigrator
    
    migrator = SchemaMigrator(
        library_path=ctx.obj['library_path'],
        data_path=ctx.obj['data_path']
    )
    
    results = migrator.run_migration(dry_run=dry_run)
    
    click.echo(f"\n📊 Migration Summary:")
    click.echo(f"  Total books: {results['total']}")
    click.echo(f"  Cleaned: {results['cleaned']}")
    click.echo(f"  Skipped: {results['skipped']}")
    click.echo(f"  Errors: {results['errors']}")
    
    if results.get("changes") and dry_run:
        click.echo(f"\n📋 Proposed changes:")
        for change in results["changes"][:10]:  # Show first 10
            fields_str = f" (remove: {', '.join(change['complex_fields_removed'])})" if change['complex_fields_removed'] else ""
            media_type_str = f" (type: {change['old_media_type']} → {change['new_media_type']})" if change['old_media_type'] != change['new_media_type'] else ""
            click.echo(f"  {change['folder_name']}: {change['title'][:50]}{fields_str}{media_type_str}")
        if len(results["changes"]) > 10:
            click.echo(f"  ... and {len(results['changes']) - 10} more")
        
        click.echo(f"\n💡 Run with --force to apply these changes")


@cli.command()
@click.option('--force', is_flag=True, help='Apply changes to existing books')
@click.pass_context
def detect_media_types(ctx, force):
    """Detect and update media types for all books using enhanced detection"""
    extractor = MetadataExtractor(
        library_path=ctx.obj['library_path'],
        data_path=ctx.obj['data_path']
    )
    
    if not extractor.library_index['books']:
        click.echo("No books in library. Run 'extract' first.")
        return
    
    click.echo("🔍 Analyzing media types for all books...")
    
    updates = []
    for book_id, book_info in extractor.library_index['books'].items():
        folder_name = book_info.get("folder_name", book_id)
        book_dir = extractor.library_path / folder_name
        metadata_file = book_dir / "metadata.json"
        
        if not metadata_file.exists():
            continue
        
        try:
            import json
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            old_media_type = metadata.get("media_type", "unknown")
            new_media_type = extractor.detect_media_type(metadata)
            
            if old_media_type != new_media_type:
                updates.append({
                    'book_id': book_id,
                    'title': metadata.get('title', 'Unknown'),
                    'old_type': old_media_type,
                    'new_type': new_media_type,
                    'metadata': metadata,
                    'metadata_file': metadata_file
                })
                
        except Exception as e:
            click.echo(f"⚠️ Error processing {book_id}: {e}")
    
    if not updates:
        click.echo("✅ All books already have correct media types!")
        return
    
    click.echo(f"\n📋 Found {len(updates)} books with updated media type classifications:")
    for update in updates:
        click.echo(f"  📚 {update['title'][:50]}: {update['old_type']} → {update['new_type']}")
    
    if not force:
        click.echo(f"\n💡 Run with --force to apply these changes")
        return
    
    # Apply the updates
    updated_count = 0
    for update in updates:
        try:
            # Update metadata
            update['metadata']['media_type'] = update['new_type']
            
            # Add contextual metadata
            update['metadata'] = extractor.add_contextual_metadata(update['metadata'])
            
            # Save updated metadata
            with open(update['metadata_file'], 'w', encoding='utf-8') as f:
                json.dump(update['metadata'], f, indent=2, ensure_ascii=False)
            
            updated_count += 1
            
        except Exception as e:
            click.echo(f"⚠️ Error updating {update['book_id']}: {e}")
    
    click.echo(f"✅ Updated {updated_count} books with new media types!")


@cli.command()
@click.pass_context
def find_duplicates(ctx):
    """Find potential duplicate books in the library"""
    extractor = MetadataExtractor(
        library_path=ctx.obj['library_path'],
        data_path=ctx.obj['data_path']
    )
    
    if not extractor.library_index['books']:
        click.echo("No books in library. Run 'extract' first.")
        return
    
    click.echo("🔍 Scanning for potential duplicate books...")
    
    all_books = []
    duplicates_found = []
    
    # Load all book metadata
    for book_id, book_info in extractor.library_index['books'].items():
        folder_name = book_info.get("folder_name", book_id)
        book_dir = extractor.library_path / folder_name
        metadata_file = book_dir / "metadata.json"
        
        if metadata_file.exists():
            try:
                import json
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                metadata['book_id'] = book_id
                all_books.append(metadata)
            except Exception as e:
                click.echo(f"⚠️ Error loading {book_id}: {e}")
    
    # Check each book for duplicates
    processed_ids = set()
    for book in all_books:
        if book['book_id'] in processed_ids:
            continue
            
        similar_books = extractor.find_similar_books(book)
        if similar_books:
            # Filter out already processed books
            similar_books = [s for s in similar_books if s['book_id'] not in processed_ids]
            
            if similar_books:
                duplicate_group = {
                    'primary': book,
                    'similar': similar_books
                }
                duplicates_found.append(duplicate_group)
                
                # Mark all as processed
                processed_ids.add(book['book_id'])
                for similar in similar_books:
                    processed_ids.add(similar['book_id'])
    
    if not duplicates_found:
        click.echo("✅ No potential duplicates found!")
        return
    
    click.echo(f"\n📚 Found {len(duplicates_found)} potential duplicate groups:")
    
    for i, group in enumerate(duplicates_found, 1):
        click.echo(f"\n{i}. PRIMARY: {group['primary']['title']} by {group['primary']['author']}")
        click.echo(f"   📁 {group['primary']['book_id'][:8]}")
        
        for similar in group['similar']:
            confidence = similar['confidence']
            similarity_type = similar['similarity_type']
            metadata = similar['metadata']
            
            click.echo(f"   🔗 {similarity_type} ({confidence:.2f}): {metadata['title']} by {metadata['author']}")
            click.echo(f"      📁 {similar['book_id'][:8]}")
            
            # Show key differences
            differences = []
            if group['primary'].get('isbn') != metadata.get('isbn'):
                differences.append(f"ISBN: {group['primary'].get('isbn', 'none')} vs {metadata.get('isbn', 'none')}")
            if group['primary'].get('year') != metadata.get('year'):
                differences.append(f"Year: {group['primary'].get('year', 'none')} vs {metadata.get('year', 'none')}")
            if group['primary'].get('publisher') != metadata.get('publisher'):
                differences.append(f"Publisher: {group['primary'].get('publisher', 'none')} vs {metadata.get('publisher', 'none')}")
            
            if differences:
                click.echo(f"      🔸 Differences: {'; '.join(differences)}")


@cli.command()
@click.argument('media_type', type=click.Choice(['book', 'web', 'unknown']))
@click.pass_context
def list_by_type(ctx, media_type):
    """List all books of a specific media type"""
    extractor = MetadataExtractor(
        library_path=ctx.obj['library_path'],
        data_path=ctx.obj['data_path']
    )
    
    if not extractor.library_index['books']:
        click.echo("No books in library. Run 'extract' first.")
        return
    
    click.echo(f"📚 Items classified as '{media_type}':")
    
    count = 0
    for book_id, book_info in extractor.library_index['books'].items():
        folder_name = book_info.get("folder_name", book_id)
        book_dir = extractor.library_path / folder_name
        metadata_file = book_dir / "metadata.json"
        
        if metadata_file.exists():
            try:
                import json
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                
                if metadata.get('media_type') == media_type:
                    count += 1
                    title = metadata.get('title', 'Unknown')
                    author = metadata.get('author', 'Unknown')
                    year = metadata.get('year', 'Unknown')
                    
                    # Show URL for web resources
                    extra_info = []
                    if media_type == 'web' and metadata.get('url'):
                        extra_info.append(f"URL: {metadata['url']}")
                    
                    extra_str = f" ({', '.join(extra_info)})" if extra_info else ""
                    
                    click.echo(f"  📖 {title} by {author} ({year}){extra_str}")
                    
                    # Show related copies if any
                    if metadata.get('related_copies'):
                        for copy in metadata['related_copies'][:2]:  # Show first 2
                            click.echo(f"     🔗 Also: {copy.get('folder_name', 'Unknown')} by {copy.get('contributor', ['unknown'])[0] if copy.get('contributor') else 'unknown'}")
                        
                        if len(metadata['related_copies']) > 2:
                            click.echo(f"     🔗 ... and {len(metadata['related_copies']) - 2} more copies")
                    
            except Exception as e:
                click.echo(f"⚠️ Error loading {book_id}: {e}")
    
    if count == 0:
        click.echo(f"  (No items found with media type '{media_type}')")
    else:
        click.echo(f"\n📊 Total: {count} items")


if __name__ == '__main__':
    cli() 