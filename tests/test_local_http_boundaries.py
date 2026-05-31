from __future__ import annotations

import mango.desktop.globe_server as globe_server
import mango.integrations.spotify.spotify_player_server as spotify_player_server


def test_spotify_loopback_guard_allows_only_local_hosts():
    assert spotify_player_server._is_loopback("127.0.0.1")
    assert spotify_player_server._is_loopback("::1")
    assert spotify_player_server._is_loopback("localhost")
    assert not spotify_player_server._is_loopback("192.168.1.2")
    assert not spotify_player_server._is_loopback("example.com")


def test_globe_server_binds_loopback_interface():
    port = globe_server.ensure_running()
    assert isinstance(port, int)
    assert port > 0
    assert globe_server._server is not None
    host, bound_port = globe_server._server.server_address[:2]
    assert host == "127.0.0.1"
    assert bound_port == port
