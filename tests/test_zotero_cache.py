"""textfold/zotero.py, and the server's /api/zotero routes, against a fake Zotero local API.

Nothing here reaches the reader's own Zotero, settings or library: the settings and the data folder are temporary, the
fake answers on a free port of this computer, and the server run here looks for no model (TEXTFOLD_NO_MODELS).

Run from the repo root:
    python3 -m unittest discover tests
"""
from contextlib import closing
import json
import os
import shutil
import site
import sqlite3
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from textfold import engine, models, pdfdoc, store, zotero, zotero_cache

ROOT = Path(__file__).resolve().parents[1]
from tests.test_pdftext import typeset
PDF = typeset([(12, "A physical PDF page for the cache import fixture.")])
SNAPSHOT = ("<!doctype html><html><head><title>Snapshot 2024</title></head><body><article><h1>Snapshot 2024</h1>"
            "<p>The first paragraph of a page Zotero saved, long enough to be read as the article it is.</p>"
            "<h2>Its method</h2><p>A second paragraph, under a heading of its own, so the page has a shape.</p></article></body></html>")


def item(key, title, **data):
    links, kind, kids = data.pop("links", {}), data.pop("itemType", "journalArticle"), data.pop("children", None)
    return {"key": key, "data": {"key": key, "itemType": kind, "title": title,
                                 "creators": [{"creatorType": "author", "lastName": "Lovelace", "firstName": "Ada"}], **data},
            "meta": {"parsedDate": "2024-05-01", **({"numChildren": kids} if kids else {})}, "links": links}


def key_of(n):
    """The n-th key of a made-up library, in Zotero's alphabet."""
    alphabet, out = "23456789ABCDEFGHIJKLMNPQRSTUVWXYZ", ""
    for _ in range(5):
        out, n = alphabet[n % 33] + out, n // 33
    return "GRP" + out


def attachment(key, ctype, mode, **data):
    return {"key": key, "data": {"key": key, "itemType": "attachment", "contentType": ctype, "linkMode": mode, **data}}


class Fake:
    """A Zotero library: its items, their attachments, the files Zotero says are theirs."""

    def __init__(self, files):
        self.off = False
        self.items = {
            "ARXVKEY2": item("ARXVKEY2", "Chain of thought", url="https://arxiv.org/abs/2201.11903", extra="Citation Key: wei2022"),
            "HTMLKEY2": item("HTMLKEY2", "A saved page", itemType="webpage",
                             links={"attachment": {"attachmentType": "text/html"}}),
            "PDFSKEY2": item("PDFSKEY2", "A paper with its PDF", DOI="10.1234/abcd",
                             links={"attachment": {"attachmentType": "application/pdf"}}),
            "PLNPKEY2": item("PLNPKEY2", "A PDF and nothing else", children=1),   # (no best attachment named: its children say)
            "FAKEPDF2": item("FAKEPDF2", "Not a PDF inside"),
            "DIGIKEY2": item("DIGIKEY2", "Only a DOI", DOI="10.5555/only"),
            "NTHGKEY2": item("NTHGKEY2", "Nothing to read"),
            "TRAVKEY2": item("TRAVKEY2", "A file name that climbs out"),
        }
        self.children = {
            "HTMLKEY2": [attachment("ATTHTML2", "text/html", "imported_url", filename="snap.html")],
            "PDFSKEY2": [attachment("ATTPDFS2", "application/pdf", "imported_file", filename="paper.pdf")],
            "PLNPKEY2": [attachment("ATTPLNP2", "application/pdf", "imported_file", filename="plain.pdf")],
            "FAKEPDF2": [attachment("ATTFAKE2", "application/pdf", "imported_file", filename="fake.pdf")],
            "TRAVKEY2": [attachment("ATTTRAV2", "application/pdf", "imported_file", filename="../../secret.pdf")],
        }
        self.group = {key_of(n): item(key_of(n), f"Group item {n}") for n in range(230)}
        self.group["LINKKEY2"] = item("LINKKEY2", "A linked file in a group")
        self.group_children = {"LINKKEY2": [attachment("ATTLINK2", "application/pdf", "linked_file", path=str(files["outside"]))]}
        self.collections = [{"key": "SUBCKEY2", "data": {"name": "methods", "parentCollection": "TPCLKEY2"}, "meta": {"numItems": 1}},
                            {"key": "TPCLKEY2", "data": {"name": "Reading", "parentCollection": False}, "meta": {"numItems": 2}}]
        self.in_collection = {"TPCLKEY2": ["ARXVKEY2", "HTMLKEY2"], "SUBCKEY2": ["PDFSKEY2"]}
        self.files = {"ATTHTML2": files["snapshot"], "ATTFAKE2": files["fake"]}   # what file/view/url answers (ATTPDFS2: not)

    def answer(self, path, params):
        if path == "users/0/groups":
            return [{"id": 42, "data": {"name": "Lab"}, "meta": {"numItems": len(self.group)}}]
        items, children = (self.items, self.children) if path.startswith("users/0") else (self.group, self.group_children)
        if path.endswith("/collections") and path.count("/") == 2:
            return self.collections if path.startswith("users/0") else []
        parts = path.split("/")
        if len(parts) == 6 and parts[2] == "collections" and parts[4:] == ["items", "top"]:
            return [items[k] for k in self.in_collection.get(parts[3], [])]
        if parts[2:] == ["items", "top"]:
            q = params.get("q", "").lower()
            return [i for i in items.values() if q in i["data"]["title"].lower()]
        if len(parts) == 5 and parts[2] == "items" and parts[4] == "children":
            return children.get(parts[3], [])
        if len(parts) == 4 and parts[2] == "items":
            return items.get(parts[3])
        return None


