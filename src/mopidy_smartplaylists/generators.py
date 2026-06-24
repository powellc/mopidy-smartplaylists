from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, cast

from mopidy.models import Playlist, Track

if TYPE_CHECKING:
    from mopidy_smartplaylists.compat import CoreProxy, Query, SearchField, Uri

logger = logging.getLogger(__name__)


def parse_decade(decade_str: str) -> str:
    decade_str = decade_str.strip().rstrip("s")
    if len(decade_str) >= 3:
        return decade_str[:3] + "*"
    return decade_str


def _search(core: CoreProxy, field: str, value: str) -> list[Track]:
    query = cast("Query[SearchField]", {field: [value]})
    result = core.library.search(query).get()
    return _extract_tracks(result)


def build_decade_mix(core: CoreProxy, decade: str) -> list[Track]:
    query = cast("Query[SearchField]", {"date": [parse_decade(decade)]})
    result = core.library.search(query).get()
    tracks = _extract_tracks(result)
    logger.info("Found %d tracks for decade %s", len(tracks), decade)
    return tracks


def build_genre_mix(core: CoreProxy, genre: str) -> list[Track]:
    return _search(core, "genre", genre)


def build_artist_mix(core: CoreProxy, artist: str) -> list[Track]:
    return _search(core, "artist", artist)


def build_album_mix(core: CoreProxy, album_uri: str) -> list[Track]:
    tracks = core.library.lookup(cast("list[Uri]", [album_uri])).get()
    flat = _flatten_lookup(tracks)
    logger.info("Found %d tracks for album %s", len(flat), album_uri)
    return flat


def build_instant_mix(core: CoreProxy, track_uri: str, limit: int = 50) -> list[Track]:
    lookup_result = core.library.lookup(cast("list[Uri]", [track_uri])).get()
    seed_tracks = _flatten_lookup(lookup_result)
    if not seed_tracks:
        logger.warning("No track found for URI: %s", track_uri)
        return []

    seed = seed_tracks[0]
    genres: list[str] = []
    artists: list[str] = []

    if seed.genre:
        genres = [g.strip() for g in seed.genre.split("/") if g.strip()]
    if seed.artists:
        artists.extend(a_ref.name for a_ref in seed.artists if a_ref.name)

    similar: dict[str, Track] = {}

    for genre in genres:
        g_query = cast("Query[SearchField]", {"genre": [genre]})
        genre_result = core.library.search(g_query).get()
        for batch in genre_result:
            for t in batch.tracks:
                if t.uri and t.uri != track_uri:
                    similar[t.uri] = t

    for artist in artists:
        if len(similar) >= limit:
            break
        a_query = cast("Query[SearchField]", {"artist": [artist]})
        artist_result = core.library.search(a_query).get()
        for batch in artist_result:
            for t in batch.tracks:
                if t.uri and t.uri != track_uri:
                    similar[t.uri] = t

    tracks = list(similar.values())[:limit]
    logger.info("Instant mix: found %d tracks similar to %s", len(tracks), seed.name)
    return tracks


def save_smart_playlist(
    core: CoreProxy,
    prefix: str,
    name: str,
    tracks: list[Track],
) -> Playlist | None:
    playlist_name = f"{prefix} {name}"
    uri: str = f"mopidy:smartplaylists:{_sanitize_name(name)}"

    existing = core.playlists.lookup(cast("Uri", uri)).get()
    if existing:
        core.playlists.delete(existing.uri).get()

    playlist = Playlist(
        name=playlist_name,
        uri=cast("Uri", uri),
        tracks=tuple(tracks),
    )
    saved = core.playlists.save(playlist).get()
    logger.info("Saved smart playlist: %s (%d tracks)", playlist_name, len(tracks))
    return saved


def refresh_smart_playlists(core: CoreProxy, config_dict: dict) -> None:
    prefix = config_dict.get("playlist_prefix", "[Smart]")

    decades_raw = config_dict.get("decades", "")
    if decades_raw:
        decades = [d.strip() for d in decades_raw.split(",") if d.strip()]
        for decade in decades:
            tracks = build_decade_mix(core, decade)
            if tracks:
                save_smart_playlist(core, prefix, f"{decade}s Mix", tracks)

    genres_raw = config_dict.get("genres", "")
    if genres_raw:
        genres = [g.strip() for g in genres_raw.split(",") if g.strip()]
        for genre in genres:
            tracks = build_genre_mix(core, genre)
            if tracks:
                save_smart_playlist(core, prefix, f"{genre} Mix", tracks)

    artists_raw = config_dict.get("artists", "")
    if artists_raw:
        artists = [a.strip() for a in artists_raw.split(",") if a.strip()]
        for artist in artists:
            tracks = build_artist_mix(core, artist)
            if tracks:
                save_smart_playlist(core, prefix, f"{artist} Mix", tracks)


def _extract_tracks(search_result: list) -> list[Track]:
    tracks: list[Track] = []
    for batch in search_result:
        tracks.extend(batch.tracks)
    return tracks


def _flatten_lookup(lookup_result: dict[Uri, list[Track]]) -> list[Track]:
    tracks: list[Track] = []
    for uri_tracks in lookup_result.values():
        tracks.extend(uri_tracks)
    return tracks


def _sanitize_name(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", name).lower()
