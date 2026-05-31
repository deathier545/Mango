"""Open allowed Windows apps via Start Menu shortcuts, well-known paths, and safe aliases."""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)

_NAME_RE = re.compile(r"[^a-z0-9]+")
_URL_IN_TEXT_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)
_DOMAIN_RE = re.compile(
    r"^(?:www\.)?[a-z0-9][-a-z0-9.]*\.[a-z]{2,}(?:/[^\s]*)?$",
    re.IGNORECASE,
)

_BROWSER_KEYS = frozenset({"edge", "chrome", "firefox", "brave"})
_BROWSER_PHRASES: tuple[tuple[str, str], ...] = (
    ("microsoft edge", "edge"),
    ("msedge", "edge"),
    ("google chrome", "chrome"),
    ("chrome", "chrome"),
    ("mozilla firefox", "firefox"),
    ("firefox", "firefox"),
    ("brave browser", "brave"),
    ("brave", "brave"),
    ("edge", "edge"),
)

_SITE_SHORTCUTS: dict[str, str] = {
    "youtube": "https://www.youtube.com/",
    "youtu": "https://www.youtube.com/",
    "yt": "https://www.youtube.com/",
    "google": "https://www.google.com/",
    "gmail": "https://mail.google.com/",
    "reddit": "https://www.reddit.com/",
    "twitter": "https://twitter.com/",
    "x": "https://x.com/",
    "github": "https://github.com/",
    "twitch": "https://www.twitch.tv/",
    "netflix": "https://www.netflix.com/",
    "amazon": "https://www.amazon.com/",
    "wikipedia": "https://www.wikipedia.org/",
    "bing": "https://www.bing.com/",
}

# App keys that must not be treated as YouTube search queries.
_KNOWN_APP_KEYS = frozenset(
    {
        "edge",
        "chrome",
        "firefox",
        "brave",
        "spotify",
        "discord",
        "slack",
        "teams",
        "zoom",
        "steam",
        "vlc",
        "vscode",
        "code",
        "notepad",
        "calculator",
        "calc",
        "paint",
        "settings",
        "terminal",
        "wt",
        "explorer",
        "obs",
        "signal",
        "telegram",
        "whatsapp",
        "outlook",
    }
)

_VIDEO_QUERY_HINTS = (
    "video",
    "youtube",
    "youtu",
    "watch",
    "mr beast",
    "mrbeast",
    "channel",
    "playlist",
)


def _norm(s: str) -> str:
    return _NAME_RE.sub("", s.casefold())


# Normalize user phrases to our canonical keys (e.g. "Spotify Music" app label).
_KEY_ALIASES: dict[str, str] = {
    "spotifymusic": "spotify",
    "spotifyabspotifymusic": "spotify",
    "microsoftteams": "teams",
    "xbox": "xbox",
    "xboxapp": "xbox",
    "vlcmediaplayer": "vlc",
    "obsstudio": "obs",
    "bravebrowser": "brave",
    "googlechrome": "chrome",
    "chromebrowser": "chrome",
    "googchrome": "chrome",
    "microsoftedge": "edge",
    "msedge": "edge",
    "edgebrowser": "edge",
    "mozillafirefox": "firefox",
    "visualstudiocode": "vscode",
    "vscodeinsiders": "vscode",
    "discordapp": "discord",
    "slackapp": "slack",
}


def normalized_app_key(app_name: str) -> str:
    """Normalize user-facing app label for lookups (same rules as ``open_app``)."""
    raw = (app_name or "").strip()
    if not raw:
        return ""
    key = _norm(raw)
    return _KEY_ALIASES.get(key, key)


def _default_browser_key() -> str | None:
    raw = os.getenv("MANGO_DEFAULT_BROWSER", "edge").strip().casefold()
    if raw in ("", "default", "system"):
        return None
    if raw in _BROWSER_KEYS:
        return raw
    aliased = normalized_app_key(raw)
    return aliased if aliased in _BROWSER_KEYS else None


