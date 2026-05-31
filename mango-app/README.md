# Mango App (Electron + React)

Desktop UI for Mango voice assistant, backed by Python runtime (`python -m mango`).

## Requirements

- Node.js 18+ and npm
- Python 3.11+ in workspace root (recommended: `.venv`)
- Windows (current launch scripts target PowerShell/Windows paths)

## Project layout

- `mango-app/electron/main.cjs` - Electron main process + Python spawn + IPC
- `mango-app/electron/preload.cjs` - secure renderer bridge (`window.mango`)
- `mango-app/src/App.tsx` - main UI (orb, tabs, controls)
- `mango-app/src/App.css` - UI theme/style
- `../mango` - Python runtime package

## Install

From `mango-app`:

```bash
npm install
```

## Run from repo root

```powershell
..\scripts\start-mango-full.ps1
```

Creates/uses `../.venv`, installs npm deps if needed, then runs `npm run dev`.

## Run modes

- `npm run dev` - start Vite + Electron together (recommended)
- `npm run dev:web` - web-only renderer (no Electron bridge)
- `npm run dev:electron` - Electron only (expects dev web server on port 5180; override via `MANGO_DEV_PORT` in `.env.development`)
- `npm run build` - production build (TypeScript + Vite)
- `npm run start` - run Electron app

## Python runtime and environment

Electron launches Python from workspace root (`../`) using:

```bash
python -m mango
```

Expected:

- Python module `mango` importable from workspace root
- optional virtualenv at either:
  - `../.venv/Scripts/python.exe`
  - `./.venv/Scripts/python.exe`

## Required `.env` values (workspace root)

Minimum common setup:

- `GROQ_API_KEY=...`
- `GROQ_MODEL=...` (optional override)

Useful toggles:

- `MANGO_STARTUP_INTRO=1` (set `0` to disable intro)
- `MANGO_STARTUP_WEATHER=1` (set `0` to skip startup weather fetch)
- `MANGO_INTRO_PLACE_NAME=DeKalb`
- `MANGO_INTRO_LAT=41.9295`
- `MANGO_INTRO_LON=-88.7504`
- `MANGO_INTRO_TIMEZONE=America/Chicago`

HUD toggles:

- Electron app HUD is React canvas (default path)
- legacy Python pygame HUD can be blocked with `MANGO_DISABLE_LEGACY_HUD=1`

## Doctor mode and utility modes

From workspace root:

```bash
python -m mango --doctor
python -m mango --oww-mic-probe
python -m mango --discord-voice
python -m mango --desktop
```

## Troubleshooting

- **UI says bridge missing**: launch with `npm run dev` (not `dev:web` only).
- **Electron opens but Mango won’t start**: verify Python path and `GROQ_API_KEY`.
- **Old HUD window appears**: ensure `MANGO_DISABLE_LEGACY_HUD=1` and restart Mango.
- **No startup weather**: check network and `MANGO_STARTUP_WEATHER`; defaults to DeKalb fallback.
- **Blank/unstable orb**: switch tabs once and restart app; check dev console for renderer errors.
