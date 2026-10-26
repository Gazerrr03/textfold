"""A page sent from the reader's own browser (extension/): what they see, signed in or subscribed, read as they see it.

The extension serializes the tab when the reader clicks its button (extension/snapshot.js: shadow roots spelled out,
frames put in place, what the browser did not show marked) and hands it to this program by native messaging: the
browser starts it, writes one message to its standard input, reads the answer from its standard output, and lets only
the extensions named in its manifest (allowed_origins) reach it. No port is opened. The page's cookies never leave the
browser: what comes is the page as it was drawn.

A snapshot is stored as a web page of the library (webpage.py: web-<host>-<hash>), its HTML as it came beside it
(snapshot.html), and read as any web page is. A page already in the library is not written over.

  python3 -m textfold capture install --extension <id> [--browser chrome ...]   the host's manifest, for that extension
  python3 -m textfold capture-host                                             what the browser starts
"""
import json
import os
import re
import struct
import sys
import time
import urllib.parse
from pathlib import Path

from . import local, store, webpage

HOST = "app.textfold.capture"
FORMAT = "textfold/snapshot"
MAX = 64 * 2**20   # what a browser sends a native host at most
# where each browser looks for a host's manifest, for this user (on Windows: the registry, not done yet)
DIRS = {
    "darwin": {"chrome": "Library/Application Support/Google/Chrome/NativeMessagingHosts",
               "chromium": "Library/Application Support/Chromium/NativeMessagingHosts",
               "edge": "Library/Application Support/Microsoft Edge/NativeMessagingHosts",
               "brave": "Library/Application Support/BraveSoftware/Brave-Browser/NativeMessagingHosts"},
    "linux": {"chrome": ".config/google-chrome/NativeMessagingHosts", "chromium": ".config/chromium/NativeMessagingHosts",
              "edge": ".config/microsoft-edge/NativeMessagingHosts", "brave": ".config/BraveSoftware/Brave-Browser/NativeMessagingHosts"},
}


# ── native messaging: each message its length (4 bytes, this computer's order), then its JSON ───────
def read_message(stream):
    head = stream.read(4)
    if not head:
        return None
    if len(head) < 4:
        raise ValueError("cut-off")
    n = struct.unpack("=I", head)[0]
    if n > MAX:
        raise ValueError("too-large")
    body = stream.read(n)
    if len(body) < n:
        raise ValueError("cut-off")
    return json.loads(body.decode("utf-8"))


def write_message(stream, obj):
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    stream.write(struct.pack("=I", len(body)) + body)
    stream.flush()


# ── a snapshot, kept ─────────────────────────────────────────────────
def _server_url():
    """The reader of the TextFold running now (server.json), if one is."""
    try:
        s = json.loads((store.DATA / "server.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    pid = s.get("pid") if isinstance(s, dict) else None
    if not isinstance(pid, int) or not isinstance(s.get("url"), str):
        return None
    try:
        os.kill(pid, 0)
    except (OSError, ValueError):
        return None   # (a server ended outright leaves its file behind)
    return s["url"]


def receive(msg):
    """A snapshot the extension sent: checked, stored, and where to open it. {"ok", "paper", "new", "open"}."""
    if not isinstance(msg, dict) or msg.get("format") != FORMAT:
        raise ValueError("not-a-snapshot")
    url, html = msg.get("url"), msg.get("html")
    if not isinstance(url, str) or not re.match(r"https?://", url, re.I):
        raise ValueError("not-a-web-page")   # (a file:, a chrome:, an extension's page: not one TextFold reads)
    if not isinstance(html, str) or not html.strip():
        raise ValueError("no-page")
    url = url.split("#")[0]
    pid = webpage.pid_of(url)
    d = store.pdir(pid)
    new = not (d / "meta.json").exists()
    if new:
        md, read, info = webpage.read(html, url)   # (too few words: web-notext, said to the extension)
        host = re.sub(r"^www\.", "", urllib.parse.urlparse(url).hostname or "")
        if info["title"] == host:   # (the page names itself nowhere TextFold reads: the tab's title)
            info["title"] = (msg.get("title") or "").strip()[:300] or host
        d.mkdir(parents=True, exist_ok=True)
        (d / "url.txt").write_text(url, encoding="utf-8")
        meta = webpage.meta_of(pid, url, info)
        meta["source"] = {**meta["source"], "via": "browser"}
        meta["snapshot_kind"] = "browser"
        meta["snapshot_taken"] = msg.get("taken") if isinstance(msg.get("taken"), str) else time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        pre = local.prefetch(re.findall(r'<img[^>]*\ssrc="([^"]+)"', read))
        local.store_doc(pid, read, meta, "snapshot.html", html, lambda folder: local.Images(folder, None, pre=pre).resolve, sizes=True)
        (d / "source.md").write_text(md, encoding="utf-8")
    there = _server_url()
    return {"ok": True, "paper": pid, "new": new, "open": f"{there}/p/{pid}" if there else None}


def host(stdin=None, stdout=None):
    """What the browser starts: each message answered, until the browser closes the stream."""
    stdin = stdin or sys.stdin.buffer
    stdout = stdout or sys.stdout.buffer
    while True:
        try:
            msg = read_message(stdin)
        except ValueError as e:
            write_message(stdout, {"ok": False, "error": str(e)})
            return 1
        if msg is None:
            return 0
        try:
            reply = receive(msg)
        except ValueError as e:
            reply = {"ok": False, "error": str(e)}
        except Exception as e:   # (anything else: said, not a crash the browser would only call "disconnected")
            reply = {"ok": False, "error": f"{type(e).__name__}: {e}"[:300]}
        write_message(stdout, reply)


# ── installing the host ──────────────────────────────────────────────
def launcher(home=None):
    """The program a manifest names (a path, no arguments): this Python, this TextFold, the library it uses now."""
    home = Path(home or store.HOME)
    home.mkdir(parents=True, exist_ok=True)
    keep = "".join(f'{k}="{os.environ[k]}" ' for k in ("TEXTFOLD_DATA", "HOME", "PYTHONPATH") if os.environ.get(k))
    f = home / "capture-host"
    f.write_text(f'#!/bin/sh\n# TextFold\'s native messaging host (textfold/capture.py), started by the browser\n'
                 f'exec env {keep}"{sys.executable}" -m textfold capture-host "$@"\n', encoding="utf-8")
    f.chmod(0o755)
    return f


def manifest(path, extensions):
    return {"name": HOST, "description": "TextFold: pages sent from the browser", "path": str(path), "type": "stdio",
            "allowed_origins": [f"chrome-extension://{e}/" for e in extensions]}


def install(extensions, browsers=None, home=None, dirs=None):
    """The host's manifest where each browser looks for it, for this user: [paths written]."""
    if not extensions or not all(re.fullmatch(r"[a-p]{32}", e) for e in extensions):
        raise ValueError("an extension's id is 32 letters from a to p")
    places = dirs or {b: Path.home() / p for b, p in DIRS.get(sys.platform, {}).items()}
    if not places:
        raise ValueError(f"not yet on {sys.platform}")
    path, out = launcher(home), []
    for b, where in places.items():
        if browsers and b not in browsers:
            continue
        where = Path(where)
        where.mkdir(parents=True, exist_ok=True)
        f = where / f"{HOST}.json"
        f.write_text(json.dumps(manifest(path, extensions), indent=2), encoding="utf-8")
        out.append(f)
    return out
