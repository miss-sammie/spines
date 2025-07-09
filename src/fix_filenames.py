#!/usr/bin/env python3
"""
Fix filename / folder mismatches in a Spines 2.0 library.

For every book in *library.json* the canonical folder name is recomputed from
    Author_Title_Year_ISBN
using the same rules as the ingestion pipeline.  If a book's current
`folder_name` does not match, its folder (and contained files) will be renamed
accordingly together with the paths stored inside *library.json* and the
per-book *metadata.json*.

Run with --dry-run first to preview changes:

    python spines-2.0/src/fix_filenames.py --dry-run

Apply changes:

    python spines-2.0/src/fix_filenames.py --apply
"""

import argparse
import json
import os
import re
from pathlib import Path
from typing import Tuple

SUPPORTED_EXTS = ['.pdf', '.epub', '.mobi', '.azw', '.azw3', '.djvu', '.djv', '.txt']

# ---------------------------------------------------------------------------
# Helpers copied from MetadataExtractor.normalize_filename (kept lightweight)
# ---------------------------------------------------------------------------

def _clean_for_filename(s: str, max_length: int = 50) -> str:
    if not s:
        return 'Unknown'
    cleaned = re.sub(r'[^\w\s\-]', '', s)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    cleaned = cleaned.replace(' ', '_')
    return cleaned[:max_length]

def compute_folder_name(meta: dict) -> str:
    author = _clean_for_filename(str(meta.get('author', 'Unknown_Author')).split(',')[0], 30)
    title  = _clean_for_filename(meta.get('title', 'Unknown_Title'), 40)
    year   = str(meta.get('year', 'Unknown_Year'))
    ident  = meta.get('isbn') or 'no_id'
    return f"{author}_{title}_{year}_{ident}"

# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def rename_single_book(books_root: Path, book_meta: dict, dry_run: bool) -> Tuple[bool, str, str]:
    """Return (changed?, old_folder, new_folder)."""
    old_folder = book_meta.get('folder_name') or book_meta['id']
    new_folder = compute_folder_name(book_meta)

    if old_folder == new_folder:
        return False, old_folder, new_folder

    print(f"* {old_folder} -> {new_folder}{' (dry-run)' if dry_run else ''}")

    if dry_run:
        return True, old_folder, new_folder

    # Ensure target folder unique
    suffix = 1
    target_folder = new_folder
    while (books_root / target_folder).exists():
        target_folder = f"{new_folder}_{suffix}"
        suffix += 1
    if target_folder != new_folder:
        print(f"  ‣ Target folder exists, using {target_folder} instead")
        new_folder = target_folder

    old_dir = books_root / old_folder
    new_dir = books_root / new_folder

    if old_dir.exists():
        old_dir.rename(new_dir)
        # Rename internal files prefixed with old folder name
        for f in new_dir.iterdir():
            if f.is_file() and f.name.startswith(old_folder):
                f.rename(new_dir / f.name.replace(old_folder, new_folder, 1))
    else:
        # Maybe files live directly under library root
        for ext in SUPPORTED_EXTS:
            p = books_root / f"{old_folder}{ext}"
            if p.exists():
                p.rename(books_root / f"{new_folder}{ext}")

    # Update inner metadata.json
    meta_file = new_dir / 'metadata.json'
    if meta_file.exists():
        try:
            meta_data = json.loads(meta_file.read_text(encoding='utf-8'))
            meta_data['folder_name'] = new_folder
            for k in ['filename', 'pdf_filename', 'text_filename']:
                if k in meta_data and meta_data[k]:
                    base, ext = os.path.splitext(meta_data[k])
                    meta_data[k] = f"{new_folder}{ext}"
            meta_file.write_text(json.dumps(meta_data, indent=2, ensure_ascii=False), encoding='utf-8')
        except Exception as e:
            print(f"  ! Could not update inner metadata.json: {e}")

    # Update caller's metadata now (path updated by caller)
    book_meta['folder_name'] = new_folder
    book_meta['path'] = f"books/{new_folder}"

    return True, old_folder, new_folder


def main():
    parser = argparse.ArgumentParser(description="Fix Spines filename inconsistencies")
    parser.add_argument('--library', default='spines-2.0/data/library.json', help='Path to library.json')
    parser.add_argument('--books-path', default='spines-2.0/books', help='Path to books directory')
    parser.add_argument('--apply', action='store_true', help='Perform changes (default: dry run)')
    args = parser.parse_args()

    dry_run = not args.apply
    lib_path = Path(args.library)
    books_root = Path(args.books_path)

    if not lib_path.exists():
        parser.error(f"library.json not found at {lib_path}")
    if not books_root.exists():
        parser.error(f"Books directory not found at {books_root}")

    library = json.loads(lib_path.read_text(encoding='utf-8'))

    changes = 0
    for book_id, meta in library.get('books', {}).items():
        changed, old_f, new_f = rename_single_book(books_root, meta, dry_run)
        if changed:
            changes += 1

    if changes == 0:
        print("✓ Everything already consistent – no action required.")
        return

    if dry_run:
        print(f"\n{changes} item(s) would be fixed.  Re-run with --apply to execute.")
    else:
        lib_path.write_text(json.dumps(library, indent=2, ensure_ascii=False), encoding='utf-8')
        print(f"\n✓ Completed.  {changes} item(s) updated and library.json rewritten.")


if __name__ == '__main__':
    main() 