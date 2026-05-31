"""Fix imports after package relocation."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANGO = ROOT / "mango"

MOVES: dict[str, str] = {
  "spotify_auto_close.py": "integrations/spotify/spotify_auto_close.py",
  "spotify_desktop_api.py": "integrations/spotify/spotify_desktop_api.py",
  "spotify_playback_router.py": "integrations/spotify/spotify_playback_router.py",
  "spotify_player_server.py": "integrations/spotify/spotify_player_server.py",
  "spotify_track_resolver.py": "integrations/spotify/spotify_track_resolver.py",
  "spotify_uri_launcher.py": "integrations/spotify/spotify_uri_launcher.py",
  "spotify_user_auth.py": "integrations/spotify/spotify_user_auth.py",
  "spotify_volume_duck.py": "integrations/spotify/spotify_volume_duck.py",
  "spotify_windows_ui.py": "integrations/spotify/spotify_windows_ui.py",
  "discord_bridge_launcher.py": "integrations/discord/discord_bridge_launcher.py",
  "discord_music_sync.py": "integrations/discord/discord_music_sync.py",
  "discord_tts_client.py": "integrations/discord/discord_tts_client.py",
  "discord_voice_audio.py": "integrations/discord/discord_voice_audio.py",
  "discord_voice_bot.py": "integrations/discord/discord_voice_bot.py",
  "discord_voice_client.py": "integrations/discord/discord_voice_client.py",
  "discord_voice_control.py": "integrations/discord/discord_voice_control.py",
  "wake_audio_gates.py": "wake/wake_audio_gates.py",
  "wake_capture.py": "wake/wake_capture.py",
  "wake_listener.py": "wake/wake_listener.py",
  "wake_phrase.py": "wake/wake_phrase.py",
  "oww_wake.py": "wake/oww_wake.py",
  "oww_mic_probe.py": "wake/oww_mic_probe.py",
  "smart_store.py": "smart/smart_store.py",
  "smart_routines.py": "smart/smart_routines.py",
  "smart_brief.py": "smart/smart_brief.py",
  "smart_timeline.py": "smart/smart_timeline.py",
  "desktop_smart.py": "smart/desktop_smart.py",
  "desktop_app.py": "desktop/desktop_app.py",
  "desktop_ipc.py": "desktop/desktop_ipc.py",
  "jarvis_hud.py": "desktop/jarvis_hud.py",
  "mango_hud.py": "desktop/mango_hud.py",
  "globe_server.py": "desktop/globe_server.py",
}

MOD_TO_FULL: dict[str, str] = {
  old.removesuffix(".py"): "mango." + new.replace("/", ".").removesuffix(".py")
  for old, new in MOVES.items()
}


def _shim_content(target: str) -> str:
  return (
    f'"""Compatibility shim — prefer `{target}`."""\n'
    "import sys as _sys\n"
    f"import {target} as _impl\n"
    "_sys.modules[__name__] = _impl\n"
  )


def _rewrite_from_mango_import_line(line: str) -> str:
  m = re.match(r"^(\s*)from mango import (.+)$", line)
  if not m:
    return line
  indent, rest = m.group(1), m.group(2).strip()
  parts = [p.strip() for p in rest.split(",")]
  lines: list[str] = []
  for part in parts:
    if " as " in part:
      mod, alias = [x.strip() for x in part.split(" as ", 1)]
    else:
      mod, alias = part, part
    full = MOD_TO_FULL.get(mod)
    if full:
      lines.append(f"{indent}import {full} as {alias}")
    else:
      lines.append(f"{indent}from mango import {part}")
  return "\n".join(lines)


def _rewrite_file(text: str) -> str:
  out_lines: list[str] = []
  for line in text.splitlines():
    if line.strip().startswith("from mango import "):
      out_lines.append(_rewrite_from_mango_import_line(line))
    else:
      # Fix broken prior rewrite: from pkg.mod import mod as alias -> import pkg.mod as alias
      broken = re.match(
        r"^(\s*)from (mango\.[\w.]+)\.([\w]+) import \3 as (\w+)$",
        line,
      )
      if broken:
        indent, pkg, mod, alias = broken.groups()
        out_lines.append(f"{indent}import {pkg}.{mod} as {alias}")
        continue
      broken2 = re.match(
        r"^(\s*)from (mango\.[\w.]+)\.([\w]+) import \3$",
        line,
      )
      if broken2:
        indent, pkg, mod = broken2.groups()
        out_lines.append(f"{indent}import {pkg}.{mod}")
        continue
      out_lines.append(line)
  return "\n".join(out_lines) + ("\n" if text.endswith("\n") else "")


def main() -> None:
  for old_name, new_rel in MOVES.items():
    target = "mango." + new_rel.replace("/", ".").removesuffix(".py")
    (MANGO / old_name).write_text(_shim_content(target), encoding="utf-8")

  changed = 0
  for path in ROOT.rglob("*.py"):
    if any(p in path.parts for p in (".venv", "node_modules", "OpenJarvis", "wake word")):
      continue
    text = path.read_text(encoding="utf-8")
    new = _rewrite_file(text)
    if new != text:
      path.write_text(new, encoding="utf-8")
      changed += 1
  print(f"Fixed shims and imports in {changed} files.")


if __name__ == "__main__":
  main()
