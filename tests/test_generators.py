from unittest import mock

import pytest
from mopidy.models import Artist, Playlist, SearchResult, Track

from mopidy_smartplaylists.generators import (
    _extract_tracks,
    _flatten_lookup,
    _sanitize_name,
    build_artist_mix,
    build_decade_mix,
    build_genre_mix,
    build_instant_mix,
    parse_decade,
    refresh_smart_playlists,
    save_smart_playlist,
)


class TestParseDecade:
    def test_four_digit_year(self):
        assert parse_decade("1980") == "198*"

    def test_with_suffix(self):
        assert parse_decade("1980s") == "198*"

    def test_three_digit(self):
        assert parse_decade("199") == "199*"

    def test_whitespace(self):
        assert parse_decade("  2000  ") == "200*"


class TestSanitizeName:
    def test_lowercase(self):
        assert _sanitize_name("Hello World") == "hello_world"

    def test_special_chars(self):
        assert _sanitize_name("Jazz/Funk Mix!") == "jazz_funk_mix_"

    def test_already_sanitized(self):
        assert _sanitize_name("hello_world") == "hello_world"


class TestExtractTracks:
    def test_extracts_from_search_results(self):
        tracks = [Track(uri="dummy:1", name="Track 1"), Track(uri="dummy:2", name="Track 2")]
        results = [SearchResult(uri="dummy:search", tracks=tracks)]
        assert _extract_tracks(results) == tracks

    def test_empty_results(self):
        assert _extract_tracks([]) == []


class TestFlattenLookup:
    def test_flattens_dict_of_lists(self):
        result = {
            "dummy:1": [Track(uri="dummy:1", name="Track 1")],
            "dummy:2": [Track(uri="dummy:2", name="Track 2")],
        }
        flat = _flatten_lookup(result)
        assert len(flat) == 2

    def test_empty_lookup(self):
        assert _flatten_lookup({}) == []


class TestBuildDecadeMix:
    def test_searches_with_decade_query(self):
        core = mock.Mock()
        expected_tracks = [Track(uri="dummy:1", name="Track 1")]
        core.library.search.return_value.get.return_value = [
            SearchResult(uri="dummy:search", tracks=expected_tracks)
        ]

        result = build_decade_mix(core, "1980")

        core.library.search.assert_called_once()
        query_arg = core.library.search.call_args[0][0]
        assert "date" in query_arg
        assert query_arg["date"] == ["198*"]
        assert result == expected_tracks


class TestBuildGenreMix:
    def test_searches_with_genre_query(self):
        core = mock.Mock()
        expected_tracks = [Track(uri="dummy:1", name="Jazz Track")]
        core.library.search.return_value.get.return_value = [
            SearchResult(uri="dummy:search", tracks=expected_tracks)
        ]

        result = build_genre_mix(core, "Jazz")

        core.library.search.assert_called_once()
        query_arg = core.library.search.call_args[0][0]
        assert query_arg["genre"] == ["Jazz"]
        assert result == expected_tracks


class TestBuildArtistMix:
    def test_searches_with_artist_query(self):
        core = mock.Mock()
        expected_tracks = [Track(uri="dummy:1", name="Artist Track")]
        core.library.search.return_value.get.return_value = [
            SearchResult(uri="dummy:search", tracks=expected_tracks)
        ]

        result = build_artist_mix(core, "Miles Davis")

        core.library.search.assert_called_once()
        query_arg = core.library.search.call_args[0][0]
        assert query_arg["artist"] == ["Miles Davis"]
        assert result == expected_tracks


