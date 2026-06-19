"""``lampa-cli bookmarks`` — list / add / remove (favorites)."""

from __future__ import annotations

from typing import Optional

import typer

from ..client import LampaClient
from ..search import add_with_dedup, get_cached_card, get_media_type
from ._output import emit_json, fail, get_state

app = typer.Typer(no_args_is_help=True)


def _require_auth(state, client: LampaClient) -> None:
    if not client.is_authenticated():
        fail(state, "Not authenticated. Run 'lampa-cli auth login' first.")


@app.command("list")
def list_bookmarks(ctx: typer.Context) -> None:
    """List all bookmarks (favorites)."""
    state = get_state(ctx)
    client = LampaClient(domain=state.domain)
    _require_auth(state, client)

    try:
        bookmarks = client.list_bookmarks()
    except Exception as e:
        fail(state, str(e))

    payload = {"count": len(bookmarks), "bookmarks": bookmarks}
    if state.json_mode:
        emit_json(payload)
    else:
        if not bookmarks:
            typer.echo("No bookmarks.")
            return
        for bm in bookmarks:
            title = bm.get("card_title") or bm.get("title") or bm.get("card_id") or "?"
            typer.echo(f"{str(bm.get('id', '?')):>8}  {title}")


@app.command()
def add(
    ctx: typer.Context,
    id: str = typer.Option(..., "--id", help="TMDB id (from search results)."),
    type: Optional[str] = typer.Option(None, "--type", help="Media type ('movie' or 'tv'); defaults to the cached type."),
) -> None:
    """Add an item by TMDB id to bookmarks (idempotent)."""
    state = get_state(ctx)
    client = LampaClient(domain=state.domain)
    _require_auth(state, client)

    tmdb_id = str(id)
    card_data = get_cached_card(tmdb_id)
    media_type = type or (get_media_type(card_data) if card_data else None) or "movie"

    status, error = add_with_dedup(client, tmdb_id, media_type, card_data, None)

    payload = {
        "success": status in ("added", "already_exists"),
        "status": status,
        "tmdb_id": tmdb_id,
        "media_type": media_type,
        "target": "bookmarks",
    }
    if error:
        payload["error"] = error

    if state.json_mode:
        emit_json(payload)
    else:
        typer.echo(f"{status}: {tmdb_id} [{media_type}] -> bookmarks")
    if status == "error":
        raise typer.Exit(1)


@app.command()
def remove(
    ctx: typer.Context,
    id: str = typer.Option(..., "--id", help="Bookmark id (from 'bookmarks list', not the TMDB id)."),
) -> None:
    """Remove a bookmark by its bookmark id."""
    state = get_state(ctx)
    client = LampaClient(domain=state.domain)
    _require_auth(state, client)

    try:
        response = client.remove_bookmark(id)
        success = bool(response.secuses)
    except Exception as e:
        fail(state, str(e), payload={"success": False, "bookmark_id": id})

    payload = {"success": success, "bookmark_id": id}
    if state.json_mode:
        emit_json(payload)
    else:
        typer.echo(f"{'Removed' if success else 'Not removed'}: bookmark {id}")
    if not success:
        raise typer.Exit(1)
