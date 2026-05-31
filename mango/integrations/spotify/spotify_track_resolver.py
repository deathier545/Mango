"""Spotify track lookup and URI resolution helpers."""

from __future__ import annotations

import base64
import logging
import os
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

import httpx

logger = logging.getLogger(__name__)

TRACK_RE = re.compile(
    r"(?:https?://)?(?:open\.)?spotify\.com/track/([a-zA-Z0-9]+)",
    re.IGNORECASE,
)

INSTRUMENTALISH = re.compile(
    r"\b("
    r"instrumental|instr\.?|"
    r"karaoke|backing\s*track|"
    r"without\s*vocals?|no\s*vocals?|"
    r"minus\s*one|minus-?one|"
    r"8d\s+audio|slowed\s+reverb|"
    r"piano\s+cover|orchestral\s+version|orchestra\s+version|"
    r"type\s+beat|beats?\s+to\s+study|lo-?fi\s+beats"
    r")\b",
    re.IGNORECASE,
)


def spotify_credentials() -> tuple[str, str]:
    cid = (
        os.getenv("MANGO_SPOTIFY_CLIENT_ID", "").strip()
        or os.getenv("SPOTIFY_CLIENT_ID", "").strip()
    )
    secret = (
        os.getenv("MANGO_SPOTIFY_CLIENT_SECRET", "").strip()
        or os.getenv("SPOTIFY_CLIENT_SECRET", "").strip()
    )
    return cid, secret


def api_access_token() -> str | None:
    cid, secret = spotify_credentials()
    if not cid or not secret:
        return None
    auth = base64.b64encode(f"{cid}:{secret}".encode()).decode("ascii")
    try:
        r = httpx.post(
            "https://accounts.spotify.com/api/token",
            data={"grant_type": "client_credentials"},
            headers={"Authorization": f"Basic {auth}"},
            timeout=25.0,
        )
    except httpx.HTTPError as exc:
        logger.warning("Spotify token request failed: %s", exc)
        return None
    if r.status_code != 200:
        logger.warning("Spotify token HTTP %s", r.status_code)
        return None
    data = r.json()
    if not isinstance(data, dict):
        return None
    tok = data.get("access_token")
    return tok if isinstance(tok, str) and tok else None


