"""A text file read in whatever encoding it was saved in: UTF-8 first, then the system's own codepage, so a Chinese
Windows reads a file saved as GBK and a German one a file saved as Windows-1252 (#16). No model, no network.

Run from the repo root:
    python3 -m unittest discover tests
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from textfold import local


class ReadTest(unittest.TestCase):
    def read(self, data, codepage):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "notes.txt"
            f.write_bytes(data)
            with mock.patch.object(local, "_codepage", return_value=codepage):
                return local._read(f)

    def test_utf8_whatever_the_system(self):
        for cp in ("cp936", "cp1252", "utf-8"):
            self.assertEqual(self.read("für 中文 ✓".encode("utf-8"), cp), "für 中文 ✓")
        self.assertEqual(self.read("﻿hello".encode("utf-8"), "cp1252"), "hello")   # the BOM comes off

    def test_a_file_saved_in_the_systems_codepage(self):
        self.assertEqual(self.read("中文笔记".encode("gbk"), "cp936"), "中文笔记")
        self.assertEqual(self.read("Größe für Übersicht".encode("cp1252"), "cp1252"), "Größe für Übersicht")

    def test_a_german_file_is_never_read_as_chinese(self):
        self.assertNotIn("黵", self.read("für".encode("cp1252"), "cp1252"))
        self.assertNotIn("黵", self.read("für".encode("cp1252"), "utf-8"))   # a Mac: stand-ins, not Chinese

    def test_the_codepage_is_the_systems(self):
        self.assertTrue(local._codepage())


if __name__ == "__main__":
    unittest.main()
