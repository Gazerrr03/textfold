"""A documentation directory read as one ordered work, with page snapshots and provenance."""
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from html import escape
from urllib.parse import urljoin, urlsplit, urlunsplit, urldefrag

from bs4 import BeautifulSoup

from . import local, notes, semantic, store, webpage
from .parse import parse
from .tokens import plain

LOCK = threading.RLock()


def canonical(url):
    p = urlsplit(url)
    if p.scheme not in ("http", "https") or not p.netloc:
        raise ValueError("a documentation URL is required")
    return urlunsplit((p.scheme, p.netloc.lower(), p.path or "/", p.query, ""))


def page(url):
    data, final, charset = webpage._get(url)
    soup = BeautifulSoup(data.decode(charset or "utf-8", "replace"), "lxml")
    # Responsive sidebars commonly use "hidden lg:block"; their links still define the directory.
    for el in soup.select("a[href], img[src]"):
        attr = "href" if el.name == "a" else "src"
        el[attr] = urljoin(final, el[attr])
    return soup, canonical(final)


def directory(url):
    soup, final = page(canonical(url))
    p = urlsplit(final)
    parts = p.path.strip("/").split("/")
    # Documentation roots are explicit path segments; other sites use the current directory.
    pos = next((i for i, v in enumerate(parts) if v in ("docs", "doc", "documentation", "guide", "manual")), None)
    rootpath = "/" + "/".join(parts[:pos + 1]) + "/" if pos is not None else p.path.rsplit("/", 1)[0] + "/"
    root = urlunsplit((p.scheme, p.netloc, rootpath, "", ""))
    candidates = soup.select("aside nav, nav, aside")
    def links(nav):
        found = []
        for a in nav.select("a[href]"):
            target = canonical(urljoin(final, a["href"])) if urljoin(final, a["href"]).startswith(("http://", "https://")) else ""
            if target.startswith(root) and target not in [x["url"] for x in found]:
                # Headings of nested sidebar groups remain useful in the chapter directory.
                groups = []
                for parent in a.parents:
                    trigger = nav.find(attrs={"aria-controls": parent["id"]}) if parent.get("id") else None
                    if trigger:
                        groups.append(trigger.get_text(" ", strip=True))
                found.append({"url": target, "title": a.get_text(" ", strip=True) or target,
                              "path": list(reversed(groups))})
        return found
    entries = max((links(n) for n in candidates), key=len, default=[])
    if not entries:
        raise ValueError("No documentation directory found; provide a page with its chapter navigation")
    if final not in [e["url"] for e in entries]:
        entries.insert(0, {"url": final, "title": (soup.title.get_text() if soup.title else final), "path": []})
    return {"root": root, "title": (soup.title.get_text(" ", strip=True).split("—")[-1].strip() if soup.title else p.netloc) + " documentation",
            "chapters": entries}, (final, soup)


def pid_for(root):
    return webpage.pid_of(root)


def manifest(pid):
    f = store.pdir(pid) / "documentation.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def _write(path, value):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def _body(soup, url, title):
    body = soup.select_one("article") or soup.select_one("main")
    if body is None or not body.get_text(" ", strip=True):
        raise ValueError("No readable article on this chapter page")
    for el in body.select("nav, aside, script, style, button"):
        el.decompose()
    headings = body.find_all(re.compile("^h[1-6]$"))
    # Keep the site's own title as the chapter heading, with its original subsection ranks.
    if headings and headings[0].name == "h1":
        title = headings[0].get_text(" ", strip=True)
        headings[0].decompose()
    return f'<h1>{escape(title)}</h1><p><a href="{escape(url, quote=True)}">{escape(url)}</a></p>{body}', title


