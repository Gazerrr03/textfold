import json, os, tempfile, unittest
from pathlib import Path
from unittest import mock
from textfold import storage_settings, store
from textfold._storage_layout import DirectoryFiles

class Migration(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.source, self.target, self.home = (self.root / n for n in ("old", "new", "settings"))
        self.backend = DirectoryFiles(self.source)
        self.backend.write("papers/2306.03310/source.pdf", b"%PDF-1.4\x00\xff")
        self.backend.write("papers/2306.03310/layers/tr-zh.json", '{"title":"中文"}'.encode("utf-8"))
        self.backend.write("papers/2306.03310/notes.json", b'{"notes":[]}')
        self.backend.write("papers/.trash/old-20261001-000000/notes.json", b"{}")
        self.backend.write("library.json", b'{"folders":[]}')
        self.backend.write("zotero.json", b"{}")
        self.backend.write("server.log", b"runtime log")
        self.backend.write("engine/not-a-document", b"engine")

    def test_schedule_then_restart_copies_documents_only_without_changing_source(self):
        before = {e.key: self.backend.read(e.key) for e in self.backend.entries_for_root()}
        storage_settings.schedule(self.source, self.home, str(self.target))
        self.assertFalse(self.target.exists())
        self.assertEqual(storage_settings.active_path(self.source, self.home), self.source)
        self.backend.write("papers/2306.03310/notes.json", b'{"notes":["written before restart"]}')
        before["papers/2306.03310/notes.json"] = b'{"notes":["written before restart"]}'
        self.assertEqual(storage_settings.activate(self.source, self.home), self.target)
        for key, data in before.items():
            self.assertEqual(self.backend.read(key), data)
            if key.startswith("papers/") or key in ("library.json", "zotero.json"):
                self.assertEqual((self.target / key).read_bytes(), data)
        self.assertFalse((self.target / "server.log").exists())
        self.assertFalse((self.target / "engine").exists())
        self.assertEqual(storage_settings.active_path(self.source, self.home), self.target)

    def test_failure_keeps_the_old_library_selected(self):
        storage_settings.schedule(self.source, self.home, str(self.target))
        with mock.patch.object(storage_settings.shutil, "copy2", side_effect=OSError("disk full")):
            self.assertEqual(storage_settings.activate(self.source, self.home), self.source)
        self.assertIn("disk full", storage_settings.status(self.source, self.home)["error"])
        self.assertEqual(storage_settings.activate(self.source, self.home), self.target)

    def test_overlap_relative_and_nonempty_targets_are_refused(self):
        bad = self.root / "occupied"
        bad.mkdir()
        (bad / "keep.txt").write_bytes(b"keep")
        for path in (str(bad), str(self.source / "child"), str(self.root), "relative"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                storage_settings.schedule(self.source, self.home, path)
        self.assertEqual((bad / "keep.txt").read_bytes(), b"keep")

    def test_pending_move_can_be_cancelled(self):
        storage_settings.schedule(self.source, self.home, str(self.target))
        status = storage_settings.schedule(self.source, self.home, cancel=True)
        self.assertEqual(status["pending"], "")
        self.assertEqual(storage_settings.activate(self.source, self.home), self.source)
        self.assertFalse(self.target.exists())

    def test_conflicting_target_added_after_schedule_is_not_overwritten(self):
        storage_settings.schedule(self.source, self.home, str(self.target))
        self.target.mkdir()
        (self.target / "keep").write_bytes(b"keep")
        self.assertEqual(storage_settings.activate(self.source, self.home), self.source)
        self.assertEqual((self.target / "keep").read_bytes(), b"keep")

    def test_configuration_write_failure_does_not_select_the_copy(self):
        storage_settings.schedule(self.source, self.home, str(self.target))
        with mock.patch.object(storage_settings, "_save", side_effect=OSError("settings disk full")):
            self.assertEqual(storage_settings.activate(self.source, self.home), self.source)
        self.assertEqual(storage_settings.active_path(self.source, self.home), self.source)
        self.assertEqual(storage_settings.activate(self.source, self.home), self.target)

    def test_copy_temporary_names_do_not_collide_with_document_assets(self):
        self.backend.write("papers/2306.03310/foo", b"first")
        self.backend.write("papers/2306.03310/foo.textfold-copy", b"second")
        storage_settings.schedule(self.source, self.home, str(self.target))
        self.assertEqual(storage_settings.activate(self.source, self.home), self.target)
        self.assertEqual((self.target / "papers/2306.03310/foo.textfold-copy").read_bytes(), b"second")

    def test_source_changes_during_copy_leave_it_selected(self):
        storage_settings.schedule(self.source, self.home, str(self.target))
        original = storage_settings.shutil.copy2
        changed = False

        def copy_and_change(src, dst):
            nonlocal changed
            result = original(src, dst)
            if not changed:
                changed = True
                self.backend.write("papers/2306.03310/notes.json", b'{"notes":["new"]}')
            return result

        with mock.patch.object(storage_settings.shutil, "copy2", side_effect=copy_and_change):
            self.assertEqual(storage_settings.activate(self.source, self.home), self.source)
        self.assertEqual(storage_settings.active_path(self.source, self.home), self.source)
        self.assertEqual(self.backend.read("papers/2306.03310/notes.json"), b'{"notes":["new"]}')

    def test_another_running_server_defers_migration(self):
        storage_settings.schedule(self.source, self.home, str(self.target))
        self.backend.write("server.json", json.dumps({"format": "textfold/server", "pid": os.getpid() + 1}).encode())
        with mock.patch.object(storage_settings, "_process_alive", return_value=True):
            self.assertEqual(storage_settings.activate(self.source, self.home), self.source)
        self.assertFalse(self.target.exists())
        self.assertIn("other TextFold", storage_settings.status(self.source, self.home)["error"])

    def test_current_process_liveness_is_queried_without_signaling_it(self):
        self.assertTrue(storage_settings._process_alive(os.getpid()))

    def test_existing_library_and_return_to_original_never_copy_or_merge(self):
        storage_settings.schedule(self.source, self.home, str(self.target))
        self.assertEqual(storage_settings.activate(self.source, self.home), self.target)
        self.backend.write("papers/2306.03310/notes.json", b'{"notes":["original changed"]}')
        target_notes = self.target / "papers/2306.03310/notes.json"
        target_notes.write_bytes(b'{"notes":["destination changed"]}')
        storage_settings.schedule(self.target, self.home, str(self.source), mode="existing")
        with mock.patch.object(storage_settings, 'copy_library', side_effect=AssertionError('Existing libraries are only selected')):
            self.assertEqual(storage_settings.activate(self.source, self.home), self.source)
        self.assertEqual(self.backend.read('papers/2306.03310/notes.json'), b'{"notes":["original changed"]}')
        self.assertEqual(target_notes.read_bytes(), b'{"notes":["destination changed"]}')

    def test_runtime_selection_is_isolated_even_with_one_global_home(self):
        first, second = self.root / 'runtime-a', self.root / 'runtime-b'
        with mock.patch.object(store, 'DATA', first):
            store.schedule_storage(str(self.source), mode='existing')
            store.initialize_storage()
            self.assertEqual(store.library_root(), self.source.resolve())
        with mock.patch.object(store, 'DATA', second):
            store.initialize_storage()
            self.assertEqual(store.library_root(), second.resolve())
            self.assertFalse((second / 'storage.json').exists())
        self.assertTrue((first / 'storage.json').exists())

    def test_existing_library_validation_failure_keeps_old_library(self):
        self.target.mkdir(); (self.target / 'papers').mkdir()
        storage_settings.schedule(self.source, self.home, str(self.target), mode='existing')
        (self.target / 'papers').rmdir()
        self.assertEqual(storage_settings.activate(self.source, self.home), self.source)
        self.assertIn('existing TextFold', storage_settings.status(self.source, self.home)['error'])
