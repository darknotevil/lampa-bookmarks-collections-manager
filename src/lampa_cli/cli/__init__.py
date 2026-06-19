"""lampa-cli — Typer entry point.

Builds the root application, wires the global ``--json`` / ``--domain`` options
onto the Typer context, and registers the four command groups. The console
script declared in ``pyproject.toml`` points at :func:`main`.
"""

from __future__ import annotations

import typer

from ._output import State
from . import auth, backup, bookmarks, collections, items

app = typer.Typer(
    help="Manage Lampa MX bookmarks and collections via the cub.rip API.",
    no_args_is_help=True,
    add_completion=False,
)

app.add_typer(auth.app, name="auth", help="Authentication: login / logout / status.")
app.add_typer(collections.app, name="collections", help="Browse and manage collections.")
app.add_typer(items.app, name="items", help="Search and add/remove movies and shows.")
app.add_typer(bookmarks.app, name="bookmarks", help="Manage bookmarks (favorites).")
app.add_typer(backup.app, name="backup", help="Export / import favorites and collections.")


@app.callback()
def _main(
    ctx: typer.Context,
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Emit machine-readable JSON instead of human-readable output.",
    ),
    domain: str = typer.Option(
        "cub.rip",
        "--domain",
        help="CUB domain to talk to.",
    ),
) -> None:
    """Shared options for every command."""
    ctx.obj = State(domain=domain, json_mode=json_output)


def main() -> None:
    """Console-script entry point (see ``[project.scripts]``)."""
    app()
