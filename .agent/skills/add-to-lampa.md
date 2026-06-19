---
name: add-to-lampa
description: adding movie to lampa
---

# Add To Lampa

## Overview

Use the installed `lampa-cli` command to add movies/TV shows to Lampa bookmarks
or collections. Pass the global `--json` flag so every command outputs
structured JSON with no interactive prompts.

`items search` caches the full data of every result on disk, so `items add` only
needs the TMDB id: it recovers the title, poster and media type from that cache
itself. You never have to copy card data around.

**Prerequisite:** an authenticated session (`lampa-cli auth login`). The session,
config and search cache live in XDG dirs, so the command works from any
directory.

**Commands:** `items search`, `items add`, `items remove`, `collections list`,
`collections create`, `items bulk-add`. For more than a handful of titles, prefer
**`items bulk-add`** (one pass, one JSON report) over looping `search`+`add` —
see *Bulk Workflow* below.

## Two-Step Workflow

### Step 1 — Search

Run a search to get TMDB ids for the movie/show:

```bash
lampa-cli --json items search "Movie Title YEAR"
```

Example output:
```json
{
  "query": "Sexy Beast",
  "year": 2000,
  "results": [
    {"id": "11826", "title": "Сексуальная тварь", "original_title": "Sexy Beast", "year": 2001, "media_type": "movie"}
  ]
}
```

**How to pick the correct result:**
- Match `year` to the requested year (or closest if an exact match is missing)
- Use `original_title` to disambiguate when `title` is localized
- Check `media_type` — "movie" for films, "tv" for series

**Titles like `"Русское / Original"`:** pass them as-is. The tool searches by the
**original (latin) part** automatically — it matches TMDB far more reliably than
the localized side. (`items bulk-add` does this for every item too.)

### Step 2 — Add

Add the selected item using only the TMDB id from `results[N]`:

```bash
lampa-cli --json items add --id <ID>
```

To add to a specific collection instead of bookmarks:

```bash
lampa-cli --json items add --id <ID> --collection-id <COLLECTION_ID>
```

The media type is taken from the cached search result. Pass `--type movie|tv`
only as a fallback when you add an id that did not come from a `search` run.

**Output `status` field — adding is idempotent:**
- `"added"` — newly added (`success: true`)
- `"already_exists"` — the item was already there (`success: true`, exit 0). This
  is **not an error** — do NOT retry, re-search, or "diagnose" it.
- `"error"` — a real failure (`success: false`, exit 1); `error` explains why.

## Optional — List Collections

If you need to find a collection id first:

```bash
lampa-cli --json collections list
```

Example output:
```json
{
  "collections": [
    {"id": "2948", "title": "My Movies", "items_count": 42, "views": 100, "username": "user"},
    {"id": "3100", "title": "Anime", "items_count": 15, "views": 30, "username": "user"}
  ]
}
```

## Creating a Collection

Create (or reuse) a collection by name — **idempotent**, so it never makes a
duplicate:

```bash
lampa-cli --json collections create --name "My Movies"
```

Output: `{"id": "3051", "title": "My Movies", "created": true}`. If a collection
with that name already exists, you get its id with `"created": false`. Use the
returned `id` as `--collection-id` when adding.


## Removing from a Collection

Remove a movie/show from a specific collection by TMDB id. The media type comes
from the search cache (run `items search` first), or pass `--type` as a fallback.

```bash
lampa-cli --json items remove --id <ID> --collection-id <CID>
```

**Output `status` field — removing is idempotent:**
- `"removed"` — the item was removed (`success: true`)
- `"not_found"` — it wasn't in the collection (`success: true`, exit 0). This is
  **not an error** — do NOT retry or "diagnose" it.
- `"error"` — a real failure (`success: false`, exit 1); `error` explains why.

`--collection-id` is **required** — `items remove` only removes from a collection
(this is the `collections/remove-card` endpoint). Removing a plain
bookmark/favorite is a different operation (`lampa-cli bookmarks remove`).

### Classifying anime / cartoon / movie

When the source doesn't label the type, decide with:
- The TMDB `media_type` (`movie` vs `tv`) from the search result
- **Animation** genre + Japanese origin → anime; **Animation** genre otherwise → cartoon
- The surrounding context (article/list title mentions "аниме", "мультфильмы", a studio like Ghibli/Pixar/Disney)
- Otherwise → movie

## Bulk Workflow

For many titles, write them to a JSON file once and add them in a **single pass**
with `items bulk-add`. This amortizes startup, dedups, year-matches, prefers the
original title, and returns one structured report — far better than looping
`search`+`add` per title.

**Input file** — a JSON list of items (or `{"items": [...]}`):

```json
[
  {"title": "Враг / Enemy", "year": 2013},
  {"title": "Black Swan", "year": 2010, "type": "movie"},
  {"title": "Атака титанов", "collection": "Аниме"}
]
```

Per-item fields: `title` (required), `year`, `type` (`movie`|`tv`), `collection`
(name — created/reused automatically).

```bash
# Per-item destinations (each item's "collection" name, else bookmarks)
lampa-cli --json items bulk-add --input items.json

# Or force everything into one collection
lampa-cli --json items bulk-add --input items.json --collection-id 3051
```

Output report:
```json
{
  "total": 3, "added": 2, "already_exists": 1, "not_found": 0, "errors": 0,
  "items": [ {"title": "...", "status": "added", "tmdb_id": "...", "target": "bookmarks"} ]
}
```

`already_exists` counts as success. Only `not_found` (no TMDB match) and `errors`
need follow-up — record those titles for the user.

## Full Example

Add "Сексуальная тварь 2000" to bookmarks:

1. **Search:**
   ```bash
   lampa-cli --json items search "Сексуальная тварь 2000"
   ```
   From `results`, pick index 0: `{"id": "11826", "year": 2001, "media_type": "movie"}` (closest year match to 2000).

2. **Add** (just the id from `results[0]`):
   ```bash
   lampa-cli --json items add --id 11826
   ```

## Important Rules

- For **many titles, use `items bulk-add`** with a JSON file — don't loop `search`+`add`
- **Always** run `items search` before a single `items add` — `add` relies on the cache that `search` writes (`bulk-add` searches internally, so it needs no prior `search`)
- **NEVER** invent or guess a TMDB id — use ONLY the `id` values from the `results` array
- **Always** include the year in the search query when known (e.g. `"Фукусима 2020"`)
- `status: "already_exists"` is **success** — never retry or re-diagnose a duplicate
- `status: "not_found"` from `items remove` is **success** (item wasn't there) — don't retry
- Use `collections create --name` (idempotent) to get a collection id
- If no collection is specified, add to bookmarks (omit `--collection-id`)
- `items remove` needs `--collection-id` and removes only from that collection
