"""Document contracts and local I/O regressions; all libraries are disposable."""
import copy
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from textfold import local, notes, store
from textfold.documents import ConflictError, Document, LibraryState, Source
from textfold.storage import DocumentStore, LocalDirectoryBackend, document_info


class MemoryBackend:
    def __init__(self):
        self.documents, self.clock = {}, 0
        self.state = LibraryState()

    def get(self, identity):
        try: return copy.deepcopy(self.documents[identity])
        except KeyError: raise FileNotFoundError(identity) from None

    def info(self, identity):
        return document_info(self.get(identity))

    def list(self):
        return [document_info(doc) for doc in self.documents.values()]

    def save(self, doc):
        old = self.documents.get(doc.id)
        if doc.revision != (old.revision if old else None): raise ConflictError(doc.id)
        self.clock += 1
        doc.revision, doc.created, doc.updated = self.clock, (old.created if old else time.time()), time.time()
        self.documents[doc.id] = copy.deepcopy(doc)

    def delete(self, identity):
        self.get(identity)
        del self.documents[identity]

    def get_library(self):
        return copy.deepcopy(self.state)

    def save_library(self, state):
        if state.revision != self.state.revision: raise ConflictError('library')
        self.clock += 1
        state.revision = self.clock
        self.state = copy.deepcopy(state)


class DocumentContract(unittest.TestCase):
    def test_detached_documents_roundtrip_unknown_assets_and_reject_stale_edits(self):
        with tempfile.TemporaryDirectory() as root:
            for backend in (LocalDirectoryBackend(root), MemoryBackend()):
                with self.subTest(backend=type(backend).__name__):
                    repo = DocumentStore(backend)
                    doc = Document('md-contract', meta={'id': 'md-contract', 'title': 'Contract'},
                                   source=Source(html='Original', pdf=b'%PDF-original'),
                                   extensions={'ids.json': b'{"units": {"old": {"section": "s1"}}}'})
                    repo.save(doc)
                    changed, stale = repo.get(doc.id), repo.get(doc.id)
                    changed.notes = {'notes': [{'id': 'n-note', 'text': 'Kept'}]}
                    repo.save(changed)
                    self.assertIsNone(stale.notes)
                    with self.assertRaises(ConflictError): repo.save(stale)
                    result = repo.get(doc.id)
                    self.assertEqual(result.source.pdf, b'%PDF-original')
                    self.assertEqual(result.extensions, doc.extensions)
                    self.assertEqual(repo.list()[0].note_count, 1)

    def test_pathless_adapter_supports_layers_and_internal_parser_workspaces(self):
        backend = MemoryBackend()
        doc = Document('md-memory', meta={'id': 'md-memory', 'title': 'Memory'}, source=Source(html='Original'))
        backend.save(doc)
        with store.use_backend(backend):
            store.write(doc.id, 'en', {'version': 'test'})
            self.assertEqual(store.read(doc.id, 'en')['version'], 'test')
            with store.repository().workspace(doc.id) as folder:
                (folder / 'llm-cache').mkdir()
                (folder / 'llm-cache/reply.json').write_bytes(b'{"out": "paid reply"}')
            self.assertEqual(store.document(doc.id).processing.replies['reply.json'], b'{"out": "paid reply"}')


