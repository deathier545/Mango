"""URI helpers for spotify_play (no network)."""

import mango.integrations.spotify.spotify_auto_close as sac
import mango.integrations.spotify.spotify_track_resolver as sres
from mango.tools import spotify_play as sp


def test_track_id_from_uri_accepts_play_suffix() -> None:
    assert sp._track_id_from_spotify_uri("spotify:track:abcXYZ12") == "abcXYZ12"
    assert sp._track_id_from_spotify_uri("spotify:track:abcXYZ12:play") == "abcXYZ12"


def test_uri_for_desktop_playback_adds_play() -> None:
    assert sp._uri_for_desktop_playback("spotify:track:abc") == "spotify:track:abc:play"
    assert sp._uri_for_desktop_playback("spotify:track:abc:play") == "spotify:track:abc:play"


def test_spotify_exe_uri_param_strips_play_suffix() -> None:
    assert sp._spotify_exe_uri_param("spotify:track:abcXYZ:play") == "spotify:track:abcXYZ"
    assert sp._spotify_exe_uri_param("spotify:track:abcXYZ") == "spotify:track:abcXYZ"


def test_likely_instrumental_flags_common_titles() -> None:
    inst = {
        "name": "Thunderstruck (Instrumental)",
        "artists": [{"name": "AC/DC Tribute"}],
        "album": {"name": "Rock Karaoke Vol 1"},
    }
    assert sp._likely_instrumental_or_karaoke(inst) is True
    vocal = {
        "name": "Thunderstruck",
        "artists": [{"name": "AC/DC"}],
        "album": {"name": "The Razors Edge"},
    }
    assert sp._likely_instrumental_or_karaoke(vocal) is False


def test_api_search_best_track_skips_instrumental_for_vocal(monkeypatch) -> None:
    inst_hit = {
        "name": "Song (Instrumental)",
        "uri": "spotify:track:aaa",
        "popularity": 99,
        "artists": [{"name": "Various"}],
        "album": {"name": "Instrumentals"},
    }
    vocal_hit = {
        "name": "Song",
        "uri": "spotify:track:bbb",
        "popularity": 80,
        "artists": [{"name": "Real Band"}],
        "album": {"name": "Album"},
    }
    monkeypatch.setattr(sres, "api_search_tracks", lambda tok, q, limit=15: [inst_hit, vocal_hit])
    best = sp._api_search_best_track("tok", "Song")
    assert best["uri"] == "spotify:track:bbb"


def test_api_search_best_track_when_only_instrumental_picks_top_popularity(monkeypatch) -> None:
    low = {
        "name": "A (instrumental)",
        "uri": "spotify:track:1",
        "popularity": 5,
        "artists": [{"name": "X"}],
        "album": {"name": "Y"},
    }
    high = {
        "name": "B (instrumental)",
        "uri": "spotify:track:2",
        "popularity": 92,
        "artists": [{"name": "Z"}],
        "album": {"name": "W"},
    }
    monkeypatch.setattr(sres, "api_search_tracks", lambda tok, q, limit=15: [low, high])
    best = sp._api_search_best_track("tok", "q")
    assert best["uri"] == "spotify:track:2"


def test_spotify_auto_close_uri_match() -> None:
    assert sac._uris_match("spotify:track:abc", "spotify:track:abc:play")
    assert not sac._uris_match("spotify:track:abc", "spotify:track:xyz")


def test_spotify_auto_close_not_early_on_track_glitch() -> None:
    duration = 200_000
    assert not sac.should_close_after_track_change(
        saw_target_streak=5,
        last_progress_ms=30_000,
        duration_ms=duration,
    )
    assert sac.should_close_after_track_change(
        saw_target_streak=3,
        last_progress_ms=180_000,
        duration_ms=duration,
    )


def test_parse_music_query_artist_only() -> None:
    p = sres.parse_music_query("play a song by Bruno Mars")
    assert p.artist_only is True
    assert p.artist == "Bruno Mars"
    assert p.title == ""


