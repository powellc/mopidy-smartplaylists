from __future__ import annotations

import logging
from collections import deque
from typing import TYPE_CHECKING

import pykka
from mopidy.core import CoreListener

from mopidy_smartplaylists.generators import build_smart_queue_tracks, refresh_smart_playlists

if TYPE_CHECKING:
    from mopidy_smartplaylists.compat import Config, CoreProxy, Uri

logger = logging.getLogger(__name__)

_smart_queue_enabled: bool = False
_recent_uris: deque = deque(maxlen=50)
_cooldown_counter: int = 0
_frontend_instance: SmartPlaylistsFrontend | None = None


class SmartPlaylistsFrontend(pykka.ThreadingActor, CoreListener):
    def __init__(self, config: Config, core: CoreProxy) -> None:
        super().__init__()
        self.config = config
        self.core = core
        section = dict(self.config.get("smartplaylists", {}))
        self._uris: list[Uri] | None = _parse_uris(section)
        self._min_tracks = _parse_int(section, "smart_queue_min_tracks", 5)
        self._refill_to = _parse_int(section, "smart_queue_refill_to", 15)
        self._cooldown = _parse_int(section, "smart_queue_cooldown", 3)
        self._variety = _parse_float(section, "smart_queue_variety", 0.15)
        dedup = _parse_int(section, "smart_queue_dedup", 50)
        global _recent_uris, _frontend_instance
        _recent_uris = deque(maxlen=dedup)
        _frontend_instance = self
        if _parse_bool(section, "smart_queue_enabled", False):
            global _smart_queue_enabled
            _smart_queue_enabled = True

    def on_start(self) -> None:
        section = dict(self.config.get("smartplaylists", {}))
        has_recipes = any(section.get(k) for k in ("decades", "genres", "artists"))
        if has_recipes:
            logger.info("Generating smart playlists from config recipes...")
            refresh_smart_playlists(self.core, section)
        else:
            logger.debug("No smart playlist recipes configured")

    def on_stop(self) -> None:
        global _frontend_instance
        _frontend_instance = None

    def playlists_loaded(self) -> None:
        section = dict(self.config.get("smartplaylists", {}))
        interval = int(section.get("refresh_interval", 0))
        if interval > 0:
            logger.info("Smart playlists loaded, running refresh...")
            refresh_smart_playlists(self.core, section)

    def track_playback_started(self, track) -> None:
        self._refill_queue()

    def tracklist_changed(self) -> None:
        self._refill_queue()

    def _refill_queue(self) -> None:
        global _cooldown_counter
        if not _smart_queue_enabled:
            return
        if _cooldown_counter > 0:
            _cooldown_counter -= 1
            return
        try:
            tl_tracks = self.core.tracklist.get_tracks().get()
        except Exception:
            return
        if len(tl_tracks) >= self._min_tracks:
            return
        try:
            current = self.core.playback.get_current_track().get()
        except Exception:
            current = None
        if not current or not current.uri:
            return
        _recent_uris.append(current.uri)
        needed = self._refill_to - len(tl_tracks)
        if needed <= 0:
            return
        try:
            tracks = build_smart_queue_tracks(
                self.core, current.uri, needed,
                uris=self._uris,
                variety_chance=self._variety,
            )
        except Exception:
            logger.exception("Smart queue track generation failed")
            return
        existing: set = set(_recent_uris)
        existing.update(t.uri for t in tl_tracks if t.uri)
        to_add = [t for t in tracks if t.uri and t.uri not in existing]
        if to_add:
            try:
                self.core.tracklist.add(to_add).get()
            except Exception:
                logger.exception("Failed to add tracks to queue")
                return
            _cooldown_counter = self._cooldown
            logger.info(
                "Smart queue: added %d/%d tracks (queue had %d)",
                len(to_add), len(tracks), len(tl_tracks),
            )


def toggle_smart_queue(enable: bool) -> None:
    global _smart_queue_enabled
    _smart_queue_enabled = enable
    logger.info("Smart queue %s", "enabled" if enable else "disabled")
    if enable and _frontend_instance:
        _frontend_instance._refill_queue()


def smart_queue_status() -> dict:
    return {
        "enabled": _smart_queue_enabled,
        "recent_tracks": len(_recent_uris),
    }


def _parse_uris(section: dict) -> list[Uri] | None:
    raw = section.get("search_uris")
    if raw is None:
        return None
    if isinstance(raw, (list, tuple)):
        return list(raw)
    if isinstance(raw, str) and raw.strip():
        return [u.strip() for u in raw.split(",") if u.strip()]
    return None


def _parse_int(section: dict, key: str, default: int) -> int:
    try:
        return int(section.get(key, default) or default)
    except (ValueError, TypeError):
        return default


def _parse_float(section: dict, key: str, default: float) -> float:
    try:
        return float(section.get(key, default) or default)
    except (ValueError, TypeError):
        return default


def _parse_bool(section: dict, key: str, default: bool) -> bool:
    raw = section.get(key, default)
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        return raw.lower() in ("true", "yes", "1")
    return bool(raw)
