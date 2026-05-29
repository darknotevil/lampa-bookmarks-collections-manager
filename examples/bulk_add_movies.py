#!/usr/bin/env python3
"""
Bulk add movies from parsed results to Lampa bookmarks/collections.

Workflow:
1. Load parsed_results.json from movies_to_parse
2. Classify: anime -> anime collection, cartoons -> cartoon collection
3. Articles with 10+ items -> themed collection, <10 -> bookmarks
4. Search each title, add to appropriate destination
5. Log failures to failed_to_fetch
"""

import json
import sys
import os
import time
import re
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.client import LampaClient
from src.search import add_with_dedup, search_and_get_id

# Paths
PARSED_RESULTS = os.path.expanduser("~/movies_to_parse/parsed_results.json")
FAILED_FILE = os.path.expanduser("~/movies_to_parse/failed_to_fetch")
LOG_FILE = os.path.expanduser("~/movies_to_parse/add_log.txt")

# Category keywords for classification
ANIME_KEYWORDS = {"аниме", "anime", "studio ghibli", "吉卜力", "宮崎", "新海", "大友"}
CARTOON_KEYWORDS = {"мульт", "cartoon", "disney", "pixar", "animated", "анимаци"}


def classify_item(item, page_title=""):
    """Classify an item as anime, cartoon, or movie based on title and context."""
    title_lower = item.get("title", "").lower()
    hint = item.get("type_hint", "movie")
    context = page_title.lower()

    # Explicit type_hint from parser
    if hint == "cartoon":
        return "cartoon"
    if hint == "anime":
        return "anime"

    # Check context
    if any(kw in context for kw in CARTOON_KEYWORDS):
        return "cartoon"
    if any(kw in context for kw in ANIME_KEYWORDS):
        return "anime"

    # Check title for known patterns
    known_anime = {"нава", "души", "унесенные призраками", "порко", "кайко",
                   "spirited away", "princess mononoke", "howl", "totoro",
                   "your name", "weathering with you", "akira", "ghost in the shell",
                   "евangelion", "атака титанов", "one piece", "naruto"}
    known_cartoons = {"лило и стич", "как приручить дракона", "Finding nemo",
                      "up", "wall-e", "coco", "moana", "frozen", "toy story",
                      "shrek", "madagascar", "kung fu panda", "zootopia",
                      "маша и медведь", "смешарики"}

    for kw in known_anime:
        if kw in title_lower:
            return "anime"
    for kw in known_cartoons:
        if kw in title_lower:
            return "cartoon"

    return "movie"


def create_collection_if_not_exists(client, name, existing_collections):
    """Create a collection if it doesn't already exist. Returns collection ID."""
    # Check if it exists
    for coll in existing_collections:
        if name.lower() in coll.get("title", "").lower():
            return coll["id"], False

    # Create new collection
    print(f"  Creating collection: {name}")
    try:
        response = client.create_collection(name)
        coll_id = str(response.collection.id)
        print(f"  Created: {coll_id}")
        return coll_id, True
    except Exception as e:
        print(f"  ERROR creating collection '{name}': {e}")
        return None, False


