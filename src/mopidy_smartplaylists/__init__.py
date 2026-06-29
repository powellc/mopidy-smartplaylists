import pathlib
from importlib.metadata import version

from mopidy import config, ext

__version__ = version("mopidy-smartplaylists")


class Extension(ext.Extension):
    dist_name = "mopidy-smartplaylists"
    ext_name = "smartplaylists"
    version = __version__

    def get_default_config(self) -> str:
        return config.read(pathlib.Path(__file__).parent / "ext.conf")

    def get_config_schema(self) -> config.ConfigSchema:
        schema = super().get_config_schema()
        schema["decades"] = config.String(optional=True)
        schema["genres"] = config.String(optional=True)
        schema["artists"] = config.String(optional=True)
        schema["artist_discography"] = config.String(optional=True)
        schema["playlist_prefix"] = config.String(optional=True)
        schema["refresh_interval"] = config.Integer(optional=True, minimum=0)
        schema["search_uris"] = config.List(optional=True)
        schema["playlist_dir"] = config.String(optional=True)
        schema["max_tracks"] = config.Integer(optional=True, minimum=0)
        schema["max_per_album"] = config.Integer(optional=True, minimum=0)
        schema["max_per_artist"] = config.Integer(optional=True, minimum=0)
        schema["smart_queue_enabled"] = config.Boolean(optional=True)
        schema["smart_queue_min_tracks"] = config.Integer(optional=True, minimum=0)
        schema["smart_queue_refill_to"] = config.Integer(optional=True, minimum=0)
        schema["smart_queue_cooldown"] = config.Integer(optional=True, minimum=0)
        schema["smart_queue_dedup"] = config.Integer(optional=True, minimum=0)
        schema["smart_queue_variety"] = config.Float(optional=True, minimum=0.0, maximum=1.0)
        return schema

    def validate_environment(self) -> None:
        pass

    def setup(self, registry: ext.Registry) -> None:
        from mopidy_smartplaylists.web import app_factory

        registry.add(
            "http:app",
            {
                "name": self.ext_name,
                "factory": app_factory,
            },
        )

        registry.add(
            "http:static",
            {
                "name": self.ext_name,
                "path": str(pathlib.Path(__file__).parent / "static"),
            },
        )

        from mopidy_smartplaylists.frontend import SmartPlaylistsFrontend

        registry.add("frontend", SmartPlaylistsFrontend)