def serve_fake(fake):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            u = urllib.parse.urlparse(self.path)
            params = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
            path = u.path[len("/api/"):]
            if fake.off:
                return self.reply(403, b"Local API is not enabled", "text/plain")
            if path.endswith("/file/view/url"):
                f = fake.files.get(path.split("/")[3])
                return self.reply(200, f.as_uri().encode(), "text/plain") if f else self.reply(404, b"Not found", "text/plain")
            body = fake.answer(path, params)
            if body is None:
                return self.reply(404, b"Not found", "text/plain")
            total = len(body) if isinstance(body, list) else 1
            if isinstance(body, list):
                start, limit = int(params.get("start", 0)), int(params.get("limit", 25))
                body = body[start:start + limit]
            self.reply(200, json.dumps(body).encode(), "application/json", total)

        def reply(self, code, data, ctype, total=None):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            if total is not None:
                self.send_header("Total-Results", str(total))
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Setup(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="tf-zotero-"))
        zdata = cls.tmp / "zotero-data"
        (zdata / "storage" / "ATTPDFS2").mkdir(parents=True)
        (zdata / "storage" / "ATTPDFS2" / "paper.pdf").write_bytes(PDF)
        (zdata / "storage" / "ATTPLNP2").mkdir(parents=True)
        (zdata / "storage" / "ATTPLNP2" / "plain.pdf").write_bytes(PDF + b"%plain\n")
        (cls.tmp / "secret.pdf").write_bytes(PDF)   # what "../../secret.pdf" would reach from storage/<key>/
        files = {"snapshot": cls.tmp / "snap.html", "fake": cls.tmp / "fake.pdf", "outside": cls.tmp / "outside.pdf"}
        files["snapshot"].write_text(SNAPSHOT, encoding="utf-8")
        files["fake"].write_bytes(b"#!/bin/sh\necho not a pdf\n")
        files["outside"].write_bytes(PDF)
        cls.fake = Fake(files)
        cls.srv = serve_fake(cls.fake)
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        cls.home = cls.tmp / "home"
        (cls.home / ".textfold").mkdir(parents=True)
        cls.settings = {"use_thoughtdag_env": False, "zotero": {"base": cls.base, "data_dir": str(zdata)}}
        (cls.home / ".textfold" / "settings.json").write_text(json.dumps(cls.settings), encoding="utf-8")
        cls.data = cls.tmp / "data"
        (cls.data / "papers").mkdir(parents=True)
        # this process's settings and library, the temporary ones
        cls.saved = (models.SETTINGS, models.OLD_HOMES, store.DATA)
        models.SETTINGS, models.OLD_HOMES, store.DATA = cls.home / ".textfold" / "settings.json", (), cls.data

    @classmethod
    def tearDownClass(cls):
        models.SETTINGS, models.OLD_HOMES, store.DATA = cls.saved
        cls.srv.shutdown()
        shutil.rmtree(cls.tmp, ignore_errors=True)


