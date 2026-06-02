"""
Shared search helpers for Lampa MX.

This module is the single source of truth for searching titles and shaping
the results. Both the interactive human CLI (``examples/add_items.py``) and
the agent JSON CLI (``examples/agent_tool.py``) build on top of it, so the
multi-source search, year matching and card-data shaping live in exactly
one place.

It also keeps a tiny on-disk cache (``config/search_cache.json``) that maps
a TMDB id to the full "card data" produced by the last search. That lets the
``add`` step recover the card data by id alone — callers never have to pass
the bulky card JSON (poster paths, ratings, …) back in, which keeps agent
token usage low and avoids a TMDB re-fetch that can 404 for some ids.
"""

import json
from typing import Any, Dict, List, Optional, Tuple

import requests

from .utils import PROJECT_ROOT, parse_search_query

SEARCH_CACHE_PATH = PROJECT_ROOT / "config" / "search_cache.json"


# ============================================
# Field extraction (movies use *_title, TV uses *_name)
# ============================================

def get_year(item: Dict[str, Any]) -> int:
    """Extract the release/air year from a raw TMDB result item (0 if absent)."""
    date = item.get("release_date") or item.get("first_air_date")
    if date:
        try:
            return int(date[:4])
        except ValueError:
            return 0
    return 0


def get_title(item: Dict[str, Any]) -> str:
    """Get the display title from a raw TMDB result item."""
    return item.get("title") or item.get("name") or "Unknown"


def get_media_type(item: Dict[str, Any]) -> str:
    """Get the media type ('movie' or 'tv') from a raw TMDB result item."""
    return item.get("media_type", "movie")


def build_card_data(item: Dict[str, Any]) -> Dict[str, Any]:
    """Build the minimal card data that ``LampaClient.add_bookmark`` expects.

    Passing this to ``add_bookmark`` lets it skip the TMDB re-fetch (which can
    404 for some ids). The shape differs for movies vs TV shows — see
    ``add_bookmark`` for the exact fields the API wants.
    """
    media_type = get_media_type(item)
    card: Dict[str, Any] = {
        "id": item.get("id"),
        "poster_path": item.get("poster_path", ""),
        "vote_average": item.get("vote_average", 0),
        "media_type": media_type,
    }
    if media_type == "movie":
        card["title"] = item.get("title", "")
        card["original_title"] = item.get("original_title", item.get("title", ""))
        card["release_date"] = item.get("release_date", "")
    else:
        card["name"] = item.get("name", "")
        card["original_name"] = item.get("original_name", item.get("name", ""))
        card["first_air_date"] = item.get("first_air_date", "")
    return card


def normalize_result(item: Dict[str, Any]) -> Dict[str, Any]:
    """Build a compact dict for display / JSON output.

    Deliberately omits poster paths and ratings: they are noise for picking a
    title and just burn tokens in agent output. The full card data is kept in
    the search cache instead (see :func:`save_search_cache`).
    """
    result = {
        "id": str(item.get("id")),
        "title": get_title(item),
        "media_type": get_media_type(item),
    }
    original = item.get("original_title") or item.get("original_name")
    if original and original != result["title"]:
        result["original_title"] = original
    year = get_year(item)
    if year:
        result["year"] = year
    return result


# ============================================
# Multi-source search
# ============================================

