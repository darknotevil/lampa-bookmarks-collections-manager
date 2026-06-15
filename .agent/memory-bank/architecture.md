# Architecture — Lampa bookmarks manager

CLI + Python library that talks to the **cub.rip** Lampa MX backend to manage
collections and bookmarks. Two consumption surfaces share the same core:

- `examples/add_items.py` — interactive, human-facing CLI.
- `examples/agent_tool.py` — JSON-only CLI for LLM agents (no prompts, structured output).

Both are thin wrappers over the library code; don't reintroduce per-script
copies of search/card helpers.

## Module map

```
src/
  client.py   # LampaClient — all HTTP + API methods
  models.py   # Pydantic models for API responses
  auth.py     # auth helpers (device-code + token login)
  search.py   # shared search/card logic + on-disk result cache
  utils.py    # XDG paths, settings/account IO, URL builders, query parsing
examples/
  login.py              # device-code / token login
  list_collections.py   # browse collections
  create_collection.py  # create a collection
  add_items.py          # interactive add (human-facing)
  agent_tool.py         # JSON-only CLI for LLM agents
  bulk_add_movies.py    # bulk-add helper
```

User-state lives outside the repo under XDG base dirs (app name
`lampa-bookmarks`):

- `$XDG_CONFIG_HOME/lampa-bookmarks/settings.json` — domain/protocol/timeout
- `$XDG_STATE_HOME/lampa-bookmarks/account.json` — saved token + profile,
  0600 perms, dir 0700 (created by `save_account` in `src/utils.py`)
- `$XDG_CACHE_HOME/lampa-bookmarks/search_cache.json` — `tmdb_id -> full card
  data`, written by `save_search_cache` in `src/search.py`

Paths are derived via the `_xdg(env_var, fallback)` helper in `src/utils.py`;
`src/search.py` imports `CACHE_DIR` from there. **No path constants point at the
repo root** — the project used to keep these in `config/` but was migrated to
XDG to stop polluting `$PROJECT_ROOT` and to give `account.json` proper
permissions.

`src/search.py` is the **single source of truth** for searching and shaping
results — both CLIs delegate to it.

## Two-step agent workflow (token-efficient)

1. `agent_tool.py search "Title YEAR"` → returns compact JSON results **and**
   writes the full card data of every hit to
   `$XDG_CACHE_HOME/lampa-bookmarks/search_cache.json` keyed by `tmdb_id`.
2. `agent_tool.py add --tmdb-id <id> [--collection-id <id>]` → recovers the
   card data + media_type from the cache. No `--card-data`, no `--type` needed.

Why the cache exists: previously the agent had to copy the whole card_data
JSON (poster_path, vote_average, …) back into `--card-data` on every add — heavy
token round-trips. The cache removes that; agent output is also trimmed (no
poster paths / ratings in search results).

For many titles, `bulk-add` reads a JSON file, dedups, year-matches, prefers the
original title, and returns one structured report — preferred over looping
`search` + `add`.

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
- **`bookmarks/dump` returns text/plain**, one JSON bookmark per line — parsed
  manually in `list_bookmarks`, not via the JSON helper.
- **Search sources & priority:** catalog → search/multi → movie → tv → anime.
  Catalog is best for localized content (e.g. Russian cartoons). `search/multi`
  filters out people; **catalog does NOT** — `search.py` strips
  `media_type == "person"` itself.
- **`media_type` shape differs:** movies use `title`/`original_title`/`release_date`,
  TV uses `name`/`original_name`/`first_air_date`. `build_card_data` handles both.
- **`parse_search_query`** strips trailing 4-digit years (19xx/20xx) and noise
  words ("фильм", "сериал", "movie", "show", …) — TMDB search works better
  without them. Year is returned separately for result filtering.

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