def test_parse_music_query_title_and_artist() -> None:
    p = sres.parse_music_query("play Uptown Funk by Bruno Mars")
    assert p.artist_only is False
    assert p.title == "Uptown Funk"
    assert p.artist == "Bruno Mars"


def test_title_only_artist_name_is_penalized() -> None:
    posner_wrong = {
        "name": "Bruno Mars",
        "uri": "spotify:track:wrong",
        "popularity": 99,
        "artists": [{"name": "Mike Posner"}],
        "album": {"name": "At Night, Alone."},
    }
    parsed = sres.parse_music_query("a song by Bruno Mars")
    assert sres.title_only_mentions_artist("Bruno Mars", posner_wrong)
    assert sres.score_track_for_query(parsed, posner_wrong) < 0
    real = {
        "name": "Uptown Funk (feat. Bruno Mars)",
        "uri": "spotify:track:good",
        "popularity": 90,
        "artists": [{"name": "Mark Ronson"}, {"name": "Bruno Mars"}],
        "album": {"name": "Uptown Special"},
    }
    assert sres.artist_matches_requested("Bruno Mars", real)
    assert sres.score_track_for_query(parsed, real) > sres.score_track_for_query(parsed, posner_wrong)


def test_toy_soldier_typo_prefers_eminem_over_britney() -> None:
    parsed = sres.parse_music_query("toy soilder by eminem")
    britney = {
        "name": "Toy Soldier",
        "uri": "spotify:track:britney",
        "popularity": 72,
        "artists": [{"name": "Britney Spears"}],
        "album": {"name": "Blackout"},
    }
    eminem = {
        "name": "Like Toy Soldiers",
        "uri": "spotify:track:eminem",
        "popularity": 78,
        "artists": [{"name": "Eminem"}],
        "album": {"name": "Encore"},
    }
    assert sres.artist_matches_requested("eminem", eminem)
    assert not sres.artist_matches_requested("eminem", britney)
    assert sres.score_track_for_query(parsed, eminem) > sres.score_track_for_query(parsed, britney)
    ranked = sres._filter_and_rank_tracks([britney, eminem], parsed)
    assert ranked[0]["uri"] == "spotify:track:eminem"


def test_title_match_ratio_handles_soilder_typo() -> None:
    assert sres.title_match_ratio("toy soilder", "Like Toy Soldiers") >= 0.5
    assert sres.title_match_ratio("toy soilder", "Toy Soldier") >= 0.5


def test_api_search_best_track_artist_only_uses_top_track(monkeypatch) -> None:
    top = {
        "name": "Locked Out of Heaven",
        "uri": "spotify:track:bruno1",
        "popularity": 88,
        "artists": [{"name": "Bruno Mars"}],
        "album": {"name": "Unorthodox Jukebox"},
    }

    monkeypatch.setattr(
        sres,
        "api_best_track_for_artist",
        lambda tok, name: top if name == "Bruno Mars" else None,
    )
    monkeypatch.setattr(sres, "api_search_tracks", lambda *a, **k: [])
    best = sres.api_search_best_track("tok", "play a song by Bruno Mars")
    assert best["uri"] == "spotify:track:bruno1"


def test_api_search_best_track_respects_prefer_vocals_off(monkeypatch) -> None:
    monkeypatch.setenv("MANGO_SPOTIFY_PREFER_VOCALS", "0")
    only = {
        "name": "Karaoke Night",
        "uri": "spotify:track:zz",
        "popularity": 3,
        "artists": [{"name": "K"}],
        "album": {"name": "K"},
    }
    limits: list[int] = []

    def fake(tok, q, limit=15):
        limits.append(limit)
        return [only]

    monkeypatch.setattr(sres, "api_search_tracks", fake)
    assert sp._api_search_best_track("tok", "q") == only
    assert limits == [1]
