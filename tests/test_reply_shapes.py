"""A model's reply read whatever shape it comes in (#17): an OpenAI-compatible endpoint in JSON mode promises valid JSON,
not the schema's shape, so a reply's units may come as strings, as an object keyed by id or as one JSON string, and its
text as a list of parts. No model is called.

Run from the repo root:
    python3 -m unittest discover tests
"""
import json
import tempfile
import unittest
from pathlib import Path

from textfold import llm, llm_openai

UNIT = {"id": "U0", "role": "claim", "takeaway": "Folding helps readers", "topic": "folding", "reason": "Levels nest",
        "evidence": [0]}


class UnitsTest(unittest.TestCase):
    def test_as_asked(self):
        self.assertEqual(llm.units_of({"units": [UNIT]}), [UNIT])

    def test_other_shapes(self):
        for units in ([json.dumps(UNIT)], {"U0": {k: v for k, v in UNIT.items() if k != "id"}}, json.dumps([UNIT])):
            with self.subTest(units=type(units).__name__):
                self.assertEqual(llm.units_of({"units": units})[0]["takeaway"], UNIT["takeaway"])

    def test_what_cannot_be_read_is_dropped(self):
        self.assertEqual(llm.units_of({"units": ["U0", "U1"]}), [])
        self.assertEqual(llm.units_of({"units": "not json"}), [])
        self.assertEqual(llm.units_of("a string, not an object"), [])

    def test_as_obj(self):
        self.assertEqual(llm.as_obj('{"takeaway": "x"}'), {"takeaway": "x"})
        self.assertEqual(llm.as_obj("x"), {})
        self.assertEqual(llm.as_obj(None), {})


class ContentTest(unittest.TestCase):
    def test_text_or_parts(self):
        self.assertEqual(llm_openai._content({"choices": [{"message": {"content": "{}"}}]}), "{}")
        parts = [{"type": "text", "text": '{"a"'}, {"type": "text", "text": ": 1}"}]
        self.assertEqual(llm_openai._content({"choices": [{"message": {"content": parts}}]}), '{"a": 1}')
        self.assertEqual(llm_openai._content({"choices": [{"message": "{}"}]}), "{}")

    def test_not_a_completion(self):
        for body in ({"error": "Model busy"}, {"choices": ["x"]}, "a string", {"choices": []}):
            with self.subTest(body=body):
                self.assertIsNone(llm_openai._content(body))


class ForgetTest(unittest.TestCase):
    def test_a_kept_reply_its_caller_could_not_read_is_dropped(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "abc.json"
            f.write_text("{}")
            llm.forget({"file": str(f)})
            self.assertFalse(f.exists())
            llm.forget({})   # a reply that was never kept: nothing to drop


if __name__ == "__main__":
    unittest.main()