def api_search_tracks(token: str, query: str, *, limit: int = 15) -> list[dict[str, Any]]:
    lim = max(1, min(int(limit), 50))
    try:
        r = httpx.get(
            "https://api.spotify.com/v1/search",
            params={"q": query, "type": "track", "limit": str(lim), "market": "US"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=25.0,
        )
    except httpx.HTTPError as exc:
        logger.warning("Spotify search failed: %s", exc)
        return []
    if r.status_code != 200:
        logger.warning("Spotify search HTTP %s", r.status_code)
        return []
    data = r.json()
    try:
        items = data["tracks"]["items"]
        if not isinstance(items, list):
            return []
        return [x for x in items if isinstance(x, dict)]
    except (KeyError, TypeError):
        return []


def track_text_blob(track: dict[str, Any]) -> str:
    parts: list[str] = [str(track.get("name") or "")]
    al = track.get("album")
    if isinstance(al, dict):
        parts.append(str(al.get("name") or ""))
    arts = track.get("artists")
    if isinstance(arts, list):
        for a in arts:
            if isinstance(a, dict):
                parts.append(str(a.get("name") or ""))
    return " ".join(parts)


def likely_instrumental_or_karaoke(track: dict[str, Any]) -> bool:
    blob = track_text_blob(track).casefold()
    if INSTRUMENTALISH.search(blob):
        return True
    if " stem" in blob or "stems" in blob or "multitrack" in blob:
        return True
    return False


def prefer_non_instrumental_search() -> bool:
    return os.getenv("MANGO_SPOTIFY_PREFER_VOCALS", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


@dataclass(frozen=True)
class ParsedMusicQuery:
    raw: str
    title: str
    artist: str
    artist_only: bool


_GENERIC_TITLE_WORDS = frozenset(
    {
        "a",
        "an",
        "some",
        "any",
        "song",
        "songs",
        "track",
        "tracks",
        "music",
        "something",
        "anything",
        "random",
    }
)


def _strip_leading_play_verbs(q: str) -> str:
    return re.sub(
        r"^(?:please\s+)?(?:play|start|queue|put on)\s+",
        "",
        q,
        flags=re.IGNORECASE,
    ).strip()


def parse_music_query(query: str) -> ParsedMusicQuery:
    """Parse 'Freak by Radiohead', 'a song by Bruno Mars', or plain track queries."""
    raw = (query or "").strip().strip("\"'")
    if not raw or raw.lower().startswith("spotify:"):
        return ParsedMusicQuery(raw=raw, title=raw, artist="", artist_only=False)

    q = _strip_leading_play_verbs(raw)

    artist_only = re.match(
        r"^(?:(?:a|an|some|any)\s+)?(?:(?:song|track|music)\s+)?by\s+(?P<artist>.+)$",
        q,
        flags=re.IGNORECASE,
    )
    if artist_only:
        artist = artist_only.group("artist").strip().strip("\"'")
        return ParsedMusicQuery(raw=raw, title="", artist=artist, artist_only=True)

    by_match = re.match(
        r"^(?P<title>.+?)\s+by\s+(?P<artist>.+)$",
        q,
        flags=re.IGNORECASE,
    )
    if by_match:
        title = by_match.group("title").strip().strip("\"'")
        artist = by_match.group("artist").strip().strip("\"'")
        title_tokens = [
            t
            for t in re.findall(r"[a-z0-9']+", title.casefold())
            if t not in _GENERIC_TITLE_WORDS
        ]
        if not title_tokens:
            return ParsedMusicQuery(raw=raw, title="", artist=artist, artist_only=True)
        return ParsedMusicQuery(raw=raw, title=title, artist=artist, artist_only=False)

    return ParsedMusicQuery(raw=raw, title=q, artist="", artist_only=False)


def normalize_name(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").casefold()).strip()


def track_artist_names(track: dict[str, Any]) -> list[str]:
    arts = track.get("artists")
    if not isinstance(arts, list):
        return []
    out: list[str] = []
    for a in arts:
        if isinstance(a, dict):
            name = str(a.get("name") or "").strip()
            if name:
                out.append(name)
    return out


def artist_matches_requested(requested_artist: str, track: dict[str, Any]) -> bool:
    """True when a credited artist matches the requested name (handles minor typos)."""
    req = normalize_name(requested_artist)
    if not req:
        return True
    req_tokens = [t for t in req.split() if len(t) >= 2]
    for name in track_artist_names(track):
        an = normalize_name(name)
        if not an:
            continue
        if req == an or req in an or an in req:
            return True
        an_tokens = an.split()
        if req_tokens and all(any(rt in at or at in rt for at in an_tokens) for rt in req_tokens):
            return True
        if len(req_tokens) == 1 and len(req_tokens[0]) >= 4:
            token = req_tokens[0]
            for at in an_tokens:
                if at.startswith(token[:4]) or token.startswith(at[:4]):
                    if abs(len(at) - len(token)) <= 2:
                        return True
    return False


def title_only_mentions_artist(requested_artist: str, track: dict[str, Any]) -> bool:
    """e.g. Mike Posner — 'Bruno Mars' when user asked for Bruno Mars the artist."""
    req = normalize_name(requested_artist)
    if not req:
        return False
    title = normalize_name(str(track.get("name") or ""))
    if req not in title and not all(tok in title for tok in req.split() if len(tok) >= 3):
        return False
    return not artist_matches_requested(requested_artist, track)


_COMMON_WORD_FIXES: dict[str, str] = {
    "soilder": "soldier",
    "soilders": "soldiers",
    "solider": "soldier",
    "soliders": "soldiers",
}


def _fix_token(tok: str) -> str:
    low = tok.casefold()
    return _COMMON_WORD_FIXES.get(low, tok)


def _title_search_variants(title: str) -> list[str]:
    """Original title plus typo fixes and light plural tweaks for Spotify search."""
    base = (title or "").strip()
    if not base:
        return []
    seen: set[str] = set()
    out: list[str] = []

    def _add(s: str) -> None:
        s = s.strip()
        if s and s.casefold() not in seen:
            seen.add(s.casefold())
            out.append(s)

    _add(base)
    words = base.split()
    fixed_words = [_fix_token(w) for w in words]
    fixed = " ".join(fixed_words)
    _add(fixed)
    if words:
        last = fixed_words[-1]
        if last.endswith("s") and len(last) > 3:
            _add(" ".join(fixed_words[:-1] + [last[:-1]]))
        elif len(last) >= 3:
            _add(" ".join(fixed_words[:-1] + [last + "s"]))
    return out


def _word_similar(a: str, b: str) -> bool:
    a = a.casefold()
    b = b.casefold()
    if not a or not b:
        return False
    if a == b or a in b or b in a:
        return True
    if len(a) >= 4 and len(b) >= 4:
        return SequenceMatcher(None, a, b).ratio() >= 0.8
    return False


def title_match_ratio(requested_title: str, track_name: str) -> float:
    """0..1 — how many requested title tokens appear in the track name (fuzzy)."""
    req_tokens = [
        t
        for t in re.findall(r"[a-z0-9']+", normalize_name(requested_title))
        if len(t) >= 2 and t not in _GENERIC_TITLE_WORDS
    ]
    if not req_tokens:
        return 0.0
    title_tokens = re.findall(r"[a-z0-9']+", normalize_name(track_name))
    if not title_tokens:
        return 0.0
    matched = 0
    for rt in req_tokens:
        rt_alt = _fix_token(rt)
        for tt in title_tokens:
            if _word_similar(rt, tt) or _word_similar(rt_alt, tt):
                matched += 1
                break
    return matched / len(req_tokens)


def normalize_search_query(query: str) -> str:
    """Turn natural phrasing into a tighter Spotify search string."""
    parsed = parse_music_query(query)
    if parsed.raw.lower().startswith("spotify:"):
        return parsed.raw
    if parsed.artist_only and parsed.artist:
        return f"artist:{parsed.artist}"
    if parsed.title and parsed.artist:
        variants = _title_search_variants(parsed.title)
        title_q = variants[0] if variants else parsed.title
        return f"track:{title_q} artist:{parsed.artist}"
    return parsed.title or parsed.raw


def api_search_artists(token: str, name: str, *, limit: int = 5) -> list[dict[str, Any]]:
    lim = max(1, min(int(limit), 10))
    try:
        r = httpx.get(
            "https://api.spotify.com/v1/search",
            params={"q": name, "type": "artist", "limit": str(lim)},
            headers={"Authorization": f"Bearer {token}"},
            timeout=25.0,
        )
    except httpx.HTTPError as exc:
        logger.warning("Spotify artist search failed: %s", exc)
        return []
    if r.status_code != 200:
        return []
    data = r.json()
    try:
        items = data["artists"]["items"]
        return [x for x in items if isinstance(x, dict)] if isinstance(items, list) else []
    except (KeyError, TypeError):
        return []


def api_artist_top_track(token: str, artist_id: str) -> dict[str, Any] | None:
    try:
        r = httpx.get(
            f"https://api.spotify.com/v1/artists/{artist_id}/top-tracks",
            params={"market": "US"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=25.0,
        )
    except httpx.HTTPError as exc:
        logger.warning("Spotify artist top-tracks failed: %s", exc)
        return None
    if r.status_code != 200:
        return None
    data = r.json()
    tracks = data.get("tracks") if isinstance(data, dict) else None
    if not isinstance(tracks, list):
        return None
    for t in tracks:
        if isinstance(t, dict) and not likely_instrumental_or_karaoke(t):
            return t
    return tracks[0] if tracks and isinstance(tracks[0], dict) else None


def api_best_track_for_artist(token: str, artist_name: str) -> dict[str, Any] | None:
    artists = api_search_artists(token, artist_name, limit=8)
    if not artists:
        return None
    req = normalize_name(artist_name)

    def _artist_score(a: dict[str, Any]) -> float:
        name = normalize_name(str(a.get("name") or ""))
        pop = float(a.get("popularity") or 0)
        score = pop
        if req and name:
            if req == name or req in name or name in req:
                score += 200.0
            req_toks = req.split()
            if req_toks and all(t in name for t in req_toks):
                score += 120.0
        return score

    artists.sort(key=_artist_score, reverse=True)
    best_artist = artists[0]
    aid = best_artist.get("id")
    if not isinstance(aid, str) or not aid:
        return None
    track = api_artist_top_track(token, aid)
    if track:
        logger.info(
            "spotify_play artist-only: %r -> artist %r top track %r",
            artist_name[:60],
            best_artist.get("name"),
            track.get("name"),
        )
    return track


def score_track_for_query(parsed: ParsedMusicQuery, track: dict[str, Any]) -> float:
    """Higher = better match (popularity is only a tie-breaker)."""
    score = float(int(track.get("popularity") or 0)) * 0.15

    if parsed.artist and title_only_mentions_artist(parsed.artist, track):
        return -10_000.0

    if parsed.artist:
        if artist_matches_requested(parsed.artist, track):
            score += 500.0
        else:
            return -10_000.0

    if parsed.title:
        track_name = str(track.get("name") or "")
        ratio = title_match_ratio(parsed.title, track_name)
        score += ratio * 200.0
        want = normalize_name(parsed.title)
        title = normalize_name(track_name)
        if want and title and (want == title or want in title or title in want):
            score += 60.0

    if not parsed.artist and not parsed.title:
        ql = parsed.raw.casefold()
        blob = track_text_blob(track).casefold()
        for word in re.findall(r"[a-z0-9']+", ql):
            if len(word) >= 2 and word in blob:
                score += 15.0
    return score


def _filter_and_rank_tracks(
    items: list[dict[str, Any]],
    parsed: ParsedMusicQuery,
) -> list[dict[str, Any]]:
    if not items:
        return []
    if parsed.artist:
        items = [t for t in items if artist_matches_requested(parsed.artist, t)]
        if not items:
            return []
    if prefer_non_instrumental_search():
        clean = [t for t in items if not likely_instrumental_or_karaoke(t)]
        if clean:
            items = clean
    items.sort(key=lambda t: score_track_for_query(parsed, t), reverse=True)
    return items


def api_search_track_for_artist_and_title(
    token: str,
    artist: str,
    title: str,
) -> dict[str, Any] | None:
    """Search only tracks credited to the requested artist (handles typos / 'Like Toy Soldiers')."""
    if not artist.strip():
        return None
    parsed = ParsedMusicQuery(
        raw=f"{title} by {artist}",
        title=title.strip(),
        artist=artist.strip(),
        artist_only=False,
    )
    seen: set[str] = set()
    pool: list[dict[str, Any]] = []
    for tv in _title_search_variants(title):
        for q in (
            f"track:{tv} artist:{artist}",
            f'artist:"{artist}" {tv}',
            f"{tv} artist:{artist}",
        ):
            for t in api_search_tracks(token, q, limit=25):
                uri = t.get("uri")
                if not isinstance(uri, str) or uri in seen:
                    continue
                if not artist_matches_requested(artist, t):
                    continue
                seen.add(uri)
                pool.append(t)
    ranked = _filter_and_rank_tracks(pool, parsed)
    if ranked:
        best = ranked[0]
        logger.info(
            "spotify_play artist+title search: %r by %r -> %r",
            title[:60],
            artist[:40],
            track_text_blob(best)[:80],
        )
        return best
    return None


def api_search_best_track(token: str, query: str) -> dict[str, Any] | None:
    parsed = parse_music_query(query)

    if parsed.artist_only and parsed.artist:
        top = api_best_track_for_artist(token, parsed.artist)
        if top:
            return top

    search_q = normalize_search_query(query)
    if not prefer_non_instrumental_search():
        items = api_search_tracks(token, search_q, limit=1)
        return items[0] if items else None

    items = api_search_tracks(token, search_q, limit=25)
    if not items and search_q != query:
        items = api_search_tracks(token, query, limit=25)
    if not items and parsed.artist and parsed.title:
        for tv in _title_search_variants(parsed.title):
            items = api_search_tracks(token, f"{tv} {parsed.artist}", limit=25)
            if items:
                break

    ranked = _filter_and_rank_tracks(items, parsed)
    if not ranked and parsed.artist and parsed.title:
        ranked_item = api_search_track_for_artist_and_title(token, parsed.artist, parsed.title)
        if ranked_item:
            return ranked_item
    if not ranked:
        if parsed.artist and parsed.title:
            ranked_item = api_search_track_for_artist_and_title(token, parsed.artist, parsed.title)
            if ranked_item:
                return ranked_item
        if parsed.artist:
            return api_best_track_for_artist(token, parsed.artist)
        return None
    best = ranked[0]
    logger.info(
        "spotify_play pick: %r for query %r (search=%r score=%.1f)",
        track_text_blob(best)[:80],
        query[:80],
        search_q[:80],
        score_track_for_query(parsed, best),
    )
    return best


def api_get_track(token: str, track_id: str) -> dict[str, Any] | None:
    try:
        r = httpx.get(
            f"https://api.spotify.com/v1/tracks/{track_id}",
            params={"market": "US"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=25.0,
        )
    except httpx.HTTPError as exc:
        logger.warning("Spotify track fetch failed: %s", exc)
        return None
    if r.status_code != 200:
        return None
    data = r.json()
    return data if isinstance(data, dict) else None


def track_id_from_spotify_uri(uri: str) -> str | None:
    u = uri.strip()
    if not u.lower().startswith("spotify:track:"):
        return None
    rest = u.split(":", 2)
    if len(rest) < 3:
        return None
    tid = rest[2].strip()
    tid = tid.split(":")[0].strip() if ":" in tid else tid
    return tid if re.fullmatch(r"[a-zA-Z0-9]+", tid) else None


def _ddgs_text_rows(q: str, n: int) -> list[dict[str, Any]]:
    try:
        from ddgs import DDGS

        with DDGS() as ddgs:
            return list(ddgs.text(q, max_results=n) or [])
    except Exception:
        logger.debug("ddgs text search failed", exc_info=True)
    return []


def track_ids_from_ddgs(query: str, *, max_ids: int = 10) -> list[str]:
    q2 = f"{query} site:open.spotify.com/track"
    rows = _ddgs_text_rows(q2, 12)
    ids: list[str] = []
    seen: set[str] = set()
    for item in rows:
        for field in ("href", "body", "title"):
            raw = str(item.get(field, "") or "")
            m = TRACK_RE.search(raw)
            if m:
                tid = m.group(1)
                if tid not in seen:
                    seen.add(tid)
                    ids.append(tid)
                if len(ids) >= max_ids:
                    return ids
    return ids
