# Architecture — Lampa bookmarks manager

CLI + Python library that talks to the **cub.rip** Lampa MX backend to manage
collections and bookmarks. A single packaged command, **`lampa-cli`** (Typer),
serves both consumers from the same core:

- default output — human-readable text.
- `--json` global flag — structured JSON for LLM agents (no prompts).

The `cli/` modules are thin wrappers over the library code; don't reintroduce
per-command copies of search/card helpers.

## Module map

```
pyproject.toml            # hatchling; [project.scripts] lampa-cli = lampa_cli.cli:main
src/lampa_cli/
  client.py   # LampaClient — all HTTP + API methods
  models.py   # Pydantic models for API responses
  auth.py     # auth helpers (device-code + token login)
  search.py   # shared search/card logic + on-disk result cache
  utils.py    # XDG paths, settings/account IO, URL builders, query parsing
  cli/
    __init__.py     # root Typer app, global --json/--domain, main()
    _output.py      # State + JSON/error output sinks
    auth.py         # auth login/logout/status
    collections.py  # collections list/view/create/like (+ find_collection_by_name)
    items.py        # items search/add/remove/bulk-add
    bookmarks.py    # bookmarks list/add/remove
    backup.py       # backup export/import (favorites + collections)
```

User-state lives outside the repo under XDG base dirs (app name
`lampa-bookmarks`):

- `$XDG_CONFIG_HOME/lampa-bookmarks/settings.json` — domain/protocol/timeout
- `$XDG_STATE_HOME/lampa-bookmarks/account.json` — saved token + profile,
  0600 perms, dir 0700 (created by `save_account` in `src/utils.py`)
- `$XDG_CACHE_HOME/lampa-bookmarks/search_cache.json` — `tmdb_id -> full card
  data`, written by `save_search_cache` in `src/search.py`

Paths are derived via the `_xdg(env_var, fallback)` helper in
`src/lampa_cli/utils.py`; `src/lampa_cli/search.py` imports `CACHE_DIR` from
there. **No path constants point at the repo root** — the project used to keep
these in `config/` but was migrated to XDG to stop polluting `$PROJECT_ROOT` and
to give `account.json` proper permissions.

`src/lampa_cli/search.py` is the **single source of truth** for searching and
shaping results — every `items` subcommand delegates to it.

## Two-step agent workflow (token-efficient)

1. `lampa-cli --json items search "Title YEAR"` → returns compact JSON results
   **and** writes the full card data of every hit to
   `$XDG_CACHE_HOME/lampa-bookmarks/search_cache.json` keyed by `tmdb_id`.
2. `lampa-cli --json items add --id <id> [--collection-id <id>]` → recovers the
   card data + media_type from the cache. No card data, no `--type` needed.

Why the cache exists: previously the agent had to copy the whole card_data
JSON (poster_path, vote_average, …) back into `--card-data` on every add — heavy
token round-trips. The cache removes that; agent output is also trimmed (no
poster paths / ratings in search results).

For many titles, `items bulk-add` reads a JSON file, dedups, year-matches,
prefers the original title, and returns one structured report — preferred over
looping `search` + `add`.

## API quirks (non-obvious, easy to get wrong)

- **Write endpoints are form-urlencoded, not JSON.** `create`, `collections/add`,
  `bookmarks/add`, `bookmarks/remove` use `_form_request` with
  `application/x-www-form-urlencoded`. Read endpoints use JSON via `_request`.
- **Write endpoints want token as a COOKIE, profile as a HEADER** — not the
  header-token setup used by read endpoints. See `_form_request`.
- **`secuses` is the real (misspelled) success field** in API responses. Models
  mirror the typo on purpose (`AddItemResponse.secuses`, etc.). Don't "fix" it.
- **`add_bookmark` without card_data re-fetches from TMDB** (`apitmdb` proxy),
  which **404s for some ids**. Always pass card_data when you already have it
  (search results / cache). Collection adds only need `tmdb_id` + `card_type`.
