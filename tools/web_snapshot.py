"""A page rendered by a browser and serialized as its reader sees it (web-snapshot.js): shadow roots spelled out, what the
browser does not show marked, each iframe's own page put in its place. Into <out>/<name>/rendered2.html.

    python3 tools/web_snapshot.py <name> <url> <out>     (with playwright installed)
"""
import json, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
name, url, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
JS = (Path(__file__).parent / "web-snapshot.js").read_text()
d = out / name; d.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1280, "height": 900}, locale="en-US")
    pg = ctx.new_page()
    pg.goto(url, wait_until="domcontentloaded", timeout=45000)
    try:
        pg.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass
    h = 0
    for _ in range(40):
        pg.mouse.wheel(0, 1600); pg.wait_for_timeout(250)
        nh = pg.evaluate("document.documentElement.scrollHeight")
        if pg.evaluate("window.scrollY + innerHeight") >= nh - 5 and nh == h:
            break
        h = nh
    pg.wait_for_timeout(1500)
    html = pg.evaluate(JS)
    frames = {}
    for f in pg.main_frame.child_frames:
        try:
            k = f.frame_element().get_attribute("data-tf-frame")
            inner = f.evaluate(JS)
            m = re.search(r"<body[^>]*>(.*)</body>", inner, re.S)
            frames[k] = (f.url, m.group(1) if m else "")
        except Exception as e:
            frames[k if 'k' in dir() else '?'] = (f.url, f"<!-- frame not read: {type(e).__name__} -->")
    html = re.sub(r"<!--TF-FRAME-(\d+)-->", lambda m: frames.get(m.group(1), ("", ""))[1], html)
    (d / "rendered2.html").write_text(html, encoding="utf-8")
    print(name, len(html), "frames:", [(k, u[:60], len(v)) for k, (u, v) in frames.items()],
          "hidden marked:", html.count("data-tf-css-hidden"), "shadow roots:", html.count("data-tf-shadow"))
    b.close()
