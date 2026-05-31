# Mango roadmap

Active engineering backlog (non-security). Completed upgrade checklist lives in git history (`TODO_UPGRADES.md` archived).

## Done recently

- Package layout: `mango/integrations/{spotify,discord}`, `mango/wake`, `mango/smart`, `mango/desktop`
- Split `main.py` → `voice_loop`, `voice_prompt`, `llm_tool_loop`
- Split `tool_registry` → `tool_policy`, `tool_definitions`
- Config: `config_dotenv` (no parent `.env` walk); pytest isolation via empty tmp `.env`
- CI: pinned deps + ruff + mypy; `requirements-dev.txt` + `pyproject.toml`

## Next

- Optional: split `config_build.py` into section loaders (`load_wake_config`, etc.)
- Expand mypy `disallow_untyped_defs` to integrations and `voice_loop`
- Optional: drop compatibility shims (`mango/spotify_*.py`, `jarvis_hud.py`) after one release
- `mango-app`: document settings file precedence (repo root vs `mango-app/`)
- Wake training: keep under `wake word/` or move to `tools/wake-training/` with its own README

## Ideas

- Plugin entry points for tools instead of central `execute()` elif chain
- Minimal install extras (`[spotify]`, `[discord]`, `[wake-oww]`) in `pyproject.toml`
