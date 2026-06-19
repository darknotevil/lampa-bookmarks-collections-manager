"""``lampa-cli collections`` — list / view / create / like."""

from __future__ import annotations

from typing import Optional

import typer

from ..client import LampaClient
from ._output import emit_json, fail, get_state

app = typer.Typer(no_args_is_help=True)

CATEGORIES = ["user", "new", "top", "week", "month", "big", "all"]


def find_collection_by_name(client: LampaClient, name: str) -> Optional[str]:
    """Return the id of an existing *user* collection matching ``name``
    (case-insensitive, trimmed), or None. Shared with ``items bulk-add``."""
    target = name.strip().lower()
    response = client.list_collections(category="user")
    for coll in response.results:
        if (coll.title or "").strip().lower() == target:
            return str(coll.id)
    return None


def _require_auth(state, client: LampaClient) -> None:
    if not client.is_authenticated():
        fail(state, "Not authenticated. Run 'lampa-cli auth login' first.")


@app.command("list")
def list_collections(
    ctx: typer.Context,
    category: str = typer.Option("user", "--category", help=f"One of: {', '.join(CATEGORIES)}."),
    page: int = typer.Option(1, "--page", help="Page number."),
) -> None:
    """List collections by category (default: your own)."""
    state = get_state(ctx)
    client = LampaClient(domain=state.domain)
    _require_auth(state, client)

    if category not in CATEGORIES:
        fail(state, f"Invalid category '{category}'. Must be one of: {', '.join(CATEGORIES)}.")

    try:
        response = client.list_collections(category=category, page=page)
    except Exception as e:
        fail(state, str(e))

    collections = [
        {
            "id": str(coll.id),
            "title": coll.title,
            "items_count": coll.items_count,
            "views": coll.views,
            "username": coll.username,
        }
        for coll in response.results
    ]
    payload = {"collections": collections, "total_pages": response.total_pages}

    if state.json_mode:
        emit_json(payload)
    else:
        if not collections:
            typer.echo("No collections found.")
            return
        for coll in collections:
            typer.echo(f"{coll['id']:>8}  {coll['title']}  ({coll['items_count']} items)")


@app.command()
def view(
    ctx: typer.Context,
    id: str = typer.Option(..., "--id", help="Collection id."),
    page: int = typer.Option(1, "--page", help="Page number."),
) -> None:
    """Show the items in a collection."""
    state = get_state(ctx)
    client = LampaClient(domain=state.domain)
    _require_auth(state, client)

    try:
        response = client.view_collection(id, page=page)
    except Exception as e:
        fail(state, str(e))

    items = [
        {
            "id": str(item.id),
            "title": item.title or item.name,
            "media_type": item.media_type,
            "year": (item.release_date or item.first_air_date or "")[:4] or None,
        }
        for item in response.results
    ]
    payload = {"collection_id": id, "results": items, "total_pages": response.total_pages}

    if state.json_mode:
        emit_json(payload)
    else:
        if not items:
            typer.echo("Collection is empty.")
            return
        for item in items:
            year = f" ({item['year']})" if item["year"] else ""
            typer.echo(f"{item['id']:>8}  [{item['media_type']}]  {item['title']}{year}")


@app.command()
def create(
    ctx: typer.Context,
    name: str = typer.Option(..., "--name", help="Collection title."),
) -> None:
    """Create a collection. Idempotent: reuses an existing one with the same name."""
    state = get_state(ctx)
    client = LampaClient(domain=state.domain)
    _require_auth(state, client)

    try:
        existing_id = find_collection_by_name(client, name)
        if existing_id is not None:
            payload = {"id": existing_id, "title": name, "created": False}
        else:
            response = client.create_collection(name)
            payload = {"id": str(response.collection.id), "title": name, "created": True}
    except Exception as e:
        fail(state, str(e))

    if state.json_mode:
        emit_json(payload)
    else:
        verb = "Created" if payload["created"] else "Already exists"
        typer.echo(f"{verb}: {payload['title']} (id {payload['id']})")


@app.command()
def like(
    ctx: typer.Context,
    id: str = typer.Option(..., "--id", help="Collection id."),
    unlike: bool = typer.Option(False, "--unlike", help="Remove the like instead of adding it."),
) -> None:
    """Like (or, with --unlike, unlike) a collection."""
    state = get_state(ctx)
    client = LampaClient(domain=state.domain)
    _require_auth(state, client)

    try:
        client.like_collection(id, like=not unlike)
    except Exception as e:
        fail(state, str(e))

    payload = {"id": id, "liked": not unlike}
    if state.json_mode:
        emit_json(payload)
    else:
        typer.echo(f"{'Unliked' if unlike else 'Liked'} collection {id}.")
