import logging

import pykka
from mopidy.config import Config
from mopidy.core import CoreListener, CoreProxy

from mopidy_smartplaylists.generators import refresh_smart_playlists

logger = logging.getLogger(__name__)


class SmartPlaylistsFrontend(pykka.ThreadingActor, CoreListener):
    def __init__(self, config: Config, core: CoreProxy) -> None:
        super().__init__()
        self.config = config
        self.core = core

    def on_start(self) -> None:
        section = dict(self.config.get("smartplaylists", {}))
        has_recipes = any(section.get(k) for k in ("decades", "genres", "artists"))
        if has_recipes:
            logger.info("Generating smart playlists from config recipes...")
            refresh_smart_playlists(self.core, section)
        else:
            logger.debug("No smart playlist recipes configured")

    def on_stop(self) -> None:
        pass

    def playlists_loaded(self) -> None:
        section = dict(self.config.get("smartplaylists", {}))
        interval = int(section.get("refresh_interval", 0))
        if interval > 0:
            logger.info("Smart playlists loaded, running refresh...")
            refresh_smart_playlists(self.core, section)
