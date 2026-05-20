#!/usr/bin/env python3
"""
Example: List collections from Lampa MX.

Usage:
    python examples/list_collections.py --category new
    
Categories: user, new, top, week, month, big, all
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.client import LampaClient
from src.utils import format_response


def main():
    parser = argparse.ArgumentParser(description='List Lampa MX Collections')
    parser.add_argument('--category', type=str, default='new',
                        choices=['user', 'new', 'top', 'week', 'month', 'big', 'all'],
                        help='Category to list (default: new)')
    parser.add_argument('--page', type=int, default=1, help='Page number (default: 1)')
    parser.add_argument('--domain', type=str, default='cub.rip', help='CUB domain')
    
    args = parser.parse_args()
    
    client = LampaClient(domain=args.domain)
    
    if not client.is_authenticated():
        print("Error: Not authenticated. Run examples/login.py first.")
        sys.exit(1)
    
    try:
        print(f"Loading collections: category={args.category}, page={args.page}")
        response = client.list_collections(category=args.category, page=args.page)
        
        print(f"\nFound {len(response.results)} collections (total pages: {response.total_pages})")
        print("=" * 60)
        
        for coll in response.results:
            print(f"\nID: {coll.id}")
            print(f"Title: {coll.title}")
            print(f"Items: {coll.items_count}")
            print(f"Views: {coll.views}")
            print(f"Liked: {coll.liked}")
            print(f"Owner: @{coll.username}")
            if coll.cid:
                print(f"Owner ID: {coll.cid}")
        
        # View first collection items
        if response.results:
            first = response.results[0]
            print(f"\n{'=' * 60}")
            print(f"Viewing items in: {first.title}")
            print(f"{'=' * 60}")
            
            items_response = client.view_collection(first.id)
            print(f"Items: {len(items_response.results)}")
            
            for item in items_response.results[:10]:
                title = item.title or item.name or "Unknown"
                print(f"  - {title} (ID: {item.id}, Type: {item.media_type})")
            
            if len(items_response.results) > 10:
                print(f"  ... and {len(items_response.results) - 10} more")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