def import_set(url="", pid="", mode="import", progress=lambda *args: None, stop=None):
    """Import, explicitly update, or fetch only failed pages. Successful snapshots survive retry failures."""
    with LOCK:
        if mode == 'import':
            requested = canonical(url)
            for f in (store.DATA / 'papers').glob('*/documentation.json'):
                existing = json.loads(f.read_text(encoding='utf-8'))
                if requested == existing['root'] or any(requested in (c['url'], c.get('final_url')) for c in existing['chapters']):
                    return {'paper': f.parent.name, 'reused': True, 'readable': (f.parent / 'source.html').exists(),
                            'documentation': existing}
        old = manifest(pid) if pid else None
        if mode == "retry":
            if not old:
                raise ValueError("No documentation set to retry")
            plan, first = old, None
        else:
            plan, first = directory(url or (old or {})["root"])
            pid = pid or pid_for(plan["root"])
            old = manifest(pid)
            if old and mode == "import":
                return {"paper": pid, "reused": True, "readable": (store.pdir(pid) / 'source.html').exists(), "documentation": old}
        d = store.pdir(pid)
        d.mkdir(parents=True, exist_ok=True)
        snapshots = d / "pages"
        snapshots.mkdir(exist_ok=True)
        previous = {c["url"]: c for c in (old or {}).get("chapters", [])}
        chapters = []
        next_id = max([int(c["id"].split("-")[-1]) for c in previous.values()] + [0])
        for entry in plan["chapters"]:
            prev = previous.get(entry["url"], {})
            if not prev:
                next_id += 1
            chapter = {**entry, "id": prev.get("id") or f"page-{next_id}", "status": prev.get("status", "pending")}
            chapters.append(chapter)
        selected = [c for c in chapters if mode != "retry" or c["status"] != "ready"]
        def read(c):
            if stop is not None and stop.is_set():
                from .llm import Stopped
                raise Stopped()
            try:
                soup, final = (first[1], first[0]) if first and c["url"] == first[0] else page(c["url"])
                html, title = _body(soup, final, c["title"])
                # Absolute source links have already been resolved by page().
                (snapshots / (c["id"] + ".html")).write_text(html, encoding="utf-8")
                c.update(status="ready", title=title, final_url=final, error="")
            except Exception as e:
                c.update(status="failed", error=str(e), retained=(snapshots / (c["id"] + ".html")).exists())
            return c
        with ThreadPoolExecutor(max_workers=6) as pool:
            for n, _ in enumerate(pool.map(read, selected), 1):
                progress("fetch", n, len(selected))
        if not any((snapshots / (c["id"] + ".html")).exists() for c in chapters):
            result = {**plan, "chapters": chapters}
            _write(d / "documentation.json", result)
            return {"paper": pid, "readable": False, "reused": False, "documentation": result}
        olddoc = store.parsed(pid) if (d / "source.html").exists() else None
        images = local.Images(d / "img", None)
        combined = BeautifulSoup('<article class="ltx_document"></article>', 'lxml')
        groups, origins, targets = {}, {}, {}
        # Normalize each chapter separately to keep its heading hierarchy and page-local anchor ids.
        for c in chapters:
            f = snapshots / (c["id"] + ".html")
            if not f.exists():
                continue
            raw = BeautifulSoup(f.read_text(encoding="utf-8"), "lxml")
            normalized = BeautifulSoup(semantic.normalize(str(raw), resolve_img=images.resolve), "lxml")
            headings = normalized.select('section[id] > .ltx_title')
            source_headings = raw.find_all(re.compile('^h[1-6]$'))
            for before in source_headings:
                match = next((h for h in headings if h.get_text(' ', strip=True) == before.get_text(' ', strip=True)), None)
                if match and before.get('id'):
                    targets[c['url'] + '#' + before['id']] = c['id'] + '-' + match.parent['id']
            if headings:
                targets[c['url']] = c['id'] + '-' + headings[0].parent['id']
            for el in normalized.select("[id]"):
                before = el["id"]
                el["id"] = c["id"] + "-" + before
                origins[el["id"]] = c["url"]
            for a in normalized.select('a[href^="#"]'):
                a["href"] = "#" + c["id"] + "-" + a["href"][1:]
            parent = combined.article
            path = c.get('path', [])
            for depth, label in enumerate(path):
                key = tuple(path[:depth + 1])
                if key not in groups:
                    sid = 'group-' + '-'.join(semantic.slug(s) for s in key)
                    section = combined.new_tag('section', attrs={'class': semantic.SECTION_CLASS[min(depth, 3)], 'id': sid})
                    heading = combined.new_tag('h' + str(min(depth + 2, 6)), attrs={'class': 'ltx_title ltx_title_section'})
                    heading.string = label
                    section.append(heading)
                    parent.append(section)
                    groups[key] = section
                parent = groups[key]
            if path:
                for section in normalized.select('section'):
                    heading = section.find(re.compile('^h[1-6]$'), recursive=False)
                    if heading:
                        depth = min(int(heading.name[1]) - 2 + len(path), 3)
                        section['class'] = semantic.SECTION_CLASS[depth]
                        heading.name = 'h' + str(depth + 2)
            for child in list(normalized.article.contents):
                parent.append(child.extract())
        for a in combined.select('a[href]'):
            if a['href'] in targets and a.get_text(strip=True) != urldefrag(a['href'])[0]:
                a['href'] = '#' + targets[a['href']]
        html = str(combined.article)
        meta = {"id": pid, "title": plan["title"], "authors": [], "date": "", "version": "", "abs_url": plan["root"], "html_url": "",
                "source": {"kind": "web", "site": urlsplit(plan["root"]).netloc, "url": plan["root"]},
                "reading_mode": "original", "chapter_sources": origins, "snapshot": time.strftime('%Y-%m-%d'),
                "label": urlsplit(plan["root"]).netloc + ' docs'}
        newdoc = parse(html, meta)
        unresolved = []
        with notes._LOCK:
            if olddoc:
                data = notes.read(pid)
                targets = {}
                for u in newdoc['units']:
                    targets.setdefault((source_of(newdoc, u), text_of(newdoc, u)), []).append(u)
                moved = {u: targets.get((source_of(olddoc, u), text_of(olddoc, u)), []) for u in olddoc['units']}
                for note in data["notes"]:
                    if recite(note, olddoc, targets, moved):
                        unresolved.append(note['id'])
                    a = note["anchor"]
                    uid = a.get("unit")
                    if not uid and not a.get('unresolved'):
                        section = a.get('section')
                        if section and not any(c['id'] == section for c in newdoc['chunks']):
                            a.update(section=None, unresolved=True, original_section=section,
                                     source_url=olddoc['meta'].get('chapter_sources', {}).get(section, ''))
                            unresolved.append(note['id'])
                        continue
                    source = a.get('source_url') or source_of(olddoc, uid)
                    exact = a.get("quote", {}).get("exact", "")
                    original = a.get('original_text') if a.get('unresolved') else text_of(olddoc, uid)
                    matches = targets.get((source, original), [])
                    hit = None
                    if len(matches) != 1 and exact:
                        hit = quote_hit(newdoc, source, a['quote'])
                        matches = [hit[0]] if hit else []
                    if len(matches) == 1:
                        target = matches[0]
                        a.update(unit=target, section=newdoc["units"][target]["chunk"], source_url=source)
                        if text_of(newdoc, target) != original:
                            a.update(quote_offsets(newdoc, target, exact, hit[1]))
                        a.pop("unresolved", None)
                        a.pop('original_text', None)
                    else:
                        a.update(unit=None, section=None, unresolved=True, source_url=source,
                                 original_unit=a.get('original_unit', uid), original_text=original)
                        unresolved.append(note["id"])
                notes._write(pid, data)
                # A changed source invalidates token/atom offsets, just as a Markdown replacement does.
                if (d / "source.html").read_text(encoding="utf-8") != html:
                    import shutil
                    previous = d / "previous"
                    previous.mkdir(exist_ok=True)
                    if (d / "layers").exists():
                        shutil.rmtree(previous / "layers", ignore_errors=True)
                        (d / "layers").rename(previous / "layers")
            (d / "source.html").write_text(html, encoding="utf-8")
            _write(d / "meta.json", meta)
            result = {**plan, "chapters": chapters, "updated": store.stamp(), "unresolved_annotations": list(dict.fromkeys(unresolved))}
            _write(d / "documentation.json", result)
        return {"paper": pid, "readable": True, "reused": False, "documentation": result}


