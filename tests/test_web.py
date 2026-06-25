import json
from unittest import mock

import tornado.testing
import tornado.web
from mopidy.models import Playlist, Ref, Track

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


class _HandlerTestBase:
    def make_app(self, handler_cls, **kwargs):
        return tornado.web.Application(
            [
                (r"/test", handler_cls, kwargs),
            ]
        )

    def call_handler(self, handler_cls, method="POST", body=None, **kwargs):
        app = self.make_app(handler_cls, **kwargs)
        request = tornado.httputil.HTTPServerRequest(
            method=method,
            uri="/test",
            body=json.dumps(body).encode() if isinstance(body, dict) else body,
            connection=mock.Mock(),
            headers=tornado.httputil.HTTPHeaders(),
        )
        return handler_cls(app, request, **kwargs)


class TestDecadeMixHandler:
    def test_missing_decade_returns_400(self):
        app = tornado.web.Application(
            [
                (
                    r"/decade",
                    DecadeMixHandler,
                    {"core": mock.Mock(), "prefix": "[Smart]"},
                ),
            ]
        )
        request = tornado.httputil.HTTPServerRequest(
            method="POST",
            uri="/decade",
            body=json.dumps({}).encode(),
            connection=mock.Mock(),
            headers=tornado.httputil.HTTPHeaders(),
        )
        handler = DecadeMixHandler(app, request, core=mock.Mock(), prefix="[Smart]")
        handler.set_status = mock.Mock()
        handler.write = mock.Mock()
        handler.post()
        handler.set_status.assert_called_once_with(400)

    def test_success(self):
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

        app = tornado.web.Application(
            [
                (r"/decade", DecadeMixHandler, {"core": core, "prefix": "[Smart]"}),
            ]
        )
        request = tornado.httputil.HTTPServerRequest(
            method="POST",
            uri="/decade",
            body=json.dumps({"decade": "1980"}).encode(),
            connection=mock.Mock(),
            headers=tornado.httputil.HTTPHeaders(),
        )
        handler = DecadeMixHandler(app, request, core=core, prefix="[Smart]")
        handler._transforms = []
        handler.write = mock.Mock()
        handler.post()
        data = handler.write.call_args[0][0]
        assert data["playlist"]["name"] == "[Smart] 1980s Mix"
        assert data["playlist"]["tracks"] == 1


class TestGenreMixHandler:
    def test_missing_genre_returns_400(self):
        app = tornado.web.Application(
            [
                (
                    r"/genre",
                    GenreMixHandler,
                    {"core": mock.Mock(), "prefix": "[Smart]"},
                ),
            ]
        )
        request = tornado.httputil.HTTPServerRequest(
            method="POST",
            uri="/genre",
            body=json.dumps({}).encode(),
            connection=mock.Mock(),
            headers=tornado.httputil.HTTPHeaders(),
        )
        handler = GenreMixHandler(app, request, core=mock.Mock(), prefix="[Smart]")
        handler.set_status = mock.Mock()
        handler.write = mock.Mock()
        handler.post()
        handler.set_status.assert_called_once_with(400)


class TestArtistMixHandler:
    def test_missing_artist_returns_400(self):
        app = tornado.web.Application(
            [
                (
                    r"/artist",
                    ArtistMixHandler,
                    {"core": mock.Mock(), "prefix": "[Smart]"},
                ),
            ]
        )
        request = tornado.httputil.HTTPServerRequest(
            method="POST",
            uri="/artist",
            body=json.dumps({}).encode(),
            connection=mock.Mock(),
            headers=tornado.httputil.HTTPHeaders(),
        )
        handler = ArtistMixHandler(app, request, core=mock.Mock(), prefix="[Smart]")
        handler.set_status = mock.Mock()
        handler.write = mock.Mock()
        handler.post()
        handler.set_status.assert_called_once_with(400)


class TestAlbumMixHandler:
    def test_missing_uri_returns_400(self):
        app = tornado.web.Application(
            [
                (
                    r"/album",
                    AlbumMixHandler,
                    {"core": mock.Mock(), "prefix": "[Smart]"},
                ),
            ]
        )
        request = tornado.httputil.HTTPServerRequest(
            method="POST",
            uri="/album",
            body=json.dumps({}).encode(),
            connection=mock.Mock(),
            headers=tornado.httputil.HTTPHeaders(),
        )
        handler = AlbumMixHandler(app, request, core=mock.Mock(), prefix="[Smart]")
        handler.set_status = mock.Mock()
        handler.write = mock.Mock()
        handler.post()
        handler.set_status.assert_called_once_with(400)


class TestInstantMixHandler:
    def test_missing_uri_returns_400(self):
        app = tornado.web.Application(
            [
                (
                    r"/instant-mix",
                    InstantMixHandler,
                    {"core": mock.Mock(), "prefix": "[Smart]"},
                ),
            ]
        )
        request = tornado.httputil.HTTPServerRequest(
            method="POST",
            uri="/instant-mix",
            body=json.dumps({}).encode(),
            connection=mock.Mock(),
            headers=tornado.httputil.HTTPHeaders(),
        )
        handler = InstantMixHandler(app, request, core=mock.Mock(), prefix="[Smart]")
        handler.set_status = mock.Mock()
        handler.write = mock.Mock()
        handler.post()
        handler.set_status.assert_called_once_with(400)


class TestRefreshHandler:
    def test_calls_refresh(self):
        config = mock.Mock()
        config.get.return_value = {"playlist_prefix": "[Smart]"}
        core = mock.Mock()

        app = tornado.web.Application(
            [
                (r"/refresh", RefreshHandler, {"core": core, "config": config}),
            ]
        )
        request = tornado.httputil.HTTPServerRequest(
            method="POST",
            uri="/refresh",
            body=b"{}",
            connection=mock.Mock(),
            headers=tornado.httputil.HTTPHeaders(),
        )
        handler = RefreshHandler(app, request, core=core, config=config)
        handler.write = mock.Mock()
        handler.post()
        assert handler.write.call_args[0][0] == {"status": "ok"}


class TestStatusHandler:
    def test_returns_smart_playlists(self):
        core = mock.Mock()
        core.playlists.as_list.return_value.get.return_value = [
            Ref(uri="mopidy:smartplaylists:jazz_mix", name="[Smart] Jazz Mix", type="playlist"),
            Ref(uri="mopidy:playlist:normal", name="Normal Playlist", type="playlist"),
        ]

        def lookup_side_effect(uri):
            result = mock.Mock()
            playlists = {
                "mopidy:smartplaylists:jazz_mix": Playlist(
                    name="[Smart] Jazz Mix",
                    uri="mopidy:smartplaylists:jazz_mix",
                    tracks=[Track(uri="dummy:1", name="T")],
                ),
            }
            result.get.return_value = playlists.get(uri)
            return result

        core.playlists.lookup.side_effect = lookup_side_effect

        app = tornado.web.Application(
            [
                (r"/status", StatusHandler, {"core": core, "prefix": "[Smart]"}),
            ]
        )
        request = tornado.httputil.HTTPServerRequest(
            method="GET",
            uri="/status",
            body=None,
            connection=mock.Mock(),
            headers=tornado.httputil.HTTPHeaders(),
        )
        handler = StatusHandler(app, request, core=core, prefix="[Smart]")
        handler.write = mock.Mock()
        handler.get()
        data = handler.write.call_args[0][0]
        assert data["count"] == 1
        assert data["smart_playlists"][0]["name"] == "[Smart] Jazz Mix"
