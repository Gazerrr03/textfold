"""A library TextFold 0.10.9 or before left on a Chinese Windows: its files in the system's codepage (GBK), with
Windows' line ends. 0.10.10 reads and writes UTF-8, and read such a file as UTF-8: "'utf-8' codec can't decode byte
0xa1" (the first byte of 。 in GBK) on the first page, a library read as empty. Now each is read in the codepage once
and written again as UTF-8. A scratch data folder; the codepage is GBK's here, whatever this computer's.

Run from the repo root:
    python3 -m unittest discover tests
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from textfold import library, local, models, notes, store


def as_old_windows(f):
    """The file as the old TextFold wrote it on a Chinese Windows: GBK, CRLF."""
    text = Path(f).read_text(encoding="utf-8")
    Path(f).write_bytes(text.replace("\n", "\r\n").encode("gbk"))


class OldCodepageFiles(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        for p in (mock.patch.object(store, "DATA", self.tmp / "data"), mock.patch.object(store, "codepage", return_value="gbk"),
                  mock.patch.object(models, "SETTINGS", self.tmp / "settings.json")):
            p.start()
            self.addCleanup(p.stop)
        self.pid = local.import_text("# 第三方跨境支付的法律监管\n\n近年来，跨境电子商务迅速发展。监管规则大多针对银行业务制定。\n")
        self.d = store.pdir(self.pid)

    def test_a_paper_written_in_gbk_opens_and_is_written_again_as_utf8(self):
        for name in ("meta.json", "source.html"):
            as_old_windows(self.d / name)
        with self.assertRaises(UnicodeDecodeError):
            (self.d / "meta.json").read_bytes().decode("utf-8")   # (what 0.10.10 to 0.10.13 met)
        doc = store.assemble(self.pid)
        self.assertEqual(doc["meta"]["title"], "第三方跨境支付的法律监管")
        self.assertIn("跨境电子商务", "".join(t.get("t", "") for u in doc["units"].values() for t in u["toks"]))
        for name in ("meta.json", "source.html"):
            raw = (self.d / name).read_bytes()
            self.assertIn("跨境", raw.decode("utf-8"))   # once read, UTF-8 from then on
        self.assertEqual(store.assemble(self.pid)["meta"]["title"], "第三方跨境支付的法律监管")

    def test_the_list_of_papers_and_their_translated_titles(self):
        layers = self.d / "layers"
        layers.mkdir(exist_ok=True)
        (layers / "tr-zh.json").write_text(json.dumps({"title": "跨境支付。", "units": {}, "chunks": {}, "version": "v1"}, ensure_ascii=False, indent=1), encoding="utf-8")
        for f in (self.d / "meta.json", layers / "tr-zh.json"):
            as_old_windows(f)
        row = next(p for p in store.papers() if p["id"] == self.pid)
        self.assertEqual(row["title"], "第三方跨境支付的法律监管")

    def test_the_library_its_folders_kept(self):
        library.path().write_text(json.dumps({"folders": [{"id": "f1", "name": "法学论文"}], "in": {self.pid: "f1"}}, ensure_ascii=False, indent=1), encoding="utf-8")
        as_old_windows(library.path())
        d = library.load()
        self.assertEqual([f["name"] for f in d["folders"]], ["法学论文"])   # (read as empty before, and saved so)

    def test_the_settings_and_the_notes(self):
        models.SETTINGS.write_text(json.dumps({"model": "claude/claude-code/sonnet", "lang": "zh", "name": "读者。"}, ensure_ascii=False, indent=1), encoding="utf-8")
        as_old_windows(models.SETTINGS)
        self.assertEqual(models.load_settings()["model"], "claude/claude-code/sonnet")
        nf = notes._file(self.pid)
        nf.parent.mkdir(parents=True, exist_ok=True)
        nf.write_text(json.dumps({"notes": [{"id": "n1", "text": "这一段说明了监管的困境。"}]}, ensure_ascii=False, indent=1), encoding="utf-8")
        as_old_windows(nf)
        self.assertEqual(notes.read(self.pid)["notes"][0]["text"], "这一段说明了监管的困境。")

    def test_a_file_in_utf8_reads_as_it_did(self):
        f = self.tmp / "x.json"
        f.write_bytes('{"a": "跨境"}\r\n'.encode("utf-8"))
        self.assertEqual(store.read_text(f), '{"a": "跨境"}\n')
        self.assertEqual(f.read_bytes(), '{"a": "跨境"}\r\n'.encode("utf-8"))   # (left as it is)
        bad = self.tmp / "bad.json"
        bad.write_bytes(b'{"a": "\xff\xfe"}')   # in neither: read with stand-ins, not rewritten
        with mock.patch.object(store, "codepage", return_value="utf-8"):
            self.assertEqual(store.read_text(bad), '{"a": "��"}')
        self.assertEqual(bad.read_bytes(), b'{"a": "\xff\xfe"}')


if __name__ == "__main__":
    unittest.main()