def cached_pdf(data, parent='PDFSKEY2', attachment='ATTPDFS2', ident=123, library=1):
    from PIL import Image
    with closing(sqlite3.connect(data / 'zotero.sqlite')) as db, db:
        db.executescript('CREATE TABLE IF NOT EXISTS libraries(libraryID INTEGER, type TEXT);'
                         'CREATE TABLE IF NOT EXISTS groups(libraryID INTEGER, groupID INTEGER);'
                         'CREATE TABLE IF NOT EXISTS items(itemID INTEGER, libraryID INTEGER, key TEXT);')
        db.execute('INSERT INTO libraries VALUES (?,?)', (library, 'user' if library == 1 else 'group'))
        db.execute('INSERT INTO items VALUES (?,?,?)', (ident, library, attachment))
    folder = data / 'llm-for-zotero-mineru' / str(ident)
    (folder / 'images').mkdir(parents=True, exist_ok=True)
    Image.new('RGB', (30, 20), 'blue').save(folder / 'images/fig.png')
    (folder / '_llm_source.json').write_text(json.dumps({'attachmentId': ident, 'attachmentKey': attachment, 'parentItemKey': parent}))
    (folder / 'full.md').write_text('# Cached paper\n\nOriginal words.')
    blocks = [
        {'type': 'text', 'text': '1 Introduction', 'text_level': 1, 'bbox': [100, 100, 900, 150], 'page_idx': 0},
        {'type': 'text', 'text': 'These are the original cached words and the method used to measure the turbulent velocity field.', 'bbox': [100, 160, 900, 300], 'page_idx': 0},
        {'type': 'equation', 'text': '$$E = mc^2$$', 'bbox': [200, 310, 800, 350], 'page_idx': 0},
        {'type': 'image', 'img_path': 'images/fig.png', 'image_caption': ['Figure 1. Measured field $u^2$.'], 'bbox': [100, 100, 900, 500], 'page_idx': 1},
        {'type': 'table', 'table_body': '<table><tr><td>42</td></tr></table>', 'table_caption': ['Table 1. Values.'], 'bbox': [100, 600, 900, 800], 'page_idx': 1},
    ]
    (folder / 'content_list.json').write_text(json.dumps(blocks))
    return folder


