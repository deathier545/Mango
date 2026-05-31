# Environment variables

Copy `.env.example` to `.env` at the **repository root** (same folder as `mango/`).

## Minimal

| Variable | Purpose |
|----------|---------|
| `GROQ_API_KEY` | Cloud LLM (default provider) |
| `HOTKEY` | Push-to-talk combo (default `alt+w`) |

For local Ollama instead of Groq: `MANGO_LLM_PROVIDER=ollama` and `MANGO_OLLAMA_MODEL=…`.

## Sections in `.env.example`

| Topic | Key prefixes |
|-------|----------------|
| LLM | `GROQ_*`, `MANGO_LLM_*`, `MANGO_OLLAMA_*` |
| Memory | `MANGO_MEMORY_TIER`, `MANGO_MEMORY_*` — see [memory-tiers.md](../memory-tiers.md) |
| Tools | `MANGO_DISABLED_TOOLS`, `MANGO_REQUIRE_*_CONFIRMATION` |
| Wake | `MANGO_WAKE*`, `MANGO_OWW_*`, `MANGO_ALWAYS_LISTEN*` |
| Audio / STT | `MANGO_WHISPER_*`, `MANGO_MIN_RECORD_*`, `MANGO_AUDIO_*` |
| TTS | `MANGO_TTS_*`, `ELEVENLABS_*` |
| Memory | `MANGO_MEMORY_*`, `MANGO_PERSISTENT_MEMORY` |
| Spotify | `MANGO_SPOTIFY_*`, `SPOTIFY_*` |
| Discord voice | `MANGO_DISCORD_*` |
| Tools / policy | `MANGO_REQUIRE_*_CONFIRMATION`, `MANGO_STRICT_TOOLS` |
| Desktop / session | `MANGO_SESSION_LOG*`, `MANGO_LOG_*` |

Full comments and defaults: [.env.example](../../.env.example).
