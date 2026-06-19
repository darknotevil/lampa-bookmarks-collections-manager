"""
Data models for Lampa MX API responses.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Any, Union
from datetime import datetime


class Profile(BaseModel):
    """User profile data."""
    id: Union[str, int]
    name: Optional[str] = None
    icon: Optional[str] = "l_1"
    child: bool = False
    age: int = 0

    @field_validator("id", mode="before")
    @classmethod
    def id_to_str(cls, v):
        return str(v)


class Account(BaseModel):
    """Account data returned after login."""
    token: str
    email: Optional[str] = None
    id: Optional[Union[str, int]] = None
    profile: Optional[Profile] = None

    @field_validator("id", mode="before")
    @classmethod
    def id_to_str(cls, v):
        if v is not None:
            return str(v)
        return v

    def to_dict(self) -> dict:
        """Convert to dict for storage."""
        return self.model_dump(exclude_none=True)

    @classmethod
    def from_dict(cls, data: dict) -> 'Account':
        """Create Account from stored dict."""
        if 'profile' in data and isinstance(data['profile'], dict):
            data['profile'] = Profile(**data['profile'])
        return cls(**data)


class CollectionItem(BaseModel):
    """Item in a collection (movie or TV show)."""
    id: Union[str, int]
    title: Optional[str] = None

    @field_validator("id", mode="before")
    @classmethod
    def id_to_str(cls, v):
        if v is not None:
            return str(v)
        return v
    name: Optional[str] = None
    overview: Optional[str] = None
    backdrop_path: Optional[str] = None
    poster_path: Optional[str] = None
    media_type: Optional[str] = "movie"
    vote_average: Optional[float] = None
    vote_count: Optional[int] = None
    popularity: Optional[float] = None
    release_date: Optional[str] = None
    first_air_date: Optional[str] = None
    adult: Optional[bool] = False
    genre_ids: Optional[List[int]] = None
    original_language: Optional[str] = None
    tmdb_id: Optional[str] = None


class Collection(BaseModel):
    """Collection data."""
    id: Union[str, int]
    title: str
    items_count: int = 0
    views: int = 0
    liked: int = 0
    username: Optional[str] = None
    cid: Optional[Union[str, int]] = None  # Owner user ID
    backdrop_path: Optional[str] = None
    icon: Optional[str] = "l_1"
    time: Optional[int] = None
    items: Optional[List[CollectionItem]] = None

    @field_validator("id", "cid", mode="before")
    @classmethod
    def id_to_str(cls, v):
        if v is not None:
            return str(v)
        return v

    @property
    def created_at(self) -> Optional[datetime]:
        """Parse timestamp to datetime."""
        if self.time:
            return datetime.fromtimestamp(self.time)
        return None


class CollectionsListResponse(BaseModel):
    """Response from collections list endpoint."""
    results: List[Collection] = []
    total_pages: Optional[int] = 15


class CollectionsViewResponse(BaseModel):
    """Response from collections view endpoint."""
    results: List[CollectionItem] = []
    total_pages: Optional[int] = 15


class LoginResponse(BaseModel):
    """Response from device/add endpoint."""
    token: str
    email: Optional[str] = None
    id: Optional[str] = None
    profile: Optional[Profile] = None


class LikeRequest(BaseModel):
    """Request body for liking a collection."""
    id: str
    dir: int = 1  # 1 for like, -1 for unlike


class CreatedCollection(BaseModel):
    """Collection object returned after creation."""
    id: Union[str, int]
    title: str
    hpu: str
    cid: Union[str, int]
    time: int
    items_count: int = 0
    views: int = 0
    username: Optional[str] = None
    backdrop_path: Optional[str] = ""
    icon: Optional[str] = "l_1"

    @field_validator("id", "cid", mode="before")
    @classmethod
    def id_to_str(cls, v):
        if v is not None:
            return str(v)
        return v


class CreateCollectionResponse(BaseModel):
    """Response from /api/collections/create endpoint."""
    secuses: bool
    collection: CreatedCollection
    duration: Optional[float] = None


class AddItemRequest(BaseModel):
    """Request data for adding an item to a collection."""
    id: str  # Collection ID (CUB-assigned)
    card_id: str  # TMDB ID
    card_type: str  # 'movie' or 'tv'


class AddItemResponse(BaseModel):
    """Response from /api/collections/add endpoint."""
    secuses: bool
    duration: Optional[float] = None


# ============================================
# Bookmark Models
# ============================================

class Bookmark(BaseModel):
    """Bookmark (favorite) entry."""
    id: Union[str, int]
    cid: Union[str, int]  # Customer/user ID
    lid: Union[str, int]  # Library/item ID
    type: str = "book"  # Bookmark type (e.g. "book")
    card_id: Union[str, int]  # TMDB ID
    data: str  # JSON string of card data
    profile: Union[str, int]  # Profile ID
    time: int  # Timestamp in milliseconds
    card_title: Optional[str] = None
    card_type: Optional[str] = None  # "movie" or "tv"
    card_poster: Optional[str] = None  # Poster path

    @field_validator("id", "cid", "lid", "card_id", "profile", mode="before")
    @classmethod
    def id_to_str(cls, v):
        if v is not None:
            return str(v)
        return v


class BookmarkDuration(BaseModel):
    """Duration wrapper for bookmark responses."""
    bookmark: Bookmark
    duration: Optional[float] = None

    @field_validator("bookmark", mode="before")
    @classmethod
    def parse_bookmark(cls, v):
        if isinstance(v, dict):
            return Bookmark(**v)
        return v


class BookmarkResponse(BaseModel):
    """Response from /api/bookmarks/add or /api/bookmarks/remove endpoint."""
    secuses: bool
    bookmark: Bookmark
    write: Optional[str] = None  # "insert" or "delete"
    duration: Optional[float] = None


class BookmarksDumpResponse(BaseModel):
    """Response from /api/bookmarks/dump endpoint."""
    version: Optional[str] = None
    bookmarks: List[str] = []  # Raw strings of bookmarks