- **`bookmarks/dump` returns text/plain**, parsed manually in `list_bookmarks`
  (not via the JSON helper). It may answer either as a single wrapper object
  (`{"secuses": true, "bookmarks": [...], "version": ...}`) or one JSON bookmark
  per line; `list_bookmarks` normalises both to a flat list.
- **`bookmarks/remove` reports `secuses: false` even on success** — the delete
  still happens. Don't trust the flag as a hard failure signal for removals.
- **Search sources & priority:** catalog → search/multi → movie → tv → anime.
  Catalog is best for localized content (e.g. Russian cartoons). `search/multi`
  filters out people; **catalog does NOT** — `search.py` strips
  `media_type == "person"` itself.
- **`media_type` shape differs:** movies use `title`/`original_title`/`release_date`,
  TV uses `name`/`original_name`/`first_air_date`. `build_card_data` handles both.
- **`parse_search_query`** strips trailing 4-digit years (19xx/20xx) and noise
  words ("фильм", "сериал", "movie", "show", …) — TMDB search works better
  without them. Year is returned separately for result filtering.

## Backup / restore (no server-side dump exists)

- **cub.rip's built-in "Backup" is useless for this tool.** Lampa's
  `core/account/backup.js` (`users/backup/export` / `import`) just serializes
  the browser `localStorage` to the cloud — it does NOT carry server-side
  bookmarks/collections. There is **no `collections/dump`** endpoint (returns
  404). So a real backup is assembled by enumeration.
- **`backup export`** walks `list_all_user_collections()` +
  `view_all_collection_items(id, items_count)` and `list_bookmarks()`. Format:
  `{version, exported_at, account, bookmarks:[raw dump dicts], collections:[{title, items_count, items:[{tmdb_id, media_type, title}]}]}`.
  Bookmarks are stored raw (full card `data` → exact restore); collection items
  are compact (id+type+title is all restore needs).
- **`collections/view` is lossy AND filters per raw page.** It returns only
  TMDB-resolvable cards (a collection backs up with fewer items than
  `items_count` — e.g. a docs collection 53→4). The drop happens *after* the
  fixed raw-page window of **20**, so an entire page can resolve to 0 cards
  while later pages still have items → **never stop at the first empty page.**
  `view_all_collection_items` walks exactly `ceil(items_count / 20)` pages
  (`LampaClient.VIEW_PAGE_SIZE = 20`); stop-on-empty is only the fallback when
  `items_count` is unknown.
- **`cid` for user collections comes from the TOKEN, not `account.id`.** The
  customer id is base64 in the token's first dot-segment (`{"id": <cid>}`); a
  token-based login can leave `account.id` holding the *profile* id, which made
  user-collection listing return nothing. `LampaClient._customer_id()` decodes
  the token (falls back to `account.id`) and `list_collections(category="user")`
  uses it — so user listing / idempotent create / backup all work regardless of
  how the session was created.
- **`backup import`** is idempotent: it pre-maps existing user collections by
  name (cub allows duplicate names, so blind create would spawn dupes on
  re-run), reuses or creates, then re-adds items/bookmarks via `add_with_dedup`
  (HTTP 500 / already-present = success). `--dry-run` is fully offline (no
  auth, no writes); `--only all|bookmarks|collections` scopes both directions.

## ID reference

| ID | Source | Example |
|----|--------|---------|
| Collection ID | `create_collection` / `list_collections` | `2948` |
| TMDB ID (card_id) | TMDB search / movie URL | `550` (Fight Club) |
| Profile ID | account after login | `780890` |
| User ID (cid) | account after login | `732666` |

## Mirrors

`cub.rip` (primary), `durex.monster`, `cubnotrip.top` — set in
`$XDG_CONFIG_HOME/lampa-bookmarks/settings.json`.
