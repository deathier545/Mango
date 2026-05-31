"""One-shot: move mango modules into subpackages and rewrite imports (run from repo root)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANGO = ROOT / "mango"

MOVES: dict[str, str] = {
  # spotify
  "spotify_auto_close.py": "integrations/spotify/spotify_auto_close.py",
  "spotify_desktop_api.py": "integrations/spotify/spotify_desktop_api.py",
  "spotify_playback_router.py": "integrations/spotify/spotify_playback_router.py",
  "spotify_player_server.py": "integrations/spotify/spotify_player_server.py",
  "spotify_track_resolver.py": "integrations/spotify/spotify_track_resolver.py",
  "spotify_uri_launcher.py": "integrations/spotify/spotify_uri_launcher.py",
  "spotify_user_auth.py": "integrations/spotify/spotify_user_auth.py",
  "spotify_volume_duck.py": "integrations/spotify/spotify_volume_duck.py",
  "spotify_windows_ui.py": "integrations/spotify/spotify_windows_ui.py",
  # discord
  "discord_bridge_launcher.py": "integrations/discord/discord_bridge_launcher.py",
  "discord_music_sync.py": "integrations/discord/discord_music_sync.py",
  "discord_tts_client.py": "integrations/discord/discord_tts_client.py",
  "discord_voice_audio.py": "integrations/discord/discord_voice_audio.py",
  "discord_voice_bot.py": "integrations/discord/discord_voice_bot.py",
  "discord_voice_client.py": "integrations/discord/discord_voice_client.py",
  "discord_voice_control.py": "integrations/discord/discord_voice_control.py",
  # wake
  "wake_audio_gates.py": "wake/wake_audio_gates.py",
  "wake_capture.py": "wake/wake_capture.py",
  "wake_listener.py": "wake/wake_listener.py",
  "wake_phrase.py": "wake/wake_phrase.py",
  "oww_wake.py": "wake/oww_wake.py",
  "oww_mic_probe.py": "wake/oww_mic_probe.py",
  # smart
  "smart_store.py": "smart/smart_store.py",
  "smart_routines.py": "smart/smart_routines.py",
  "smart_brief.py": "smart/smart_brief.py",
  "smart_timeline.py": "smart/smart_timeline.py",
  "desktop_smart.py": "smart/desktop_smart.py",
  # desktop
  "desktop_app.py": "desktop/desktop_app.py",
  "desktop_ipc.py": "desktop/desktop_ipc.py",
  "jarvis_hud.py": "desktop/jarvis_hud.py",
  "globe_server.py": "desktop/globe_server.py",
}

# Old import prefix -> new (for modules that moved)
IMPORT_REWRITES: list[tuple[str, str]] = []
for old_name, new_rel in MOVES.items():
  mod = old_name.removesuffix(".py")
  new_mod = "mango." + new_rel.replace("/", ".").removesuffix(".py")
  IMPORT_REWRITES.append((f"mango.{mod}", new_mod))

# Sort longest first so substrings don't partial-match wrongly
IMPORT_REWRITES.sort(key=lambda x: len(x[0]), reverse=True)

INIT_PACKAGES = [
  MANGO / "integrations" / "__init__.py",
  MANGO / "integrations" / "spotify" / "__init__.py",
  MANGO / "integrations" / "discord" / "__init__.py",
  MANGO / "wake" / "__init__.py",
  MANGO / "smart" / "__init__.py",
  MANGO / "desktop" / "__init__.py",
]


def _ensure_inits() -> None:
  for path in INIT_PACKAGES:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
      path.write_text('"""Mango subpackage."""\n', encoding="utf-8")


def _move_files() -> None:
  for old_name, new_rel in MOVES.items():
    src = MANGO / old_name
    dst = MANGO / new_rel
    if not src.is_file():
      if dst.is_file():
        continue
      raise FileNotFoundError(src)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
      dst.unlink()
    src.rename(dst)


def _rewrite_file(path: Path) -> bool:
  text = path.read_text(encoding="utf-8")
  orig = text
  for old, new in IMPORT_REWRITES:
    text = text.replace(old, new)
  if text != orig:
    path.write_text(text, encoding="utf-8")
    return True
  return False


def _add_shims() -> None:
  for old_name, new_rel in MOVES.items():
    mod = old_name.removesuffix(".py")
    new_mod = "mango." + new_rel.replace("/", ".").removesuffix(".py")
    shim = MANGO / old_name
    if shim.exists():
      continue
    shim.write_text(
      f'"""Compatibility shim — use `{new_mod}`."""\n'
      f"from {new_mod} import *  # noqa: F403\n",
      encoding="utf-8",
    )


def main() -> None:
  _ensure_inits()
  _move_files()
  changed = 0
  for path in list(ROOT.rglob("*.py")):
    if ".venv" in path.parts or "node_modules" in path.parts:
      continue
    if "OpenJarvis" in path.parts:
      continue
    if "wake word" in path.parts:
      continue
    if _rewrite_file(path):
      changed += 1
  _add_shims()
  print(f"Relocated {len(MOVES)} modules; rewrote imports in {changed} files.")


if __name__ == "__main__":
  main()
