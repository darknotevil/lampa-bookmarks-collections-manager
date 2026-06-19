"""
lampa-cli — library + CLI for managing Lampa MX collections and bookmarks
via the cub.rip API.
"""

from .client import LampaClient
from .auth import LampaAuth
from .models import (
    Account, Profile, Collection, CollectionItem,
    CreateCollectionResponse, CreatedCollection,
    AddItemResponse, AddItemRequest,
    Bookmark, BookmarkResponse, BookmarksDumpResponse,
)

__all__ = [
    'LampaClient', 'LampaAuth',
    'Account', 'Profile', 'Collection', 'CollectionItem',
    'CreateCollectionResponse', 'CreatedCollection',
    'AddItemResponse', 'AddItemRequest',
    'Bookmark', 'BookmarkResponse', 'BookmarksDumpResponse',
]