class CacheTest(Setup):
    def setUp(self):
        (self.data / 'zotero.json').unlink(missing_ok=True)

    def test_cache_appears_then_imports_without_parsing_and_survives_cache_loss(self):
        data = self.tmp / 'zotero-data'
        self.assertEqual(zotero.read('users/0', 'PDFSKEY2', cached=True)['needs'], 'zotero-cache')
        cache = cached_pdf(data)
        try:
            with patch.object(engine, 'convert', side_effect=AssertionError('must not parse')), patch.object(engine, 'crop', side_effect=AssertionError('must not use engine')):
                got = zotero.read('users/0', 'PDFSKEY2', cached=True)
            d = store.pdir(got['paper'])
            html = (d / 'source.html').read_text()
            self.assertIn('original cached words', html)
            self.assertIn('<math', html)
            self.assertIn('<img', html)
            self.assertIn('<table', html)
            self.assertNotIn('$u^2$', html)
            self.assertEqual((d / 'source.pdf').read_bytes(), PDF)
            self.assertEqual(json.loads((d / 'layout.json').read_text())[0]['b'], [.1, .1, .9, .15])
            self.assertTrue(any(p['page'] == 2 for p in pdfdoc.place(got['paper']).values()))
            (d / 'notes.json').write_text('{"keep":true}')
            shutil.rmtree(cache)
            self.assertEqual(zotero.read('users/0', 'PDFSKEY2', cached=True)['paper'], got['paper'])
            self.assertEqual((d / 'notes.json').read_text(), '{"keep":true}')
        finally:
            shutil.rmtree(data / 'llm-for-zotero-mineru', ignore_errors=True)
            (data / 'zotero.sqlite').unlink(missing_ok=True)

    def test_existing_reading_copy_is_reported_as_reused(self):
        data = self.tmp / 'zotero-data'
        cache = cached_pdf(data)
        try:
            got = zotero.read('users/0', 'PDFSKEY2', cached=True)
            # An upstream import may already own this PDF's reading copy, without attachment bookkeeping.
            (self.data / 'zotero.json').unlink()
            again = zotero.read('users/0', 'PDFSKEY2', cached=True)
            self.assertEqual(again['paper'], got['paper'])
            self.assertTrue(again['reused'])
        finally:
            shutil.rmtree(data / 'llm-for-zotero-mineru', ignore_errors=True)
            (data / 'zotero.sqlite').unlink(missing_ok=True)

    def test_missing_image_is_rendered_from_selected_pdf_without_writing_the_cache(self):
        data = self.tmp / 'zotero-data'
        cache = cached_pdf(data)
        try:
            (cache / 'images/fig.png').unlink()
            def render(pdf, crops):
                from PIL import Image
                self.assertEqual(pdf, data / 'storage/ATTPDFS2/paper.pdf')
                for page, box, target in crops:
                    self.assertEqual((page, box), (2, [.1, .1, .9, .5]))
                    Image.new('RGB', (40, 30)).save(target)
                return {str(c[2]) for c in crops}
            with tempfile.TemporaryDirectory() as tmp, patch.object(engine, 'crop_here', side_effect=render) as crop:
                sc = zotero_cache.structured(json.loads((cache / 'content_list.json').read_text()), cache, Path(tmp),
                                            data / 'storage/ATTPDFS2/paper.pdf', 'Paper')
                self.assertTrue((Path(tmp) / sc['pages'][1]['blocks'][0]['image_source']).exists())
                crop.assert_called_once()
            self.assertEqual(list((cache / 'images').iterdir()), [])
        finally:
            shutil.rmtree(data / 'llm-for-zotero-mineru', ignore_errors=True)
            (data / 'zotero.sqlite').unlink(missing_ok=True)

    def test_multiple_pdfs_remember_choice_and_switch_during_wait(self):
        self.fake.children['ARXVKEY2'] = self.fake.children['PDFSKEY2'] + self.fake.children['PLNPKEY2']
        try:
            got = zotero.read('users/0', 'ARXVKEY2', cached=True)
            self.assertEqual(got['needs'], 'attachment')   # PDF selection precedes arXiv
            got = zotero.read('users/0', 'ARXVKEY2', 'ATTPLNP2')
            self.assertEqual((got['needs'], got['attachment']), ('zotero-cache', 'ATTPLNP2'))
            self.assertEqual(zotero.read('users/0', 'ARXVKEY2', cached=True)['attachment'], 'ATTPLNP2')
            self.assertEqual(zotero.read('users/0', 'ARXVKEY2', select=True)['selected'], 'ATTPLNP2')
            old = self.data / 'papers/pdf-0123456789abcdef'
            old.mkdir(exist_ok=True)
            (old / 'source.html').write_text('Previously imported PDF')
            zotero.link('users/0', 'ARXVKEY2', old.name, 'Old', {'attachment': 'ATTPLNP2'})
            self.assertEqual(zotero.read('users/0', 'ARXVKEY2', 'ATTPDFS2')['attachment'], 'ATTPDFS2')
            switched = zotero.read('users/0', 'ARXVKEY2', cached=True)
            self.assertEqual(switched['needs'], 'zotero-cache')
            self.assertNotIn('paper', switched)
            self.assertEqual((old / 'source.html').read_text(), 'Previously imported PDF')
            with self.assertRaisesRegex(ValueError, 'bad-attachment'):
                zotero.read('users/0', 'ARXVKEY2', 'ATTHTML2')
        finally:
            del self.fake.children['ARXVKEY2']

    def test_library_identity_and_partially_written_output(self):
        data = self.tmp / 'zotero-data'
        file = data / 'storage/ATTPDFS2/paper.pdf'
        cache = cached_pdf(data, library=2)
        try:
            self.assertIsNone(zotero_cache.find('users/0', 'PDFSKEY2', 'ATTPDFS2', file, data))
            with closing(sqlite3.connect(data / 'zotero.sqlite')) as db, db:
                db.execute('INSERT INTO groups VALUES (2,42)')
            self.assertIsNotNone(zotero_cache.find('groups/42', 'PDFSKEY2', 'ATTPDFS2', file, data))
            (cache / 'content_list.json').write_text('[{')
            self.assertIsNone(zotero_cache.find('groups/42', 'PDFSKEY2', 'ATTPDFS2', file, data))
        finally:
            shutil.rmtree(data / 'llm-for-zotero-mineru', ignore_errors=True)
            (data / 'zotero.sqlite').unlink(missing_ok=True)

    def test_existing_numeric_cache_without_provenance_uses_database_attachment_and_parent(self):
        data = self.tmp / 'zotero-data'
        file = data / 'storage/ATTPDFS2/paper.pdf'
        cache = cached_pdf(data)
        try:
            with closing(sqlite3.connect(data / 'zotero.sqlite')) as db, db:
                db.execute('CREATE TABLE itemAttachments(itemID INTEGER, parentItemID INTEGER)')
                db.execute('INSERT INTO items VALUES (124,1,?)', ('PDFSKEY2',))
                db.execute('INSERT INTO itemAttachments VALUES (123,124)')
            (cache / '_llm_source.json').unlink()
            self.assertIsNotNone(zotero_cache.find('users/0', 'PDFSKEY2', 'ATTPDFS2', file, data))
            self.assertIsNone(zotero_cache.find('users/0', 'WRONGKEY', 'ATTPDFS2', file, data))
            self.assertIsNone(zotero_cache.find('groups/42', 'PDFSKEY2', 'ATTPDFS2', file, data))
            (cache / '_llm_source.json').write_text(json.dumps({'attachmentId': 123, 'attachmentKey': 'OTHERKEY', 'parentItemKey': 'PDFSKEY2'}))
            self.assertIsNone(zotero_cache.find('users/0', 'PDFSKEY2', 'ATTPDFS2', file, data))
        finally:
            shutil.rmtree(data / 'llm-for-zotero-mineru', ignore_errors=True)
            (data / 'zotero.sqlite').unlink(missing_ok=True)

    def test_original_mineru_content_list_filename_is_read(self):
        data = self.tmp / 'zotero-data'
        file = data / 'storage/ATTPDFS2/paper.pdf'
        cache = cached_pdf(data)
        try:
            (cache / 'content_list.json').rename(cache / 'original-job_content_list.json')
            found = zotero_cache.find('users/0', 'PDFSKEY2', 'ATTPDFS2', file, data)
            self.assertIsNotNone(found)
            self.assertTrue(found[1])
        finally:
            shutil.rmtree(data / 'llm-for-zotero-mineru', ignore_errors=True)
            (data / 'zotero.sqlite').unlink(missing_ok=True)

    def test_finalized_markdown_cache_without_content_list_imports_without_parser(self):
        data = self.tmp / 'zotero-data'
        cache = cached_pdf(data)
        try:
            (cache / 'content_list.json').unlink()
            (cache / 'manifest.json').write_text(json.dumps({'sections': [], 'totalPages': 2}))
            (cache / 'full.md').write_text('# Finalized paper\n\nOriginal finalized words.\n\n![A figure](images/fig.png)')
            pending = cache / '_llm_write_pending.json'
            pending.write_text('{}')
            file = data / 'storage/ATTPDFS2/paper.pdf'
            self.assertIsNone(zotero_cache.find('users/0', 'PDFSKEY2', 'ATTPDFS2', file, data))
            pending.unlink()
            with patch.object(store, 'DATA', self.tmp / 'finalized-import'), \
                 patch.object(engine, 'crop_here') as crop, patch.object(engine, 'convert') as parse:
                got = zotero.read('users/0', 'PDFSKEY2', cached=True)
                self.assertIn('paper', got)
                html = (store.pdir(got['paper']) / 'source.html').read_text()
                self.assertIn('Original finalized words', html)
                self.assertIn('<img', html)
                self.assertTrue((store.pdir(got['paper']) / 'source.pdf').is_file())
                crop.assert_not_called()
                parse.assert_not_called()
        finally:
            shutil.rmtree(data / 'llm-for-zotero-mineru', ignore_errors=True)
            (data / 'zotero.sqlite').unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
