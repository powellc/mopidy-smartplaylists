import logging
import re

from mopidy.core import CoreProxy
from mopidy.models import Playlist, Track, TrackField

logger = logging.getLogger(__name__)


def parse_decade(decade_str: str) -> str:
    decade_str = decade_str.strip()
    if len(decade_str) == 4:
        return decade_str[:3] + "*"
    if decade_str.endswith("s"):
        return decade_str[:3] + "*"
    return decade_str


def build_decade_mix(core: CoreProxy, decade: str) -> list[Track]:
    query = {TrackField.DATE: [parse_decade(decade)]}
    result = core.library.search(query).get()
    tracks = _extract_tracks(result)
    logger.info("Found %d tracks for decade %s", len(tracks), decade)
    return tracks


def build_genre_mix(core: CoreProxy, genre: str) -> list[Track]:
    query = {TrackField.GENRE: [genre]}
    result = core.library.search(query).get()
    tracks = _extract_tracks(result)
    logger.info("Found %d tracks for genre %s", len(tracks), genre)
    return tracks


def build_artist_mix(core: CoreProxy, artist: str) -> list[Track]:
    query = {TrackField.ARTIST: [artist]}
    result = core.library.search(query).get()
    tracks = _extract_tracks(result)
    logger.info("Found %d tracks for artist %s", len(tracks), artist)
    return tracks


def build_album_mix(core: CoreProxy, album_uri: str) -> list[Track]:
    tracks = core.library.lookup([album_uri]).get()
    flat = _flatten_lookup(tracks)
    logger.info("Found %d tracks for album %s", len(flat), album_uri)
    return flat


def build_instant_mix(core: CoreProxy, track_uri: str, limit: int = 50) -> list[Track]:
    lookup_result = core.library.lookup([track_uri]).get()
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
        for artist_ref in seed.artists:
            if artist_ref.name:
                artists.append(artist_ref.name)

    similar: dict[str, Track] = {}

    for genre in genres:
        query = {TrackField.GENRE: [genre]}
        result = core.library.search(query).get()
        for batch in result:
            for t in batch.tracks:
                if t.uri and t.uri != track_uri:
                    similar[t.uri] = t

    for artist in artists:
        if len(similar) >= limit:
            break
        query = {TrackField.ARTIST: [artist]}
        result = core.library.search(query).get()
        for batch in result:
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
    uri = f"mopidy:smartplaylists:{_sanitize_name(name)}"

    existing = core.playlists.lookup(uri).get()
    if existing:
        core.playlists.delete(existing.uri).get()

    playlist = Playlist(
        name=playlist_name,
        uri=uri,
        tracks=tracks,
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


def _extract_tracks(search_result) -> list[Track]:
    tracks: list[Track] = []
    for batch in search_result:
        tracks.extend(batch.tracks)
    return tracks


def _flatten_lookup(lookup_result: dict[str, list[Track]]) -> list[Track]:
    tracks: list[Track] = []
    for uri_tracks in lookup_result.values():
        tracks.extend(uri_tracks)
    return tracks


def _sanitize_name(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", name).lower()
