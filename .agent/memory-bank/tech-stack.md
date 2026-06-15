# Tech stack — Lampa bookmarks manager

Python 3.13 (per `.venv` / `__pycache__/*.cpython-313.pyc`). Pure-Python, no
build step.

## Setup

```bash
pip install -r requirements.txt
# or, since skill.md uses uv:
uv pip install -r requirements.txt
```

First-time login (one of):

```bash
python examples/login.py --code 123456                    # device code from https://cub.rip/add
python examples/login.py --token TOKEN --profile PROFILE  # existing session
```

Account is persisted to `$XDG_STATE_HOME/lampa-bookmarks/account.json`
(`~/.local/state/lampa-bookmarks/account.json` by default), 0600 perms.

## Commands

- `run` (interactive CLI):
  ```bash
  python examples/add_items.py --search "Title" [-i]
  python examples/list_collections.py --category user
  python examples/create_collection.py --name "My Movies"
  ```
- `run` (agent / JSON CLI — see `.agent/skills/add-to-lampa.md`):
  ```bash
  uv run examples/agent_tool.py search "Title YEAR"
  uv run examples/agent_tool.py add --tmdb-id <ID> [--collection-id <CID>]
  uv run examples/agent_tool.py bulk-add --input items.json
  uv run examples/agent_tool.py list-collections
  uv run examples/agent_tool.py create-collection --name "..."
  uv run examples/agent_tool.py remove --tmdb-id <ID> --collection-id <CID>
  ```
- `build`: none (pure Python).
- `test`: `python -m pytest tests/` _(test directory is referenced in README but
  not yet present in the tree — add as the project grows)._
- `lint`: none configured.

## Dependencies

Runtime (`requirements.txt`):

- `requests>=2.28.0` — HTTP client for cub.rip / apitmdb proxy.
- `pydantic>=2.0.0` — response models, including the deliberately misspelled
  `secuses` field that mirrors the API.
- `python-dotenv>=1.0.0` — `.env` loading for local config / secrets.

No dev deps pinned.

## Config / state / cache (XDG, app name `lampa-bookmarks`)

| File | Default path | Override env | Purpose |
|---|---|---|---|
| `settings.json` | `~/.config/lampa-bookmarks/` | `XDG_CONFIG_HOME` | `{domain, protocol, timeout}` (cub.rip / https / 8000) |
| `account.json` | `~/.local/state/lampa-bookmarks/` | `XDG_STATE_HOME` | Saved token + profile, 0600, auto-written by `login.py` |
| `search_cache.json` | `~/.cache/lampa-bookmarks/` | `XDG_CACHE_HOME` | `tmdb_id -> card data`, written by `search`, consumed by `add`/`remove` |

Paths are derived by `src/utils.py:_xdg()`; `src/search.py` imports `CACHE_DIR`
from there. None of these files live in the repo — `config/` was retired
during XDG migration.
