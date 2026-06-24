from unittest import mock

from mopidy.models import Playlist

from mopidy_smartplaylists.frontend import SmartPlaylistsFrontend


class TestSmartPlaylistsFrontend:
    def test_on_start_with_recipes(self):
        config = mock.Mock()
        config.get.return_value = {
            "decades": "1980,1990",
            "genres": "",
            "artists": "",
            "playlist_prefix": "[Smart]",
            "refresh_interval": "0",
        }
        core = mock.Mock()
        core.library.search.return_value.get.return_value = []
        core.playlists.lookup.return_value.get.return_value = None
        core.playlists.save.return_value.get.return_value = Playlist(
            name="test", uri="dummy:pl", tracks=[]
        )

        frontend = SmartPlaylistsFrontend(config, core)
        frontend.on_start()

        assert core.library.search.call_count == 2

    def test_on_start_without_recipes(self):
        config = mock.Mock()
        config.get.return_value = {
            "decades": "",
            "genres": "",
            "artists": "",
            "playlist_prefix": "[Smart]",
            "refresh_interval": "0",
        }
        core = mock.Mock()

        frontend = SmartPlaylistsFrontend(config, core)
        frontend.on_start()

        core.library.search.assert_not_called()

    def test_playlists_loaded_with_interval(self):
        config = mock.Mock()
        config.get.return_value = {
            "decades": "1980",
            "playlist_prefix": "[Smart]",
            "refresh_interval": "24",
        }
        core = mock.Mock()
        core.library.search.return_value.get.return_value = []
        core.playlists.lookup.return_value.get.return_value = None
        core.playlists.save.return_value.get.return_value = Playlist(
            name="test", uri="dummy:pl", tracks=[]
        )

        frontend = SmartPlaylistsFrontend(config, core)
        frontend.playlists_loaded()

        core.library.search.assert_called()

    def test_playlists_loaded_without_interval(self):
        config = mock.Mock()
        config.get.return_value = {
            "playlist_prefix": "[Smart]",
            "refresh_interval": "0",
        }
        core = mock.Mock()

        frontend = SmartPlaylistsFrontend(config, core)
        frontend.playlists_loaded()

        core.library.search.assert_not_called()