def source_of(doc, uid):
    chunk = doc["units"].get(uid, {}).get("chunk", "")
    return doc["meta"].get("chapter_sources", {}).get(chunk, "")


def reader_document(doc, chapter=''):
    """Keep one ordered library work while limiting the live zoom scene to its active source chapter."""
    state = manifest(doc['meta']['id'])
    if not state:
        return doc
    chapters = [{**c, 'available': (store.pdir(doc['meta']['id']) / 'pages' / (c['id'] + '.html')).exists()} for c in state['chapters']]
    available = [c for c in chapters if c['available']]
    chosen = next((c for c in available if c['id'] == chapter), None) or available[0]
    url = chosen['url']
    chunks = [c for c in doc['chunks'] if doc['meta']['chapter_sources'].get(c['id']) == url]
    base_level = min(c['level'] for c in chunks)
    chunks = [{**c, 'level': c['level'] - base_level + 2} for c in chunks]
    cids = {c['id'] for c in chunks}
    units = {u: v for u, v in doc['units'].items() if v['chunk'] in cids}
    page_for = {c['url']: c['id'] for c in chapters}
    meta = {**doc['meta'], 'active_chapter': chosen['id'], 'documentation_chapters': chapters,
            'document_unit_chapters': {u: page_for.get(source_of(doc, u)) for u in doc['units']}}
    return {**doc, 'meta': meta, 'chunks': chunks, 'units': units,
            'blocks': [b for b in doc['blocks'] if b.get('chunk') in cids],
            'edges': [e for e in doc['edges'] if e['f'] in units and (e['tk'] != 'unit' or e['t'] in units)]}


