#!/usr/bin/env python3
"""
Example: Add movies or TV shows to a Lampa MX Collection or Bookmarks.

This is the interactive, human-facing tool. For LLM agents use
``examples/agent_tool.py`` instead (structured JSON, no prompts).

Usage:
    # Add a single movie to a collection by TMDB ID
    python examples/add_items.py --collection-id 2948 --tmdb-id 350

    # Add a TV show to a collection
    python examples/add_items.py --collection-id 2948 --tmdb-id 1399 --type tv

    # Add multiple items to a collection at once
    python examples/add_items.py --collection-id 2948 --tmdb-id 350 27205 155

    # Add to bookmarks (favorites) instead of a collection
    python examples/add_items.py --tmdb-id 350

    # Add to bookmarks via search (auto-selects best result)
    python examples/add_items.py --search "The Devil Wears Prada"

    # Search with interactive selection (pick from results)
    python examples/add_items.py --collection-id 2948 --search "фукусима 2020" -i
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.client import LampaClient
from src.search import (
    build_card_data,
    get_media_type,
    get_title,
    get_year,
    match_year,
    search_titles,
)
from src.utils import parse_search_query


def format_result(item: dict, index: int, query_year: int = 0) -> str:
    """Format a search result for display."""
    title = get_title(item)
    item_id = item.get('id')
    item_type = get_media_type(item)
    year = get_year(item)
    year_str = f" ({year})" if year else ""
    year_match = " *" if query_year and year == query_year else ""
    return f"  {index}. {title}{year_str} — TMDB ID: {item_id} ({item_type}){year_match}"


def select_result(client, query: str, query_year: int = 0, interactive: bool = False):
    """Search for a title and return the selected raw result item (or None)."""
    print(f"Searching for: '{query}'" + (f" (year: {query_year})" if query_year else ""))

    # Interactive mode merges every source so the user can see all options;
    # non-interactive mode takes the first source that returns anything.
    results = search_titles(client, query, merge=interactive)

    if not results:
        print("No results found in any source.")
        return None

    if interactive:
        for i, item in enumerate(results):
            print(format_result(item, i + 1, query_year))
        if query_year:
            print("\n* = matches extracted year")

        print("\nSelect result number [1]: ", end='')
        try:
            choice = input().strip()
            choice_idx = 0 if choice == '' else int(choice) - 1
        except (ValueError, EOFError):
            choice_idx = 0

        if not 0 <= choice_idx < len(results):
            print("Invalid selection. Using first result.")
            choice_idx = 0
        return results[choice_idx]

    # Non-interactive: prefer a unique year match, otherwise the first result.
    chosen, matches = match_year(results, query_year)
    if chosen:
        return chosen
    if len(matches) > 1:
        print(f"\nMultiple results match year {query_year}:")
        for i, item in enumerate(matches[:5]):
            print(format_result(item, i + 1, query_year))
        return matches[0]
    return results[0]


def add_one(client, collection_id, tmdb_id, media_type, card_data=None, title=None):
    """Add a single item to a collection or bookmarks and report the result."""
    label = title or f"TMDB ID {tmdb_id}"
    if collection_id:
        print(f"Adding '{label}' (type: {media_type}) to collection {collection_id}...")
        response = client.add_item_to_collection(collection_id, tmdb_id, media_type)
    else:
        print(f"Adding '{label}' (type: {media_type}) to bookmarks (favorites)...")
        response = client.add_bookmark(tmdb_id, media_type, card_data=card_data)

    if response.secuses:
        print("  Success!")
    else:
        print(f"  Failed. Response: {response.model_dump()}")


def search_and_add(client, collection_id, query, media_type="movie", interactive=False):
    """Search for a title and add the selected result to the collection or bookmarks."""
    search_title, query_year = parse_search_query(query)
    if search_title != query:
        print(f"Note: Extracted year {query_year} from query, searching for '{search_title}'")

    selected = select_result(client, search_title, query_year, interactive)
    if selected is None:
        return

    add_one(
        client,
        collection_id,
        str(selected['id']),
        get_media_type(selected),
        card_data=build_card_data(selected),
        title=get_title(selected),
    )


def main():
    parser = argparse.ArgumentParser(description='Add items to a Lampa MX Collection or Bookmarks')
    parser.add_argument('--collection-id', type=str, required=False, default=None,
                        help='CUB Collection ID (omit to add to bookmarks/favorites instead)')
    parser.add_argument('--tmdb-id', type=str, nargs='+', help='TMDB ID(s) of movie(s)/show(s) to add')
    parser.add_argument('--type', type=str, default='movie', choices=['movie', 'tv'],
                        help='Media type (default: movie)')
    parser.add_argument('--search', type=str, help='Search query (adds first result)')
    parser.add_argument('-i', '--interactive', action='store_true',
                        help='Interactive mode: select from search results across all sources')
    parser.add_argument('--domain', type=str, default='cub.rip', help='CUB domain')

    args = parser.parse_args()

    if not args.tmdb_id and not args.search:
        parser.print_help()
        print("\nError: Provide either --tmdb-id or --search")
        sys.exit(1)

    client = LampaClient(domain=args.domain)

    if not client.is_authenticated():
        print("Error: Not authenticated. Run examples/login.py first.")
        sys.exit(1)

    try:
        if args.search:
            search_and_add(client, args.collection_id, args.search, args.type, args.interactive)
            return

        # Direct TMDB ID add (card data is fetched from TMDB by add_bookmark)
        for tmdb_id in args.tmdb_id:
            add_one(client, args.collection_id, tmdb_id, args.type)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
