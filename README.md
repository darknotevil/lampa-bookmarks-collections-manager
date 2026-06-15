# Lampa bookmarks manager

Утилита для добавления в коллекции или закладки фильмов/сериалов/аниме Lampa mx c синхронизацией cub.rip с помощью API.

Поддерживает авторизацию, создание коллекции, поиск и добавление фильмов/сериалов/аниме по названию или TMDB ID в коллекцию или избранное.

Поддерживает интерактивный режим для выбора нужного фильма.

Полностью навайбкожен для себя. Дополнения и изменения приветствуются.

Спроектирован для использования в LLM. `.agent/skills/add-to-lampa.md` и `examples/agent_tool.py` прилагаются.


Рекомендуется использовать с плагином collections.js который переопределяет стандартное поведение коллекций.
```bash
pip install -r requirements.txt
```
### 1. Login

**Используя код девайса:**

https://cub.rip/add

```bash
python examples/login.py --code 123456
```

Появится файл `$XDG_STATE_HOME/lampa-bookmarks/account.json` (по умолчанию `~/.local/state/lampa-bookmarks/account.json`, права 0600).
 
### 2. List Collections

```bash
свои
python examples/list_collections.py --category user

чужие
python examples/list_collections.py --category new
python examples/list_collections.py --category top
```

### 3. Создать коллекцию

```bash
python examples/create_collection.py --name "My Movies"
```

Вернет collection id который можно использовать при добавлении.

### 4. Добавить фильм в избранное/коллекцию

Ищет по всем типам контента. Умеет вырезать слова фильм,сериал,tv show,movie и т.д. Умеет выделять год.
По умолчанию добавляет в избранное. При указании collecion-id - в коллекцию.

```bash
# Найти и добавить (автоматически выбирает первый результат)
python examples/add_items.py--search "The Devil Wears Prada"

# Интерактивный режим с выбором (есть возможность выбрать любой из поиска)
python examples/add_items.py --search "смешарики" -i

# Add by TMDB ID
python examples/add_items.py --collection-id 2948 --tmdb-id 350

# Add multiple movies
python examples/add_items.py --collection-id 2948 --tmdb-id 350 27205 155

# Add a TV show
python examples/add_items.py --collection-id 2948 --tmdb-id 1399 --type tv


```


**Login Using Existing Token:**
```bash
python examples/login.py --token YOUR_TOKEN --profile YOUR_PROFILE_ID
```


## Фичи
TODO:
- добавление коллекции с mdblist.com (сразу есть tmdb id)


Done:
- ✅ Аутентификация по девайс коду
- ✅ Token-based login
- ✅ Session persistence
- ✅ List collections by category
- ✅ View collection items
- ✅ Like/unlike collections
- ✅ Create collections
- ✅ Add items to collections (by TMDB ID)
- ✅ Add items to bookmarks (favorites)
- ✅ Remove bookmarks
- ✅ List bookmarks
- ✅ TMDB proxy integration
- ✅ плагин для лампы коллекции + избранное в одном месте


### 6. Python API

```python
from src.client import LampaClient

# Create client
client = LampaClient(domain='cub.rip')

# Login with token
client.login_with_token(
    token='your_token',
    profile_id='your_profile_id',
    email='your@email.com'
)

# List collections
collections = client.list_collections(category='new')
for coll in collections.results:
    print(f"{coll.title} - {coll.items_count} items")

# View collection items
items = client.view_collection(collection_id='123')
for item in items.results:
    print(f"{item.title} (TMDB ID: {item.id})")

# Create a new collection
resp = client.create_collection(name="My Favorites")
print(f"Created: {resp.collection.id}")

# Add items to collection (uses TMDB IDs)
client.add_item_to_collection(
    collection_id=resp.collection.id,
    tmdb_id='350',       # The Devil Wears Prada
    media_type='movie'
)

# Like a collection
client.like_collection(collection_id='123', like=True)

# Add to bookmarks (favorites)
client.add_bookmark(tmdb_id='350', media_type='movie')

# Add to bookmarks with pre-built card data (e.g., from search)
search_results = client.search_movies(query='Inception')
if search_results:
    client.add_bookmark(
        tmdb_id=str(search_results[0]['id']),
        media_type='movie',
        card_data=search_results[0]  # Pass search result directly
    )

# Remove a bookmark
client.remove_bookmark(bookmark_id='53838463')

# List all bookmarks
bookmarks = client.list_bookmarks()

# Search TMDB
results = client.search_tmdb(query='Inception')
```

## Project Structure

