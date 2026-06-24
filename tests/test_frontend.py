from unittest import mock

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

        frontend = SmartPlaylistsFrontend(config, core)
        frontend.on_start()

        core.library.search.assert_called()

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
            "playlist_prefix": "[Smart]",
            "refresh_interval": "24",
        }
        core = mock.Mock()

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
