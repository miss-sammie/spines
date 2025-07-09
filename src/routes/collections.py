"""Collections API routes.

Exposes CRUD operations and simple helpers for book collections.

MVP endpoints:
    • GET  /api/collections                     – list collections (metadata only)
    • POST /api/collections                    – create/update (JSON body)
    • GET  /api/collections/<cid>              – get collection (optional resolved list)
    • POST /api/collections/<cid>/books/<bid>  – add/remove book to static collection

All endpoints live under the *collections_bp* blueprint which is registered by
``src.web_server.create_app``.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request, abort, current_app

from src.services.collection_service import CollectionManager
from src.metadata_extractor import MetadataExtractor

collections_bp = Blueprint("collections", __name__)


# Helpers -------------------------------------------------------------------

def get_manager():
    """Instantiate a CollectionManager using app config paths."""
    config = current_app.config if current_app else None
    library_path = config.get("LIBRARY_PATH", "./books") if config else "./books"
    data_path = config.get("DATA_PATH", "./data") if config else "./data"
    return CollectionManager(library_path=library_path, data_path=data_path)


# Routes --------------------------------------------------------------------


@collections_bp.route("/api/collections", methods=["GET"])
def list_collections():
    manager = get_manager()
    cols = manager.list_collections()
    return jsonify({"collections": cols})


@collections_bp.route("/api/collections", methods=["POST"])
def create_or_update_collection():
    payload = request.get_json(force=True, silent=True) or {}
    manager = get_manager()

    cid = payload.get("id")
    if cid and manager.get_collection(cid):
        # update
        updated = manager.update_collection(cid, **payload)
        return jsonify(updated), 200

    # create new
    name = payload.get("name")
    if not name:
        abort(400, "'name' field required")
    collection = manager.create_collection(
        name=name,
        description=payload.get("description", ""),
        mode=payload.get("mode", "dynamic"),
        filters=payload.get("filters"),
        book_ids=payload.get("book_ids"),
        icon=payload.get("icon"),
        collection_id=cid,
    )
    return jsonify(collection), 201


@collections_bp.route("/api/collections/<cid>", methods=["GET"])
def get_collection(cid):
    manager = get_manager()
    col = manager.get_collection(cid)
    if not col:
        abort(404)

    resolve_flag = request.args.get("resolve")
    if resolve_flag:
        books = manager.resolve_books(col)
        return jsonify({"collection": col, "books": books})
    return jsonify(col)


@collections_bp.route("/api/collections/<cid>/books/<bid>", methods=["POST"])
def modify_collection_books(cid, bid):
    manager = get_manager()
    col = manager.get_collection(cid)
    if not col:
        abort(404)

    action = request.args.get("action", "add")
    try:
        if action == "add":
            manager.add_book(cid, bid)
        elif action == "remove":
            manager.remove_book(cid, bid)
        else:
            abort(400, "invalid action")
    except ValueError as exc:
        abort(400, str(exc))

    return jsonify({"status": "ok", "collection": manager.get_collection(cid)}) 