def _strip_browser_from_text(text: str) -> tuple[str | None, str]:
    """If text names a browser, return (browser_key, remainder)."""
    t = (text or "").strip()
    low = t.casefold()
    for phrase, bkey in sorted(_BROWSER_PHRASES, key=lambda x: -len(x[0])):
        if phrase not in low:
            continue
        pattern = re.compile(re.escape(phrase), re.IGNORECASE)
        remainder = pattern.sub(" ", t).strip()
        remainder = re.sub(r"\s+", " ", remainder)
        remainder = re.sub(r"^(on|in|with|using)\s+", "", remainder, flags=re.I).strip()
        remainder = re.sub(r"\s+(on|in|with|using)$", "", remainder, flags=re.I).strip()
        return bkey, remainder
    return None, t


def _normalize_url(raw: str) -> str | None:
    s = (raw or "").strip().strip('"').strip("'")
    if not s:
        return None
    if _URL_IN_TEXT_RE.match(s):
        return s
    key = normalized_app_key(s)
    if key in _SITE_SHORTCUTS:
        return _SITE_SHORTCUTS[key]
    if _DOMAIN_RE.match(s):
        return "https://" + s.lstrip("/")
    return None


def _clean_video_search_query(text: str) -> str:
    q = re.sub(r"\s+", " ", (text or "").strip())
    for pat in (
        r"^(please\s+)?(open|watch|play|find|show|launch|pull up|queue)\s+(a\s+)?(the\s+)?",
        r"\s+(video|videos)(\s+on\s+youtube)?$",
        r"\s+on\s+youtube$",
        r"^youtube\s+(search\s+)?",
    ):
        q = re.sub(pat, "", q, flags=re.IGNORECASE).strip()
    return q


def _youtube_search_url(query: str) -> str:
    return f"https://www.youtube.com/results?search_query={quote_plus(query)}"


def _try_youtube_search(text: str) -> str | None:
    """Turn phrases like 'mr beast video' into a YouTube search URL."""
    raw = (text or "").strip()
    if not raw or _URL_IN_TEXT_RE.search(raw) or _DOMAIN_RE.match(raw):
        return None

    key = normalized_app_key(raw)
    if key in _SITE_SHORTCUTS or key in _STATIC_ALIASES or key in _KNOWN_APP_KEYS:
        return None
    if _try_direct_exe(key) or _resolve_installed_app(key):
        return None

    low = raw.casefold()
    if not any(h in low for h in _VIDEO_QUERY_HINTS):
        return None

    query = _clean_video_search_query(raw)
    if len(query) < 2:
        return None
    return _youtube_search_url(query)


def _parse_web_request(app_name: str, url: str | None = None) -> tuple[str | None, str] | None:
    """Return (browser_key|None, normalized_url) when opening a site/page."""
    explicit_url = _normalize_url(url or "")
    if not explicit_url and (url or "").strip():
        explicit_url = _try_youtube_search((url or "").strip())
    browser_from_name, remainder = _strip_browser_from_text(app_name or "")

    if explicit_url:
        browser = browser_from_name
        if not browser:
            b2, _ = _strip_browser_from_text(remainder)
            browser = b2
        if not browser:
            browser = _default_browser_key()
        return browser, explicit_url

    text = (remainder or "").strip()
    if not text:
        return None

    url_match = _URL_IN_TEXT_RE.search(text)
    if url_match:
        browser = browser_from_name or _default_browser_key()
        return browser, url_match.group(0).rstrip(".,);]")

    norm = normalized_app_key(text)
    if norm in _SITE_SHORTCUTS:
        browser = browser_from_name or _default_browser_key()
        return browser, _SITE_SHORTCUTS[norm]

    as_url = _normalize_url(text)
    if as_url:
        browser = browser_from_name or _default_browser_key()
        return browser, as_url

    yt = _try_youtube_search(text)
    if yt:
        browser = browser_from_name or _default_browser_key()
        return browser, yt

    return None