class TestBuildInstantMix:
    def test_returns_similar_tracks_by_genre(self):
        core = mock.Mock()
        seed = Track(
            uri="dummy:seed",
            name="Seed Track",
            genre="Jazz",
            artists=[Artist(name="Miles Davis")],
        )
        core.library.lookup.return_value.get.return_value = {
            "dummy:seed": [seed],
        }

        similar = [
            Track(uri="dummy:similar1", name="Similar 1", genre="Jazz"),
            Track(uri="dummy:similar2", name="Similar 2", genre="Jazz"),
        ]
        core.library.search.return_value.get.return_value = [
            SearchResult(uri="dummy:search", tracks=similar),
        ]

        result = build_instant_mix(core, "dummy:seed", limit=50)

        assert len(result) == 2
        assert result[0].uri == "dummy:similar1"

    def test_excludes_seed_track(self):
        core = mock.Mock()
        seed = Track(uri="dummy:seed", name="Seed Track", genre="Rock")
        core.library.lookup.return_value.get.return_value = {
            "dummy:seed": [seed],
        }
        same_as_seed = [Track(uri="dummy:seed", name="Seed Track", genre="Rock")]
        core.library.search.return_value.get.return_value = [
            SearchResult(uri="dummy:search", tracks=same_as_seed),
        ]

        result = build_instant_mix(core, "dummy:seed")

        assert len(result) == 0

    def test_empty_lookup_returns_empty(self):
        core = mock.Mock()
        core.library.lookup.return_value.get.return_value = {}
        result = build_instant_mix(core, "dummy:nonexistent")
        assert result == []


class TestSaveSmartPlaylist:
    def test_creates_new_playlist(self):
        core = mock.Mock()
        core.playlists.lookup.return_value.get.return_value = None
        saved = Playlist(
            name="[Smart] Jazz Mix",
            uri="mopidy:smartplaylists:jazz_mix",
            tracks=[Track(uri="dummy:1", name="Track")],
        )
        core.playlists.save.return_value.get.return_value = saved

        tracks = [Track(uri="dummy:1", name="Track")]
        result = save_smart_playlist(core, "[Smart]", "Jazz Mix", tracks)

        assert result == saved
        core.playlists.save.assert_called_once()

    def test_deletes_existing_before_save(self):
        core = mock.Mock()
        existing = Playlist(
            name="[Smart] Old Jazz Mix",
            uri="mopidy:smartplaylists:jazz_mix",
            tracks=[],
        )
        core.playlists.lookup.return_value.get.return_value = existing
        saved = Playlist(
            name="[Smart] Jazz Mix",
            uri="mopidy:smartplaylists:jazz_mix",
            tracks=[Track(uri="dummy:1", name="Track")],
        )
        core.playlists.save.return_value.get.return_value = saved

        tracks = [Track(uri="dummy:1", name="Track")]
        result = save_smart_playlist(core, "[Smart]", "Jazz Mix", tracks)

        assert result == saved
        core.playlists.delete.assert_called_once_with(existing.uri)


class TestRefreshSmartPlaylists:
    def test_skips_when_no_recipes(self):
        core = mock.Mock()
        config = {}
        refresh_smart_playlists(core, config)
        core.library.search.assert_not_called()

    def test_generates_decade_mixes(self):
        core = mock.Mock()
        config = {"decades": "1980,1990", "playlist_prefix": "[Smart]"}
        core.library.search.return_value.get.return_value = [
            SearchResult(uri="dummy:search", tracks=[Track(uri="dummy:1", name="T")])
        ]
        core.playlists.lookup.return_value.get.return_value = None
        core.playlists.save.return_value.get.return_value = Playlist(
            name="test", uri="dummy:playlist", tracks=[]
        )

        refresh_smart_playlists(core, config)

        assert core.library.search.call_count == 2
        assert core.playlists.save.call_count == 2

    def test_generates_genre_mixes(self):
        core = mock.Mock()
        config = {"genres": "Jazz,Rock", "playlist_prefix": "[Smart]"}
        core.library.search.return_value.get.return_value = [
            SearchResult(uri="dummy:search", tracks=[Track(uri="dummy:1", name="T")])
        ]
        core.playlists.lookup.return_value.get.return_value = None
        core.playlists.save.return_value.get.return_value = Playlist(
            name="test", uri="dummy:playlist", tracks=[]
        )

        refresh_smart_playlists(core, config)

        assert core.library.search.call_count == 2
        assert core.playlists.save.call_count == 2