def main():
    parser = argparse.ArgumentParser(description="Bulk add movies to Lampa")
    parser.add_argument("--results", default=PARSED_RESULTS, help="Path to parsed results JSON")
    parser.add_argument("--dry-run", action="store_true", help="Only plan, don't add")
    parser.add_argument("--domain", default="cub.rip", help="CUB domain")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between API calls (seconds)")
    args = parser.parse_args()

    # Load parsed results
    with open(args.results, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Initialize client
    client = LampaClient(domain=args.domain)
    if not client.is_authenticated():
        print("ERROR: Not authenticated. Run login.py first.")
        sys.exit(1)

    # Get existing collections
    existing_collections = []
    try:
        resp = client.list_collections(category="user")
        for coll in resp.results:
            existing_collections.append({
                "id": str(coll.id),
                "title": coll.title,
                "items_count": coll.items_count,
            })
        print(f"Existing collections: {len(existing_collections)}")
        for c in existing_collections:
            print(f"  [{c['id']}] {c['title']} ({c['items_count']} items)")
    except Exception as e:
        print(f"Warning: Could not list collections: {e}")

    # Initialize log - write to file as we go
    log_fh = open(LOG_FILE, "w", encoding="utf-8")
    log_lines = []
    def log(msg):
        log_lines.append(msg)
        log_fh.write(msg + "\n")
        log_fh.flush()
        print(msg)
        sys.stdout.flush()

    log("=" * 60)
    log("Bulk add started")
    log("=" * 60)

    # Phase 1: Classify articles and plan collections
    collections_to_create = {}  # name -> article_index
    article_plans = []  # list of (article, collection_id_or_None, items)

    anime_items = []
    cartoon_items = []
    movie_items_for_bookmarks = []

    for idx, article in enumerate(data.get("successful", [])):
        url = article["url"]
        page_title = article.get("page_title", "")
        items = article.get("items", [])

        # Classify each item
        classified = {"anime": [], "cartoon": [], "movie": []}
        for item in items:
            cat = classify_item(item, page_title)
            classified[cat].append(item)

        # Global anime and cartoon collections
        anime_items.extend(classified["anime"])
        cartoon_items.extend(classified["cartoon"])

        # Movies: if 10+ items from one article -> themed collection
        movies = classified["movie"]
        if len(movies) >= 10:
            coll_name = page_title
            if coll_name not in collections_to_create:
                collections_to_create[coll_name] = idx
            article_plans.append((article, coll_name, movies))
        else:
            # < 10 items -> bookmarks
            movie_items_for_bookmarks.extend(movies)

    log(f"\nClassification summary:")
    log(f"  Anime items: {len(anime_items)}")
    log(f"  Cartoon items: {len(cartoon_items)}")
    log(f"  Movie collections (10+): {len(collections_to_create)}")
    for name in collections_to_create:
        log(f"    - {name}")
    log(f"  Movies for bookmarks (<10 from article): {len(movie_items_for_bookmarks)}")

    if args.dry_run:
        log("\n[DRY RUN] Would create collections and add items as planned above.")
        return

    # Phase 2: Create collections
    collection_ids = {}  # name -> id

    # Anime collection
    if anime_items:
        coll_id, _ = create_collection_if_not_exists(client, "Аниме", existing_collections)
        if coll_id:
            collection_ids["anime"] = coll_id
            existing_collections.append({"id": coll_id, "title": "Аниме", "items_count": 0})

    # Cartoon collection
    if cartoon_items:
        coll_id, _ = create_collection_if_not_exists(client, "Мультфильмы", existing_collections)
        if coll_id:
            collection_ids["cartoons"] = coll_id
            existing_collections.append({"id": coll_id, "title": "Мультфильмы", "items_count": 0})

    # Themed collections
    for coll_name in collections_to_create:
        coll_id, _ = create_collection_if_not_exists(client, coll_name, existing_collections)
        if coll_id:
            collection_ids[coll_name] = coll_id
            existing_collections.append({"id": coll_id, "title": coll_name, "items_count": 0})

    # Phase 3: Add all items
    failed_items = []
    added_count = 0
    total_items = (len(anime_items) + len(cartoon_items) +
                   sum(len(movies) for _, _, movies in article_plans) +
                   len(movie_items_for_bookmarks))

    log(f"\nAdding {total_items} items...")

    # Helper to add a batch
    def add_batch(items, collection_id, label):
        nonlocal added_count
        log(f"\n--- {label} ({len(items)} items) ---")
        for i, item in enumerate(items):
            title = item["title"]
            year = item.get("year", "")
            log(f"  [{i+1}/{len(items)}] {title} ({year})...")

            # Pass the year so the shared helper can year-match the results.
            query = f"{title} {year}" if year else title
            result = search_and_get_id(client, query)
            if result:
                tmdb_id, media_type, card_data = result
                status, err_msg = add_with_dedup(
                    client, tmdb_id, media_type, card_data, collection_id)
                if status == "added":
                    added_count += 1
                    log(f"    -> Added (TMDB: {tmdb_id})")
                elif status == "already_exists":
                    added_count += 1
                    log(f"    -> Already present (TMDB: {tmdb_id})")
                else:
                    log(f"    -> FAILED: {err_msg}")
                    failed_items.append({
                        "title": title, "year": year,
                        "reason": f"add_failed: {err_msg}", "tmdb_id": tmdb_id
                    })
            else:
                log(f"    -> NOT FOUND")
                failed_items.append({
                    "title": title, "year": year,
                    "reason": "not_found_in_search"
                })

            time.sleep(args.delay)

    # Add anime
    if collection_ids.get("anime"):
        add_batch(anime_items, collection_ids["anime"],
                  f"Anime -> {collection_ids['anime']}")

    # Add cartoons
    if collection_ids.get("cartoons"):
        add_batch(cartoon_items, collection_ids["cartoons"],
                  f"Cartoons -> {collection_ids['cartoons']}")

    # Add themed collection movies
    for article, coll_name, movies in article_plans:
        coll_id = collection_ids.get(coll_name)
        if coll_id:
            add_batch(movies, coll_id, f"Collection: {coll_name}")

    # Add bookmark movies
    if movie_items_for_bookmarks:
        add_batch(movie_items_for_bookmarks, None, "Bookmarks (favorites)")

    # Phase 4: Summary
    log("\n" + "=" * 60)
    log("SUMMARY")
    log("=" * 60)
    log(f"  Total items processed: {total_items}")
    log(f"  Successfully added: {added_count}")
    log(f"  Failed: {len(failed_items)}")

    # Save failed items
    all_failed = []
    # Add URL-level failures
    for fail in data.get("failed", []):
        all_failed.append({
            "type": "url_failed",
            "url": fail["url"],
            "reason": fail.get("reason", ""),
            "expected": fail.get("expected", ""),
        })
    # Add item-level failures
    for fail in failed_items:
        all_failed.append({
            "type": "item_failed",
            "title": fail["title"],
            "year": fail.get("year"),
            "reason": fail.get("reason", ""),
            "tmdb_id": fail.get("tmdb_id"),
        })

    # Write log file
    log_fh.write("\n".join(log_lines))
    log_fh.close()

    # Update failed_to_fetch file
    failed_md = "# Failed to Fetch\n\n"

    if any(f.get("type") == "url_failed" for f in all_failed):
        failed_md += "## URLs that could not be parsed\n\n"
        failed_md += "| # | URL | Reason |\n"
        failed_md += "|---|-----|--------|\n"
        for i, f in enumerate(all_failed):
            if f.get("type") == "url_failed":
                failed_md += f"| {i+1} | {f['url']} | {f['reason']} |\n"
        failed_md += "\n"

    if any(f.get("type") == "item_failed" for f in all_failed):
        failed_md += "## Items that could not be added\n\n"
        failed_md += "| # | Title | Year | Reason |\n"
        failed_md += "|---|-------|------|--------|\n"
        for i, f in enumerate(all_failed):
            if f.get("type") == "item_failed":
                failed_md += f"| {i+1} | {f['title']} | {f.get('year', '?')} | {f['reason']} |\n"
        failed_md += "\n"

    with open(FAILED_FILE, "w", encoding="utf-8") as f:
        f.write(failed_md)

    log(f"\nLog saved to: {LOG_FILE}")
    log(f"Failed items saved to: {FAILED_FILE}")


if __name__ == "__main__":
    main()
