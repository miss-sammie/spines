#!/usr/bin/env python3
"""
orphan_check.py – detect catalogue entries in library.json whose corresponding book
folder is missing on disk.

Usage (from project root)
-------------------------
# default locations (spines-2.0 layout)
python -m spines_2_0.src.utils.orphan_check

# explicit locations
python -m spines_2_0.src.utils.orphan_check --library-json spines-2.0/data/library.json --library-root spines-2.0

The script does *not* modify any files. It lists offending IDs so you can decide
how to clean them up (or extend the script to auto-remove them).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List, Tuple


def find_orphans(library_json: Path, books_dir: Path) -> List[Tuple[str, str]]:
    """Return list of (book_id, folder_name) whose expected folder is missing.

    The check *always* uses ``folder_name`` and ignores the ``path`` field, because
    in practice Spines serves every book out of the single ``books/`` directory.
    """
    with library_json.open(encoding="utf-8") as fh:
        data = json.load(fh)

    books = data.get("books", {})
    orphans: List[Tuple[str, str]] = []

    for book_id, info in books.items():
        folder_name = info.get("folder_name")

        if not folder_name:
            # Malformed entry – treat as orphan so it shows up in report
            orphans.append((book_id, "(missing folder_name field)"))
            continue

        candidate = books_dir / folder_name

        if not candidate.exists():
            orphans.append((book_id, folder_name))

    return orphans


def main(argv: List[str] | None = None) -> None:
    ap = argparse.ArgumentParser(
        description="Detect orphan entries in Spines library.json (missing book folders)"
    )
    ap.add_argument(
        "--library-json",
        default="spines-2.0/data/library.json",
        help="Path to library.json (default: spines-2.0/data/library.json)",
    )
    ap.add_argument(
        "--library-root",
        default="spines-2.0",
        metavar="DIR",
        help="Base directory of the Spines installation (default: spines-2.0)",
    )
    ap.add_argument(
        "--books-dir",
        default="books",
        metavar="DIR",
        help="Directory (relative to library-root) containing all book folders (default: books)",
    )
    args = ap.parse_args(argv)

    library_json = Path(args.library_json).expanduser().resolve()
    library_root = Path(args.library_root).expanduser().resolve()
    books_dir = (library_root / args.books_dir).resolve()

    if not library_json.exists():
        ap.error(f"library.json not found: {library_json}")
    if not books_dir.exists():
        ap.error(f"books directory not found: {books_dir}")

    orphans = find_orphans(library_json, books_dir)

    if orphans:
        print(f"\u26a0\ufe0f  Found {len(orphans)} orphan entr{'y' if len(orphans)==1 else 'ies'}:")
        for book_id, rel_path in orphans:
            print(f"  • {book_id} → {rel_path}")
    else:
        print("\u2705 No orphan entries detected – catalogue is clean!")


if __name__ == "__main__":
    main() 