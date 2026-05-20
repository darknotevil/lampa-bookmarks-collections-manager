"""
Main API client for Lampa MX.

Handles HTTP requests with authentication, collections management,
and TMDB proxy operations.
"""

import json
import requests
from typing import Optional, Dict, Any, List
from .models import (
    Account,
    Collection,
    CollectionItem,
    CollectionsListResponse,
    CollectionsViewResponse,
    CreateCollectionResponse,
    CreatedCollection,
    AddItemResponse,
    Bookmark,
    BookmarkResponse,
    BookmarksDumpResponse,
)
from .utils import (
    load_config,
    load_account,
    save_account,
    build_url,
    build_tmdb_proxy_url,
    validate_code
)


class LampaClient:
    """
    Main client for interacting with Lampa MX API.
    
    Usage:
        client = LampaClient()
        client.login_with_code("123456")
        collections = client.list_collections(category="user")
    """

    # Default CUB mirrors
    CUB_MIRRORS = ["cub.rip", "durex.monster", "cubnotrip.top"]
    
    def __init__(
        self,
        domain: Optional[str] = None,
        protocol: str = "https",
        timeout: int = 8000,
        account_path: Optional[str] = None
    ):
        """
        Initialize Lampa API client.
        
        Args:
            domain: CUB domain (defaults to first available mirror)
            protocol: HTTP protocol (http or https)
            timeout: Request timeout in milliseconds
            account_path: Path to saved account file
        """
        self.domain = domain or self.CUB_MIRRORS[0]
        self.protocol = protocol
        self.timeout = timeout / 1000  # Convert to seconds
        self.account: Optional[Account] = None
        self.session = requests.Session()
        self.account_path = account_path
        
        # Try to load saved account
        saved = load_account(account_path)
        if saved:
            self.account = Account.from_dict(saved)
            self._setup_headers()
        
        # Setup default headers
        self.session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        })

    def _setup_headers(self) -> None:
        """Setup authentication headers if account exists."""
        if self.account and self.account.token:
            headers = {
                'token': self.account.token,
            }
            if self.account.profile and self.account.profile.id:
                headers['profile'] = self.account.profile.id
            self.session.headers.update(headers)

    def _get_api_url(self, path: str) -> str:
        """Build full API URL."""
        return build_url(self.protocol, self.domain, f"/api/{path}")

    def _get_collections_url(self, path: str) -> str:
        """Build full Collections API URL."""
        return build_url(self.protocol, self.domain, f"/api/collections/{path}")

    def _request(
        self,
        method: str,
        url: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Make HTTP request with error handling (JSON body).
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Full URL
            data: Request body (for POST/PUT) — sent as JSON
            params: Query parameters
            timeout: Override timeout in seconds
            
        Returns:
            Response JSON data
            
        Raises:
            requests.exceptions.RequestException: On network errors
            ValueError: On non-200 responses
        """
        try:
            response = self.session.request(
                method=method,
                url=url,
                json=data,
                params=params,
                timeout=timeout or self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise e
        except ValueError as e:
            # JSON decode error
            raise ValueError(f"Failed to parse response: {e}")

    def _form_request(
        self,
        method: str,
        url: str,
        data: Optional[Dict] = None,
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Make HTTP request with form-urlencoded body.
        
        Used by write endpoints (create, add) that expect
        application/x-www-form-urlencoded instead of JSON.
        These endpoints require token as a cookie (not header)
        and profile as a header.
        
        Args:
            method: HTTP method (POST)
            url: Full URL
            data: Form fields dict
            timeout: Override timeout in seconds
            
        Returns:
            Response JSON data
        """
        import requests as req
        
        # Build headers for form request — token as cookie, profile as header
        headers = {
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest',
        }
        if self.account and self.account.profile and self.account.profile.id:
            headers['profile'] = self.account.profile.id
        
        cookies = {}
        if self.account and self.account.token:
            cookies['token'] = self.account.token
        
        try:
            response = req.request(
                method=method,
                url=url,
                data=data,
                headers=headers,
                cookies=cookies,
                timeout=timeout or self.timeout
            )
            response.raise_for_status()
            return response.json()
        except req.exceptions.RequestException as e:
            raise e
        except ValueError as e:
            raise ValueError(f"Failed to parse response: {e}")

    def get(self, path: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make GET request to API."""
        return self._request('GET', self._get_api_url(path), params=params)

    def post(self, path: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make POST request to API."""
        return self._request('POST', self._get_api_url(path), data=data)

    # ============================================
    # Authentication Methods
    # ============================================

    def login_with_code(self, code: str) -> Account:
        """
        Login using 6-digit code from QR scan.
        
        Args:
            code: 6-digit code
            
        Returns:
            Account object with token
            
        Raises:
            ValueError: If code is invalid or login fails
        """
        if not validate_code(code):
            raise ValueError("Code must be 6 digits")
        
        response = self.post('device/add', {'code': code})
        
        self.account = Account(
            token=response['token'],
            email=response.get('email'),
            id=response.get('id'),
        )
        
        # Parse profile if present
        if 'profile' in response:
            from .models import Profile
            self.account.profile = Profile(**response['profile'])
        
        self._setup_headers()
        
        # Save account
        save_account(self.account.to_dict(), self.account_path)
        
        return self.account

    def login_with_token(self, token: str, profile_id: Optional[str] = None, email: Optional[str] = None) -> Account:
        """
        Login using existing token.
        
        Args:
            token: Authentication token
            profile_id: Profile ID
            email: Email address
            
        Returns:
            Account object
        """
        self.account = Account(
            token=token,
            email=email,
            id=profile_id,
        )
        if profile_id:
            from .models import Profile
            self.account.profile = Profile(id=profile_id)
        
        self._setup_headers()
        save_account(self.account.to_dict(), self.account_path)
        
        return self.account

    def logout(self) -> None:
        """Clear session and saved account."""
        self.account = None
        self.session.headers.clear()
        self.session.close()
        self.session = requests.Session()
        
        # Clear saved account
        from .utils import clear_account
        clear_account(self.account_path)

    def is_authenticated(self) -> bool:
        """Check if client is authenticated."""
        return self.account is not None and self.account.token is not None

    # ============================================
    # Collections Methods
    # ============================================

    def list_collections(
        self,
        category: str = "new",
        page: int = 1
    ) -> CollectionsListResponse:
        """
        List collections by category.
        
        Args:
            category: Category (user, new, top, week, month, big, all)
            page: Page number
            
        Returns:
            CollectionsListResponse with collections
        """
        if not self.is_authenticated():
            raise RuntimeError("Not authenticated. Call login_with_code() or login_with_token() first.")
        
        # For user category, use cid parameter
        if category == "user" and self.account:
            params = {'cid': self.account.id, 'page': page}
        else:
            params = {'category': category, 'page': page}
        
        response = self._request('GET', self._get_collections_url('list'), params=params)
        
        return CollectionsListResponse(
            results=[Collection(**item) for item in response.get('results', [])],
            total_pages=response.get('total_pages', 15)
        )

    def view_collection(self, collection_id: str, page: int = 1) -> CollectionsViewResponse:
        """
        View collection details and items.
        
        Args:
            collection_id: Collection ID
            page: Page number
            
        Returns:
            CollectionsViewResponse with items
        """
        if not self.is_authenticated():
            raise RuntimeError("Not authenticated.")
        
        response = self._request(
            'GET',
            self._get_collections_url(f'view/{collection_id}'),
            params={'page': page}
        )
        
        return CollectionsViewResponse(
            results=[CollectionItem(**item) for item in response.get('results', [])],
            total_pages=response.get('total_pages', 15)
        )

    def like_collection(self, collection_id: str, like: bool = True) -> Dict[str, Any]:
        """
        Like or unlike a collection.
        
        Args:
            collection_id: Collection ID
            like: True to like, False to unlike
            
        Returns:
            Response data
        """
        if not self.is_authenticated():
            raise RuntimeError("Not authenticated.")
        
        return self._request(
            'POST',
            self._get_collections_url('liked'),
            data={'id': collection_id, 'dir': 1 if like else -1}
        )

    def create_collection(self, name: str) -> CreateCollectionResponse:
        """
        Create a new collection.

        Endpoint: POST /api/collections/create
        Content-Type: application/x-www-form-urlencoded

        Args:
            name: Collection title (will also be used as hpu slug)

        Returns:
            CreateCollectionResponse containing the new collection object

        Raises:
            RuntimeError: If not authenticated
        """
        if not self.is_authenticated():
            raise RuntimeError("Not authenticated. Call login_with_code() or login_with_token() first.")

        response = self._form_request(
            'POST',
            self._get_collections_url('create'),
            data={'name': name}
        )

        return CreateCollectionResponse(
            secuses=response.get('secuses', False),
            collection=CreatedCollection(**response['collection']),
            duration=response.get('duration')
        )

    def add_item_to_collection(
        self,
        collection_id: str,
        tmdb_id: str,
        media_type: str = "movie"
    ) -> AddItemResponse:
        """
        Add a movie or TV show to an existing collection.

        Endpoint: POST /api/collections/add
        Content-Type: application/x-www-form-urlencoded

        Args:
            collection_id: CUB Collection ID (server-assigned, from create_collection or list_collections)
            tmdb_id: TMDB ID of the movie or TV show to add
            media_type: Type of media — 'movie' or 'tv' (default: 'movie')

        Returns:
            AddItemResponse with success status

        Raises:
            RuntimeError: If not authenticated
            ValueError: If media_type is invalid
        """
        if not self.is_authenticated():
            raise RuntimeError("Not authenticated.")

        if media_type not in ('movie', 'tv'):
            raise ValueError(f"Invalid media_type: '{media_type}'. Must be 'movie' or 'tv'.")

        response = self._form_request(
            'POST',
            self._get_collections_url('add'),
            data={
                'id': collection_id,
                'card_id': tmdb_id,
                'card_type': media_type,
            }
        )

        return AddItemResponse(
            secuses=response.get('secuses', False),
            duration=response.get('duration')
        )

    # ============================================
    # Bookmarks Methods
    # ============================================

    def add_bookmark(
        self,
        tmdb_id: str,
        media_type: str = "movie",
        card_data: Optional[Dict[str, Any]] = None,
        bookmark_type: str = "book"
    ) -> BookmarkResponse:
        """
        Add a movie or TV show to bookmarks (favorites).

        Endpoint: POST /api/bookmarks/add
        Content-Type: application/x-www-form-urlencoded

        The API expects minimal card data in the following format:

        For movies:
            {
                "id": 550,
                "title": "Fight Club",
                "original_title": "Fight Club",
                "release_date": "1999-10-15",
                "poster_path": "/pB8BM7pdSp6B6Ih7QZ4DrQ3PmJK.jpg",
                "vote_average": 8.4,
                "media_type": "movie"
            }

        For TV shows:
            {
                "id": 1399,
                "name": "Game of Thrones",
                "original_name": "Game of Thrones",
                "first_air_date": "2011-04-17",
                "poster_path": "/...jpg",
                "vote_average": 8.4,
                "media_type": "tv"
            }

        Args:
            tmdb_id: TMDB ID of the movie or TV show
            media_type: Type of media — 'movie' or 'tv' (default: 'movie')
            card_data: Optional pre-built minimal card data dict matching the
                       structure above. If not provided, will be built from
                       TMDB data using get_tmdb_movie/get_tmdb_tv.
            bookmark_type: Bookmark type (default: 'book')

        Returns:
            BookmarkResponse with success status and bookmark details

        Raises:
            RuntimeError: If not authenticated
        """
        if not self.is_authenticated():
            raise RuntimeError("Not authenticated.")

        # Build card data with required fields from TMDB
        if card_data is None:
            if media_type == "movie":
                tmdb_data = self.get_tmdb_movie_by_id(tmdb_id)
                card_data = {
                    "id": tmdb_data.get("id"),
                    "title": tmdb_data.get("title"),
                    "original_title": tmdb_data.get("original_title"),
                    "release_date": tmdb_data.get("release_date"),
                    "poster_path": tmdb_data.get("poster_path"),
                    "vote_average": tmdb_data.get("vote_average"),
                    "media_type": "movie",
                }
            else:
                tmdb_data = self.get_tmdb_tv_by_id(tmdb_id)
                card_data = {
                    "id": tmdb_data.get("id"),
                    "name": tmdb_data.get("name"),
                    "original_name": tmdb_data.get("original_name"),
                    "first_air_date": tmdb_data.get("first_air_date"),
                    "poster_path": tmdb_data.get("poster_path"),
                    "vote_average": tmdb_data.get("vote_average"),
                    "media_type": "tv",
                }

        response = self._form_request(
            'POST',
            self._get_api_url('bookmarks/add'),
            data={
                'type': bookmark_type,
                'data': json.dumps(card_data),
                'card_id': tmdb_id,
                'id': 0,  # 0 for adding new bookmark
            }
        )

        return BookmarkResponse(
            secuses=response.get('secuses', False),
            bookmark=Bookmark(**response['bookmark']),
            write=response.get('write'),
            duration=response.get('duration')
        )

    def remove_bookmark(
        self,
        bookmark_id: str,
        bookmark_type: str = "book"
    ) -> BookmarkResponse:
        """
        Remove a bookmark (favorite).

        Endpoint: POST /api/bookmarks/remove
        Content-Type: application/x-www-form-urlencoded

        Args:
            bookmark_id: Bookmark ID (from add_bookmark response or list_bookmarks)
            bookmark_type: Bookmark type (default: 'book')

        Returns:
            BookmarkResponse with success status

        Raises:
            RuntimeError: If not authenticated
        """
        if not self.is_authenticated():
            raise RuntimeError("Not authenticated.")

        response = self._form_request(
            'POST',
            self._get_api_url('bookmarks/remove'),
            data={
                'type': bookmark_type,
                'data': '{}',
                'card_id': 0,
                'id': bookmark_id,
            }
        )

        return BookmarkResponse(
            secuses=response.get('secuses', False),
            bookmark=Bookmark(**response.get('bookmark', {})),
            write=response.get('write'),
            duration=response.get('duration')
        )

    def list_bookmarks(self) -> List[Dict[str, Any]]:
        """
        List all bookmarks (favorites) for current user.

        Endpoint: GET /api/bookmarks/dump
        Returns raw text dump that needs parsing.

        Returns:
            List of bookmark data dicts parsed from the dump response

        Raises:
            RuntimeError: If not authenticated
        """
        if not self.is_authenticated():
            raise RuntimeError("Not authenticated.")

        # The dump endpoint returns text/plain, not JSON
        # Use a custom request to handle text response
        import requests as req

        headers = {
            'Accept': 'text/plain, */*; q=0.01',
            'X-Requested-With': 'XMLHttpRequest',
        }
        if self.account and self.account.profile and self.account.profile.id:
            headers['profile'] = self.account.profile.id

        cookies = {}
        if self.account and self.account.token:
            cookies['token'] = self.account.token

        url = self._get_api_url('bookmarks/dump')

        try:
            response = req.request(
                method='GET',
                url=url,
                headers=headers,
                cookies=cookies,
                timeout=self.timeout
            )
            response.raise_for_status()
            text = response.text
        except req.exceptions.RequestException as e:
            raise e

        # Parse the text dump - each line is a JSON bookmark entry
        bookmarks = []
        for line in text.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            try:
                bookmark_data = json.loads(line)
                bookmarks.append(bookmark_data)
            except json.JSONDecodeError:
                # Skip malformed lines
                continue

        return bookmarks


    # ============================================
    # TMDB Proxy Methods
    # ============================================

    def search_tmdb(self, query: str, page: int = 1) -> Dict[str, Any]:
        """
        Search for movies/TV shows via TMDB proxy.
        
        Args:
            query: Search query
            page: Page number
            
        Returns:
            Search results
        """
        email = self.account.email if self.account else None
        url = build_tmdb_proxy_url(
            self.protocol,
            self.domain,
            f"?sort=search&query={query}&page={page}",
            email
        )
        
        return self._request('GET', url)

    def search_movies(self, query: str, page: int = 1) -> List[Dict[str, Any]]:
        """
        Search movies via CUB TMDB proxy.
        
        Args:
            query: Search query
            page: Page number
            
        Returns:
            List of movie result dicts
        """
        email = self.account.email if self.account else None
        url = build_tmdb_proxy_url(
            self.protocol,
            self.domain,
            f"search/movie?query={query}&page={page}",
            email
        )
        result = self._request('GET', url)
        return result.get('results', [])

    def search_tv(self, query: str, page: int = 1) -> List[Dict[str, Any]]:
        """
        Search TV shows via CUB TMDB proxy.
        
        Args:
            query: Search query
            page: Page number
            
        Returns:
            List of TV show result dicts
        """
        email = self.account.email if self.account else None
        url = build_tmdb_proxy_url(
            self.protocol,
            self.domain,
            f"search/tv?query={query}&page={page}",
            email
        )
        result = self._request('GET', url)
        return result.get('results', [])

    def search_anime(self, query: str, page: int = 1) -> List[Dict[str, Any]]:
        """
        Search anime via CUB TMDB proxy.
        
        Args:
            query: Search query
            page: Page number
            
        Returns:
            List of anime result dicts
        """
        email = self.account.email if self.account else None
        url = build_tmdb_proxy_url(
            self.protocol,
            self.domain,
            f"search/anime?query={query}&page={page}",
            email
        )
        result = self._request('GET', url)
        return result.get('results', [])

    def search_multi(self, query: str, page: int = 1) -> List[Dict[str, Any]]:
        """
        Search across all media types (movies, TV, people) via CUB TMDB proxy.
        Uses search/multi endpoint.
        
        Args:
            query: Search query
            page: Page number
            
        Returns:
            List of result dicts with media_type field (people filtered out)
        """
        email = self.account.email if self.account else None
        url = build_tmdb_proxy_url(
            self.protocol,
            self.domain,
            f"search/multi?query={query}&page={page}",
            email
        )
        result = self._request('GET', url)
        results = result.get('results', [])
        # Filter out people results, keep only movies and TV shows
        return [r for r in results if r.get('media_type') in ('movie', 'tv')]

    def search_catalog(self, query: str, page: int = 1) -> List[Dict[str, Any]]:
        """
        Search via CUB catalog search endpoint.

        This endpoint searches the CUB catalog (including localized content like
        Russian cartoons) and returns results with media_type field.

        Endpoint: GET /api/catalog/search?query=...&where=catalog

        Args:
            query: Search query (supports Cyrillic and other languages)
            page: Page number

        Returns:
            List of result dicts with media_type field
        """
        if not self.is_authenticated():
            raise RuntimeError("Not authenticated.")

        url = self._get_api_url('catalog/search')
        params = {
            'query': query,
            'where': 'catalog',
            'page': page,
        }
        result = self._request('GET', url, params=params)
        return result.get('results', [])

    def get_tmdb_movie(self, tmdb_id: str) -> Dict[str, Any]:
        """
        Get movie details from TMDB proxy.
        
        Args:
            tmdb_id: TMDB movie ID
            
        Returns:
            Movie details
        """
        email = self.account.email if self.account else None
        url = build_tmdb_proxy_url(
            self.protocol,
            self.domain,
            f"movie/{tmdb_id}",
            email
        )
        
        return self._request('GET', url)

    def get_tmdb_tv(self, tmdb_id: str) -> Dict[str, Any]:
        """
        Get TV show details from TMDB proxy.
        
        Args:
            tmdb_id: TMDB TV show ID
            
        Returns:
            TV show details
        """
        email = self.account.email if self.account else None
        url = build_tmdb_proxy_url(
            self.protocol,
            self.domain,
            f"tv/{tmdb_id}",
            email
        )
        
        return self._request('GET', url)

    def get_tmdb_movie_by_id(self, tmdb_id: str, language: str = "en-US") -> Dict[str, Any]:
        """
        Get movie details from TMDB API proxy.
        Uses apitmdb.{domain}/3/movie/{id} endpoint.

        Args:
            tmdb_id: TMDB movie ID
            language: Language code (default: en-US)

        Returns:
            Movie details dict
        """
        url = build_url(self.protocol, self.domain, f"/apitmdb/3/movie/{tmdb_id}")
        params = {'language': language}
        return self._request('GET', url, params=params)

    def get_tmdb_tv_by_id(self, tmdb_id: str, language: str = "en-US") -> Dict[str, Any]:
        """
        Get TV show details from TMDB API proxy.
        Uses apitmdb.{domain}/3/tv/{id} endpoint.

        Args:
            tmdb_id: TMDB TV show ID
            language: Language code (default: en-US)

        Returns:
            TV show details dict
        """
        url = build_url(self.protocol, self.domain, f"/apitmdb/3/tv/{tmdb_id}")
        params = {'language': language}
        return self._request('GET', url, params=params)

    # ============================================
    # User Methods
    # ============================================

    def get_user(self) -> Dict[str, Any]:
        """
        Get current user data.
        
        Returns:
            User data
        """
        if not self.is_authenticated():
            raise RuntimeError("Not authenticated.")
        
        return self.get('users/get')
