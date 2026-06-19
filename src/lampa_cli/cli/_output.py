"""Shared output helpers for the lampa-cli command groups.

Every command builds a plain ``dict`` payload (the exact shape the JSON/agent
consumers rely on). In ``--json`` mode that dict is printed verbatim; otherwise
a command renders a human-readable view itself. This module centralises the
global state plumbing (domain + json flag stashed on the Typer context) and the
two output sinks so the command modules stay thin.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, NoReturn, Optional

import typer


@dataclass
class State:
    """Global options shared by every command, carried on ``ctx.obj``."""

    domain: str = "cub.rip"
    json_mode: bool = False


def get_state(ctx: typer.Context) -> State:
    """Return the :class:`State` set up by the root callback."""
    if not isinstance(ctx.obj, State):
        # Safety net for direct command invocation in tests.
        ctx.obj = State()
    return ctx.obj


def emit_json(payload: Any) -> None:
    """Print a payload as pretty UTF-8 JSON (the agent-facing output shape)."""
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))


def fail(state: State, message: str, *, payload: Optional[dict] = None) -> NoReturn:
    """Report an error in the right format and exit with code 1.

    In JSON mode the error is merged into ``payload`` (or a bare
    ``{"error": ...}``); in human mode it is printed to stderr in red.
    """
    if state.json_mode:
        body = dict(payload or {})
        body["error"] = message
        emit_json(body)
    else:
        typer.secho(f"Error: {message}", fg=typer.colors.RED, err=True)
    raise typer.Exit(1)
