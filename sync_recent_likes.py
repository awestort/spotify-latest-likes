#!/usr/bin/env python3
"""Copy your most recently liked Spotify songs into one playlist.

Reads your newest Liked Songs, finds (or creates) a playlist with a fixed name,
and replaces that playlist's contents with those songs. Standard library only.

Required environment variables:
    SPOTIFY_CLIENT_ID
    SPOTIFY_CLIENT_SECRET
    SPOTIFY_REFRESH_TOKEN

Optional environment variables:
    PLAYLIST_NAME    default "My 100 Latest Likes"
    PLAYLIST_ID      skip the name lookup and use this playlist directly
    PLAYLIST_PUBLIC  "true" to make a newly created playlist public (default private)
    TRACK_COUNT      how many songs, 1 to 100 (default 100)

Usage:
    python3 sync_recent_likes.py             # do it
    python3 sync_recent_likes.py --dry-run   # print what would happen, change nothing
"""

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# The two overrides below exist only so the script can be tested against a fake server.
API = os.environ.get("SPOTIFY_API_BASE", "https://api.spotify.com/v1")
TOKEN_URL = os.environ.get("SPOTIFY_TOKEN_URL", "https://accounts.spotify.com/api/token")

PLAYLIST_NAME = os.environ.get("PLAYLIST_NAME", "My 100 Latest Likes")
PLAYLIST_ID = os.environ.get("PLAYLIST_ID", "").strip()
PLAYLIST_PUBLIC = os.environ.get("PLAYLIST_PUBLIC", "false").strip().lower() == "true"
COUNT = max(1, min(int(os.environ.get("TRACK_COUNT", "100")), 100))  # PUT accepts at most 100


def die(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def http(method, url, headers=None, body=None, retries=4):
    """One HTTP call with simple retry on rate limits and server errors."""
    data = None
    headers = dict(headers or {})
    if body is not None:
        if isinstance(body, (dict, list)):
            data = json.dumps(body).encode()
            headers.setdefault("Content-Type", "application/json")
        else:
            data = body if isinstance(body, bytes) else str(body).encode()
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            raw = e.read().decode(errors="replace")
            if e.code == 429 and attempt < retries:
                wait = int(e.headers.get("Retry-After", "2")) + 1
                print(f"Rate limited, waiting {wait}s")
                time.sleep(wait)
                continue
            if e.code >= 500 and attempt < retries:
                time.sleep(2 * (attempt + 1))
                continue
            die(f"{method} {url} -> HTTP {e.code}: {raw[:500]}")
        except urllib.error.URLError as e:
            if attempt < retries:
                time.sleep(2 * (attempt + 1))
                continue
            die(f"{method} {url} failed: {e.reason}")


def get_access_token():
    cid = os.environ.get("SPOTIFY_CLIENT_ID")
    secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
    refresh = os.environ.get("SPOTIFY_REFRESH_TOKEN")
    if not (cid and secret and refresh):
        die("Set SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET and SPOTIFY_REFRESH_TOKEN.")
    basic = base64.b64encode(f"{cid}:{secret}".encode()).decode()
    resp = http(
        "POST",
        TOKEN_URL,
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        body=urllib.parse.urlencode({"grant_type": "refresh_token", "refresh_token": refresh}),
    )
    if "access_token" not in resp:
        die("Token refresh did not return an access token. Redo the one-time sign-in.")
    if resp.get("refresh_token") and resp["refresh_token"] != refresh:
        print("NOTE: Spotify issued a new refresh token. Update the SPOTIFY_REFRESH_TOKEN secret "
              "if the old one stops working.")
    return resp["access_token"]


def fetch_liked(auth, want, everything=False):
    """Return a list of (added_at, uri) for liked tracks, API order (newest first)."""
    out = []
    offset = 0
    while True:
        page = http("GET", f"{API}/me/tracks?limit=50&offset={offset}", headers=auth)
        for item in page.get("items", []):
            track = item.get("track") or {}
            uri = track.get("uri") or ""
            # Skip local files and anything that is not a normal Spotify track.
            if uri.startswith("spotify:track:") and not track.get("is_local"):
                out.append((item.get("added_at", ""), uri))
        offset += 50
        if not page.get("next"):
            break
        if not everything and len(out) >= want:
            break
    return out


def newest_tracks(auth, want):
    tracks = fetch_liked(auth, want)
    dates = [d for d, _ in tracks]
    if dates != sorted(dates, reverse=True):
        # The docs do not promise an order, so verify it and fall back to a full sort.
        print("Liked Songs did not come back newest first. Fetching everything and sorting.")
        tracks = sorted(fetch_liked(auth, want, everything=True), key=lambda t: t[0], reverse=True)
    return tracks[:want]


def find_or_create_playlist(auth, dry_run):
    if PLAYLIST_ID:
        return PLAYLIST_ID
    me = http("GET", f"{API}/me", headers=auth)
    my_id = me.get("id")
    offset = 0
    while True:
        page = http("GET", f"{API}/me/playlists?limit=50&offset={offset}", headers=auth)
        for pl in page.get("items", []):
            if pl and pl.get("name") == PLAYLIST_NAME and (pl.get("owner") or {}).get("id") == my_id:
                return pl["id"]
        offset += 50
        if not page.get("next"):
            break
    if dry_run:
        print(f'[dry run] Would create playlist "{PLAYLIST_NAME}".')
        return None
    created = http(
        "POST",
        f"{API}/me/playlists",
        headers=auth,
        body={
            "name": PLAYLIST_NAME,
            "public": PLAYLIST_PUBLIC,
            "description": "Auto-updated weekly with my most recently liked songs.",
        },
    )
    print(f'Created playlist "{PLAYLIST_NAME}" ({created["id"]}).')
    return created["id"]


def main():
    dry_run = "--dry-run" in sys.argv
    token = get_access_token()
    auth = {"Authorization": f"Bearer {token}"}

    tracks = newest_tracks(auth, COUNT)
    if not tracks:
        print("No liked songs found. Leaving the playlist alone.")
        return
    uris = [u for _, u in tracks]
    print(f"Found {len(uris)} liked songs. Newest added {tracks[0][0]}, oldest in set {tracks[-1][0]}.")

    playlist_id = find_or_create_playlist(auth, dry_run)
    if dry_run:
        print("[dry run] No changes made.")
        return

    http("PUT", f"{API}/playlists/{playlist_id}/items", headers=auth, body={"uris": uris})
    print(f'Updated "{PLAYLIST_NAME}" with {len(uris)} songs.')


if __name__ == "__main__":
    main()
