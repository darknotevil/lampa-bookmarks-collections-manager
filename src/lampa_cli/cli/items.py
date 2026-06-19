"""``lampa-cli items`` — search / add / remove / bulk-add.

Thin wrappers over :mod:`lampa_cli.search`. ``search`` caches full card data on
disk keyed by TMDB id, so ``add`` only needs the id (no bulky JSON, no TMDB
re-fetch). Adds and removes are idempotent: an already-present item is a success
(``already_exists``), and removing a missing item is ``not_found``.
"""

from __future__ import annotations

import json
import time
from typing import Optional

import typer

from ..client import LampaClient
from ..search import (
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
from ..utils import parse_search_query
from ._output import emit_json, fail, get_state
from .collections import find_collection_by_name

app = typer.Typer(no_args_is_help=True)

MediaType = typer.Option(None, "--type", help="Media type override ('movie' or 'tv'); defaults to the cached type.")


def _require_auth(state, client: LampaClient) -> None:
    if not client.is_authenticated():
        fail(state, "Not authenticated. Run 'lampa-cli auth login' first.")


@app.command()
def search(
    ctx: typer.Context,
    query: str = typer.Argument(..., help='Search query, e.g. "Fight Club 1999".'),
) -> None:
    """Search for movies/TV shows and cache the full card data for later 'add'."""
    state = get_state(ctx)
    client = LampaClient(domain=state.domain)
    _require_auth(state, client)

    search_title, query_year = parse_search_query(clean_search_title(query))
    try:
        results = search_titles(client, search_title, merge=True)
    except Exception as e:
        fail(state, str(e))

    # Cache full card data so `add` can recover it by id alone.
    save_search_cache(results)
    normalized = [normalize_result(item) for item in results]
    payload = {"query": search_title, "year": query_year, "results": normalized}

    if state.json_mode:
        emit_json(payload)
    else:
        if not normalized:
            typer.echo("No results.")
            return
        for item in normalized:
            year = f" ({item['year']})" if item.get("year") else ""
            orig = f"  / {item['original_title']}" if item.get("original_title") else ""
            typer.echo(f"{item['id']:>8}  [{item['media_type']}]  {item['title']}{orig}{year}")


@app.command()
def add(
    ctx: typer.Context,
    id: str = typer.Option(..., "--id", help="TMDB id (from search results)."),
    collection_id: Optional[str] = typer.Option(None, "--collection-id", help="Target collection (omit for bookmarks)."),
    type: Optional[str] = MediaType,
) -> None:
    """Add an item by TMDB id to a collection, or to bookmarks when no collection is given."""
    state = get_state(ctx)
    client = LampaClient(domain=state.domain)
    _require_auth(state, client)

    tmdb_id = str(id)
    card_data = get_cached_card(tmdb_id)
    media_type = type or (get_media_type(card_data) if card_data else None)

    if media_type is None:
        fail(
            state,
            "TMDB id not in search cache. Run 'items search' first, or pass --type.",
            payload={"success": False, "status": "error", "tmdb_id": tmdb_id},
        )

    target = f"collection:{collection_id}" if collection_id else "bookmarks"
    status, error = add_with_dedup(client, tmdb_id, media_type, card_data, collection_id)

    payload = {
        # already-present items are idempotent successes, not failures
        "success": status in ("added", "already_exists"),
        "status": status,
        "tmdb_id": tmdb_id,
        "media_type": media_type,
        "target": target,
    }
    if error:
        payload["error"] = error

    if state.json_mode:
        emit_json(payload)
    else:
        typer.echo(f"{status}: {tmdb_id} [{media_type}] -> {target}")
    if status == "error":
        raise typer.Exit(1)


@app.command()
def remove(
    ctx: typer.Context,
    id: str = typer.Option(..., "--id", help="TMDB id (from search results)."),
    collection_id: str = typer.Option(..., "--collection-id", help="Collection to remove the item from."),
    type: Optional[str] = MediaType,
) -> None:
    """Remove an item by TMDB id from a collection (idempotent)."""
    state = get_state(ctx)
    client = LampaClient(domain=state.domain)
    _require_auth(state, client)

    tmdb_id = str(id)
    card_data = get_cached_card(tmdb_id)
    media_type = type or (get_media_type(card_data) if card_data else None) or "movie"

    status, error = remove_with_dedup(client, tmdb_id, media_type, collection_id)

    payload = {
        # a card that wasn't there is an idempotent success, not a failure
        "success": status in ("removed", "not_found"),
        "status": status,
        "tmdb_id": tmdb_id,
        "media_type": media_type,
        "collection_id": collection_id,
    }
    if error:
        payload["error"] = error

    if state.json_mode:
        emit_json(payload)
    else:
        typer.echo(f"{status}: {tmdb_id} [{media_type}] from collection:{collection_id}")
    if status == "error":
        raise typer.Exit(1)


@app.command("bulk-add")
def bulk_add(
    ctx: typer.Context,
    input: str = typer.Option(..., "--input", help="JSON file: list of {title, year?, type?, collection?}."),
    collection_id: Optional[str] = typer.Option(None, "--collection-id", help="Add everything to this collection (overrides per-item 'collection')."),
    delay: float = typer.Option(0.3, "--delay", help="Delay in seconds between items."),
) -> None:
    """Search + add many items from a JSON file in one pass.

    Destination per item: --collection-id wins; else the item's "collection" is
    resolved/created by name (idempotent); else bookmarks.
    """
    state = get_state(ctx)
    client = LampaClient(domain=state.domain)
    _require_auth(state, client)

    try:
        with open(input, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        fail(state, f"Could not read input '{input}': {e}")

    items = data.get("items", []) if isinstance(data, dict) else data
    if not isinstance(items, list):
        fail(state, "Input must be a JSON list or an object with an 'items' list.")

    # Cache for resolving/creating named collections (name -> id).
    name_to_id: dict = {}

    def resolve_collection(item: dict) -> Optional[str]:
        if collection_id:
            return collection_id
        name = item.get("collection")
        if not name:
            return None
        key = name.strip().lower()
        if key not in name_to_id:
            cid = find_collection_by_name(client, name)
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
        target_cid = resolve_collection(item)

        status, error = add_with_dedup(client, tmdb_id, media_type, card_data, target_cid)
        counts[status] += 1
        record.update({
            "status": status,
            "tmdb_id": tmdb_id,
            "media_type": media_type,
            "target": f"collection:{target_cid}" if target_cid else "bookmarks",
        })
        if error:
            record["error"] = error
        records.append(record)

        if delay:
            time.sleep(delay)

    payload = {
        "total": len(items),
        "added": counts["added"],
        "already_exists": counts["already_exists"],
        "not_found": counts["not_found"],
        "errors": counts["error"],
        "items": records,
    }

    if state.json_mode:
        emit_json(payload)
    else:
        typer.echo(
            f"total={payload['total']} added={payload['added']} "
            f"already_exists={payload['already_exists']} "
            f"not_found={payload['not_found']} errors={payload['errors']}"
        )