def text_of(doc, uid):
    return plain(doc["units"].get(uid, {}).get("toks", []), doc["atoms"])


def recite(note, olddoc, targets, moved):
    """Keep answer references on their source paragraphs; a missing source uses the reader's bad-cite marker."""
    unresolved = False
    for turn in notes.turns(note):
        retained = {c['id']: c for c in turn.get('unresolved_cites', [])}
        missing = {}
        def move(uid):
            if uid in retained:
                identity = retained[uid]
                matches = targets.get((identity['source_url'], identity['text']), [])
            elif uid in moved:
                identity = {'id': '!' + uid, 'source_url': source_of(olddoc, uid), 'text': text_of(olddoc, uid)}
                matches = moved[uid]
            else:
                return uid   # inference and already-invalid model citations keep their existing meaning
            if len(matches) == 1:
                return matches[0]
            missing[identity['id']] = identity
            return identity['id']
        if turn.get('cites'):
            turn['cites'] = list(dict.fromkeys(move(c) for c in turn['cites']))
        if turn.get('a'):
            turn['a'] = notes.CITE.sub(lambda m: '[[' + move(m.group(1)) + ']]', turn['a'])
        if missing:
            turn['unresolved_cites'] = list(missing.values())
            unresolved = True
        else:
            turn.pop('unresolved_cites', None)
    return unresolved


def quote_hit(doc, source, quote):
    """Find an occurrence, not just a paragraph. Repeated words need a uniquely fitting saved context."""
    exact, pre, suf = quote['exact'], quote.get('prefix', ''), quote.get('suffix', '')
    hits = []
    for uid in doc['units']:
        if source_of(doc, uid) != source:
            continue
        text = text_of(doc, uid)
        at = text.find(exact)
        while at >= 0:
            end = at + len(exact)
            fit = notes._common(text[:at][::-1], pre[::-1]) + notes._common(text[end:], suf)
            hits.append((fit, uid, at))
            at = text.find(exact, at + 1)
    if len(hits) == 1:
        return hits[0][1:]
    hits.sort(reverse=True)
    if len(hits) > 1 and hits[0][0] >= notes.FIT and hits[0][0] > hits[1][0]:
        return hits[0][1:]
    return None


def quote_offsets(doc, uid, exact, at):
    """A retained source quote's new token and sentence ranges, for the existing highlight renderer."""
    unit = doc['units'][uid]
    if not exact or at < 0:
        return {'tokens': None, 'sents': []}
    cursor, selected = 0, []
    for i, token in enumerate(unit['toks']):
        end = cursor + len(plain([token], doc['atoms']))
        if cursor < at + len(exact) and end > at:
            selected.append(i)
        cursor = end + (1 if token.get('s') else 0)
    if not selected:
        return {'tokens': None, 'sents': []}
    start, end = selected[0], selected[-1]
    return {'tokens': [start, end], 'sents': [i for i, (a, b) in enumerate(unit['sents']) if a <= end and b > start]}
