# Tech stack — Lampa bookmarks manager

Python ≥3.10 (dev `.venv` is 3.13). Packaged with **hatchling**; installable as
the `lampa-cli` console script via `uv tool install`.

## Setup

```bash
uv tool install .            # install the lampa-cli command (or: uv tool install git+<repo>)
# dev / run without installing:
uv run lampa-cli --help
```

First-time login (one of):

```bash
lampa-cli auth login                                   # prompts for the 6-digit device code
lampa-cli auth login --code 123456                     # device code from https://cub.rip/add
lampa-cli auth login --token TOKEN --profile PROFILE   # existing session
lampa-cli auth status                                  # who am I / is the token still valid?
```

Account is persisted to `$XDG_STATE_HOME/lampa-bookmarks/account.json`
(`~/.local/state/lampa-bookmarks/account.json` by default), 0600 perms.

## Commands

`lampa-cli [--json] [--domain cub.rip] <group> <verb>`. Output is human-readable
by default; the global `--json` flag switches every command to the structured
JSON the agent workflow relies on (see `.agent/skills/add-to-lampa.md`).

```bash
# auth
lampa-cli auth login|logout|status

# collections
lampa-cli collections list [--category user|new|top|week|month|big|all] [--page N]
lampa-cli collections view --id <CID> [--page N]
lampa-cli collections create --name "My Movies"        # idempotent by name
lampa-cli collections like --id <CID> [--unlike]

# items (movies/shows)
lampa-cli items search "Title YEAR"                     # caches card data on disk
lampa-cli items add --id <TMDB_ID> [--collection-id <CID>] [--type movie|tv]
lampa-cli items remove --id <TMDB_ID> --collection-id <CID> [--type movie|tv]
lampa-cli items bulk-add --input items.json [--collection-id <CID>] [--delay 0.3]

# bookmarks (favorites)
lampa-cli bookmarks list
lampa-cli bookmarks add --id <TMDB_ID> [--type movie|tv]
lampa-cli bookmarks remove --id <BOOKMARK_ID>           # bookmark id, not TMDB id
```

- `build`: `uv build` (hatchling). `test`: none yet (no `tests/` in tree).
  `lint`: none configured.

## Dependencies

Declared in `pyproject.toml` (`[project.dependencies]`):

- `requests>=2.28` — HTTP client for cub.rip / apitmdb proxy.
- `pydantic>=2.0` — response models, including the deliberately misspelled
  `secuses` field that mirrors the API.
- `typer>=0.12` — CLI framework (pulls in click + rich).

No dev deps pinned. (`python-dotenv` and `requirements.txt` were removed in the
move to a packaged CLI.)

## Config / state / cache (XDG, app name `lampa-bookmarks`)

| File | Default path | Override env | Purpose |
|---|---|---|---|
| `settings.json` | `~/.config/lampa-bookmarks/` | `XDG_CONFIG_HOME` | `{domain, protocol, timeout}` (cub.rip / https / 8000) |
| `account.json` | `~/.local/state/lampa-bookmarks/` | `XDG_STATE_HOME` | Saved token + profile, 0600, auto-written by `auth login` |
| `search_cache.json` | `~/.cache/lampa-bookmarks/` | `XDG_CACHE_HOME` | `tmdb_id -> card data`, written by `items search`, consumed by `items add`/`remove` |

Paths are derived by `src/lampa_cli/utils.py:_xdg()`; `src/lampa_cli/search.py`
imports `CACHE_DIR` from there. None of these files live in the repo.
