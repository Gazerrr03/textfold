"""Two easy ways in to a model (as in ThoughtDAG): the ChatGPT plan through a local bridge, and an OpenRouter key made
by one authorisation.

ChatGPT bridge: openai-oauth (npm) serves the ChatGPT plan as an OpenAI-compatible endpoint on 127.0.0.1:10531. It
signs in with Codex's login (~/.codex/auth.json); when there is none, its sign-in runs first and opens a browser (the
bridge alone, started without a terminal, would only stop for want of a login). Started detached, it outlives this
server; `npx openai-oauth stop` stops it.

OpenRouter: OAuth with PKCE, OpenRouter's supported one-click door. No app registration and no secret: this server
makes the verifier, the browser takes the reader to OpenRouter's consent page, OpenRouter sends them back here with a
code, and the code and verifier become a key. The key waits in memory until the reader picks models and saves the
provider (settings, mode 600); it can be revoked on OpenRouter's keys page.
"""
import base64
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

from . import agents, providers
from .store import HOME

BRIDGE = "http://127.0.0.1:10531/v1"
BRIDGE_PACKAGE = "openai-oauth@2"
AUTH_URL = "https://openrouter.ai/auth"
EXCHANGE_URL = "https://openrouter.ai/api/v1/auth/keys"
_OR = {}   # the authorisation under way: verifier, back (where to return), minted (the key, until saved)
_SEEN = {"at": 0.0, "status": None}   # the bridge's last status, asked for again after a few seconds
_START = {"thread": None, "login": None, "error": None}   # a start under way: its sign-in link, what stopped it


def codex_login():
    """Whether Codex has a login openai-oauth can sign in with ($CODEX_HOME, else ~/.codex)."""
    homes = [os.environ.get("CODEX_HOME"), str(Path.home() / ".codex")]
    return any(h and (Path(h) / "auth.json").exists() for h in homes)


def bridge_status(fresh=False, strict=False):
    """Whether the bridge answers, and its models; when it does not, what starting it needs, and of a start under way its
    sign-in link (login) or what stopped it (error). strict: a probe that failed for another reason than nothing
    answering raises (the discovery keeps its last result); a bridge that is not running is not a failure."""
    if fresh or _SEEN["status"] is None or time.time() - _SEEN["at"] >= 5:
        try:
            with urllib.request.urlopen(f"{BRIDGE}/models", timeout=2) as r:
                ids = [m.get("id") for m in json.loads(r.read()).get("data", []) if m.get("id")]
            st = {"running": True, "models": ids}
        except Exception as e:
            if strict and not providers.unreachable(e):
                raise
            npx = shutil.which("npx", path=agents.child_env()["PATH"])
            st = {"running": False, "node": bool(npx), "codexLogin": codex_login()}
        _SEEN.update({"at": time.time(), "status": st})
    st = dict(_SEEN["status"])
    if not st["running"]:
        st.update({k: _START[k] for k in ("login", "error") if _START[k]})
    return st


def bridge_provider(text_only, status=None):
    """The running bridge as a provider found on its own (as a running Ollama is): no key, its text models."""
    st = bridge_status() if status is None else status
    if not st.get("running"):
        return None
    ids = [i for i in st["models"] if not text_only.search(i)]
    return {"key": "chatgpt-bridge", "name": "ChatGPT", "protocol": "openai", "base": BRIDGE, "api_key": "none",
            "source": "bridge", "preset": "chatgpt-bridge", "models": [{"id": i, "name": f"{i} (ChatGPT)"} for i in ids]}


def bridge_start():
    """Start the bridge detached, signing in first when Codex has no login (a browser opens on the sign-in page, its link
    kept in the status too, should no window open). It runs on its own; the caller polls the status, whose error says
    what stopped it (#12)."""
    env = agents.child_env()
    npx = shutil.which("npx", path=env["PATH"])
    if not npx:
        raise RuntimeError("Node.js (npx) was not found on this computer")
    if not (_START["thread"] and _START["thread"].is_alive()):
        _START.update(login=None, error=None)
        _START["thread"] = threading.Thread(target=_start, args=(npx, env), daemon=True)
        _START["thread"].start()
    return bridge_status(fresh=True)


def _start(npx, env):
    HOME.mkdir(parents=True, exist_ok=True)
    path = HOME / "bridge.log"
    since = path.stat().st_size if path.exists() else 0   # what this start writes: an earlier one's lines are not its reason
    run = dict(cwd=tempfile.gettempdir(), env=env, stdin=subprocess.DEVNULL)
    try:
        if not codex_login():   # openai-oauth's own sign-in: it prints the link, and waits for the browser's answer
            p = subprocess.Popen([npx, "-y", BRIDGE_PACKAGE, "login", "--no-open"], stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", **run)
            with open(path, "a", encoding="utf-8") as log:
                for line in p.stdout:
                    log.write(line)
                    log.flush()
                    link = re.search(r"https://\S+", line)
                    if link and not _START["login"]:
                        _START["login"] = link.group(0)
                        webbrowser.open(link.group(0))
            if p.wait():
                raise RuntimeError(_said(path, since) or f"the ChatGPT sign-in stopped (exit {p.returncode})")
            _START["login"] = None
        with open(path, "a", encoding="utf-8") as log:
            p = subprocess.Popen([npx, "-y", BRIDGE_PACKAGE, "--detach"], stdout=log, stderr=log, start_new_session=True, **run)
        try:   # it leaves the bridge running and ends; one that ends with an error says why in the log
            code = p.wait(timeout=180)
        except subprocess.TimeoutExpired:
            return
        if code:
            raise RuntimeError(_said(path, since) or f"the bridge stopped (exit {code})")
    except Exception as e:
        _START.update(login=None, error=str(e)[:400])


def _said(path, since=0):
    """The last lines this start wrote to the bridge's log: what openai-oauth said when it stopped."""
    try:
        with open(path, "rb") as f:
            f.seek(since)
            lines = [l.strip() for l in f.read().decode("utf-8", "replace").splitlines() if l.strip()]
    except OSError:
        return ""
    return " ".join(lines[-3:])[:400]


def _b64(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def openrouter_start(callback, back, desktop=False):
    """desktop: the consent page opens in the system browser, and the app waits for the key (openrouter_minted)."""
    verifier = _b64(secrets.token_bytes(48))
    challenge = _b64(hashlib.sha256(verifier.encode()).digest())
    _OR.clear()
    _OR.update({"verifier": verifier, "back": back or "/", "at": time.time(), "desktop": bool(desktop)})
    q = urllib.parse.urlencode({"callback_url": callback, "code_challenge": challenge, "code_challenge_method": "S256"})
    return f"{AUTH_URL}?{q}"


def openrouter_finish(code):
    """The code OpenRouter sent back, and the verifier kept here, exchanged for a key. Returns (key, error, back)."""
    verifier, back = _OR.pop("verifier", None), _OR.get("back", "/")
    if not code or not verifier:
        return None, "no authorisation was under way", back
    body = json.dumps({"code": code, "code_verifier": verifier, "code_challenge_method": "S256"}).encode()
    req = urllib.request.Request(EXCHANGE_URL, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            key = json.loads(r.read()).get("key")
    except Exception as e:
        return None, str(e)[:200], back
    if not key:
        return None, "no key in the reply", back
    _OR["minted"] = key
    return key, None, back


def minted():
    return _OR.get("minted")


def for_desktop():
    return bool(_OR.get("desktop"))


def take_minted():
    return _OR.pop("minted", None)

