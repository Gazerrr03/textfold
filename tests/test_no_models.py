"""TEXTFOLD_NO_MODELS=1 (a test server, a CI run, a program that only stores documents): no model is asked, whatever
model is named, also the command line's `--model sonnet` and a request to the server that names one (#32); a reply
kept on disk is still read. Nothing here runs an agent or calls a model.

Run from the repo root:
    python3 -m unittest discover tests
"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from textfold import llm, models

SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}
API = {"id": "myapi/some-model", "kind": "api", "protocol": "openai", "base": "http://127.0.0.1:9/v1", "api_key": "x",
       "provider": "My API", "model": "myapi/some-model", "effort": None}


class NoModels(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cache = Path(self.tmp.name)
        once = mock.patch.object(llm, "_once", return_value=({"ok": True}, 0))
        self.once = once.start()
        self.addCleanup(once.stop)

    def test_a_named_model_is_not_asked(self):
        s = {"model": None}   # (settings given: the real ones are not read)
        named = [models.resolve("sonnet", s), models.resolve("pi/anthropic/claude-sonnet-5-5", s),
                 models.resolve("codebuddy/codebuddy/glm-5.1", s), API]   # (the command line's sonnet, an agent's, an API's)
        with mock.patch.dict(os.environ, {"TEXTFOLD_NO_MODELS": "1"}):
            for spec in named:
                with self.subTest(model=spec["id"]):
                    with self.assertRaises(RuntimeError) as e:
                        llm.call("Return JSON {\"ok\": true}.", SCHEMA, spec, self.cache)
                    self.assertTrue(str(e.exception).startswith("No model is available"))   # (the server's "no-model")
        self.once.assert_not_called()

    def test_a_reply_kept_is_read(self):
        with mock.patch.dict(os.environ):
            os.environ.pop("TEXTFOLD_NO_MODELS", None)
            rec, cached = llm.call("Return JSON {\"ok\": true}.", SCHEMA, API, self.cache)
        self.assertEqual((rec["out"], cached, self.once.call_count), ({"ok": True}, False, 1))
        with mock.patch.dict(os.environ, {"TEXTFOLD_NO_MODELS": "1"}):
            rec, cached = llm.call("Return JSON {\"ok\": true}.", SCHEMA, API, self.cache)
            self.assertEqual((rec["out"], cached), ({"ok": True}, True))
            with self.assertRaises(RuntimeError):   # asked again (regenerate): no model
                llm.call("Return JSON {\"ok\": true}.", SCHEMA, API, self.cache, force=True)
        self.assertEqual(self.once.call_count, 1)


if __name__ == "__main__":
    unittest.main()
