"""A local service that is not running is not a failed discovery (#24): no Ollama and no ChatGPT bridge, the most common
case, finds nothing and says nothing; and once the agents and the services are known, a saved model that is gone gives
way as a generation's does, so the page names the model the next generation uses.

Run from the repo root:
    python3 -m unittest discover tests
"""
import os
import time
import unittest
import urllib.error
from unittest import mock

from textfold import agents, bridges, models, server


def refused(*a, **k):
    raise urllib.error.URLError(ConnectionRefusedError(61, "Connection refused"))


class NotRunning(unittest.TestCase):
    def setUp(self):
        old = dict(server.DISCOVERY)
        server.DISCOVERY.update(live={"ollama": [], "bridge": None}, bridge={}, refreshing=False, ready=False, error="")
        self.addCleanup(lambda: server.DISCOVERY.update(old))
        bridges._SEEN.update(at=0.0, status=None)

    def refresh(self):
        # (a test run may set TEXTFOLD_NO_MODELS, which skips the probes; these tests are about the probes)
        env = mock.patch.dict("os.environ")
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("TEXTFOLD_NO_MODELS", None)
        server.refresh_models()
        end = time.monotonic() + 5
        while server.DISCOVERY["refreshing"] and time.monotonic() < end:
            time.sleep(.01)

    def test_nothing_running_is_nothing_found_not_a_failure(self):
        with mock.patch("urllib.request.urlopen", side_effect=refused):
            self.refresh()
        self.assertEqual(server.DISCOVERY["error"], "")
        self.assertTrue(server.DISCOVERY["ready"])
        self.assertEqual(server.DISCOVERY["live"]["ollama"], [])

    def test_a_wrong_answer_still_is_one(self):
        bad = urllib.error.HTTPError("http://localhost:11434/api/tags", 500, "Server Error", {}, None)
        with mock.patch("urllib.request.urlopen", side_effect=bad):
            self.refresh()
        self.assertIn("Ollama", server.DISCOVERY["error"])


class SavedChoice(unittest.TestCase):
    def payload(self, ready, scanned):
        s = {"model": "gone-model", "providers": []}
        state = {"scanning": False, "scanned_at": time.time() if scanned else None, "agents": []}
        with mock.patch.object(models, "load_settings", return_value=s), \
             mock.patch.dict(server.DISCOVERY, {"ready": ready, "live": {"ollama": ["llama3"], "bridge": None}}), \
             mock.patch.dict(agents.STATE, state), \
             mock.patch.object(server.engine, "status", return_value={}):
            return server.models_payload()

    def test_kept_while_not_yet_known(self):
        self.assertEqual(self.payload(ready=False, scanned=True)["selected"], "gone-model")
        self.assertEqual(self.payload(ready=True, scanned=False)["selected"], "gone-model")

    def test_gives_way_once_known(self):
        d = self.payload(ready=True, scanned=True)
        self.assertNotEqual(d["selected"], "gone-model")
        self.assertNotIn("gone-model", {m["id"] for m in d["models"]})


if __name__ == "__main__":
    unittest.main()
