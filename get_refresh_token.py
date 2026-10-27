#!/usr/bin/env python3
"""One-time helper: sign in to Spotify and print a refresh token.

Run this on your own computer (not in GitHub). It opens your browser, you click
Agree, and it prints the refresh token to paste into a GitHub secret.

Before running, add this exact Redirect URI to your Spotify app:
    http://127.0.0.1:8888/callback

Usage:
    python3 get_refresh_token.py
"""

import base64
import getpass
import http.server
import json
import os
import secrets
import threading
import urllib.parse
import urllib.request
import webbrowser

PORT = 8888
REDIRECT_URI = f"http://127.0.0.1:{PORT}/callback"
SCOPES = "user-library-read playlist-read-private playlist-modify-private playlist-modify-public"


def main():
    client_id = os.environ.get("SPOTIFY_CLIENT_ID") or input("Client ID: ").strip()
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET") or getpass.getpass("Client Secret (hidden): ").strip()
    state = secrets.token_urlsafe(16)
    result = {}
    done = threading.Event()

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if urllib.parse.urlparse(self.path).path != "/callback":
                self.send_response(404)
                self.end_headers()
                return
            if qs.get("state", [""])[0] != state:
                result["error"] = "state mismatch"
            elif "error" in qs:
                result["error"] = qs["error"][0]
            else:
                result["code"] = qs.get("code", [""])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h3>Done. You can close this tab and go back to the terminal.</h3>")
            done.set()

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", PORT), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    url = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode({
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "state": state,
        "show_dialog": "true",
    })
    print("Opening your browser. If nothing opens, paste this link in manually:\n" + url + "\n")
    webbrowser.open(url)
    done.wait(timeout=300)
    server.shutdown()

    if "code" not in result:
        raise SystemExit(f"Sign-in failed: {result.get('error', 'timed out')}")

    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    req = urllib.request.Request(
        "https://accounts.spotify.com/api/token",
        data=urllib.parse.urlencode({
            "grant_type": "authorization_code",
            "code": result["code"],
            "redirect_uri": REDIRECT_URI,
        }).encode(),
        headers={"Authorization": f"Basic {basic}", "Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        tokens = json.loads(resp.read())

    print("Success. Your refresh token (keep it private, treat it like a password):\n")
    print(tokens["refresh_token"])
    print("\nSave it as the GitHub secret SPOTIFY_REFRESH_TOKEN.")


if __name__ == "__main__":
    main()
