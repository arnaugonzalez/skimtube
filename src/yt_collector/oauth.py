"""Optional: add your YouTube subscriptions to the channel list (OAuth 2.0 loopback + PKCE).

Needs a Google Cloud OAuth client of type "Desktop app", provided via
YTC_OAUTH_CLIENT_ID / YTC_OAUTH_CLIENT_SECRET or the downloaded JSON at
$XDG_CONFIG_HOME/yt-collector/client_secret.json. The refresh token is stored at
$XDG_CONFIG_HOME/yt-collector/token.json (mode 0600), never in the working directory.
"""
from __future__ import annotations

import base64
import hashlib
import http.server
import json
import os
import secrets
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

from . import log

AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URI = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/youtube.readonly"
API = "https://www.googleapis.com/youtube/v3"


def config_dir() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "yt-collector"


def load_client() -> tuple[str, str] | None:
    cid = os.environ.get("YTC_OAUTH_CLIENT_ID")
    csec = os.environ.get("YTC_OAUTH_CLIENT_SECRET")
    if cid and csec:
        return cid, csec
    client_json = config_dir() / "client_secret.json"
    if client_json.exists():
        data = json.loads(client_json.read_text())
        node = data.get("installed") or data.get("web") or {}
        if node.get("client_id") and node.get("client_secret"):
            return node["client_id"], node["client_secret"]
    return None


def _post_token(params: dict) -> dict:
    req = urllib.request.Request(TOKEN_URI, data=urllib.parse.urlencode(params).encode(),
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


class _Handler(http.server.BaseHTTPRequestHandler):
    code: str | None = None
    state: str | None = None

    def do_GET(self):  # noqa: N802
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        if params.get("state", [""])[0] != _Handler.state:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"state mismatch")
            return
        _Handler.code = params.get("code", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"<h2>yt-collector authorized.</h2><p>You can close this tab.</p>")

    def log_message(self, *args):
        pass


def authorize() -> int:
    client = load_client()
    if not client:
        print("Missing OAuth client: set YTC_OAUTH_CLIENT_ID and YTC_OAUTH_CLIENT_SECRET, "
              f"or save the downloaded JSON as {config_dir() / 'client_secret.json'}",
              file=sys.stderr)
        return 1
    cid, csec = client
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    _Handler.state = secrets.token_urlsafe(16)
    srv = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    redirect_uri = f"http://127.0.0.1:{srv.server_address[1]}/"
    auth_url = AUTH_URI + "?" + urllib.parse.urlencode({
        "client_id": cid, "redirect_uri": redirect_uri, "response_type": "code",
        "scope": SCOPE, "access_type": "offline", "prompt": "consent",
        "code_challenge": challenge, "code_challenge_method": "S256",
        "state": _Handler.state,
    })
    print(f"Opening the browser for consent. If it does not open, visit:\n  {auth_url}")
    threading.Thread(target=lambda: webbrowser.open(auth_url), daemon=True).start()
    srv.handle_request()
    srv.server_close()
    if not _Handler.code:
        print("No authorization code received", file=sys.stderr)
        return 1
    tok = _post_token({"client_id": cid, "client_secret": csec, "code": _Handler.code,
                       "code_verifier": verifier, "redirect_uri": redirect_uri,
                       "grant_type": "authorization_code"})
    if "refresh_token" not in tok:
        print(f"No refresh_token in the response (keys: {sorted(tok)})", file=sys.stderr)
        return 1
    token_file = config_dir() / "token.json"
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.touch(mode=0o600)
    token_file.write_text(json.dumps({"refresh_token": tok["refresh_token"]}))
    print(f"Saved refresh token to {token_file}")
    return 0


def subscription_channel_ids() -> list[str]:
    """Channel ids you are subscribed to, or [] when OAuth is not set up or fails."""
    token_file = config_dir() / "token.json"
    client = load_client()
    if not token_file.exists() or not client:
        return []
    refresh = json.loads(token_file.read_text()).get("refresh_token")
    try:
        access = _post_token({"client_id": client[0], "client_secret": client[1],
                              "refresh_token": refresh, "grant_type": "refresh_token"}
                             )["access_token"]
        ids, page = [], None
        while True:
            params = {"part": "snippet", "mine": "true", "maxResults": "50"}
            if page:
                params["pageToken"] = page
            req = urllib.request.Request(f"{API}/subscriptions?{urllib.parse.urlencode(params)}",
                                         headers={"Authorization": f"Bearer {access}"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read().decode())
            ids += [it["snippet"]["resourceId"]["channelId"] for it in data.get("items", [])]
            page = data.get("nextPageToken")
            if not page:
                return ids
    except urllib.error.HTTPError as e:
        hint = " (refresh token expired? run: yt-collector auth)" if e.code in (400, 401) else ""
        log(f"warning: subscriptions API failed with HTTP {e.code}{hint}; "
            "using the channels file only")
    except (urllib.error.URLError, KeyError) as e:
        log(f"warning: cannot read subscriptions ({e}); using the channels file only")
    return []
