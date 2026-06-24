from unittest import mock

from mopidy_smartplaylists import Extension
from mopidy_smartplaylists import frontend as frontend_lib
from mopidy_smartplaylists import web as web_lib


def test_get_default_config():
    ext = Extension()
    config = ext.get_default_config()
    assert "[smartplaylists]" in config
    assert "enabled = true" in config
    assert "decades =" in config
    assert "genres =" in config
    assert "artists =" in config
    assert "playlist_prefix = [Smart]" in config
    assert "refresh_interval = 0" in config


def test_get_config_schema():
    ext = Extension()
    schema = ext.get_config_schema()
    assert "decades" in schema
    assert "genres" in schema
    assert "artists" in schema
    assert "playlist_prefix" in schema
    assert "refresh_interval" in schema


def test_setup_registers_http_app():
    ext = Extension()
    registry = mock.Mock()
    ext.setup(registry)
    calls = [c.args for c in registry.add.call_args_list]
    http_app_calls = [c for c in calls if c[0] == "http:app"]
    assert len(http_app_calls) == 1
    assert http_app_calls[0][1]["name"] == "smartplaylists"
    assert http_app_calls[0][1]["factory"] == web_lib.app_factory


def test_setup_registers_frontend():
    ext = Extension()
    registry = mock.Mock()
    ext.setup(registry)
    calls = [c.args for c in registry.add.call_args_list]
    frontend_calls = [c for c in calls if c[0] == "frontend"]
    assert len(frontend_calls) == 1
    assert frontend_calls[0][1] == frontend_lib.SmartPlaylistsFrontend
