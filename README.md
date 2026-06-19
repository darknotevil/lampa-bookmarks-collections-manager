# Lampa bookmarks manager

Утилита для добавления в коллекции или закладки фильмов/сериалов/аниме Lampa mx c синхронизацией cub.rip с помощью API.

Поддерживает авторизацию, создание коллекции, поиск и добавление фильмов/сериалов/аниме по названию или TMDB ID в коллекцию или избранное.

Поддерживает интерактивный режим для выбора нужного фильма.

Полностью навайбкожен для себя. Дополнения и изменения приветствуются.

Спроектирован для использования в LLM: ставится как команда `lampa-cli`, у любой команды есть глобальный флаг `--json` для структурированного вывода. Инструкция для агента — `.agent/skills/add-to-lampa.md`.


Рекомендуется использовать с плагином collections.js который переопределяет стандартное поведение коллекций.
https://github.com/darknotevil/lampa-plugins-collection

### Install
```bash
uv tool install .            # ставит команду lampa-cli (или: uv tool install git+<repo>)
# запуск без установки во время разработки:
uv run lampa-cli --help
```

Любой команде можно добавить глобальный флаг `--json` (машинный вывод) и `--domain` (зеркало).

### 1. Login

**Используя код девайса** (https://cub.rip/add):

```bash
lampa-cli auth login                 # спросит 6-значный код
lampa-cli auth login --code 123456   # неинтерактивно
lampa-cli auth status                # кто я / валиден ли токен
```

Появится файл `$XDG_STATE_HOME/lampa-bookmarks/account.json` (по умолчанию `~/.local/state/lampa-bookmarks/account.json`, права 0600).

**Через существующий токен:**
```bash
lampa-cli auth login --token YOUR_TOKEN --profile YOUR_PROFILE_ID
```

### 2. List Collections

```bash
# свои
lampa-cli collections list --category user

# чужие
lampa-cli collections list --category new
lampa-cli collections list --category top

# содержимое коллекции
lampa-cli collections view --id 2948
```

### 3. Создать коллекцию

```bash
lampa-cli collections create --name "My Movies"
```

Вернёт collection id (идемпотентно — повторный вызов не создаёт дубликат), который можно использовать при добавлении.

### 4. Добавить фильм в избранное/коллекцию

Ищет по всем типам контента. Умеет вырезать слова фильм, сериал, tv show, movie и т.д. Умеет выделять год.
По умолчанию `items add` добавляет в избранное; при указании `--collection-id` — в коллекцию.

```bash
# Найти (кэширует карточки на диск для последующего add по id)
lampa-cli items search "The Devil Wears Prada"

# Добавить в избранное по TMDB id из результатов поиска
lampa-cli items add --id 350

# Добавить в коллекцию
lampa-cli items add --id 350 --collection-id 2948

# Сериал (тип берётся из кэша поиска; --type — запасной вариант)
lampa-cli items add --id 1399 --collection-id 2948 --type tv

# Убрать из коллекции
lampa-cli items remove --id 350 --collection-id 2948

# Массовое добавление из JSON-файла
lampa-cli items bulk-add --input items.json
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
from lampa_cli.client import LampaClient
```

## Project Structure

```
lampa-bookmarks-collections-manager/
├── AGENTS.md               # Routing entry point for AI agents
├── CLAUDE.md               # @AGENTS.md (Claude Code shim)
├── README.md               # This file
├── pyproject.toml          # Packaging (hatchling) + deps + lampa-cli entry point
├── .agent/
│   ├── memory-bank/        # Architecture, tech stack, progress
│   ├── skills/
│   │   └── add-to-lampa.md # Agent skill describing the lampa-cli --json workflow
│   ├── notes/              # Gotchas / patterns
│   ├── resources/          # Shared templates
│   └── sessions/           # Per-session summaries (gitignored)
└── src/
    └── lampa_cli/
        ├── __init__.py     # Package exports (library API)
        ├── client.py       # Main API client
        ├── auth.py         # Authentication module
        ├── models.py       # Pydantic data models
        ├── search.py       # Shared search/card logic + result cache
        ├── utils.py        # Utility functions
        └── cli/            # Typer CLI: auth / collections / items / bookmarks
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

1. **Token Expiry:** Token expiry behavior is unknown. Long-running sessions may need token refresh.

2. **Rate Limits:** API rate limits are unknown.

3. **`bookmarks remove`** reports `secuses: false` even when the deletion succeeds — the flag from this endpoint isn't a reliable success signal.

## License

MIT

## References

- [Lampa MX Source](https://github.com/yumata/lampa-source)
- [Collections Plugin](../plugins_collection/collections)
