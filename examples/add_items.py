#!/usr/bin/env python3
"""
Example: Add movies or TV shows to a Lampa MX Collection or Bookmarks.

Usage:
    # Add a single movie to a collection by TMDB ID
    python examples/add_items.py --collection-id 2948 --tmdb-id 350
    
    # Add a TV show to a collection
    python examples/add_items.py --collection-id 2948 --tmdb-id 1399 --type tv
    
    # Add multiple items to a collection at once
    python examples/add_items.py --collection-id 2948 --tmdb-id 350 27205 155
    
    # Add to bookmarks (favorites) instead of a collection
    python examples/add_items.py --tmdb-id 350
    
    # Add to bookmarks via search
    python examples/add_items.py --search "The Devil Wears Prada"
    
    # Search for a movie first, then add it to a collection (auto-selects first result)
    python examples/add_items.py --collection-id 2948 --search "The Devil Wears Prada"
    
    # Search with interactive selection (pick from results)
    python examples/add_items.py --collection-id 2948 --search "фукусима 2020" -i
    
    # Search with year extraction (auto-selects matching year if single match)
    python examples/add_items.py --collection-id 2948 --search "фукусима 2020"
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.client import LampaClient
from src.utils import parse_search_query


def get_year(item: dict) -> int:
    """Extract year from a search result item."""
    if item.get('release_date'):
        return int(item['release_date'][:4])
    elif item.get('first_air_date'):
        return int(item['first_air_date'][:4])
    return 0


def get_title(item: dict) -> str:
    """Get title from a search result item."""
    return item.get('title') or item.get('name') or 'Unknown'


def get_media_type(item: dict) -> str:
    """Get media type from a search result item."""
    return item.get('media_type', 'movie')


def format_result(item: dict, index: int, query_year: int = 0) -> str:
    """Format a search result for display."""
    title = get_title(item)
    item_id = item.get('id')
    item_type = get_media_type(item)
    year = get_year(item)
    year_str = f" ({year})" if year else ""
    year_match = " *" if query_year and year == query_year else ""
    return f"  {index}. {title}{year_str} — TMDB ID: {item_id} ({item_type}){year_match}"


def search_multi_source(client, query: str, query_year: int = 0, interactive: bool = False):
    """
    Search across multiple sources with fallback.

    Search order:
    1. Catalog search (searches CUB catalog — best for localized content like Russian cartoons)
    2. Multi-search (searches movies, TV, and people together via search/multi)
    3. Individual searches (movies, TV, anime) as fallback

    If interactive mode is enabled, shows results from all sources (5 per category).
    Otherwise, falls back through sources until results are found.
    """
    print(f"Searching for: '{query}'" + (f" (year: {query_year})" if query_year else ""))

    # Step 1: Try catalog search first (best for localized content)
    catalog_results = client.search_catalog(query)

    # Step 2: Try multi-search (searches movies, TV, people together)
    multi_results = client.search_multi(query)

    # Step 3: Also search individual sources for fallback
    movies = client.search_movies(query)
    tv_shows = client.search_tv(query)
    anime = client.search_anime(query)

    # Tag items with source type for display
    tagged_catalog = [(item, 'catalog') for item in catalog_results]
    tagged_movies = [(item, 'movie') for item in movies]
    tagged_tv = [(item, 'tv') for item in tv_shows]
    tagged_anime = [(item, 'anime') for item in anime]

    if interactive:
        # Interactive mode: show all categories with up to 5 results each
        all_results = []

        print(f"\nCatalog:")
        if tagged_catalog:
            for i, (item, _) in enumerate(tagged_catalog[:5]):
                line = format_result(item, len(all_results) + 1, query_year)
                print(line)
                all_results.append(item)
        else:
            print("  (no results)")

        # Only show TMDB fallback categories if catalog returned nothing
        if not catalog_results:
            if multi_results:
                print(f"\nMulti-Search Results:")
                for i, item in enumerate(multi_results[:5]):
                    line = format_result(item, len(all_results) + 1, query_year)
                    print(line)
                    all_results.append(item)
            else:
                print(f"\nMulti-Search:")
                print("  (no results)")

            print(f"\nMovies:")
            if tagged_movies:
                for i, (item, _) in enumerate(tagged_movies[:5]):
                    line = format_result(item, len(all_results) + 1, query_year)
                    print(line)
                    all_results.append(item)
            else:
                print("  (no results)")

            print(f"\nTV Shows:")
            if tagged_tv:
                for i, (item, _) in enumerate(tagged_tv[:5]):
                    line = format_result(item, len(all_results) + 1, query_year)
                    print(line)
                    all_results.append(item)
            else:
                print("  (no results)")

            print(f"\nAnime:")
            if tagged_anime:
                for i, (item, _) in enumerate(tagged_anime[:5]):
                    line = format_result(item, len(all_results) + 1, query_year)
                    print(line)
                    all_results.append(item)
            else:
                print("  (no results)")

        if not all_results:
            print("\nNo results found in any source.")
            return None

        if query_year:
            print(f"\n* = matches extracted year")

        # Prompt user to select
        print(f"\nSelect result number [1]: ", end='')
        try:
            choice = input().strip()
            if choice == '':
                choice_idx = 0
            else:
                choice_idx = int(choice) - 1
        except (ValueError, EOFError):
            choice_idx = 0

        if choice_idx < 0 or choice_idx >= len(all_results):
            print(f"Invalid selection. Using first result.")
            choice_idx = 0

        return all_results[choice_idx]

    else:
        # Non-interactive mode: try catalog first, then multi-search, then fallback through sources
        all_results = []

        # Try catalog search first (best for localized content)
        if catalog_results:
            all_results = catalog_results
        elif multi_results:
            all_results = multi_results
        elif movies:
            all_results = movies
        elif tv_shows:
            all_results = tv_shows
        elif anime:
            all_results = anime
        else:
            print("No results found in any source.")
            return None

        # If year was extracted, try to find matching result
        if query_year:
            year_matches = [item for item in all_results if get_year(item) == query_year]
            if len(year_matches) == 1:
                return year_matches[0]
            elif len(year_matches) > 1:
                # Multiple matches - show them and pick first
                print(f"\nMultiple results match year {query_year}:")
                for i, item in enumerate(year_matches[:5]):
                    print(format_result(item, i + 1, query_year))
                return year_matches[0]

        # No year filter or no match - return first result
        return all_results[0]


def search_and_add(client, collection_id, query, media_type="movie", interactive=False):
    """Search for a title and add the selected result to the collection or bookmarks."""
    # Parse query to extract year
    search_title, query_year = parse_search_query(query)
    
    if search_title != query:
        print(f"Note: Extracted year {query_year} from query, searching for '{search_title}'")
    
    # Search with multi-source fallback
    selected = search_multi_source(client, search_title, query_year, interactive)
    
    if selected is None:
        return
    
    tmdb_id = str(selected['id'])
    actual_type = get_media_type(selected)
    title = get_title(selected)
    
    if collection_id:
        print(f"\nAdding '{title}' (TMDB ID: {tmdb_id}) to collection {collection_id}...")
        response = client.add_item_to_collection(collection_id, tmdb_id, actual_type)
        
        if response.secuses:
            print(f"  Success! Added '{title}' to the collection.")
        else:
            print(f"  Failed. Response: {response.model_dump()}")
    else:
        print(f"\nAdding '{title}' (TMDB ID: {tmdb_id}) to bookmarks (favorites)...")
        response = client.add_bookmark(tmdb_id, actual_type, card_data=selected)
        
        if response.secuses:
            print(f"  Success! Added '{title}' to bookmarks.")
        else:
            print(f"  Failed. Response: {response.model_dump()}")


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
        # Search-based add
        if args.search:
            search_and_add(client, args.collection_id, args.search, args.type, args.interactive)
            return
        
        # Direct TMDB ID add
        for tmdb_id in args.tmdb_id:
            if args.collection_id:
                print(f"Adding TMDB ID {tmdb_id} (type: {args.type}) to collection {args.collection_id}...")
                response = client.add_item_to_collection(
                    collection_id=args.collection_id,
                    tmdb_id=tmdb_id,
                    media_type=args.type
                )
                
                if response.secuses:
                    print(f"  Success!")
                else:
                    print(f"  Failed. Response: {response.model_dump()}")
            else:
                print(f"Adding TMDB ID {tmdb_id} (type: {args.type}) to bookmarks (favorites)...")
                response = client.add_bookmark(tmdb_id, args.type)
                
                if response.secuses:
                    print(f"  Success! Bookmark ID: {response.bookmark.id}")
                else:
                    print(f"  Failed. Response: {response.model_dump()}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
