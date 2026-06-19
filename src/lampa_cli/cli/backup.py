"""``lampa-cli backup`` — export / import favorites and collections.

cub.rip's built-in "Backup" only dumps the browser ``localStorage`` to the
cloud (see Lampa's ``core/account/backup.js``); it does not cover server-side
data, and there is no ``collections/dump`` endpoint (it answers 404). So a real
backup of favorites + collections is assembled by enumeration:

* bookmarks  → ``bookmarks/dump`` (raw, exact)
* collections → ``collections/list?cid=<id>`` + ``collections/view/{id}``
  paged to exhaustion. ``view`` is TMDB-resolved and lossy: unresolvable cards
  are dropped, so a collection may back up with fewer items than ``items_count``.

The on-disk format is a single JSON document (``--out`` or stdout). ``import``
recreates everything idempotently via the existing write endpoints; it is
re-runnable and supports ``--dry-run`` (offline, no writes).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import typer

from ..client import LampaClient
from ..models import CollectionItem
from ..search import add_with_dedup
from ._output import emit_json, fail, get_state

app = typer.Typer(no_args_is_help=True)

FORMAT_VERSION = 1


class Scope(str, Enum):
    """Which sections a command should touch."""

    all = "all"
    bookmarks = "bookmarks"
    collections = "collections"


def _require_auth(state, client: LampaClient) -> None:
    if not client.is_authenticated():
        fail(state, "Not authenticated. Run 'lampa-cli auth login' first.")


def _item_media_type(item: CollectionItem) -> str:
    """Derive 'movie' / 'tv' from a TMDB-resolved collection card.

    ``collections/view`` does not carry an explicit ``media_type``; TV shows are
    identified by ``name`` / ``first_air_date`` and movies by ``title`` /
    ``release_date``. We treat a card as TV only when it has a TV-style name and
    lacks a movie title, which matches how the API shapes the two kinds.
    """
    has_tv = bool(item.name or item.first_air_date)
    has_movie = bool(item.title or item.release_date)
    return "tv" if (has_tv and not has_movie) else "movie"


# ============================================
# export
# ============================================

@app.command("export")
def export_backup(
    ctx: typer.Context,
    out: Optional[str] = typer.Option(
        None, "--out", help="Write the backup JSON to this file (default: stdout)."
    ),
    only: Scope = typer.Option(
        Scope.all, "--only", help="Limit the backup to one section."
    ),
) -> None:
    """Export favorites and collections to a JSON backup."""
    state = get_state(ctx)
    client = LampaClient(domain=state.domain)
    _require_auth(state, client)

    account = client.account
    backup: Dict[str, Any] = {
        "version": FORMAT_VERSION,
        "exported_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "domain": state.domain,
        "account": {
            "id": account.id if account else None,
            "email": account.email if account else None,
            "profile": account.profile.id if account and account.profile else None,
        },
    }

    try:
        if only in (Scope.all, Scope.bookmarks):
            # Raw dump entries keep the full card ``data`` for an exact re-add.
            backup["bookmarks"] = client.list_bookmarks()

        if only in (Scope.all, Scope.collections):
            collections: List[Dict[str, Any]] = []
            for coll in client.list_all_user_collections():
                items = client.view_all_collection_items(str(coll.id), coll.items_count)
                collections.append(
                    {
                        "id": str(coll.id),
                        "title": coll.title,
                        "items_count": coll.items_count,
                        "items": [
                            {
                                "tmdb_id": str(it.id),
                                "media_type": _item_media_type(it),
                                "title": it.title or it.name,
                            }
                            for it in items
                        ],
                    }
                )
            backup["collections"] = collections
    except Exception as e:  # network / parse errors
        fail(state, str(e))

    n_bm = len(backup.get("bookmarks", []))
    n_coll = len(backup.get("collections", []))
    n_items = sum(len(c["items"]) for c in backup.get("collections", []))

    if out:
        try:
            with open(out, "w", encoding="utf-8") as f:
                json.dump(backup, f, ensure_ascii=False, indent=2)
        except OSError as e:
            fail(state, f"Failed to write '{out}': {e}")
        summary = {
            "written": out,
            "bookmarks": n_bm,
            "collections": n_coll,
            "collection_items": n_items,
        }
        if state.json_mode:
            emit_json(summary)
        else:
            typer.echo(
                f"Wrote {out}: {n_bm} bookmarks, {n_coll} collections "
                f"({n_items} items)."
            )
    else:
        # No file: the backup itself is the output (agents capture stdout).
        emit_json(backup)


# ============================================
# import
# ============================================

@app.command("import")
def import_backup(
    ctx: typer.Context,
    file: str = typer.Argument(..., help="Path to a backup JSON produced by 'export'."),
    only: Scope = typer.Option(
        Scope.all, "--only", help="Restore only one section."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Report what would be restored without writing anything."
    ),
) -> None:
    """Restore favorites and collections from a JSON backup (idempotent)."""
    state = get_state(ctx)

    try:
        with open(file, "r", encoding="utf-8") as f:
            backup = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        fail(state, f"Failed to read backup '{file}': {e}")

    if not isinstance(backup, dict) or "version" not in backup:
        fail(state, "Not a valid lampa-cli backup file.")

    bookmarks = backup.get("bookmarks", []) if only in (Scope.all, Scope.bookmarks) else []
    collections = backup.get("collections", []) if only in (Scope.all, Scope.collections) else []

    if dry_run:
        payload = {
            "dry_run": True,
            "bookmarks": len(bookmarks),
            "collections": len(collections),
            "collection_items": sum(len(c.get("items", [])) for c in collections),
        }
        if state.json_mode:
            emit_json(payload)
        else:
            typer.echo(
                f"Would restore {payload['bookmarks']} bookmarks and "
                f"{payload['collections']} collections "
                f"({payload['collection_items']} items)."
            )
        return

    client = LampaClient(domain=state.domain)
    _require_auth(state, client)

    results: Dict[str, Any] = {"bookmarks": {}, "collections": []}

    # --- bookmarks ---
    for bm in bookmarks:
        tmdb_id = str(bm.get("card_id"))
        media_type = bm.get("card_type") or "movie"
        card_data = None
        raw = bm.get("data")
        if isinstance(raw, str) and raw:
            try:
                card_data = json.loads(raw)
            except json.JSONDecodeError:
                card_data = None
        status, _ = add_with_dedup(client, tmdb_id, media_type, card_data, None)
        results["bookmarks"][status] = results["bookmarks"].get(status, 0) + 1

    # --- collections ---
    # Map existing collections by name up front: cub.rip lets two collections
    # share a name, so creating blindly would spawn duplicates on every re-run.
    # We reuse an existing one when the names match (case-insensitive).
    if collections:
        existing = {
            (c.title or "").strip().lower(): str(c.id)
            for c in client.list_all_user_collections()
        }
    else:
        existing = {}

    for coll in collections:
        title = coll.get("title") or ""
        entry: Dict[str, Any] = {"title": title, "items": {}}
        key = title.strip().lower()
        collection_id = existing.get(key)
        if collection_id is None:
            try:
                created = client.create_collection(title)
                collection_id = str(created.collection.id)
                existing[key] = collection_id
            except Exception as e:
                entry["error"] = str(e)
                results["collections"].append(entry)
                continue

        for it in coll.get("items", []):
            status, _ = add_with_dedup(
                client,
                str(it.get("tmdb_id")),
                it.get("media_type") or "movie",
                None,
                collection_id=collection_id,
            )
            entry["items"][status] = entry["items"].get(status, 0) + 1
        entry["collection_id"] = collection_id
        results["collections"].append(entry)

    if state.json_mode:
        emit_json(results)
    else:
        bm_summary = ", ".join(f"{k}={v}" for k, v in results["bookmarks"].items()) or "none"
        typer.echo(f"Bookmarks: {bm_summary}")
        for entry in results["collections"]:
            if "error" in entry:
                typer.echo(f"Collection '{entry['title']}': error: {entry['error']}")
            else:
                items = ", ".join(f"{k}={v}" for k, v in entry["items"].items()) or "empty"
                typer.echo(f"Collection '{entry['title']}': {items}")
