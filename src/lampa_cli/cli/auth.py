"""``lampa-cli auth`` — login / logout / status."""

from __future__ import annotations

from typing import Optional

import requests
import typer

from ..client import LampaClient
from ._output import emit_json, fail, get_state

app = typer.Typer(no_args_is_help=True)


@app.command()
def login(
    ctx: typer.Context,
    code: Optional[str] = typer.Option(None, "--code", help="6-digit code from the QR/device screen."),
    token: Optional[str] = typer.Option(None, "--token", help="Existing auth token (instead of a code)."),
    profile: Optional[str] = typer.Option(None, "--profile", help="Profile ID (used with --token)."),
    email: Optional[str] = typer.Option(None, "--email", help="Email address (optional, used with --token)."),
) -> None:
    """Authenticate and persist the session.

    With no arguments, prompts for the 6-digit code. Use --code for a
    non-interactive login, or --token/--profile to reuse an existing token.
    """
    state = get_state(ctx)
    client = LampaClient(domain=state.domain)

    try:
        if token:
            account = client.login_with_token(token=token, profile_id=profile, email=email)
        else:
            if not code:
                if state.json_mode:
                    fail(state, "Provide --code or --token (cannot prompt in --json mode).")
                code = typer.prompt("Enter 6-digit code")
            account = client.login_with_code(code)
    except ValueError as e:
        fail(state, str(e))
    except requests.exceptions.RequestException as e:
        fail(state, f"Login request failed: {e}")

    profile_id = account.profile.id if account.profile else None
    payload = {
        "authenticated": True,
        "email": account.email,
        "id": account.id,
        "profile_id": profile_id,
    }
    if state.json_mode:
        emit_json(payload)
    else:
        who = account.email or profile_id or "unknown account"
        typer.secho(f"Logged in as {who}.", fg=typer.colors.GREEN)


@app.command()
def logout(ctx: typer.Context) -> None:
    """Clear the saved session."""
    state = get_state(ctx)
    client = LampaClient(domain=state.domain)
    client.logout()

    if state.json_mode:
        emit_json({"authenticated": False})
    else:
        typer.echo("Logged out.")


@app.command()
def status(ctx: typer.Context) -> None:
    """Show the current account and whether its token is still valid."""
    state = get_state(ctx)
    client = LampaClient(domain=state.domain)

    if not client.is_authenticated():
        if state.json_mode:
            emit_json({"authenticated": False})
        else:
            typer.echo("Not logged in.")
        raise typer.Exit(0)

    account = client.account
    profile_id = account.profile.id if account.profile else None

    # A live request is the only reliable way to know the token is still good.
    try:
        client.get_user()
        token_valid = True
    except requests.exceptions.RequestException:
        token_valid = False

    payload = {
        "authenticated": True,
        "token_valid": token_valid,
        "email": account.email,
        "id": account.id,
        "profile_id": profile_id,
    }
    if state.json_mode:
        emit_json(payload)
    else:
        who = account.email or profile_id or "unknown account"
        validity = "valid" if token_valid else "INVALID/expired"
        typer.echo(f"Logged in as {who} (token {validity}).")
