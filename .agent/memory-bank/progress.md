# Progress — Lampa bookmarks manager

## Done

- Device-code + token-based authentication, session persistence.
- List collections by category (user / new / top), view collection items.
- Create collections (idempotent via `collections create`).
- Like / unlike collections.
- Add items to collections (by TMDB ID).
- Add items to bookmarks (favorites), including with prebuilt card data.
- Remove bookmarks; remove items from a collection (`collections/remove-card`).
- List bookmarks via the text/plain `bookmarks/dump` endpoint.
- TMDB proxy integration (search + details).
- Agent-friendly JSON output (global `--json`) with on-disk search cache → tiny
  two-step workflow (`items search` then `items add` by TMDB id alone).
- `items bulk-add` single-pass JSON-driven importer with year/original-title matching.
- Packaged as the installable `lampa-cli` Typer command (`uv tool install`):
  unified `auth`/`collections`/`items`/`bookmarks` noun-verb groups replacing the
  old `examples/` scripts.
- `backup export` / `backup import` for favorites + collections (assembled by
  enumeration — no server-side dump exists). Export verified live (201
  bookmarks, 10 collections, 223 items); import validated offline + `--dry-run`
  only (not run against a live account yet). See architecture → "Backup /
  restore" for the lossy-`view` and token-`cid` gotchas.

## In progress

- _(nothing tracked here yet — fill in when an active workstream starts)_

## Next

- Verify `backup import` end-to-end against a live (throwaway) account — only
  export + offline dry-run have been exercised so far.
- Import collections from **mdblist.com** (lists arrive with TMDB ids ready —
  skips the search step entirely).
- Lampa plugin combining collections + bookmarks in one UI.

## Known issues / open questions

- **Token expiry** behavior is unknown; long sessions may need a refresh path.
- **API rate limits** are unknown.
- `tests/` directory is referenced in `README.md` but not yet present in the
  tree.
- `add_bookmark` without `card_data` falls back to the `apitmdb` proxy, which
  **404s for some ids** — always pass `card_data` when available.
