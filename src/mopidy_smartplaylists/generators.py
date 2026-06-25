from __future__ import annotations

import logging
import os
import random
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


def _search(
    core: CoreProxy, field: str, value: str, uris: list[Uri] | None = None,
) -> list[Track]:
    query = cast("Query[SearchField]", {field: [value]})
    try:
        result = core.library.search(query, uris=uris).get()
    except Exception:
        logger.exception("Search failed for %s=%s", field, value)
        return []
    return _extract_tracks(result)


def _mix_tracks(
    tracks: list[Track], max_tracks: int = 0,
    max_per_album: int = 0, max_per_artist: int = 0,
) -> list[Track]:
    if not tracks:
        return []
    random.shuffle(tracks)
    seen_album: dict[str, int] = {}
    seen_artist: dict[str, int] = {}
    result: list[Track] = []
    for t in tracks:
        if max_per_album > 0:
            album_key = t.album.uri if t.album and t.album.uri else str(id(t))
            if seen_album.get(album_key, 0) >= max_per_album:
                continue
        if max_per_artist > 0:
            artists = t.artists or []
            artist_key = None
            for a in artists:
                if a.uri:
                    artist_key = a.uri
                    break
            if not artist_key:
                artist_name = (artists[0].name or "") if artists else ""
                artist_key = artist_name or str(id(t))
            if seen_artist.get(artist_key, 0) >= max_per_artist:
                continue
        if max_per_album > 0:
            seen_album[album_key] = seen_album.get(album_key, 0) + 1
        if max_per_artist > 0:
            seen_artist[artist_key] = seen_artist.get(artist_key, 0) + 1
        result.append(t)
    tracks = result
    if max_tracks > 0:
        tracks = tracks[:max_tracks]
    random.shuffle(tracks)
    return tracks


def build_decade_mix(
    core: CoreProxy, decade: str, uris: list[Uri] | None = None,
    max_tracks: int = 0, max_per_album: int = 0, max_per_artist: int = 0,
) -> list[Track]:
    query = cast("Query[SearchField]", {"date": [parse_decade(decade)]})
    try:
        result = core.library.search(query, uris=uris).get()
    except Exception:
        logger.exception("Decade search failed for %s", decade)
        return []
    tracks = _mix_tracks(_extract_tracks(result), max_tracks, max_per_album, max_per_artist)
    logger.info("Found %d tracks for decade %s", len(tracks), decade)
    return tracks


def build_genre_mix(
    core: CoreProxy, genre: str, uris: list[Uri] | None = None,
    max_tracks: int = 0, max_per_album: int = 0, max_per_artist: int = 0,
) -> list[Track]:
    return _mix_tracks(_search(core, "genre", genre, uris=uris), max_tracks, max_per_album, max_per_artist)


def build_artist_mix(
    core: CoreProxy, artist: str, uris: list[Uri] | None = None,
    max_tracks: int = 0, max_per_album: int = 0, max_per_artist: int = 0,
) -> list[Track]:
    return _mix_tracks(_search(core, "artist", artist, uris=uris), max_tracks, max_per_album, max_per_artist)


def build_album_mix(core: CoreProxy, album_uri: str) -> list[Track]:
    try:
        tracks = core.library.lookup(cast("list[Uri]", [album_uri])).get()
    except Exception:
        logger.exception("Album lookup failed for %s", album_uri)
        return []
    flat = _flatten_lookup(tracks)
    logger.info("Found %d tracks for album %s", len(flat), album_uri)
    return flat


def build_instant_mix(
    core: CoreProxy, track_uri: str, limit: int = 50, uris: list[Uri] | None = None,
) -> list[Track]:
    try:
        lookup_result = core.library.lookup(cast("list[Uri]", [track_uri])).get()
    except Exception:
        logger.exception("Track lookup failed for %s", track_uri)
        return []
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
        try:
            genre_result = core.library.search(g_query, uris=uris).get()
        except Exception:
            logger.exception("Genre search failed for %s", genre)
            continue
        for batch in genre_result:
            for t in batch.tracks:
                if t.uri and t.uri != track_uri:
                    similar[t.uri] = t

    for artist in artists:
        if len(similar) >= limit:
            break
        a_query = cast("Query[SearchField]", {"artist": [artist]})
        try:
            artist_result = core.library.search(a_query, uris=uris).get()
        except Exception:
            logger.exception("Artist search failed for %s", artist)
            continue
        for batch in artist_result:
            for t in batch.tracks:
                if t.uri and t.uri != track_uri:
                    similar[t.uri] = t

    tracks = list(similar.values())[:limit]
    logger.info("Instant mix: found %d tracks similar to %s", len(tracks), seed.name)
    return tracks


