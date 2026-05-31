from __future__ import annotations

from unittest.mock import patch

from mango.tools import open_app


def test_parse_youtube_on_edge() -> None:
    parsed = open_app._parse_web_request("edge youtube")
    assert parsed is not None
    browser, url = parsed
    assert browser == "edge"
    assert url == "https://www.youtube.com/"


def test_parse_url_with_explicit_param() -> None:
    parsed = open_app._parse_web_request("edge", "https://example.com/page")
    assert parsed is not None
    browser, url = parsed
    assert browser == "edge"
    assert url == "https://example.com/page"


def test_parse_youtube_defaults_to_edge() -> None:
    parsed = open_app._parse_web_request("youtube")
    assert parsed is not None
    browser, url = parsed
    assert browser == "edge"
    assert "youtube.com" in url


def test_parse_domain() -> None:
    parsed = open_app._parse_web_request("reddit.com")
    assert parsed is not None
    _, url = parsed
    assert url == "https://reddit.com"


def test_open_edge_still_app() -> None:
    target, how = open_app.resolve_target("Microsoft Edge")
    assert target is not None
    assert how.startswith(("direct:", "search:", "alias:", "path:", "start_menu"))


def test_parse_mr_beast_video() -> None:
    parsed = open_app._parse_web_request("edge", "mr beast video")
    assert parsed is not None
    browser, url = parsed
    assert browser == "edge"
    assert "search_query=" in url
    assert "mr" in url.casefold()


def test_youtube_search_from_app_name() -> None:
    parsed = open_app._parse_web_request("mr beast video")
    assert parsed is not None
    _, url = parsed
    assert "youtube.com/results" in url


def test_run_launches_url_in_browser() -> None:
    with patch.object(open_app, "_resolve_browser_exe", return_value=r"C:\Edge\msedge.exe"):
        with patch.object(open_app.subprocess, "Popen") as popen:
            out = open_app.run("edge", url="youtube.com")
    assert "Opened" in out
    popen.assert_called_once()
    args = popen.call_args[0][0]
    assert args[0].endswith("msedge.exe")
    assert "youtube.com" in args[1]
