# Lampa bookmarks manager

CLI + Python library for managing Lampa MX bookmarks and collections via the cub.rip API — search, add, remove, and bulk operations. Installable as the `lampa-cli` command (`uv tool install`); human-readable by default, with a global `--json` flag for LLM agents.

## Routing

When working on this project, follow the appropriate link:

- **Architecture & system patterns** → `.agent/memory-bank/architecture.md`
- **Tech stack & commands (run / build / test / lint)** → `.agent/memory-bank/tech-stack.md`
- **Project status & progress** → `.agent/memory-bank/progress.md`
- **Agent skill — adding movies/shows via `lampa-cli --json`** → `.agent/skills/add-to-lampa.md`
- **Reusable recipes (deploy, migrations, …)** → `.agent/skills/`
- **Project-specific gotchas / patterns** → `.agent/notes/`
- **Prior session summaries** → `.agent/sessions/`
- **Shared templates and rules** → `.agent/resources/`

## Updates

Update `.agent/` only when (a) the user explicitly asks ("обнови AGENTS.md", "запиши итоги"),
or (b) the user confirms at end-of-session. Never write without confirmation.