def build_smart_queue_tracks(
    core: CoreProxy, seed_uri: str, count: int,
    uris: list[Uri] | None = None,
    variety_chance: float = 0.15,
) -> list[Track]:
    instant_count = max(1, int(count * (1 - variety_chance)))
    variety_count = count - instant_count

    instant = build_instant_mix(core, seed_uri, limit=instant_count * 2, uris=uris)[:instant_count]

    variety: list[Track] = []
    if variety_count > 0:
        try:
            lookup_result = core.library.lookup(cast("list[Uri]", [seed_uri])).get()
        except Exception:
            lookup_result = {}
        seed_tracks = _flatten_lookup(lookup_result)
        seed = seed_tracks[0] if seed_tracks else None

        if seed:
            genres = [g.strip() for g in (seed.genre or "").split("/") if g.strip()]
            if genres:
                other_genre = random.choice(genres)
                variety = _search(core, "genre", other_genre, uris=uris)
            else:
                variety = _search(core, "artist", seed.artists[0].name if seed.artists else "", uris=uris)
            random.shuffle(variety)
            variety = variety[:variety_count]

    result = instant + variety
    random.shuffle(result)
    logger.info("Smart queue: added %d tracks (%d instant, %d variety) from seed %s",
                len(result), instant_count, variety_count, seed_uri)
    return result


def save_smart_playlist(
    core: CoreProxy,
    prefix: str,
    name: str,
    tracks: list[Track],
    playlist_dir: str | None = None,
) -> Playlist | None:
    playlist_name = f"{prefix} {name}"

    if playlist_dir:
        filename = f"{_safe_filename(playlist_name)}.m3u8"
        filepath = os.path.join(playlist_dir, filename)
        try:
                with open(filepath, "w") as f:
                    f.write("#EXTM3U\n")
                    for t in tracks:
                        if not t.uri:
                            continue
                        name = (t.name or "").replace("\n", " ").strip()
                        length = int(t.length / 1000) if t.length else -1
                        f.write(f"#EXTINF:{length},{name}\n")
                        f.write(f"{t.uri}\n")
        except Exception:
            logger.exception("Failed to write M3U8 file %s", filepath)
            return None
        logger.info(
            "Saved smart playlist: %s (%d tracks) as %s",
            playlist_name, len(tracks), filepath,
        )
        return Playlist(name=playlist_name, uri=f"m3u:{filename}", tracks=tuple(tracks))

    uri_safe = _sanitize_name(name)
    uri: str = f"mopidy:smartplaylists:{uri_safe}"

    try:
        existing = core.playlists.lookup(cast("Uri", uri)).get()
    except Exception:
        logger.exception("Playlist lookup failed for %s", uri)
        existing = None
    if existing:
        try:
            core.playlists.delete(existing.uri).get()
        except Exception:
            logger.exception("Failed to delete existing playlist %s", existing.uri)

    playlist = Playlist(
        name=playlist_name,
        uri=cast("Uri", uri),
        tracks=tuple(tracks),
    )
    try:
        saved = core.playlists.save(playlist).get()
    except Exception:
        logger.exception("Failed to save playlist %s", playlist_name)
        return None
    logger.info("Saved smart playlist: %s (%d tracks)", playlist_name, len(tracks))
    return saved


def refresh_smart_playlists(core: CoreProxy, config_dict: dict) -> None:
    prefix = config_dict.get("playlist_prefix", "[Smart]")
    raw = config_dict.get("search_uris")
    uris: list[Uri] | None = None
    if isinstance(raw, (list, tuple)):
        uris = cast("list[Uri]", list(raw))
    elif isinstance(raw, str) and raw.strip():
        uris = cast("list[Uri]", [u.strip() for u in raw.split(",") if u.strip()])
    playlist_dir = config_dict.get("playlist_dir")
    if isinstance(playlist_dir, str):
        playlist_dir = playlist_dir.strip() or None
    try:
        max_tracks = int(config_dict.get("max_tracks") or 0)
    except (ValueError, TypeError):
        max_tracks = 0
    try:
        max_per_album = int(config_dict.get("max_per_album") or 0)
    except (ValueError, TypeError):
        max_per_album = 0

    decades_raw = config_dict.get("decades", "")
    if decades_raw:
        decades = [d.strip() for d in decades_raw.split(",") if d.strip()]
        for decade in decades:
            try:
                tracks = build_decade_mix(core, decade, uris=uris,
                                          max_tracks=max_tracks, max_per_album=max_per_album)
            except Exception:
                logger.exception("Failed to build decade mix for %s", decade)
                continue
            if tracks:
                save_smart_playlist(core, prefix, f"{decade}s Mix", tracks, playlist_dir=playlist_dir)

    genres_raw = config_dict.get("genres", "")
    if genres_raw:
        genres = [d.strip() for d in genres_raw.split(",") if d.strip()]
        for genre in genres:
            try:
                tracks = build_genre_mix(core, genre, uris=uris,
                                         max_tracks=max_tracks, max_per_album=max_per_album)
            except Exception:
                logger.exception("Failed to build genre mix for %s", genre)
                continue
            if tracks:
                save_smart_playlist(core, prefix, f"{genre} Mix", tracks, playlist_dir=playlist_dir)

    artists_raw = config_dict.get("artists", "")
    if artists_raw:
        artists = [a.strip() for a in artists_raw.split(",") if a.strip()]
        for artist in artists:
            try:
                tracks = build_artist_mix(core, artist, uris=uris,
                                          max_tracks=max_tracks, max_per_album=max_per_album)
            except Exception:
                logger.exception("Failed to build artist mix for %s", artist)
                continue
            if tracks:
                save_smart_playlist(core, prefix, f"{artist} Mix", tracks, playlist_dir=playlist_dir)


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


def _safe_filename(name: str) -> str:
    return re.sub(r"[\0/]", "", name).strip() or "_"
