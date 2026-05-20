#!/usr/bin/env python3
"""
Example: Create a new collection in Lampa MX.

Usage:
    python examples/create_collection.py --name "My Movies"
    
The created collection ID will be printed so you can use it
with add_items.py to populate the collection.
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.client import LampaClient


def main():
    parser = argparse.ArgumentParser(description='Create a new Lampa MX Collection')
    parser.add_argument('--name', type=str, required=True, help='Collection title')
    parser.add_argument('--domain', type=str, default='cub.rip', help='CUB domain')
    
    args = parser.parse_args()
    
    client = LampaClient(domain=args.domain)
    
    if not client.is_authenticated():
        print("Error: Not authenticated. Run examples/login.py first.")
        sys.exit(1)
    
    try:
        print(f"Creating collection: '{args.name}'")
        response = client.create_collection(name=args.name)
        
        if response.secuses:
            print(f"\nSuccess!")
            print(f"  Collection ID: {response.collection.id}")
            print(f"  Title: {response.collection.title}")
            print(f"  HPU: {response.collection.hpu}")
            print(f"  Owner (cid): {response.collection.cid}")
            print(f"  Items: {response.collection.items_count}")
            print(f"\nUse this Collection ID with add_items.py:")
            print(f"  python examples/add_items.py --collection-id {response.collection.id} --tmdb-id <TMDB_ID>")
        else:
            print(f"Failed to create collection. Response: {response.model_dump()}")
            sys.exit(1)
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