class LocalDefault(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        patch = mock.patch.object(store, 'DATA', Path(self.temp.name))
        patch.start(); self.addCleanup(patch.stop)
        self.pid = local.import_text('# Document\n\nA paragraph to annotate.\n')

    def test_note_save_touches_only_notes_and_preserves_legacy_thread_turns(self):
        folder = store.pdir(self.pid)
        pdf = folder / 'original.pdf'
        with pdf.open('wb') as output: output.truncate(110 * 1024 * 1024)
        before = pdf.stat()
        legacy = {'id': 'n-thread', 'anchor': {'unit': 'u1'}, 'thread': [{'q': 'Old', 'a': 'Old reply'}, {'q': 'Added by old pip', 'a': 'New reply'}],
                  'messages': [{'id': 'stale', 'role': 'assistant', 'text': 'Stale sidecar'}]}
        with mock.patch('shutil.copytree', side_effect=AssertionError('Do not copy a document for a note')), \
             mock.patch.object(LocalDirectoryBackend, 'get', side_effect=AssertionError('Do not load originals for a note')):
            notes.put(self.pid, legacy)
            reread = notes.read(self.pid)['notes'][0]
            self.assertEqual(notes.turns(reread), legacy['thread'])
            reread['text'] = 'An annotation'
            notes.put(self.pid, reread)
        self.assertEqual(notes.turns(notes.read(self.pid)['notes'][0]), legacy['thread'])
        self.assertEqual((pdf.stat().st_mtime_ns, pdf.stat().st_size), (before.st_mtime_ns, before.st_size))

    def test_direct_asset_reads_and_saves_do_not_load_other_files(self):
        repo = store.repository()
        with mock.patch.object(repo.backend, 'get', side_effect=AssertionError('Single-file access must stay single-file')):
            repo.write_asset(self.pid, 'img/one.bin', b'image')
            self.assertEqual(repo.read_asset(self.pid, 'img/one.bin'), b'image')
            self.assertTrue(repo.has(self.pid, 'img/one.bin'))

    def test_explicit_whole_document_save_writes_only_changed_files(self):
        backend = LocalDirectoryBackend(store.DATA)
        doc = backend.get(self.pid)
        doc.source.pdf = b'%PDF-original'
        backend.save(doc)
        doc.notes = {'notes': [{'text': 'New'}]}
        from textfold._storage_layout import DirectoryFiles
        writes = []
        write = DirectoryFiles.write
        def tracked(files, key, data):
            writes.append(key)
            return write(files, key, data)
        with mock.patch.object(DirectoryFiles, 'write', tracked), \
             mock.patch('shutil.copytree', side_effect=AssertionError('No folder copy')):
            backend.save(doc)
        self.assertEqual(writes, ['notes.json'])

    def test_default_read_list_and_generation_paths_allocate_no_workspaces(self):
        with mock.patch('tempfile.TemporaryDirectory', side_effect=AssertionError('Local reads/generation use the library')):
            self.assertEqual(len(store.papers()), 1)
            self.assertTrue(store.parsed(self.pid)['units'])
            with store.repository().workspace(self.pid) as folder:
                self.assertEqual(folder.resolve(), store.pdir(self.pid).resolve())

    def test_snapshot_retries_external_writes_during_read(self):
        backend = LocalDirectoryBackend(store.DATA)
        original = backend._read_legacy
        changed = False
        def read(folder, keys=None):
            nonlocal changed
            raw = original(folder, keys)
            if not changed:
                changed = True
                (folder / 'notes.json').write_text(json.dumps({'notes': [{'text': 'External writer'}]}), encoding='utf-8')
            return raw
        with mock.patch.object(backend, '_read_legacy', side_effect=read):
            doc = backend.get(self.pid)
        self.assertEqual(doc.notes['notes'][0]['text'], 'External writer')
        doc.meta['title'] = 'Title edit'
        backend.save(doc)
        self.assertEqual(backend.get(self.pid).notes, doc.notes)

    def test_explicit_local_backend_lists_and_trashes_its_own_library(self):
        with tempfile.TemporaryDirectory() as other:
            with store.use_backend(LocalDirectoryBackend(other)):
                identity = local.import_text('# Other library\n\nOther paragraph.\n')
                self.assertEqual([p['id'] for p in store.papers()], [identity])
                self.assertTrue(store.has(identity))
                store.trash(identity)
                self.assertEqual(store.papers(), [])
                self.assertIsNotNone(store.untrash(identity))
                self.assertEqual(store.papers()[0]['id'], identity)
            self.assertEqual(store.papers()[0]['id'], self.pid)

    def test_paid_reply_survives_sigterm_before_any_generation_checkpoint(self):
        root = Path(self.temp.name)
        ready = root / 'child-ready.json'
        script = r'''
import json, os, sys, time
from pathlib import Path
from unittest import mock
from textfold import llm, pipeline, store
pid, ready = sys.argv[1:]
def ladder(doc, model, cache, **kw):
    llm.call('fixture prompt', {}, model, cache)
    Path(ready).write_text(json.dumps({'pid': os.getpid()}))
    time.sleep(120)
cfg={'kind':'agent','runtime':'claude-code','model':'fixture','id':'fixture'}
with mock.patch.object(llm, '_once', return_value=({'paid': 'reply'}, 0)), mock.patch.object(pipeline, 'task', return_value=cfg), mock.patch.object(pipeline.ladder, 'build', side_effect=ladder):
    with store.repository().workspace(pid):
        pipeline.generate(pid, 'en', cfg)
'''
        env = {**os.environ, 'TEXTFOLD_DATA': str(root), 'TEXTFOLD_NO_MODELS': ''}
        child = subprocess.Popen([sys.executable, '-c', script, self.pid, str(ready)], env=env,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 10
            while not ready.exists() and child.poll() is None and time.monotonic() < deadline: time.sleep(.02)
            self.assertTrue(ready.exists(), child.stderr.read().decode() if child.poll() is not None else 'child timed out')
            os.kill(json.loads(ready.read_text())['pid'], signal.SIGTERM)
            child.wait(10)
            cached = list((store.pdir(self.pid) / 'llm-cache').glob('*.json'))
            self.assertEqual(len(cached), 1)
            self.assertEqual(json.loads(cached[0].read_text())['out'], {'paid': 'reply'})
        finally:
            if child.poll() is None: child.kill(); child.wait(10)
            child.stderr.close()
