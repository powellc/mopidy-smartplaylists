from __future__ import annotations

import json
import logging
import random
from typing import TYPE_CHECKING, cast

import tornado.web

if TYPE_CHECKING:
    from mopidy_smartplaylists.compat import Config, CoreProxy, Uri

if TYPE_CHECKING:
    from mopidy.models import Playlist

from mopidy_smartplaylists import frontend as sq_frontend
from mopidy_smartplaylists.generators import (
    build_album_mix,
    build_artist_discography,
    build_artist_mix,
    build_genre_mix,
    build_instant_mix,
    build_smart_queue_tracks,
    refresh_smart_playlists,
    save_smart_playlist,
)

logger = logging.getLogger(__name__)


class GenreMixHandler(tornado.web.RequestHandler):
    def initialize(
        self, core: CoreProxy, prefix: str, uris: list[Uri] | None = None,
        playlist_dir: str | None = None,
        max_tracks: int = 0, max_per_album: int = 0, max_per_artist: int = 0,
    ) -> None:
        self.core = core
        self.prefix = prefix
        self.uris = uris
        self.playlist_dir = playlist_dir
        self.max_tracks = max_tracks
        self.max_per_album = max_per_album
        self.max_per_artist = max_per_artist

    def post(self) -> None:
        data = json.loads(self.request.body)
        genre = data.get("genre", "")
        if not genre:
            self.set_status(400)
            self.write({"error": "Missing 'genre' in request body"})
            return
        tracks = build_genre_mix(
            self.core, genre, uris=self.uris,
            max_tracks=self.max_tracks, max_per_album=self.max_per_album,
            max_per_artist=self.max_per_artist,
        )
        if not tracks:
            self.write({"playlist": None, "tracks": 0})
            return
        playlist = save_smart_playlist(
            self.core, self.prefix, f"{genre} Mix", tracks,
            playlist_dir=self.playlist_dir,
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


class ArtistMixHandler(tornado.web.RequestHandler):
    def initialize(
        self, core: CoreProxy, prefix: str, uris: list[Uri] | None = None,
        playlist_dir: str | None = None,
        max_tracks: int = 0, max_per_album: int = 0, max_per_artist: int = 0,
    ) -> None:
        self.core = core
        self.prefix = prefix
        self.uris = uris
        self.playlist_dir = playlist_dir
        self.max_tracks = max_tracks
        self.max_per_album = max_per_album
        self.max_per_artist = max_per_artist

    def post(self) -> None:
        data = json.loads(self.request.body)
        artist = data.get("artist", "")
        if not artist:
            self.set_status(400)
            self.write({"error": "Missing 'artist' in request body"})
            return
        tracks = build_artist_mix(
            self.core, artist, uris=self.uris,
            max_tracks=self.max_tracks, max_per_album=self.max_per_album,
            max_per_artist=self.max_per_artist,
        )
        if not tracks:
            self.write({"playlist": None, "tracks": 0})
            return
        playlist = save_smart_playlist(
            self.core, self.prefix, f"{artist} Mix", tracks,
            playlist_dir=self.playlist_dir,
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


class ArtistDiscographyHandler(tornado.web.RequestHandler):
    def initialize(
        self, core: CoreProxy, prefix: str, uris: list[Uri] | None = None,
        playlist_dir: str | None = None,
    ) -> None:
        self.core = core
        self.prefix = prefix
        self.uris = uris
        self.playlist_dir = playlist_dir

    def post(self) -> None:
        data = json.loads(self.request.body)
        artist = data.get("artist", "")
        reverse = bool(data.get("reverse", False))
        if not artist:
            self.set_status(400)
            self.write({"error": "Missing 'artist' in request body"})
            return
        tracks = build_artist_discography(
            self.core, artist, reverse=reverse, uris=self.uris,
        )
        if not tracks:
            self.write({"playlist": None, "tracks": 0})
            return
        name_suffix = " (Reverse)" if reverse else ""
        playlist = save_smart_playlist(
            self.core, self.prefix, f"{artist} - Discography{name_suffix}", tracks,
            playlist_dir=self.playlist_dir,
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


class AlbumMixHandler(tornado.web.RequestHandler):
    def initialize(
        self, core: CoreProxy, prefix: str, playlist_dir: str | None = None,
    ) -> None:
        self.core = core
        self.prefix = prefix
        self.playlist_dir = playlist_dir

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
        playlist = save_smart_playlist(
            self.core, self.prefix, f"{name} Mix", tracks,
            playlist_dir=self.playlist_dir,
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


class InstantMixHandler(tornado.web.RequestHandler):
    def initialize(
        self, core: CoreProxy, prefix: str, uris: list[Uri] | None = None,
        playlist_dir: str | None = None,
    ) -> None:
        self.core = core
        self.prefix = prefix
        self.uris = uris
        self.playlist_dir = playlist_dir

    def post(self) -> None:
        data = json.loads(self.request.body)
        uri = data.get("uri", "")
        limit = data.get("limit", 50)
        if not uri:
            self.set_status(400)
            self.write({"error": "Missing 'uri' in request body"})
            return

        seed = self._resolve_seed_track(uri)
        if not seed or not seed.uri:
            self.write({"playlist": None, "tracks": 0})
            return

        tracks = build_instant_mix(self.core, seed.uri, limit, uris=self.uris)
        if not tracks:
            self.write({"playlist": None, "tracks": 0})
            return

        seed_name = seed.name or "Instant Mix"
        playlist = save_smart_playlist(
            self.core, self.prefix, f"Instant Mix: {seed_name}", tracks,
            playlist_dir=self.playlist_dir,
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

    def _resolve_seed_track(self, uri: str):
        try:
            lookup = self.core.library.lookup([uri]).get()
        except Exception:
            lookup = None
        if lookup:
            tracks = [t for ts in lookup.values() for t in (ts or []) if t.uri]
            if tracks:
                return random.choice(tracks)
        try:
            pl = self.core.playlists.lookup(uri).get()
        except Exception:
            pl = None
        if pl and pl.tracks:
            valid = [t for t in pl.tracks if t.uri]
            if valid:
                return random.choice(valid)
        return None


class PlaylistMixHandler(tornado.web.RequestHandler):
    def initialize(
        self, core: CoreProxy, prefix: str, uris: list[Uri] | None = None,
        playlist_dir: str | None = None,
    ) -> None:
        self.core = core
        self.prefix = prefix
        self.uris = uris
        self.playlist_dir = playlist_dir

    def post(self) -> None:
        data = json.loads(self.request.body)
        playlist_uri = data.get("uri", "")
        limit = data.get("limit", 50)
        if not playlist_uri:
            self.set_status(400)
            self.write({"error": "Missing 'uri' in request body"})
            return
        try:
            pl = self.core.playlists.lookup(playlist_uri).get()
        except Exception:
            logger.exception("Playlist lookup failed for %s", playlist_uri)
            self.write({"playlist": None, "tracks": 0})
            return
        if not pl or not pl.tracks:
            self.write({"playlist": None, "tracks": 0})
            return
        seed = random.choice(pl.tracks)
        if not seed.uri:
            self.write({"playlist": None, "tracks": 0})
            return
        tracks = build_instant_mix(self.core, seed.uri, limit, uris=self.uris)
        if not tracks:
            self.write({"playlist": None, "tracks": 0})
            return
        playlist = save_smart_playlist(
            self.core, self.prefix, f"Playlist Mix: {pl.name}", tracks,
            playlist_dir=self.playlist_dir,
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


class QueueInsertNextHandler(tornado.web.RequestHandler):
    def initialize(
        self, core: CoreProxy, uris: list[Uri] | None = None,
        variety_chance: float = 0.15,
    ) -> None:
        self.core = core
        self.uris = uris
        self.variety_chance = variety_chance

    def post(self) -> None:
        data = json.loads(self.request.body)
        track_uri = data.get("uri", "")
        count = data.get("count", 15)
        if not track_uri:
            self.set_status(400)
            self.write({"error": "Missing 'uri' in request body"})
            return
        tracks = build_smart_queue_tracks(
            self.core, track_uri, count,
            uris=self.uris, variety_chance=self.variety_chance,
        )
        if not tracks:
            self.write({"tracks": 0})
            return
        try:
            current = self.core.playback.get_current_tl_track().get()
        except Exception:
            current = None
        if current:
            try:
                idx = self.core.tracklist.index(current).get()
            except Exception:
                idx = None
            if idx is not None:
                self.core.tracklist.add(tracks, at_position=idx + 1).get()
            else:
                self.core.tracklist.add(tracks).get()
        else:
            self.core.tracklist.add(tracks).get()
        self.write({"tracks": len(tracks)})


class QueueInsertEndHandler(tornado.web.RequestHandler):
    def initialize(
        self, core: CoreProxy, uris: list[Uri] | None = None,
        variety_chance: float = 0.15,
    ) -> None:
        self.core = core
        self.uris = uris
        self.variety_chance = variety_chance

    def post(self) -> None:
        data = json.loads(self.request.body)
        track_uri = data.get("uri", "")
        count = data.get("count", 15)
        if not track_uri:
            self.set_status(400)
            self.write({"error": "Missing 'uri' in request body"})
            return
        tracks = build_smart_queue_tracks(
            self.core, track_uri, count,
            uris=self.uris, variety_chance=self.variety_chance,
        )
        if not tracks:
            self.write({"tracks": 0})
            return
        self.core.tracklist.add(tracks).get()
        self.write({"tracks": len(tracks)})


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
            refs = self.core.playlists.as_list().get()
        except Exception:
            logger.exception("Failed to list playlists")
            self.set_status(500)
            self.write({
                "error": "Failed to list playlists",
                "smart_playlists": [],
                "count": 0,
            })
            return
        smart = []
        for ref in refs:
            if ref.name and ref.name.startswith(self.prefix):
                try:
                    pl = self.core.playlists.lookup(cast("Uri", ref.uri)).get()
                except Exception:
                    logger.exception("Failed to lookup playlist %s", ref.uri)
                    continue
                if pl is None:
                    continue
                smart.append({
                    "name": pl.name,
                    "uri": pl.uri,
                    "tracks": len(pl.tracks) if pl.tracks else 0,
                })
        self.write({"smart_playlists": smart, "count": len(smart)})


class PlaylistDeleteHandler(tornado.web.RequestHandler):
    def initialize(self, core: CoreProxy) -> None:
        self.core = core

    def post(self) -> None:
        data = json.loads(self.request.body)
        uri = data.get("uri", "")
        if not uri:
            self.set_status(400)
            self.write({"error": "Missing 'uri' in request body"})
            return
        try:
            self.core.playlists.delete(uri).get()
            self.write({"status": "ok"})
        except Exception as e:
            logger.exception("Failed to delete playlist %s", uri)
            self.set_status(500)
            self.write({"error": str(e)})


class SmartQueueControlHandler(tornado.web.RequestHandler):
    def initialize(self) -> None:
        pass

    def get(self) -> None:
        self.write(sq_frontend.smart_queue_status())

    def post(self) -> None:
        data = json.loads(self.request.body)
        enable = data.get("enabled", None)
        if enable is None:
            self.set_status(400)
            self.write({"error": "Missing 'enabled' in request body"})
            return
        sq_frontend.toggle_smart_queue(bool(enable))
        self.write(sq_frontend.smart_queue_status())


def _parse_search_uris(config: Config) -> list[Uri] | None:
    raw = config.get("smartplaylists", {}).get("search_uris")
    if raw is None:
        return None
    if isinstance(raw, (list, tuple)):
        return cast("list[Uri]", list(raw))
    if isinstance(raw, str):
        uris = cast("list[Uri]", [u.strip() for u in raw.split(",") if u.strip()])
        return uris or None
    return None


def _parse_playlist_dir(config: Config) -> str | None:
    raw = config.get("smartplaylists", {}).get("playlist_dir")
    return raw.strip() if raw else None


def _parse_int(config: Config, key: str, default: int) -> int:
    try:
        return int(config.get("smartplaylists", {}).get(key, default) or default)
    except (ValueError, TypeError):
        return default


def app_factory(config: Config, core: CoreProxy) -> list[tuple]:
    prefix = config.get("smartplaylists", {}).get("playlist_prefix", "[Smart]")
    uris = _parse_search_uris(config)
    playlist_dir = _parse_playlist_dir(config)
    max_tracks = _parse_int(config, "max_tracks", 0)
    max_per_album = _parse_int(config, "max_per_album", 0)
    max_per_artist = _parse_int(config, "max_per_artist", 0)

    return [
        (r"/genre", GenreMixHandler,
         {"core": core, "prefix": prefix, "uris": uris, "playlist_dir": playlist_dir,
          "max_tracks": max_tracks, "max_per_album": max_per_album,
          "max_per_artist": max_per_artist}),
        (r"/artist-discography", ArtistDiscographyHandler,
         {"core": core, "prefix": prefix, "uris": uris, "playlist_dir": playlist_dir}),
        (r"/artist", ArtistMixHandler,
         {"core": core, "prefix": prefix, "uris": uris, "playlist_dir": playlist_dir,
          "max_tracks": max_tracks, "max_per_album": max_per_album,
          "max_per_artist": max_per_artist}),
        (r"/album", AlbumMixHandler,
         {"core": core, "prefix": prefix, "playlist_dir": playlist_dir}),
        (r"/instant-mix", InstantMixHandler,
         {"core": core, "prefix": prefix, "uris": uris, "playlist_dir": playlist_dir}),
        (r"/playlist-mix", PlaylistMixHandler,
         {"core": core, "prefix": prefix, "uris": uris, "playlist_dir": playlist_dir}),
        (r"/queue-next", QueueInsertNextHandler,
         {"core": core, "uris": uris, "variety_chance": 0.15}),
        (r"/queue-end", QueueInsertEndHandler,
         {"core": core, "uris": uris, "variety_chance": 0.15}),
        (r"/refresh", RefreshHandler, {"core": core, "config": config}),
        (r"/status", StatusHandler, {"core": core, "prefix": prefix}),
        (r"/delete", PlaylistDeleteHandler, {"core": core}),
        (r"/smart-queue", SmartQueueControlHandler, {}),
    ]
