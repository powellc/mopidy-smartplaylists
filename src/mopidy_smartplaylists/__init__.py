import pathlib
from importlib.metadata import version

from mopidy import config, ext
from mopidy.config import ConfigSchema

__version__ = version("mopidy-smartplaylists")


class Extension(ext.Extension):
    dist_name = "mopidy-smartplaylists"
    ext_name = "smartplaylists"
    version = __version__

    def get_default_config(self):
        return config.read(pathlib.Path(__file__).parent / "ext.conf")

    def get_config_schema(self):
        schema = super().get_config_schema()
        schema["decades"] = config.String(optional=True)
        schema["genres"] = config.String(optional=True)
        schema["artists"] = config.String(optional=True)
        schema["playlist_prefix"] = config.String(optional=True)
        schema["refresh_interval"] = config.Integer(optional=True, minimum=0)
        return schema

    def validate_environment(self):
        pass

    def setup(self, registry):
        from mopidy_smartplaylists.web import app_factory

        registry.add("http:app", {
            "name": self.ext_name,
            "factory": app_factory,
        })

        from mopidy_smartplaylists.frontend import SmartPlaylistsFrontend

        registry.add("frontend", SmartPlaylistsFrontend)
