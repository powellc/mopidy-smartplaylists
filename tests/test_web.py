import json
from unittest import mock

import pytest
from mopidy.models import Playlist, Track

from mopidy_smartplaylists.web import (
    AlbumMixHandler,
    ArtistMixHandler,
    DecadeMixHandler,
    GenreMixHandler,
    InstantMixHandler,
    RefreshHandler,
    StatusHandler,
    app_factory,
)


class TestAppFactory:
    def test_returns_list_of_routes(self):
        config = mock.Mock()
        config.get.return_value = {"playlist_prefix": "[Smart]"}
        core = mock.Mock()
        routes = app_factory(config, core)
        assert isinstance(routes, list)
        assert len(routes) > 0
        for pattern, handler_cls, kwargs in routes:
            assert isinstance(pattern, str)
            assert issubclass(handler_cls, object)
            assert "core" in kwargs


class TestDecadeMixHandler:
    @pytest.fixture
    def handler(self):
        core = mock.Mock()
        core.library.search.return_value.get.return_value = [
            mock.Mock(tracks=[Track(uri="dummy:1", name="T")])
        ]
        core.playlists.lookup.return_value.get.return_value = None
        core.playlists.save.return_value.get.return_value = Playlist(
            name="[Smart] 1980s Mix",
            uri="mopidy:smartplaylists:1980s_mix",
            tracks=[Track(uri="dummy:1", name="T")],
        )

        h = DecadeMixHandler(mock.Mock(), mock.Mock(), core=core, prefix="[Smart]")
        h.request = mock.Mock()
        h.request.body = json.dumps({"decade": "1980"}).encode()
        return h

    def test_returns_playlist_info(self, handler):
        handler.write = mock.Mock()
        handler.post()
        data = handler.write.call_args[0][0]
        assert data["playlist"]["name"] == "[Smart] 1980s Mix"
        assert data["tracks"] == 1

    def test_missing_decade_returns_400(self):
        h = DecadeMixHandler(mock.Mock(), mock.Mock(), core=mock.Mock(), prefix="[Smart]")
        h.request = mock.Mock()
        h.request.body = json.dumps({}).encode()
        h.set_status = mock.Mock()
        h.write = mock.Mock()
        h.post()
        h.set_status.assert_called_once_with(400)


class TestGenreMixHandler:
    def test_missing_genre_returns_400(self):
        h = GenreMixHandler(mock.Mock(), mock.Mock(), core=mock.Mock(), prefix="[Smart]")
        h.request = mock.Mock()
        h.request.body = json.dumps({}).encode()
        h.set_status = mock.Mock()
        h.write = mock.Mock()
        h.post()
        h.set_status.assert_called_once_with(400)


class TestArtistMixHandler:
    def test_missing_artist_returns_400(self):
        h = ArtistMixHandler(mock.Mock(), mock.Mock(), core=mock.Mock(), prefix="[Smart]")
        h.request = mock.Mock()
        h.request.body = json.dumps({}).encode()
        h.set_status = mock.Mock()
        h.write = mock.Mock()
        h.post()
        h.set_status.assert_called_once_with(400)


class TestAlbumMixHandler:
    def test_missing_uri_returns_400(self):
        h = AlbumMixHandler(mock.Mock(), mock.Mock(), core=mock.Mock(), prefix="[Smart]")
        h.request = mock.Mock()
        h.request.body = json.dumps({}).encode()
        h.set_status = mock.Mock()
        h.write = mock.Mock()
        h.post()
        h.set_status.assert_called_once_with(400)


class TestInstantMixHandler:
    def test_missing_uri_returns_400(self):
        h = InstantMixHandler(mock.Mock(), mock.Mock(), core=mock.Mock(), prefix="[Smart]")
        h.request = mock.Mock()
        h.request.body = json.dumps({}).encode()
        h.set_status = mock.Mock()
        h.write = mock.Mock()
        h.post()
        h.set_status.assert_called_once_with(400)


class TestRefreshHandler:
    def test_calls_refresh(self):
        config = mock.Mock()
        config.get.return_value = {"playlist_prefix": "[Smart]"}
        core = mock.Mock()

        h = RefreshHandler(mock.Mock(), mock.Mock(), core=core, config=config)
        h.request = mock.Mock()
        h.request.body = b"{}"
        h.write = mock.Mock()
        h.post()
        assert h.write.call_args[0][0] == {"status": "ok"}


class TestStatusHandler:
    def test_returns_smart_playlists(self):
        core = mock.Mock()
        core.playlists.as_list.return_value.get.return_value = [
            Playlist(
                name="[Smart] Jazz Mix",
                uri="mopidy:smartplaylists:jazz_mix",
                tracks=[Track(uri="dummy:1", name="T")],
            ),
            Playlist(
                name="Normal Playlist",
                uri="mopidy:playlist:normal",
                tracks=[],
            ),
        ]

        h = StatusHandler(mock.Mock(), mock.Mock(), core=core)
        h.write = mock.Mock()
        h.get()
        data = h.write.call_args[0][0]
        assert data["count"] == 1
        assert data["smart_playlists"][0]["name"] == "[Smart] Jazz Mix"
