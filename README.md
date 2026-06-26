# mopidy-smartplaylists

[![Deploy](https://code.lab.unbl.ink/secstate/mopidy-smartplaylets/actions/workflows/deploy.yml/badge.svg)](https://code.lab.unbl.ink/secstate/mopidy-smartplaylists/actions)

Mopidy extension for generating diverse, full-length smart playlists from a local music library, with queue auto-refill.

## Features

- **Genre Mix** — playlist of tracks from albums in a given genre
- **Artist Mix** — playlist of tracks by a given artist
- **Album Mix** — expanded playlist seeded from an album
- **Instant Mix** — playlist based on a track (same genre + similar artists)
- **Playlist Mix** — instant mix generated from a random track in an existing playlist
- **Smart Queue** — auto-refills the playback queue as tracks play
- **Queue Insert** — insert smart queue tracks next or at end of the current queue
- **HTTP UI** — web interface at `/smartplaylists/static/`

## Bookmarklet: Toggle Smart Queue

Drag this link to your bookmarks bar to toggle the Smart Queue from any page:

```
javascript:(function(){var h=location.origin.replace(/\/+$/,'');fetch(h+'/smart-queue',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled:!confirm('Toggle Smart Queue?')})}).then(function(r){return r.json()}).then(function(d){alert('Smart Queue: '+(d.enabled?'On':'Off'))}).catch(function(){alert('Failed — not on Mopidy host?')})})();
```

Works when your browser is on the same Mopidy server (e.g. `http://mopidy-dev.service:6680/...`). Replaces `location.origin` with your server URL if bookmarking from a different domain.

## Configuration

Add to your Mopidy config:

```ini
[smartplaylists]
enabled = true
playlist_prefix = [Smart]
search_uris = local:directory:music

# Smart queue
smart_queue_enabled = true
smart_queue_min_tracks = 5
smart_queue_refill_to = 15
smart_queue_cooldown = 3
smart_queue_variety = 0.15
```

## Development

```sh
pip install -e .
```
