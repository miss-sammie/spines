"""CollectionManager service for creating, storing and resolving book collections.

Collections are stored as a single JSON document::

    {
        "collections": {
            "<collection_id>": {
                "id": "..",
                "name": "Whisper contributions",
                "description": "All books uploaded by Whisper",
                "icon": "📚",
                "mode": "dynamic",           # "static" or "dynamic"
                "filters": {                  # Only for dynamic collections
                    "contributor": ["whisper"]
                },
                "book_ids": ["..", ".."],   # Only for static collections (or manual overrides)
                "created": "2024-07-08T00:00:00Z",
                "updated": "2024-07-08T00:00:00Z"
            }
        }
    }

Dynamic collections use the simple JSON filter object stored in the *filters* field.  At runtime
``resolve_books`` will evaluate those filters against the library index and return the concrete
list of matching book IDs.

NOTE:  This first implementation supports only a subset of possible filters for MVP:

* contributor – exact inclusion list
* author_contains – case-insensitive substring on author
* title_contains – case-insensitive substring on title
* media_type – exact match (book / web / unknown)
* tags_any – overlap between collection.tags_any list and book.tags list
* read_by_any – overlap between collection.read_by_any list and book.read_by list

This covers the most common use-cases while keeping the logic straightforward.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from src.metadata_extractor import MetadataExtractor  # reuse existing index loading

ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"


class CollectionManager:
    """Manage book collections (static or dynamic) persisted in *collections.json*."""

    def __init__(self, library_path: str = "./books", data_path: str = "./data"):
        self.library_path = Path(library_path)
        self.data_path = Path(data_path)
        self.collections_path = self.data_path / "collections.json"

        # Ensure data directory exists
        self.data_path.mkdir(parents=True, exist_ok=True)

        if not self.collections_path.exists():
            # Initialise empty file
            self._save({"collections": {}})

        # internal cache
        self._collections: Dict[str, Dict] = {}
        self._load()

    # ---------------------------------------------------------------------
    # Public helpers
    # ---------------------------------------------------------------------
    def list_collections(self) -> List[Dict]:
        return list(self._collections.values())

    def get_collection(self, cid: str) -> Optional[Dict]:
        return self._collections.get(cid)

    def create_collection(
        self,
        name: str,
        description: str = "",
        mode: str = "dynamic",
        filters: Optional[Dict] = None,
        book_ids: Optional[List[str]] = None,
        icon: Optional[str] = None,
        collection_id: Optional[str] = None,
    ) -> Dict:
        if mode not in {"static", "dynamic"}:
            raise ValueError("mode must be either 'static' or 'dynamic'")

        cid = collection_id or uuid.uuid4().hex[:12]
        timestamp = datetime.utcnow().strftime(ISO_FMT)
        collection = {
            "id": cid,
            "name": name,
            "description": description,
            "icon": icon,
            "mode": mode,
            "filters": filters or {},
            "book_ids": book_ids or [],
            "created": timestamp,
            "updated": timestamp,
        }
        self._collections[cid] = collection
        self._save()
        return collection

    def update_collection(self, cid: str, **fields) -> Optional[Dict]:
        col = self._collections.get(cid)
        if not col:
            return None
        # allowed fields
        allowed = {
            "name",
            "description",
            "icon",
            "mode",
            "filters",
            "book_ids",
        }
        for k, v in fields.items():
            if k in allowed:
                col[k] = v
        col["updated"] = datetime.utcnow().strftime(ISO_FMT)
        self._save()
        return col

    # ----------------- Static collection helpers -------------------------
    def add_book(self, cid: str, book_id: str):
        col = self._collections.get(cid)
        if not col or col.get("mode") != "static":
            raise ValueError("Can only add books to *static* collections")
        if book_id not in col["book_ids"]:
            col["book_ids"].append(book_id)
            col["updated"] = datetime.utcnow().strftime(ISO_FMT)
            self._save()

    def remove_book(self, cid: str, book_id: str):
        col = self._collections.get(cid)
        if not col or col.get("mode") != "static":
            raise ValueError("Can only remove books from *static* collections")
        if book_id in col["book_ids"]:
            col["book_ids"].remove(book_id)
            col["updated"] = datetime.utcnow().strftime(ISO_FMT)
            self._save()

    # ---------------------------------------------------------------------
    # Resolution – turn filters or ids into concrete book dicts
    # ---------------------------------------------------------------------
    def resolve_books(self, collection: Dict, limit: Optional[int] = None) -> List[Dict]:
        """Return list of *book metadata dicts* that belong to the collection.

        This function loads the library index via :class:`MetadataExtractor` once and
        filters it in-memory.  For large libraries (> 50k) we might need a DB solution,
        but it is perfectly adequate for a typical personal collection.
        """

        extractor = MetadataExtractor(
            library_path=str(self.library_path),
            data_path=str(self.data_path),
        )
        books_index = extractor.library_index["books"]
        results: List[Dict] = []

        # ---------------- STATIC ----------------
        if collection["mode"] == "static":
            for bid in collection.get("book_ids", [])[: limit or None]:
                meta = books_index.get(bid)
                if meta:
                    # Attach id to metadata (useful client-side)
                    meta_resolved = meta.copy()
                    meta_resolved["book_id"] = bid
                    results.append(meta_resolved)
            return results

        # ---------------- DYNAMIC ----------------
        filters = collection.get("filters", {})
        for bid, meta in books_index.items():
            if self._match_filters(meta, filters):
                meta_resolved = meta.copy()
                meta_resolved["book_id"] = bid
                results.append(meta_resolved)
                if limit and len(results) >= limit:
                    break
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _match_filters(self, meta: Dict, filters: Dict) -> bool:
        """Very naive filter evaluator – supports subset described in module docstring."""
        # contributor exact list intersection
        contrib = filters.get("contributor")
        if contrib:
            contribs_meta = meta.get("contributor", []) or []
            if not any(c in contribs_meta for c in contrib):
                return False

        # author substring
        author_contains = filters.get("author_contains")
        if author_contains and author_contains.lower() not in (meta.get("author", "").lower()):
            return False

        # title substring
        title_contains = filters.get("title_contains")
        if title_contains and title_contains.lower() not in (meta.get("title", "").lower()):
            return False

        # media_type exact
        media_type = filters.get("media_type")
        if media_type and meta.get("media_type") != media_type:
            return False

        # tags any
        tags_any = filters.get("tags_any")
        if tags_any:
            tags_meta = meta.get("tags", []) or []
            if not any(t in tags_meta for t in tags_any):
                return False

        # read_by any
        read_by_any = filters.get("read_by_any")
        if read_by_any:
            readers_meta = meta.get("read_by", []) or []
            if not any(r in readers_meta for r in read_by_any):
                return False

        return True

    # ------------------------------------------------------------------
    def _load(self):
        with self.collections_path.open("r", encoding="utf-8") as fp:
            data = json.load(fp)
        self._collections = data.get("collections", {})

    def _save(self, data: Optional[Dict] = None):
        if data is None:
            data = {"collections": self._collections}
        with self.collections_path.open("w", encoding="utf-8") as fp:
            json.dump(data, fp, indent=2, ensure_ascii=False) 