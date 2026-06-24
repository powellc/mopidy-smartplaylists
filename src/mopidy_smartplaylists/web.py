import json
import logging

import tornado.web
from mopidy.config import Config
from mopidy.core import CoreProxy

from mopidy_smartplaylists.generators import (
    build_album_mix,
    build_artist_mix,
    build_decade_mix,
    build_genre_mix,
    build_instant_mix,
    refresh_smart_playlists,
    save_smart_playlist,
)

logger = logging.getLogger(__name__)


class DecadeMixHandler(tornado.web.RequestHandler):
    def initialize(self, core: CoreProxy, prefix: str) -> None:
        self.core = core
        self.prefix = prefix

    def post(self) -> None:
        data = json.loads(self.request.body)
        decade = data.get("decade", "")
        if not decade:
            self.set_status(400)
            self.write({"error": "Missing 'decade' in request body"})
            return
        tracks = build_decade_mix(self.core, decade)
        if not tracks:
            self.write({"playlist": None, "tracks": 0})
            return
        playlist = save_smart_playlist(self.core, self.prefix, f"{decade}s Mix", tracks)
        self.write({
            "playlist": {
                "name": playlist.name if playlist else None,
                "uri": playlist.uri if playlist else None,
                "tracks": len(tracks),
            },
        })


class GenreMixHandler(tornado.web.RequestHandler):
    def initialize(self, core: CoreProxy, prefix: str) -> None:
        self.core = core
        self.prefix = prefix

    def post(self) -> None:
        data = json.loads(self.request.body)
        genre = data.get("genre", "")
        if not genre:
            self.set_status(400)
            self.write({"error": "Missing 'genre' in request body"})
            return
        tracks = build_genre_mix(self.core, genre)
        if not tracks:
            self.write({"playlist": None, "tracks": 0})
            return
        playlist = save_smart_playlist(self.core, self.prefix, f"{genre} Mix", tracks)
        self.write({
            "playlist": {
                "name": playlist.name if playlist else None,
                "uri": playlist.uri if playlist else None,
                "tracks": len(tracks),
            },
        })


class ArtistMixHandler(tornado.web.RequestHandler):
    def initialize(self, core: CoreProxy, prefix: str) -> None:
        self.core = core
        self.prefix = prefix

    def post(self) -> None:
        data = json.loads(self.request.body)
        artist = data.get("artist", "")
        if not artist:
            self.set_status(400)
            self.write({"error": "Missing 'artist' in request body"})
            return
        tracks = build_artist_mix(self.core, artist)
        if not tracks:
            self.write({"playlist": None, "tracks": 0})
            return
        playlist = save_smart_playlist(self.core, self.prefix, f"{artist} Mix", tracks)
        self.write({
            "playlist": {
                "name": playlist.name if playlist else None,
                "uri": playlist.uri if playlist else None,
                "tracks": len(tracks),
            },
        })


class AlbumMixHandler(tornado.web.RequestHandler):
    def initialize(self, core: CoreProxy, prefix: str) -> None:
        self.core = core
        self.prefix = prefix

    def post(self) -> None:
        data = json.loads(self.request.body)
        album_uri = data.get("uri", "")
        if not album_uri:
            self.set_status(400)
            self.write({"error": "Missing 'uri' in request body"})
            return
        tracks = build_album_mix(self.core, album_uri)
        if not tracks:
            self.write({"playlist": None, "tracks": 0})
            return
        name = tracks[0].album.name if tracks[0].album and tracks[0].album.name else "Album"
        playlist = save_smart_playlist(self.core, self.prefix, f"{name} Mix", tracks)
        self.write({
            "playlist": {
                "name": playlist.name if playlist else None,
                "uri": playlist.uri if playlist else None,
                "tracks": len(tracks),
            },
        })


class InstantMixHandler(tornado.web.RequestHandler):
    def initialize(self, core: CoreProxy, prefix: str) -> None:
        self.core = core
        self.prefix = prefix

    def post(self) -> None:
        data = json.loads(self.request.body)
        track_uri = data.get("uri", "")
        limit = data.get("limit", 50)
        if not track_uri:
            self.set_status(400)
            self.write({"error": "Missing 'uri' in request body"})
            return
        tracks = build_instant_mix(self.core, track_uri, limit)
        if not tracks:
            self.write({"playlist": None, "tracks": 0})
            return

        lookup_result = self.core.library.lookup([track_uri]).get()
        seed_name = "Instant Mix"
        for uri_tracks in lookup_result.values():
            for t in uri_tracks:
                if t.name:
                    seed_name = t.name
                break

        playlist = save_smart_playlist(self.core, self.prefix, f"Instant Mix: {seed_name}", tracks)
        self.write({
            "playlist": {
                "name": playlist.name if playlist else None,
                "uri": playlist.uri if playlist else None,
                "tracks": len(tracks),
            },
        })


class RefreshHandler(tornado.web.RequestHandler):
    def initialize(self, core: CoreProxy, config: Config) -> None:
        self.core = core
        self.config = config

    def post(self) -> None:
        section = self.config.get("smartplaylists", {})
        refresh_smart_playlists(self.core, section)
        self.write({"status": "ok"})


class StatusHandler(tornado.web.RequestHandler):
    def initialize(self, core: CoreProxy) -> None:
        self.core = core

    def get(self) -> None:
        result = self.core.playlists.as_list().get()
        smart = [p for p in result if p.uri and "smartplaylists" in p.uri]
        self.write({
            "smart_playlists": [
                {
                    "name": p.name,
                    "uri": p.uri,
                    "tracks": len(p.tracks) if p.tracks else 0,
                }
                for p in smart
            ],
            "count": len(smart),
        })


def app_factory(config: Config, core: CoreProxy) -> list[tuple]:
    prefix = config.get("smartplaylists", {}).get("playlist_prefix", "[Smart]")

    return [
        (r"/decade", DecadeMixHandler, {"core": core, "prefix": prefix}),
        (r"/genre", GenreMixHandler, {"core": core, "prefix": prefix}),
        (r"/artist", ArtistMixHandler, {"core": core, "prefix": prefix}),
        (r"/album", AlbumMixHandler, {"core": core, "prefix": prefix}),
        (r"/instant-mix", InstantMixHandler, {"core": core, "prefix": prefix}),
        (r"/refresh", RefreshHandler, {"core": core, "config": config}),
        (r"/status", StatusHandler, {"core": core}),
    ]
