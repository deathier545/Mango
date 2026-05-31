# Mango Voice Assistant (Windows)

Push-to-talk voice assistant using local speech-to-text (Whisper), Groq or Ollama LLM with tools, and Edge neural TTS.

## Prerequisites

- Python 3.11+
- Windows (paths and app launcher assume Windows)
- Microphone and speakers

## Quick start (recommended)

**Desktop UI (Electron + voice):**

```powershell
.\scripts\start-mango-full.ps1
```

**First-time setup:**

```powershell
.\scripts\setup-env.ps1          # create .env if missing
# Edit .env: set GROQ_API_KEY, review docs\recommended.env
python -m mango --doctor         # config, mic, Groq model check
.\scripts\healthcheck.ps1        # doctor + pytest
```

Install Python deps with either `pip install -r requirements.txt` or `pip install ".[full]"` from the repo root.

**Memory:** default `MANGO_MEMORY_TIER=session` (no disk history). See [docs/memory-tiers.md](docs/memory-tiers.md).

**Trim tools:** `MANGO_DISABLED_TOOLS=discord_voice,xbox_console,...` in `.env` hides integrations you do not use. PowerShell confirmation stays on by default.

**Safe mode (debugging):** set `MANGO_SAFE_MODE=1` or enable **Safe mode** in Electron settings to force push-to-talk only, disable wake/always-listen, and skip Discord bridge + nonessential tools.

## Setup

1. Create a virtual environment and install dependencies:

```powershell
cd path\to\mango-repo
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

2. Copy `.env.example` to `.env` and set `GROQ_API_KEY` from [Groq Console](https://console.groq.com/). Optionally set `GROQ_MODEL`. Override push-to-talk with `HOTKEY` (e.g. `alt+w`, `v`, `f9`).

**Privacy:** opt-in features store plaintext on disk under `%USERPROFILE%\.mango\` when enabled (see `.env.example`).

3. Run (advanced / headless):

```powershell
python -m mango              # voice loop (push-to-talk)
python -m mango --doctor     # diagnostics only
python -m mango --ptt-only   # disable wake / always-listen for this run
```

The desktop shell starts Mango in a child process automatically — you usually do not need `python -m mango --desktop` directly.

Alternate desktop paths: `.\run-desktop.ps1`, `.\scripts\run-mango-desktop.ps1`, or `cd mango-app && npm run dev`.

## Desktop UI (`mango-app`)

Node.js 18+ required. **Recommended entrypoint:**

```powershell
.\scripts\start-mango-full.ps1
```

See [mango-app/README.md](mango-app/README.md).

## Project layout

| Path | Role |
|------|------|
| `mango/` | Python runtime, tools, integrations |
| `mango/config.py` | `Config` dataclass; `config_build.py` parses env |
| `mango/integrations/` | Spotify, Discord helpers |
| `mango/wake/`, `smart/`, `desktop/` | Wake word, smart cards, HUD / IPC |
| `mango-app/` | Electron desktop UI |
| `tests/` | Pytest |
| `docs/` | [Roadmap](docs/ROADMAP.md), [env index](docs/env/README.md) |
| `wake word/` | Optional openWakeWord training sandbox |

## Usage

- **Hold push-to-talk** (default `Alt+W`), speak, **release** to send.
- Wake phrase: `MANGO_WAKEWORD=1`, `MANGO_WAKE_PHRASE=mango`.
- Tools: files, apps, web search, Spotify, Discord voice, PowerShell (with confirmation), and more.

### Hotkeys

The `keyboard` library may need an **elevated** terminal for global hotkeys on Windows.

### First run

Whisper downloads `base.en` on first transcription (allow a few minutes).

## Development

```powershell
.\scripts\healthcheck.ps1
python -m pytest tests -q
.\run-tests.ps1
.\run-dev.ps1
python -m mango --doctor
python -m ruff check mango tests
python -m mypy mango/config.py mango/tool_registry.py mango/main.py --follow-imports=skip
```

- `requirements.txt` — runtime minimums
- `requirements-pinned.txt` — reproducible CI/local installs
- `requirements-dev.txt` — pytest, ruff, mypy, pre-commit

## Logs and artifacts

- `MANGO_LOG_FILE=logs/mango-runtime.log` (optional)
- `.\scripts\cleanup-local-artifacts.ps1` (dry run) / `-Apply`

## Memory tiers

- `MANGO_MEMORY_TIER=session` — in-process only (default)
- `day` — rolling + daily snapshots
- `profile` — durable across restarts

## Optional sibling projects

Keep unrelated trees (e.g. `OpenJarvis/`) outside this repo when possible. `OpenJarvis/` is in `.cursorignore` for editor indexing only.
