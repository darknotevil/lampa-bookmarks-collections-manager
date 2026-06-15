"""
Utility functions for Lampa Parser.
"""

import json
import os
import re
from typing import Optional, Tuple
from pathlib import Path


APP_NAME = "lampa-bookmarks"


def _xdg(var: str, fallback: str) -> Path:
    return Path(os.environ.get(var) or Path.home() / fallback) / APP_NAME


CONFIG_DIR = _xdg("XDG_CONFIG_HOME", ".config")
CACHE_DIR = _xdg("XDG_CACHE_HOME", ".cache")
STATE_DIR = _xdg("XDG_STATE_HOME", ".local/state")

CONFIG_PATH = CONFIG_DIR / "settings.json"
ACCOUNT_PATH = STATE_DIR / "account.json"


def load_config(path: Optional[str] = None) -> dict:
    """Load configuration from settings.json."""
    config_path = Path(path) if path else CONFIG_PATH
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_config(config: dict, path: Optional[str] = None) -> None:
    """Save configuration to settings.json."""
    config_path = Path(path) if path else CONFIG_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)


def load_account(path: Optional[str] = None) -> Optional[dict]:
    """Load saved account data."""
    account_path = Path(path) if path else ACCOUNT_PATH
    if account_path.exists():
        with open(account_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def save_account(account_data: dict, path: Optional[str] = None) -> None:
    """Save account data for persistent sessions."""
    account_path = Path(path) if path else ACCOUNT_PATH
    account_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with open(account_path, 'w', encoding='utf-8') as f:
        json.dump(account_data, f, indent=4, ensure_ascii=False)
    os.chmod(account_path, 0o600)


def clear_account(path: Optional[str] = None) -> None:
    """Clear saved account data."""
    account_path = Path(path) if path else ACCOUNT_PATH
    if account_path.exists():
        account_path.unlink()


def build_url(protocol: str, domain: str, path: str) -> str:
    """Build full URL from components."""
    return f"{protocol}://{domain}{path}"


def build_image_url(protocol: str, domain: str, path: str, size: str = "original") -> str:
    """Build image URL through TMDB proxy."""
    if not path:
        return ""
    return f"{protocol}://imagetmdb.{domain}/{size}{path}"


def build_tmdb_proxy_url(protocol: str, domain: str, endpoint: str, email: Optional[str] = None) -> str:
    """Build TMDB proxy URL with optional email parameter."""
    url = f"{protocol}://tmdb.{domain}/{endpoint}"
    if email:
        url += f"?email={email}"
    return url


def format_response(data: dict) -> str:
    """Format API response for display."""
    return json.dumps(data, indent=2, ensure_ascii=False)


def validate_code(code: str) -> bool:
    """Validate 6-digit login code."""
    return len(code) == 6 and code.isdigit()


# Words to strip from search queries (noise words that break TMDB search)
SEARCH_NOISE_WORDS = {
    # Russian
    "фильм", "фильмы", "сериал", "сериалы", "шоу", "аниме", "мультфильм", "мультфильмы",
    "мультсериал", "мультсериалы", "картина", "картины", "карт", "картине",
    # English
    "movie", "movies", "film", "films", "series", "show", "shows", "anime",
    "cartoon", "cartoons", "tv", "web", "series", "webseries", "web-series",
    # Common prefixes/suffixes
    "смотреть", "посмотреть", "online", "онлайн", "full", "fullhd", "hd",
}


def _strip_noise_words(title: str) -> str:
    """
    Remove noise words from a search title.
    
    Strips words like "фильм", "сериал", "movie", "show", etc. that
    would break TMDB search if included in the query.
    
    Args:
        title: Title string that may contain noise words
        
    Returns:
        Cleaned title with noise words removed
    """
    words = title.split()
    cleaned = [w for w in words if w.lower().rstrip('.,!?;:') not in SEARCH_NOISE_WORDS]
    return ' '.join(cleaned).strip()


def parse_search_query(query: str) -> Tuple[str, Optional[int]]:
    """
    Parse a search query to extract title and optional year.
    
    Extracts a 4-digit year (19xx or 20xx) from the end of the query string,
    removes noise words (фильм, сериал, movie, show, etc.), and returns
    the cleaned title and the year separately. This is useful because
    TMDB search works better without the year or noise words in the query.
    
    Args:
        query: Raw search query string (e.g. "фильм фукусима 2020")
        
    Returns:
        Tuple of (cleaned_title, year_or_none)
        
    Examples:
        >>> parse_search_query("фильм фукусима 2020")
        ("фукусима", 2020)
        >>> parse_search_query("сериал черное зеркало")
        ("черное зеркало", None)
        >>> parse_search_query("The Matrix")
        ("The Matrix", None)
        >>> parse_search_query("movie Spider-Man: No Way Home 2021")
        ("Spider-Man: No Way Home", 2021)
    """
    # Match 4-digit year (19xx or 20xx) at the end of the string
    match = re.search(r'\s*(19|20)\d{2}\s*$', query)
    if match:
        year = int(match.group(0).strip())
        # Validate year range (1900-2099)
        if 1900 <= year <= 2099:
            title = query[:match.start()].strip()
            title = _strip_noise_words(title)
            return title, year
    
    title = _strip_noise_words(query.strip())
    return title, None
