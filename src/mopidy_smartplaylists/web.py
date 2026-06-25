from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, cast

import tornado.web

if TYPE_CHECKING:
    from mopidy_smartplaylists.compat import Config, CoreProxy, Uri

if TYPE_CHECKING:
    from mopidy.models import Playlist

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
    def initialize(
        self, core: CoreProxy, prefix: str, uris: list[Uri] | None = None,
    ) -> None:
        self.core = core
        self.prefix = prefix
        self.uris = uris

    def post(self) -> None:
        data = json.loads(self.request.body)
        decade = data.get("decade", "")
        if not decade:
            self.set_status(400)
            self.write({"error": "Missing 'decade' in request body"})
            return
        tracks = build_decade_mix(self.core, decade, uris=self.uris)
        if not tracks:
            self.write({"playlist": None, "tracks": 0})
            return
        playlist = save_smart_playlist(self.core, self.prefix, f"{decade}s Mix", tracks)
        self.write(
            {
                "playlist": {
                    "name": playlist.name if playlist else None,
                    "uri": playlist.uri if playlist else None,
                    "tracks": len(tracks),
                },
            }
        )


class GenreMixHandler(tornado.web.RequestHandler):
    def initialize(
        self, core: CoreProxy, prefix: str, uris: list[Uri] | None = None,
    ) -> None:
        self.core = core
        self.prefix = prefix
        self.uris = uris

    def post(self) -> None:
        data = json.loads(self.request.body)
        genre = data.get("genre", "")
        if not genre:
            self.set_status(400)
            self.write({"error": "Missing 'genre' in request body"})
            return
        tracks = build_genre_mix(self.core, genre, uris=self.uris)
        if not tracks:
            self.write({"playlist": None, "tracks": 0})
            return
        playlist = save_smart_playlist(self.core, self.prefix, f"{genre} Mix", tracks)
        self.write(
            {
                "playlist": {
                    "name": playlist.name if playlist else None,
                    "uri": playlist.uri if playlist else None,
                    "tracks": len(tracks),
                },
            }
        )


class ArtistMixHandler(tornado.web.RequestHandler):
    def initialize(
        self, core: CoreProxy, prefix: str, uris: list[Uri] | None = None,
    ) -> None:
        self.core = core
        self.prefix = prefix
        self.uris = uris

    def post(self) -> None:
        data = json.loads(self.request.body)
        artist = data.get("artist", "")
        if not artist:
            self.set_status(400)
            self.write({"error": "Missing 'artist' in request body"})
            return
        tracks = build_artist_mix(self.core, artist, uris=self.uris)
        if not tracks:
            self.write({"playlist": None, "tracks": 0})
            return
        playlist = save_smart_playlist(self.core, self.prefix, f"{artist} Mix", tracks)
        self.write(
            {
                "playlist": {
                    "name": playlist.name if playlist else None,
                    "uri": playlist.uri if playlist else None,
                    "tracks": len(tracks),
                },
            }
        )


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
        name = (
            tracks[0].album.name
            if tracks[0].album and tracks[0].album.name
            else "Album"
        )
        playlist = save_smart_playlist(self.core, self.prefix, f"{name} Mix", tracks)
        self.write(
            {
                "playlist": {
                    "name": playlist.name if playlist else None,
                    "uri": playlist.uri if playlist else None,
                    "tracks": len(tracks),
                },
            }
        )


class InstantMixHandler(tornado.web.RequestHandler):
    def initialize(
        self, core: CoreProxy, prefix: str, uris: list[Uri] | None = None,
    ) -> None:
        self.core = core
        self.prefix = prefix
        self.uris = uris

    def post(self) -> None:
        data = json.loads(self.request.body)
        track_uri = data.get("uri", "")
        limit = data.get("limit", 50)
        if not track_uri:
            self.set_status(400)
            self.write({"error": "Missing 'uri' in request body"})
            return
        tracks = build_instant_mix(self.core, track_uri, limit, uris=self.uris)
        if not tracks:
            self.write({"playlist": None, "tracks": 0})
            return

        try:
            lookup_result = self.core.library.lookup([track_uri]).get()
        except Exception:
            logger.exception("Track lookup failed for %s", track_uri)
            self.write({"playlist": None, "tracks": 0})
            return
        seed_name = "Instant Mix"
        for uri_tracks in lookup_result.values():
            for t in uri_tracks:
                if t.name:
                    seed_name = t.name
                break

        playlist = save_smart_playlist(
            self.core, self.prefix, f"Instant Mix: {seed_name}", tracks
        )
        self.write(
            {
                "playlist": {
                    "name": playlist.name if playlist else None,
                    "uri": playlist.uri if playlist else None,
                    "tracks": len(tracks),
                },
            }
        )


class RefreshHandler(tornado.web.RequestHandler):
    def initialize(self, core: CoreProxy, config: Config) -> None:
        self.core = core
        self.config = config

    def post(self) -> None:
        section = self.config.get("smartplaylists", {})
        try:
            refresh_smart_playlists(self.core, section)
        except Exception:
            logger.exception("Refresh of smart playlists failed")
            self.set_status(500)
            self.write({"error": "Refresh failed"})
            return
        self.write({"status": "ok"})


class StatusHandler(tornado.web.RequestHandler):
    def initialize(self, core: CoreProxy, prefix: str) -> None:
        self.core = core
        self.prefix = prefix

    def get(self) -> None:
        try:
            result = self.core.playlists.as_list().get()
        except Exception:
            logger.exception("Failed to list playlists")
            self.set_status(500)
            self.write({
                "error": "Failed to list playlists",
                "smart_playlists": [],
                "count": 0,
            })
            return
        result_typed = cast("list[Playlist]", result)
        smart = [p for p in result_typed if p.name and p.name.startswith(self.prefix)]
        self.write(
            {
                "smart_playlists": [
                    {
                        "name": p.name,
                        "uri": p.uri,
                        "tracks": len(p.tracks) if p.tracks else 0,
                    }
                    for p in smart
                ],
                "count": len(smart),
            }
        )


def _parse_search_uris(config: Config) -> list[Uri] | None:
    raw = config.get("smartplaylists", {}).get("search_uris", "")
    if raw:
        uris = cast("list[Uri]", [u.strip() for u in raw.split(",") if u.strip()])
        return uris or None
    return None


def app_factory(config: Config, core: CoreProxy) -> list[tuple]:
    prefix = config.get("smartplaylists", {}).get("playlist_prefix", "[Smart]")
    uris = _parse_search_uris(config)

    return [
        (r"/decade", DecadeMixHandler, {"core": core, "prefix": prefix, "uris": uris}),
        (r"/genre", GenreMixHandler, {"core": core, "prefix": prefix, "uris": uris}),
        (r"/artist", ArtistMixHandler, {"core": core, "prefix": prefix, "uris": uris}),
        (r"/album", AlbumMixHandler, {"core": core, "prefix": prefix}),
        (r"/instant-mix", InstantMixHandler,
         {"core": core, "prefix": prefix, "uris": uris}),
        (r"/refresh", RefreshHandler, {"core": core, "config": config}),
        (r"/status", StatusHandler, {"core": core, "prefix": prefix}),
    ]