def search_titles(
    client,
    query: str,
    *,
    merge: bool = False,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Run a multi-source search and return deduplicated raw TMDB items.

    Sources are queried in priority order: CUB catalog (best for localized
    content), then ``search/multi``, then movies, TV and anime.

    Args:
        client: An authenticated ``LampaClient``.
        query: Cleaned search title (year/noise words already stripped).
        merge: If True, merge results from every source (used by interactive
            selection). If False, the first non-empty source wins.
        limit: Maximum number of results to return.

    Returns:
        Deduplicated list of raw result dicts (``person`` results removed).
    """
    sources = [
        client.search_catalog(query),
        client.search_multi(query),
        client.search_movies(query),
        client.search_tv(query),
        client.search_anime(query),
    ]

    if merge:
        ordered = [item for source in sources for item in source]
    else:
        ordered = next((source for source in sources if source), [])

    seen = set()
    results: List[Dict[str, Any]] = []
    for item in ordered:
        if get_media_type(item) == "person":
            continue
        item_id = item.get("id")
        if item_id in seen:
            continue
        seen.add(item_id)
        results.append(item)
        if len(results) >= limit:
            break
    return results


def match_year(
    results: List[Dict[str, Any]],
    year: Optional[int],
) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    """Filter results by an extracted year.

    Returns ``(chosen, matches)`` where ``matches`` is every result for that
    year and ``chosen`` is the single result when exactly one matches (else
    None, so the caller can decide how to disambiguate).
    """
    if not year:
        return None, []
    matches = [item for item in results if get_year(item) == year]
    chosen = matches[0] if len(matches) == 1 else None
    return chosen, matches


# ============================================
# Search cache (tmdb_id -> card data)
# ============================================

def save_search_cache(results: List[Dict[str, Any]]) -> None:
    """Persist card data for each result, keyed by TMDB id.

    Overwrites the previous cache so it always reflects the latest search.
    """
    cache = {str(item.get("id")): build_card_data(item) for item in results}
    SEARCH_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SEARCH_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)


def get_cached_card(tmdb_id: str) -> Optional[Dict[str, Any]]:
    """Return cached card data for a TMDB id, or None if not cached."""
    if not SEARCH_CACHE_PATH.exists():
        return None
    try:
        with open(SEARCH_CACHE_PATH, "r", encoding="utf-8") as f:
            cache = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    return cache.get(str(tmdb_id))


# ============================================
# High-level helpers (search-then-pick, idempotent add)
#
# Shared by the agent CLI (``examples/agent_tool.py``) and the bulk runner so
# the "prefer the original title", year-matching and duplicate handling live in
# exactly one place.
# ============================================

def clean_search_title(title: str) -> str:
    """Return the best part of a title to search TMDB with.

    Article lists often give titles as ``"Русское / Original"``. The original
    (latin) side matches TMDB far more reliably, so when a ``" / "`` separator
    is present we use the last part. Otherwise the title is returned unchanged.
    """
    if " / " in title:
        return title.split(" / ")[-1].strip()
    return title.strip()


def search_and_get_id(
    client,
    title: str,
    *,
    limit: int = 10,
) -> Optional[Tuple[str, str, Dict[str, Any]]]:
    """Search for ``title`` and pick the best match.

    Applies :func:`clean_search_title` (prefer the original name), strips the
    year/noise via :func:`parse_search_query`, runs the multi-source
    :func:`search_titles`, then prefers a result whose year matches the year
    parsed from the query (via :func:`match_year`), falling back to the first
    result.

    Returns ``(tmdb_id, media_type, card_data)`` or ``None`` if nothing matched.
    """
    query_title, query_year = parse_search_query(clean_search_title(title))
    if not query_title:
        return None

    results = search_titles(client, query_title, merge=True, limit=limit)
    if not results:
        return None

    chosen, _ = match_year(results, query_year)
    if chosen is None:
        chosen = results[0]
    return str(chosen["id"]), get_media_type(chosen), build_card_data(chosen)


def add_with_dedup(
    client,
    tmdb_id: str,
    media_type: str,
    card_data: Optional[Dict[str, Any]],
    collection_id: Optional[str] = None,
) -> Tuple[str, Optional[str]]:
    """Add an item to a collection or bookmarks, treating duplicates as success.

    The write endpoints answer an already-present item with HTTP 500 (see
    ``LampaClient._form_request``), which would otherwise look like a hard
    failure. We map that to the idempotent ``"already_exists"`` status so
    re-runs don't produce false negatives.

    Returns ``(status, error)`` where status is one of ``"added"``,
    ``"already_exists"`` or ``"error"`` (with ``error`` set only for the last).
    """
    try:
        if collection_id:
            response = client.add_item_to_collection(
                collection_id=collection_id,
                tmdb_id=tmdb_id,
                media_type=media_type,
            )
        else:
            response = client.add_bookmark(tmdb_id, media_type, card_data=card_data)

        if bool(response.secuses):
            return "added", None
        return "error", f"secuses=False: {response.model_dump()}"
    except requests.exceptions.HTTPError as e:
        status_code = getattr(e.response, "status_code", None)
        if status_code == 500:
            # Server rejects an item that is already present with a 500.
            return "already_exists", None
        return "error", str(e)
    except Exception as e:  # network errors, validation, etc.
        return "error", str(e)


def remove_with_dedup(
    client,
    tmdb_id: str,
    media_type: str,
    collection_id: str,
) -> Tuple[str, Optional[str]]:
    """Remove an item from a collection, treating "not present" as success.

    Mirrors :func:`add_with_dedup`. A card that isn't in the collection is
    answered by the server with an error (HTTP 500 / ``secuses:false``); we map
    that to the idempotent ``"not_found"`` status so re-runs don't fail.

    Returns ``(status, error)`` where status is one of ``"removed"``,
    ``"not_found"`` or ``"error"`` (with ``error`` set only for the last).
    """
    try:
        response = client.remove_card_from_collection(
            collection_id=collection_id,
            tmdb_id=tmdb_id,
            media_type=media_type,
        )

        if bool(response.secuses):
            return "removed", None
        return "not_found", None
    except requests.exceptions.HTTPError as e:
        status_code = getattr(e.response, "status_code", None)
        if status_code == 500:
            # Removing an item that isn't there comes back as a 500.
            return "not_found", None
        return "error", str(e)
    except Exception as e:  # network errors, validation, etc.
        return "error", str(e)