```
lampa-bookmarks-collections-manager/
├── AGENTS.md               # Routing entry point for AI agents
├── CLAUDE.md               # @AGENTS.md (Claude Code shim)
├── README.md               # This file
├── requirements.txt        # Python dependencies
├── .agent/
│   ├── memory-bank/        # Architecture, tech stack, progress
│   ├── skills/
│   │   └── add-to-lampa.md # Agent skill describing the agent_tool workflow
│   ├── notes/              # Gotchas / patterns
│   ├── resources/          # Shared templates
│   └── sessions/           # Per-session summaries (gitignored)
├── src/
│   ├── __init__.py         # Package exports
│   ├── client.py           # Main API client
│   ├── auth.py             # Authentication module
│   ├── models.py           # Pydantic data models
│   ├── search.py           # Shared search/card logic + result cache
│   └── utils.py            # Utility functions
├── examples/
│   ├── login.py              # Login example
│   ├── list_collections.py   # List collections example
│   ├── create_collection.py  # Create collection example
│   ├── add_items.py          # Add items (interactive, human-facing)
│   ├── agent_tool.py         # Add items (JSON output, for LLM agents)
│   └── bulk_add_movies.py    # Bulk-add helper
└── tests/
    ├── test_auth.py
    └── test_collections.py
```

## API Reference

### Authentication

| Method | Description |
|--------|-------------|
| `login_with_code(code)` | Login with 6-digit code |
| `login_with_token(token, profile_id, email)` | Login with existing token |
| `logout()` | Clear session |
| `is_authenticated()` | Check auth status |

### Collections

| Method | Description |
|--------|-------------|
| `list_collections(category, page)` | List collections |
| `view_collection(id, page)` | View collection items |
| `like_collection(id, like)` | Like/unlike collection |
| `create_collection(name)` | Create new collection |
| `add_item_to_collection(collection_id, tmdb_id, media_type)` | Add item by TMDB ID |

### Bookmarks

| Method | Description |
|--------|-------------|
| `add_bookmark(tmdb_id, media_type, card_data)` | Add movie/TV to bookmarks |
| `remove_bookmark(bookmark_id, bookmark_type)` | Remove a bookmark |
| `list_bookmarks()` | List all bookmarks |

### TMDB Proxy

| Method | Description |
|--------|-------------|
| `search_catalog(query, page)` | Search CUB catalog (localized content) |
| `search_tmdb(query, page)` | Search movies/TV |
| `get_tmdb_movie(tmdb_id)` | Get movie details |
| `get_tmdb_tv(tmdb_id)` | Get TV show details |
| `get_tmdb_movie_by_id(tmdb_id, language)` | Get movie via apitmdb proxy |
| `get_tmdb_tv_by_id(tmdb_id, language)` | Get TV show via apitmdb proxy |

## Configuration

Files live under XDG base directories (override via env vars):

| File | Default path | Purpose |
|---|---|---|
| `settings.json` | `$XDG_CONFIG_HOME/lampa-bookmarks/` (`~/.config/lampa-bookmarks/`) | Domain / protocol / timeout |
| `account.json` | `$XDG_STATE_HOME/lampa-bookmarks/` (`~/.local/state/lampa-bookmarks/`) | Saved token + profile, 0600 perms |
| `search_cache.json` | `$XDG_CACHE_HOME/lampa-bookmarks/` (`~/.cache/lampa-bookmarks/`) | Search result cache (safe to delete) |

Example `settings.json`:

```json
{
    "domain": "cub.rip",
    "protocol": "https",
    "timeout": 8000
}
```

## Available Domains

| Domain | Type |
|--------|------|
| `cub.rip` | Primary |
| `durex.monster` | Mirror |
| `cubnotrip.top` | Mirror |

## Known Limitations

1. **Remove Items:** The API endpoint for removing items from collections has not been discovered yet. Potential endpoints to test: `/api/collections/remove` or `/api/collections/delete`.

2. **Token Expiry:** Token expiry behavior is unknown. Long-running sessions may need token refresh.

3. **Rate Limits:** API rate limits are unknown.

## ID Reference

When adding items to collections, you need to use the correct IDs:

| ID Type | Where to Find | Example |
|---------|---------------|---------|
| **Collection ID** | Response from `create_collection()` or `list_collections()` | `2948` |
| **TMDB ID (card_id)** | TMDB search or movie URL | `350` (The Devil Wears Prada) |
| **Profile ID** | Account data after login | `780890` |
| **User ID (cid)** | Account data after login | `732666` |

## Development

### Running Tests

```bash
python -m pytest tests/
```

### Adding New Endpoints

1. Discover endpoint from network traffic
2. Add method to `src/client.py`
3. Add model to `src/models.py` if needed
4. Update examples

## License

MIT

## References

- [Lampa MX Source](https://github.com/yumata/lampa-source)
- [Collections Plugin](../plugins_collection/collections)
