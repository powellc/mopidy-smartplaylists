from unittest import mock

from mopidy.models import Album, Artist, Playlist, SearchResult, Track

from mopidy_smartplaylists.generators import (
    _extract_tracks,
    _flatten_lookup,
    _sanitize_name,
    build_artist_discography,
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
        tracks = [
            Track(uri="dummy:1", name="Track 1"),
            Track(uri="dummy:2", name="Track 2"),
        ]
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


class TestBuildArtistDiscography:
    def test_chronological_order_from_browse(self):
        core = mock.Mock()
        refs = [
            mock.Mock(
                uri="local:directory?album=local:album:late&artist=Test&date=2000",
                name="Late Album",
            ),
            mock.Mock(
                uri="local:directory?album=local:album:early&artist=Test&date=1990",
                name="Early Album",
            ),
        ]
        core.library.browse.return_value.get.return_value = refs

        early_album = Album(uri="local:album:early")
        late_album = Album(uri="local:album:late")
        early_tracks = [
            Track(uri="local:track:e1", name="Early 1", album=early_album, disc_no=1, track_no=1),
            Track(uri="local:track:e2", name="Early 2", album=early_album, disc_no=1, track_no=2),
        ]
        late_tracks = [
            Track(uri="local:track:l1", name="Late 1", album=late_album, disc_no=1, track_no=1),
        ]

        def lookup_side_effect(uris):
            result = mock.Mock()
            results = {}
            for u in uris:
                if "early" in u:
                    results[u] = early_tracks
                elif "late" in u:
                    results[u] = late_tracks
            result.get.return_value = results
            return result

        core.library.lookup.side_effect = lookup_side_effect

        result = build_artist_discography(core, "Test Artist")

        assert len(result) == 3
        assert result[0].uri == "local:track:e1"
        assert result[1].uri == "local:track:e2"
        assert result[2].uri == "local:track:l1"

    def test_reverse_chronological_order(self):
        core = mock.Mock()
        refs = [
            mock.Mock(
                uri="local:directory?album=local:album:late&artist=Test&date=2000",
                name="Late Album",
            ),
            mock.Mock(
                uri="local:directory?album=local:album:early&artist=Test&date=1990",
                name="Early Album",
            ),
        ]
        core.library.browse.return_value.get.return_value = refs

        early_tracks = [
            Track(uri="local:track:e1", name="Early 1", disc_no=1, track_no=1),
        ]
        late_tracks = [
            Track(uri="local:track:l1", name="Late 1", disc_no=1, track_no=1),
        ]

        def lookup_side_effect(uris):
            result = mock.Mock()
            results = {}
            for u in uris:
                if "early" in u:
                    results[u] = early_tracks
                elif "late" in u:
                    results[u] = late_tracks
            result.get.return_value = results
            return result

        core.library.lookup.side_effect = lookup_side_effect

        result = build_artist_discography(core, "Test Artist", reverse=True)

        assert len(result) == 2
        assert result[0].uri == "local:track:l1"
        assert result[1].uri == "local:track:e1"

    def test_undated_albums_sorted_last_chronologically(self):
        core = mock.Mock()
        refs = [
            mock.Mock(
                uri="local:directory?album=local:album:dated&artist=Test&date=2000",
                name="Dated",
            ),
            mock.Mock(
                uri="local:directory?album=local:album:undated&artist=Test",
                name="Undated",
            ),
        ]
        core.library.browse.return_value.get.return_value = refs

        dated_tracks = [Track(uri="local:track:d1", name="Dated 1", disc_no=1, track_no=1)]
        undated_tracks = [Track(uri="local:track:u1", name="Undated 1", disc_no=1, track_no=1)]

        lookups: dict[str, list[Track]] = {
            "local:album:dated": dated_tracks,
            "local:album:undated": undated_tracks,
        }

        def lookup_side_effect(uris):
            result = mock.Mock()
            result.get.return_value = {u: lookups.get(u, []) for u in uris}
            return result

        core.library.lookup.side_effect = lookup_side_effect

        result = build_artist_discography(core, "Test Artist")
        assert result[0].uri == "local:track:d1"
        assert result[1].uri == "local:track:u1"

    def test_undated_albums_sorted_first_reverse(self):
        core = mock.Mock()
        refs = [
            mock.Mock(
                uri="local:directory?album=local:album:dated&artist=Test&date=2000",
                name="Dated",
            ),
            mock.Mock(
                uri="local:directory?album=local:album:undated&artist=Test",
                name="Undated",
            ),
        ]
        core.library.browse.return_value.get.return_value = refs

        dated_tracks = [Track(uri="local:track:d1", name="Dated 1", disc_no=1, track_no=1)]
        undated_tracks = [Track(uri="local:track:u1", name="Undated 1", disc_no=1, track_no=1)]

        lookups: dict[str, list[Track]] = {
            "local:album:dated": dated_tracks,
            "local:album:undated": undated_tracks,
        }

        def lookup_side_effect(uris):
            result = mock.Mock()
            result.get.return_value = {u: lookups.get(u, []) for u in uris}
            return result

        core.library.lookup.side_effect = lookup_side_effect

        result = build_artist_discography(core, "Test Artist", reverse=True)
        assert result[0].uri == "local:track:u1"
        assert result[1].uri == "local:track:d1"

    def test_tracks_sorted_by_disc_and_track_number(self):
        core = mock.Mock()
        refs = [
            mock.Mock(
                uri="local:directory?album=local:album:a&artist=Test&date=2000",
                name="Album",
            ),
        ]
        core.library.browse.return_value.get.return_value = refs

        album_tracks = [
            Track(uri="local:track:t2", name="Track 2", disc_no=1, track_no=2),
            Track(uri="local:track:d1t1", name="Disc 1 Track 1", disc_no=2, track_no=1),
            Track(uri="local:track:t1", name="Track 1", disc_no=1, track_no=1),
        ]

        def lookup_side_effect(uris):
            result = mock.Mock()
            result.get.return_value = {uris[0]: album_tracks}
            return result

        core.library.lookup.side_effect = lookup_side_effect

        result = build_artist_discography(core, "Test Artist")
        assert result[0].uri == "local:track:t1"
        assert result[1].uri == "local:track:t2"
        assert result[2].uri == "local:track:d1t1"

    def test_empty_browse_falls_back_to_search(self):
        core = mock.Mock()
        core.library.browse.return_value.get.return_value = []

        album_a = Album(uri="local:album:a", date="2000", name="Album A")
        tracks = [
            Track(
                uri="local:track:t1", name="T1",
                album=album_a, disc_no=1, track_no=1,
            ),
        ]
        core.library.search.return_value.get.return_value = [
            mock.Mock(tracks=tracks),
        ]

        result = build_artist_discography(core, "Test Artist")
        assert len(result) == 1
        assert result[0].uri == "local:track:t1"

    def test_no_tracks_returns_empty(self):
        core = mock.Mock()
        core.library.browse.return_value.get.return_value = []
        core.library.search.return_value.get.return_value = []

        result = build_artist_discography(core, "Nonexistent")
        assert result == []


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
        uris = {t.uri for t in result}
        assert uris == {"dummy:similar1", "dummy:similar2"}

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
