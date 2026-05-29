---
name: add-to-lampa
description: adding movie to lampa
---

# Add To Lampa

## Overview

Use the `agent_tool.py` script to add movies/TV shows to Lampa bookmarks or
collections. All commands output structured JSON — no interactive prompts.

`search` caches the full data of every result on disk, so `add` only needs the
TMDB id: it recovers the title, poster and media type from that cache itself.
You never have to copy card data around.

**Working directory:** `lampa-bookmarks-collections-manager`

**Commands:** `search`, `add`, `list-collections`, `create-collection`,
`bulk-add`. For more than a handful of titles, prefer **`bulk-add`** (one pass,
one JSON report) over looping `search`+`add` — see *Bulk Workflow* below.

## Two-Step Workflow

### Step 1 — Search

Run a search to get TMDB ids for the movie/show:

```bash
cd lampa-bookmarks-collections-manager && uv run examples/agent_tool.py search "Movie Title YEAR"
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
the localized side. (`bulk-add` does this for every item too.)

### Step 2 — Add

Add the selected item using only the TMDB id from `results[N]`:

```bash
cd lampa-bookmarks-collections-manager && uv run examples/agent_tool.py add --tmdb-id <ID>
```

To add to a specific collection instead of bookmarks:

```bash
cd lampa-bookmarks-collections-manager && uv run examples/agent_tool.py add --tmdb-id <ID> --collection-id <COLLECTION_ID>
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
cd lampa-bookmarks-collections-manager && uv run examples/agent_tool.py list-collections
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
cd lampa-bookmarks-collections-manager && uv run examples/agent_tool.py create-collection --name "My Movies"
```

Output: `{"id": "3051", "title": "My Movies", "created": true}`. If a collection
with that name already exists, you get its id with `"created": false`. Use the
returned `id` as `--collection-id` when adding.


### Classifying anime / cartoon / movie

When the source doesn't label the type, decide with:
- The TMDB `media_type` (`movie` vs `tv`) from the search result
- **Animation** genre + Japanese origin → anime; **Animation** genre otherwise → cartoon
- The surrounding context (article/list title mentions "аниме", "мультфильмы", a studio like Ghibli/Pixar/Disney)
- Otherwise → movie

## Bulk Workflow

For many titles, write them to a JSON file once and add them in a **single pass**
with `bulk-add`. This amortizes startup, dedups, year-matches, prefers the
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
cd lampa-bookmarks-collections-manager && uv run examples/agent_tool.py bulk-add --input items.json

# Or force everything into one collection
cd lampa-bookmarks-collections-manager && uv run examples/agent_tool.py bulk-add --input items.json --collection-id 3051
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
   cd lampa-bookmarks-collections-manager && uv run examples/agent_tool.py search "Сексуальная тварь 2000"
   ```
   From `results`, pick index 0: `{"id": "11826", "year": 2001, "media_type": "movie"}` (closest year match to 2000).

2. **Add** (just the id from `results[0]`):
   ```bash
   cd lampa-bookmarks-collections-manager && uv run examples/agent_tool.py add --tmdb-id 11826
   ```

## Important Rules

- For **many titles, use `bulk-add`** with a JSON file — don't loop `search`+`add`
- **Always** run `search` before a single `add` — `add` relies on the cache that `search` writes (`bulk-add` searches internally, so it needs no prior `search`)
- **NEVER** invent or guess a TMDB id — use ONLY the `id` values from the `results` array
- **Always** include the year in the search query when known (e.g. `"Фукусима 2020"`)
- `status: "already_exists"` is **success** — never retry or re-diagnose a duplicate
- Use `create-collection --name` (idempotent) to get a collection id
- If no collection is specified, add to bookmarks (omit `--collection-id`)