def _resolve_browser_exe(browser_key: str | None) -> str:
    if not browser_key:
        return ""
    direct = _try_direct_exe(browser_key)
    if direct:
        return direct
    installed = _resolve_installed_app(browser_key)
    if installed:
        return installed
    return _which_on_path(browser_key)


def _launch_url(url: str, browser_key: str | None) -> str:
    url = (url or "").strip()
    if not url:
        return "Error: URL is empty."

    if browser_key:
        exe = _resolve_browser_exe(browser_key)
        if not exe:
            return (
                f"Could not find {browser_key} on this PC to open {url}. "
                "Try chrome or your default browser."
            )
        try:
            subprocess.Popen(
                [exe, url],
                close_fds=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info("open_app: url=%r browser=%r exe=%r", url, browser_key, exe)
            label = browser_key.capitalize()
            return f"Opened {url} in {label}."
        except OSError as exc:
            logger.warning("open_app: browser launch failed %s", exc, exc_info=True)
            return f"Error opening {url} in {browser_key}: {exc}"

    try:
        os.startfile(url)  # type: ignore[attr-defined]
        logger.info("open_app: url=%r via default browser", url)
        return f"Opened {url}."
    except OSError as exc:
        logger.warning("open_app: default browser open failed %s", exc, exc_info=True)
        return f"Error opening {url}: {exc}"


@lru_cache(maxsize=1)
def _start_menu_lnk_index() -> dict[str, Path]:
    roots = []
    pd = os.environ.get("ProgramData")
    ap = os.environ.get("APPDATA")
    if pd:
        roots.append(Path(pd) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    if ap:
        roots.append(Path(ap) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    idx: dict[str, Path] = {}
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*.lnk"):
            stem = _norm(path.stem)
            if stem and stem not in idx:
                idx[stem] = path
    return idx


_STATIC_ALIASES: dict[str, str] = {
    "notepad": "notepad",
    "calculator": "calc",
    "calc": "calc",
    "paint": "mspaint",
    "mspaint": "mspaint",
    "snippingtool": "snippingtool",
    "snipping": "snippingtool",
    "settings": "ms-settings:",
    "windowssettings": "ms-settings:",
    "explorer": "explorer",
    "fileexplorer": "explorer",
    "powershell": "powershell",
    "terminal": "wt",
    "wt": "wt",
    "commandprompt": "cmd",
    "cmd": "cmd",
    "taskmanager": "taskmgr",
    "photos": "ms-photos:",
    "microsoftstore": "ms-windows-store:",
    "store": "ms-windows-store:",
    "mail": "outlookmail:",
    "outlook": "outlook",
    "calendar": "outlookcal:",
    "xbox": "xbox:",
}


def _find_exe_in_dirs(exe_name: str, directories: list[str]) -> str:
    """Search only under known install folders (avoids scanning all of AppData)."""
    for d in directories:
        if not d:
            continue
        root = Path(d)
        if not root.is_dir():
            continue
        direct = root / exe_name
        if direct.is_file():
            return str(direct)
        try:
            for hit in root.rglob(exe_name):
                if hit.is_file():
                    return str(hit)
        except OSError:
            continue
    return ""


def _try_direct_exe(norm_key: str) -> str:
    """Well-known install locations (no full-disk rglob)."""
    appdata = os.environ.get("APPDATA", "")
    local = os.environ.get("LOCALAPPDATA", "")
    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")

    def first_existing(paths: list[Path]) -> str:
        for p in paths:
            try:
                if p.is_file():
                    return str(p)
            except OSError:
                continue
        return ""

    if norm_key == "spotify":
        paths: list[Path] = []
        if appdata:
            paths.append(Path(appdata) / "Spotify" / "Spotify.exe")
        if local:
            paths.append(Path(local) / "Spotify" / "Spotify.exe")
            wa = Path(local) / "Microsoft" / "WindowsApps"
            if wa.is_dir():
                paths.extend(sorted(wa.glob("Spotify*.exe")))
        hit = first_existing(paths)
        if hit:
            return hit

    if norm_key == "slack" and local:
        base = Path(local) / "slack"
        hit = first_existing([base / "slack.exe"])
        if hit:
            return hit
        try:
            for p in sorted(base.glob("app-*/slack.exe")):
                if p.is_file():
                    return str(p)
        except OSError:
            pass

    if norm_key == "discord" and local:
        try:
            for p in sorted(Path(local).glob("Discord/app-*/Discord.exe"), reverse=True):
                if p.is_file():
                    return str(p)
        except OSError:
            pass
        hit = first_existing([Path(local) / "Discord" / "Update.exe"])
        if hit:
            return hit

    if norm_key == "zoom" and appdata:
        hit = first_existing(
            [
                Path(appdata) / "Zoom" / "bin" / "Zoom.exe",
                Path(program_files) / "Zoom" / "bin" / "Zoom.exe",
            ]
        )
        if hit:
            return hit

    if norm_key == "teams" or norm_key == "microsoftteams":
        if local:
            hit = first_existing(
                [
                    Path(local) / "Microsoft" / "Teams" / "current" / "Teams.exe",
                    Path(local) / "Microsoft" / "Teams" / "Update.exe",
                ]
            )
            if hit:
                return hit

    if norm_key == "steam":
        hit = first_existing(
            [
                Path(program_files_x86) / "Steam" / "steam.exe",
                Path(program_files) / "Steam" / "steam.exe",
            ]
        )
        if hit:
            return hit

    if norm_key == "vlc":
        hit = first_existing(
            [
                Path(program_files) / "VideoLAN" / "VLC" / "vlc.exe",
                Path(program_files_x86) / "VideoLAN" / "VLC" / "vlc.exe",
            ]
        )
        if hit:
            return hit

    if norm_key == "whatsapp" and local:
        hit = first_existing([Path(local) / "WhatsApp" / "WhatsApp.exe"])
        if hit:
            return hit

    if norm_key in ("obs", "obsstudio"):
        hit = first_existing(
            [
                Path(program_files) / "obs-studio" / "bin" / "obs64.exe",
                Path(program_files_x86) / "obs-studio" / "bin" / "obs64.exe",
            ]
        )
        if hit:
            return hit

    if norm_key == "signal" and local:
        hit = first_existing([Path(local) / "Programs" / "signal-desktop" / "Signal.exe"])
        if hit:
            return hit

    if norm_key == "telegram" and local:
        hit = first_existing(
            [
                Path(local) / "Programs" / "Telegram" / "Telegram.exe",
                Path(program_files_x86) / "Telegram Desktop" / "Telegram.exe",
            ]
        )
        if hit:
            return hit

    if norm_key in ("edge", "microsoftedge"):
        hit = first_existing(
            [
                Path(program_files_x86) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
                Path(program_files) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
            ]
        )
        if hit:
            return hit

    if norm_key == "chrome" and local:
        hit = first_existing(
            [Path(local) / "Google" / "Chrome" / "Application" / "chrome.exe"]
        )
        if hit:
            return hit

    if norm_key == "brave" and local:
        hit = first_existing(
            [
                Path(local) / "BraveSoftware" / "Brave-Browser" / "Application" / "brave.exe",
            ]
        )
        if hit:
            return hit

    return ""


def _which_on_path(norm_key: str) -> str:
    """Last-resort: launcher on PATH (Chrome/Firefox/Code often register here)."""
    candidates: dict[str, tuple[str, ...]] = {
        "chrome": ("chrome", "google-chrome"),
        "brave": ("brave",),
        "firefox": ("firefox",),
        "code": ("code", "code-insiders"),
        "vscode": ("code", "code-insiders"),
        "vlc": ("vlc",),
        "teams": ("ms-teams", "teams"),
        "slack": ("slack",),
        "zoom": ("Zoom",),
    }
    for name in candidates.get(norm_key, ()):
        hit = shutil.which(name)
        if hit:
            return hit
    return ""


@lru_cache(maxsize=16)
def _resolve_installed_app(norm_key: str) -> str:
    """Disk search under known vendor folders only — cached per key."""
    local = os.environ.get("LOCALAPPDATA", "")
    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    appdata = os.environ.get("APPDATA", "")

    chrome_dirs = [
        os.path.join(program_files, "Google", "Chrome", "Application"),
        os.path.join(program_files_x86, "Google", "Chrome", "Application"),
        os.path.join(local, "Google", "Chrome", "Application"),
    ]
    brave_dirs = [
        os.path.join(program_files, "BraveSoftware", "Brave-Browser", "Application"),
        os.path.join(program_files_x86, "BraveSoftware", "Brave-Browser", "Application"),
        os.path.join(local, "BraveSoftware", "Brave-Browser", "Application"),
    ]
    firefox_dirs = [
        os.path.join(program_files, "Mozilla Firefox"),
        os.path.join(program_files_x86, "Mozilla Firefox"),
    ]
    edge_dirs = [
        os.path.join(program_files_x86, "Microsoft", "Edge", "Application"),
        os.path.join(program_files, "Microsoft", "Edge", "Application"),
    ]
    vscode_dirs = [
        os.path.join(local, "Programs", "Microsoft VS Code"),
        os.path.join(program_files, "Microsoft VS Code"),
        os.path.join(program_files, "Microsoft VS Code Insiders"),
    ]
    spotify_dirs = [
        os.path.join(appdata, "Spotify"),
        os.path.join(local, "Spotify"),
    ]
    discord_dirs = [os.path.join(local, "Discord")]
    slack_dirs = [os.path.join(local, "slack")]
    zoom_dirs = [
        os.path.join(appdata, "Zoom", "bin"),
        os.path.join(program_files, "Zoom", "bin"),
    ]
    steam_dirs = [
        os.path.join(program_files_x86, "Steam"),
        os.path.join(program_files, "Steam"),
    ]
    vlc_dirs = [
        os.path.join(program_files, "VideoLAN", "VLC"),
        os.path.join(program_files_x86, "VideoLAN", "VLC"),
    ]
    teams_dirs = [
        os.path.join(local, "Microsoft", "Teams", "current"),
        os.path.join(local, "Microsoft", "Teams"),
    ]
    obs_dirs = [
        os.path.join(program_files, "obs-studio", "bin"),
        os.path.join(program_files_x86, "obs-studio", "bin"),
    ]
    signal_dirs = [os.path.join(local, "Programs", "signal-desktop")]
    telegram_dirs = [
        os.path.join(local, "Programs", "Telegram"),
        os.path.join(program_files_x86, "Telegram Desktop"),
    ]
    whatsapp_dirs = [os.path.join(local, "WhatsApp")]

    specs: dict[str, tuple[str, list[str]]] = {
        "chrome": ("chrome.exe", chrome_dirs),
        "brave": ("brave.exe", brave_dirs),
        "firefox": ("firefox.exe", firefox_dirs),
        "edge": ("msedge.exe", edge_dirs),
        "vscode": ("Code.exe", vscode_dirs),
        "code": ("Code.exe", vscode_dirs),
        "spotify": ("Spotify.exe", spotify_dirs),
        "discord": ("Discord.exe", discord_dirs),
        "slack": ("slack.exe", slack_dirs),
        "zoom": ("Zoom.exe", zoom_dirs),
        "steam": ("steam.exe", steam_dirs),
        "vlc": ("vlc.exe", vlc_dirs),
        "teams": ("Teams.exe", teams_dirs),
        "obs64": ("obs64.exe", obs_dirs),
        "obs": ("obs64.exe", obs_dirs),
        "signal": ("Signal.exe", signal_dirs),
        "telegram": ("Telegram.exe", telegram_dirs),
        "whatsapp": ("WhatsApp.exe", whatsapp_dirs),
    }
    if norm_key not in specs:
        return ""
    exe_name, roots = specs[norm_key]
    return _find_exe_in_dirs(exe_name, roots)


def resolve_target(app_name: str) -> tuple[str | None, str]:
    """Resolve what would be launched. Returns (target, user_message). target None on failure."""
    raw = (app_name or "").strip()
    if not raw:
        return None, "Error: app_name is empty."

    key = _norm(raw)
    key = _KEY_ALIASES.get(key, key)
    logger.debug("open_app: raw=%r normalized=%r", raw, key)

    if key in _STATIC_ALIASES:
        return _STATIC_ALIASES[key], f"alias:{key}"

    direct = _try_direct_exe(key)
    if direct:
        return direct, f"direct:{key}"

    installed = _resolve_installed_app(key)
    if installed:
        return installed, f"search:{key}"

    which_hit = _which_on_path(key)
    if which_hit:
        return which_hit, f"path:{key}"

    index = _start_menu_lnk_index()
    if key in index:
        return str(index[key]), "start_menu_exact"

    matches = [
        path
        for stem, path in index.items()
        if key and (key in stem or stem in key)
    ]
    matches = list(dict.fromkeys(matches))[:5]
    if len(matches) == 1:
        return str(matches[0]), "start_menu_fuzzy"

    if matches:
        names = ", ".join(p.stem for p in matches)
        return None, f"Ambiguous app_name. Candidates: {names}. Pick one exactly."

    return (
        None,
        f"Could not open {raw}. "
        "Try: notepad, calculator, chrome, brave, edge, firefox, spotify, discord, slack, "
        "teams, zoom, steam, vlc, vscode, whatsapp, obs, signal, telegram, settings, "
        "terminal, or a Start Menu shortcut name.",
    )


def run(app_name: str, url: str | None = None) -> str:
    raw = (app_name or "").strip()
    web = _parse_web_request(raw, url)
    if web is not None:
        browser_key, target_url = web
        return _launch_url(target_url, browser_key)

    target, how = resolve_target(raw)
    if not target:
        logger.warning("open_app: no match for %r (%s)", raw, how)
        return how

    try:
        os.startfile(target)  # type: ignore[attr-defined]
        logger.info("open_app: started raw=%r target=%r via=%s", raw, target, how)
        return f"Opened {raw}."
    except OSError as exc:
        logger.warning("open_app: start failed %s", exc, exc_info=True)
        return f"Error opening {raw}: {exc}"


SCHEMA = {
    "type": "object",
    "properties": {
        "app_name": {
            "type": "string",
            "description": (
                "App to launch (notepad, edge, chrome, spotify, discord, …) OR a website "
                "(youtube, youtube.com, https://example.com). For a page in Edge, set "
                "app_name to edge and url to the site, or say e.g. edge youtube.com."
            ),
        },
        "url": {
            "type": "string",
            "description": (
                "Optional URL or site name to open in a browser (youtube.com, https://…). "
                "Use with app_name=edge or chrome to pick the browser."
            ),
        },
    },
    "required": ["app_name"],
    "additionalProperties": False,
}


DESCRIPTION = (
    "Open an application or website on this Windows PC. Apps: Spotify, Discord, Slack, "
    "Teams, Zoom, Steam, VLC, Chrome, Brave, Edge, Firefox, VS Code, WhatsApp, OBS, Signal, "
    "Telegram, plus Start Menu names and built-ins (notepad, calculator, settings, terminal). "
    "Websites: pass url= (or a site in app_name) such as youtube.com, https://reddit.com — "
    "or a YouTube search like url=mr beast video (opens results in Edge). "
    "Use app_name=edge or chrome to pick the browser (default is Edge). "
    "For Spotify tracks use spotify_play, not this tool."
)
