#!/usr/bin/env python3
"""
Agent-friendly CLI tool for Lampa MX.

Designed for LLM agents: all output is structured JSON, no interactive prompts.

Workflow:
    1. Search — returns compact JSON results and caches full card data on disk.
    2. Add    — adds by TMDB id; card data is recovered from the cache, so the
                agent only passes the id (no bulky JSON, no TMDB re-fetch).

Usage:
    # Search for a movie/show (returns JSON with TMDB ids)
    uv run examples/agent_tool.py search "Animal Crackers 2017"

    # Add by TMDB id to bookmarks (favorites) — type comes from the cache
    uv run examples/agent_tool.py add --tmdb-id 315064

    # Add by TMDB id to a specific collection
    uv run examples/agent_tool.py add --tmdb-id 315064 --collection-id 2948

    # Remove by TMDB id from a specific collection
    uv run examples/agent_tool.py remove --tmdb-id 315064 --collection-id 2948

    # Override the cached type (only needed if you skipped search)
    uv run examples/agent_tool.py add --tmdb-id 315064 --type movie

    # List user collections
    uv run examples/agent_tool.py list-collections
"""

import argparse
import json
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.client import LampaClient
from src.search import (
    add_with_dedup,
    clean_search_title,
    get_cached_card,
    get_media_type,
    normalize_result,
    remove_with_dedup,
    save_search_cache,
    search_and_get_id,
    search_titles,
)
from src.utils import parse_search_query


