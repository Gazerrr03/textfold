"""The browser's button end to end (extension/, textfold/capture.py): the extension loaded in Playwright's Chromium, pages
served here, TextFold's native host registered in that browser's own profile, five pages sent and read. Nothing here
touches the reader's own browser or library.

    python3 tools/capture_e2e.py <repo> <a scratch folder>     (playwright installed)
"""
import json, os, shutil, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright

REPO, WORK = Path(sys.argv[1]), Path(sys.argv[2])
WORDS = ("The river office kept the gauges for a century, and its records show how the spring floods rose and fell "
         "with the snow on the hills, year after year, in the same slow rhythm the town still lives by. ")
ARTICLE_FULL = "".join(f"<p>Paragraph {k}. {WORDS}</p>" for k in range(1, 7))
PAGES = {
    "/article": lambda cookie: ("<html><head><title>Rivers, for subscribers</title>"
        '<meta property="og:type" content="article"></head><body><nav>Home World</nav><article><h1>Rivers</h1>'
        + (ARTICLE_FULL if "session=reader" in cookie else f"<p>Paragraph 1. {WORDS}</p><div class=paywall>Subscribe to continue reading.</div>")
        + "</article></body></html>"),
    "/drawn": lambda c: ("<html><head><title>Drawn by its script</title></head><body><main id=m></main><script>"
        f"document.getElementById('m').innerHTML = {json.dumps(ARTICLE_FULL)};</script></body></html>"),
    "/shadow": lambda c: ("<html><head><title>In shadow roots</title></head><body><article><h1>Shadows</h1>"
        f"<p>Paragraph 0. {WORDS}</p><open-box></open-box><closed-box></closed-box>"
        '<p>A gauge is read every hour<span class="mark">*</span><span style="display:none">Since the telemetry of 2019.</span>, and the town listens.</p>'
        "</article><script>"
        "customElements.define('open-box', class extends HTMLElement { constructor() { super(); this.attachShadow({mode: 'open'}).innerHTML = "
        f"{json.dumps('<p>Open shadow. ' + WORDS + '</p>')}; }} }});"
        "customElements.define('closed-box', class extends HTMLElement { constructor() { super(); this.attachShadow({mode: 'closed'}).innerHTML = "
        f"{json.dumps('<p>Closed shadow. ' + WORDS + '</p>')}; }} }});"
        "</script></body></html>"),
    "/framed": lambda c: ("<html><head><title>In a frame</title></head><body><article><h1>Framed</h1>"
        f"<p>Paragraph 0. {WORDS}</p><iframe src='/inner' width=600 height=400></iframe></article></body></html>"),
    "/inner": lambda c: f"<html><body><p>Inside the frame. {WORDS}</p><p>The frame again. {WORDS}</p></body></html>",
}

class Pages(BaseHTTPRequestHandler):
    def do_GET(self):
        page = PAGES.get(self.path.split("?")[0])
        body = (page(self.headers.get("Cookie") or "") if page else "no").encode()
        self.send_response(200 if page else 404); self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def log_message(self, *a): pass

srv = ThreadingHTTPServer(("127.0.0.1", 0), Pages); threading.Thread(target=srv.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{srv.server_address[1]}"
ext = WORK / "ext"; shutil.rmtree(ext, ignore_errors=True); shutil.copytree(REPO / "extension", ext)
m = json.loads((ext / "manifest.json").read_text()); m["host_permissions"] = ["http://127.0.0.1/*"]   # (a test's stand-in for the click)
(ext / "manifest.json").write_text(json.dumps(m))
home, data, prof = WORK / "home", WORK / "data", WORK / "profile"
for p in (home, data, prof): shutil.rmtree(p, ignore_errors=True); p.mkdir(parents=True)
os.environ.update(TEXTFOLD_DATA=str(data), PYTHONPATH=str(REPO))
sys.path.insert(0, str(REPO))
from textfold import capture

def send(ctx, sw, path):
    pg = ctx.new_page(); pg.goto(base + path); pg.wait_for_timeout(600); pg.bring_to_front()
    reply = sw.evaluate("async () => { const [tab] = await chrome.tabs.query({active: true, lastFocusedWindow: true}); return await self.capture(tab); }")
    return pg, reply

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(str(prof), channel="chromium", headless=True,
                                               args=[f"--disable-extensions-except={ext}", f"--load-extension={ext}"])
    sw = ctx.service_workers[0] if ctx.service_workers else ctx.wait_for_event("serviceworker")
    ext_id = sw.url.split("/")[2]
    print("extension:", ext_id)
    print("host manifest:", capture.install([ext_id], dirs={"chromium": prof / "NativeMessagingHosts"}, home=home))
    ctx.add_cookies([{"name": "session", "value": "reader", "url": base}])
    results = {}
    for path in ("/article", "/drawn", "/shadow", "/framed"):
        pg, reply = send(ctx, sw, path)
        results[path] = reply
        print(path, "->", reply)
    ctx.clear_cookies()
    pg, reply = send(ctx, sw, "/article?as=visitor")
    results["/article?as=visitor"] = reply; print("/article?as=visitor ->", reply)
    pg, reply = send(ctx, sw, "/article")
    print("/article again ->", reply)
    (data / "server.json").write_text(json.dumps({"format": "textfold/server", "url": base, "pid": os.getpid()}))   # (TextFold running)
    pg, reply = send(ctx, sw, "/drawn?while=running")
    pg.wait_for_timeout(800)
    print("while TextFold runs ->", reply, "| tabs:", [x.url.replace(base, "") for x in ctx.pages][-2:])
    ctx.close()
srv.shutdown()

for path, r in results.items():
    if not r.get("ok"):
        continue
    d = data / "papers" / r["paper"]
    html = (d / "source.html").read_text(encoding="utf-8")
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    import re
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))
    print(f"{path:22} title={meta['title']!r} via={meta['source'].get('via')} kind={meta.get('snapshot_kind')} "
          f"paragraphs={html.count('<p class=\"ltx_p\"')} notes={html.count('ltx_role_footnote')} "
          f"snapshot={'snapshot.html' in os.listdir(d)} | " +
          " ".join(f"{w}:{w in text}" for w in ("Paragraph 6.", "Subscribe to continue", "Open shadow.", "Closed shadow.", "Inside the frame.", "Since the telemetry")))
