#!/usr/bin/env python3
"""
Example: Login to Lampa MX using 6-digit code.

Usage:
    python examples/login.py --code 123456
    
Or with existing token:
    python examples/login.py --token YOUR_TOKEN --profile YOUR_PROFILE_ID
"""

import argparse
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.auth import LampaAuth
from src.client import LampaClient
from src.utils import format_response


def main():
    parser = argparse.ArgumentParser(description='Login to Lampa MX')
    parser.add_argument('--code', type=str, help='6-digit code from QR scan')
    parser.add_argument('--token', type=str, help='Existing authentication token')
    parser.add_argument('--profile', type=str, help='Profile ID (required with --token)')
    parser.add_argument('--email', type=str, help='Email address (optional)')
    parser.add_argument('--domain', type=str, default='cub.rip', help='CUB domain (default: cub.rip)')
    
    args = parser.parse_args()
    
    if not args.code and not args.token:
        parser.print_help()
        print("\nError: Provide either --code or --token")
        sys.exit(1)
    
    auth = LampaAuth(domain=args.domain)
    
    try:
        if args.code:
            print(f"Logging in with code: {args.code}")
            account = auth.login_with_code(args.code)
            print(f"\nLogin successful!")
            print(f"Email: {account.email}")
            print(f"Token: {account.token[:10]}...")
            if account.profile:
                print(f"Profile ID: {account.profile.id}")
        
        elif args.token:
            print(f"Logging in with token...")
            account = auth.login_with_token(
                token=args.token,
                profile_id=args.profile,
                email=args.email
            )
            print(f"\nLogin successful!")
            print(f"Token: {account.token[:10]}...")
            if args.profile:
                print(f"Profile ID: {args.profile}")
        
        # Test the connection
        print("\nTesting connection...")
        client = LampaClient(domain=args.domain)
        
        if client.is_authenticated():
            print("Authenticated: Yes")
            
            # Try to get user data
            try:
                user = client.get_user()
                print(f"User data: {format_response(user)[:200]}...")
            except Exception as e:
                print(f"Failed to get user data: {e}")
            
            # List collections
            try:
                collections = client.list_collections(category="new")
                print(f"\nCollections (new): {len(collections.results)} found")
                for coll in collections.results[:5]:
                    print(f"  - {coll.title} ({coll.items_count} items)")
            except Exception as e:
                print(f"Failed to list collections: {e}")
        else:
            print("Authenticated: No")
            
    except ValueError as e:
        print(f"\nValidation Error: {e}")
        sys.exit(1)
    except RuntimeError as e:
        print(f"\nRuntime Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