def _print(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _require_auth(client) -> None:
    if not client.is_authenticated():
        _print({"error": "Not authenticated. Run examples/login.py first."})
        sys.exit(1)


def cmd_search(args):
    """Search subcommand — returns compact JSON results, caches full card data."""
    client = LampaClient(domain=args.domain)
    _require_auth(client)

    # Prefer the original (latin) part of "Русское / Original" titles.
    search_title, query_year = parse_search_query(clean_search_title(args.query))
    results = search_titles(client, search_title, merge=True)

    # Cache full card data so `add` can recover it by id (avoids token-heavy
    # round-trips and TMDB re-fetches).
    save_search_cache(results)

    _print({
        "query": search_title,
        "year": query_year,
        "results": [normalize_result(item) for item in results],
    })


def cmd_add(args):
    """Add subcommand — adds an item by TMDB id to bookmarks or a collection.

    Card data and media type are recovered from the search cache, so a prior
    `search` is all that's needed. `--type` is only required as a fallback when
    the id isn't cached (e.g. the search step was skipped).
    """
    client = LampaClient(domain=args.domain)
    _require_auth(client)

    tmdb_id = str(args.tmdb_id)
    card_data = get_cached_card(tmdb_id)
    media_type = args.type or (get_media_type(card_data) if card_data else None)

    if media_type is None:
        _print({
            "success": False,
            "status": "error",
            "tmdb_id": tmdb_id,
            "error": "TMDB id not in search cache. Run 'search' first, or pass --type.",
        })
        sys.exit(1)

    target = f"collection:{args.collection_id}" if args.collection_id else "bookmarks"
    status, error = add_with_dedup(
        client, tmdb_id, media_type, card_data, args.collection_id
    )

    result = {
        # already-present items are idempotent successes, not failures
        "success": status in ("added", "already_exists"),
        "status": status,
        "tmdb_id": tmdb_id,
        "media_type": media_type,
        "target": target,
    }
    if error:
        result["error"] = error
    _print(result)
    if status == "error":
        sys.exit(1)


def cmd_remove(args):
    """Remove subcommand — removes an item by TMDB id from a collection.

    Like `add`, the media type is recovered from the search cache, so a prior
    `search` is enough; `--type` is only needed as a fallback. Removing an item
    that isn't in the collection is idempotent (`status: "not_found"`).
    """
    client = LampaClient(domain=args.domain)
    _require_auth(client)

    tmdb_id = str(args.tmdb_id)
    card_data = get_cached_card(tmdb_id)
    media_type = args.type or (get_media_type(card_data) if card_data else None) or "movie"

    status, error = remove_with_dedup(
        client, tmdb_id, media_type, args.collection_id
    )

    result = {
        # a card that wasn't there is an idempotent success, not a failure
        "success": status in ("removed", "not_found"),
        "status": status,
        "tmdb_id": tmdb_id,
        "media_type": media_type,
        "collection_id": args.collection_id,
    }
    if error:
        result["error"] = error
    _print(result)
    if status == "error":
        sys.exit(1)


def cmd_list_collections(args):
    """List-collections subcommand — returns JSON list of collections."""
    client = LampaClient(domain=args.domain)
    _require_auth(client)

    try:
        response = client.list_collections(category=args.category, page=args.page)
        _print({
            "collections": [
                {
                    "id": str(coll.id),
                    "title": coll.title,
                    "items_count": coll.items_count,
                    "views": coll.views,
                    "username": coll.username,
                }
                for coll in response.results
            ],
            "total_pages": response.total_pages,
        })
    except Exception as e:
        _print({"error": str(e)})
        sys.exit(1)


def _find_collection_by_name(client, name):
    """Return the id of an existing user collection matching ``name`` (case-
    insensitive, trimmed), or None."""
    target = name.strip().lower()
    response = client.list_collections(category="user")
    for coll in response.results:
        if (coll.title or "").strip().lower() == target:
            return str(coll.id)
    return None


def cmd_create_collection(args):
    """Create-collection subcommand — idempotent: reuses an existing collection
    with the same name instead of creating a duplicate."""
    client = LampaClient(domain=args.domain)
    _require_auth(client)

    try:
        existing_id = _find_collection_by_name(client, args.name)
        if existing_id is not None:
            _print({"id": existing_id, "title": args.name, "created": False})
            return

        response = client.create_collection(args.name)
        _print({
            "id": str(response.collection.id),
            "title": args.name,
            "created": True,
        })
    except Exception as e:
        _print({"error": str(e)})
        sys.exit(1)


def cmd_bulk_add(args):
    """Bulk-add subcommand — search + add many items in one pass.

    Input is a JSON file: either a list of items or ``{"items": [...]}``. Each
    item is ``{"title": str, "year"?: int, "type"?: "movie"|"tv",
    "collection"?: str}``. Destination resolution per item:

      * ``--collection-id`` given  -> everything goes to that collection
      * item has ``"collection"``  -> resolved/created by name (idempotent)
      * otherwise                  -> bookmarks

    Output is a structured JSON report; already-present items are counted as
    ``already_exists`` (success), never as errors.
    """
    client = LampaClient(domain=args.domain)
    _require_auth(client)

    try:
        with open(args.input, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        _print({"error": f"Could not read input '{args.input}': {e}"})
        sys.exit(1)

    items = data.get("items", []) if isinstance(data, dict) else data
    if not isinstance(items, list):
        _print({"error": "Input must be a JSON list or an object with an 'items' list."})
        sys.exit(1)

    # Cache for resolving/creating named collections (name -> id).
    name_to_id = {}

    def resolve_collection(item):
        if args.collection_id:
            return args.collection_id
        name = item.get("collection")
        if not name:
            return None
        key = name.strip().lower()
        if key not in name_to_id:
            cid = _find_collection_by_name(client, name)
            if cid is None:
                cid = str(client.create_collection(name).collection.id)
            name_to_id[key] = cid
        return name_to_id[key]

    counts = {"added": 0, "already_exists": 0, "not_found": 0, "error": 0}
    records = []

    for item in items:
        title = item.get("title", "")
        year = item.get("year")
        query = f"{title} {year}" if year else title

        record = {"title": title, "year": year}
        found = search_and_get_id(client, query)
        if not found:
            counts["not_found"] += 1
            record["status"] = "not_found"
            records.append(record)
            continue

        tmdb_id, media_type, card_data = found
        media_type = item.get("type") or media_type
        collection_id = resolve_collection(item)

        status, error = add_with_dedup(
            client, tmdb_id, media_type, card_data, collection_id
        )
        counts[status] += 1
        record.update({
            "status": status,
            "tmdb_id": tmdb_id,
            "media_type": media_type,
            "target": f"collection:{collection_id}" if collection_id else "bookmarks",
        })
        if error:
            record["error"] = error
        records.append(record)

        if args.delay:
            time.sleep(args.delay)

    _print({
        "total": len(items),
        "added": counts["added"],
        "already_exists": counts["already_exists"],
        "not_found": counts["not_found"],
        "errors": counts["error"],
        "items": records,
    })


def main():
    parser = argparse.ArgumentParser(
        description='Agent-friendly tool for Lampa MX (JSON output, no interactivity)'
    )
    parser.add_argument('--domain', type=str, default='cub.rip', help='CUB domain')

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # search
    search_parser = subparsers.add_parser('search', help='Search for movies/TV shows')
    search_parser.add_argument('query', type=str, help='Search query (e.g. "Animal Crackers 2017")')
    search_parser.set_defaults(func=cmd_search)

    # add
    add_parser = subparsers.add_parser('add', help='Add item by TMDB id')
    add_parser.add_argument('--tmdb-id', type=str, required=True, help='TMDB id (from search results)')
    add_parser.add_argument('--type', type=str, default=None, choices=['movie', 'tv'],
                            help='Media type override (defaults to the cached type)')
    add_parser.add_argument('--collection-id', type=str, default=None,
                            help='Collection id (omit for bookmarks)')
    add_parser.set_defaults(func=cmd_add)

    # remove
    remove_parser = subparsers.add_parser('remove', help='Remove item by TMDB id from a collection')
    remove_parser.add_argument('--tmdb-id', type=str, required=True, help='TMDB id (from search results)')
    remove_parser.add_argument('--collection-id', type=str, required=True,
                               help='Collection id to remove the item from')
    remove_parser.add_argument('--type', type=str, default=None, choices=['movie', 'tv'],
                               help='Media type override (defaults to the cached type)')
    remove_parser.set_defaults(func=cmd_remove)

    # list-collections
    lc_parser = subparsers.add_parser('list-collections', help='List user collections')
    lc_parser.add_argument('--category', type=str, default='user',
                           choices=['user', 'new', 'top', 'week', 'month', 'big', 'all'],
                           help='Category (default: user)')
    lc_parser.add_argument('--page', type=int, default=1, help='Page number')
    lc_parser.set_defaults(func=cmd_list_collections)

    # create-collection
    cc_parser = subparsers.add_parser('create-collection',
                                      help='Create a collection (idempotent by name)')
    cc_parser.add_argument('--name', type=str, required=True, help='Collection title')
    cc_parser.set_defaults(func=cmd_create_collection)

    # bulk-add
    ba_parser = subparsers.add_parser('bulk-add',
                                      help='Search + add many items from a JSON file')
    ba_parser.add_argument('--input', type=str, required=True,
                           help='Path to JSON file: list of {title, year?, type?, collection?}')
    ba_parser.add_argument('--collection-id', type=str, default=None,
                           help='Add all items to this collection (overrides per-item "collection")')
    ba_parser.add_argument('--delay', type=float, default=0.3,
                           help='Delay in seconds between items (default: 0.3)')
    ba_parser.set_defaults(func=cmd_bulk_add)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == '__main__':
    main()
