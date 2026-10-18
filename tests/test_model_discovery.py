"""Opening pages must not wait for local model services."""
import time
import threading
import unittest
from unittest import mock

from textfold import bridges, models, providers, server


class ModelOpening(unittest.TestCase):
    def setUp(self):
        self.old = dict(server.DISCOVERY)
        server.DISCOVERY.update(live={"ollama": [], "bridge": None}, bridge={},
                                refreshing=False, ready=False, error="")
        self.addCleanup(lambda: server.DISCOVERY.update(self.old))

    def finish_refresh(self):
        end = time.monotonic() + 2
        while server.DISCOVERY["refreshing"] and time.monotonic() < end:
            time.sleep(.005)
        self.assertFalse(server.DISCOVERY["refreshing"])

    def test_opening_does_not_probe_services(self):
        def slow(*a, **kw):
            time.sleep(.15)
            return []

        settings = {"model": "saved-model", "providers": [], "ask_model": None}
        with mock.patch.object(models, "load_settings", return_value=settings), \
             mock.patch.object(providers, "ollama_models", side_effect=slow) as probe, \
             mock.patch.object(bridges, "bridge_status", return_value={"running": False}), \
             mock.patch.object(server, "listed", return_value=[]), \
             mock.patch.object(server.library, "folders", return_value=[]), \
             mock.patch.object(server.engine, "status", return_value={}):
            jobs = mock.Mock()
            jobs.list.return_value = []
            start = time.monotonic()
            server.landing_page(jobs)
            server.models_payload()
            elapsed = time.monotonic() - start
            self.assertLess(elapsed, .1, f"opening waited {elapsed:.3f}s for discovery")
            probe.assert_not_called()

    def test_slow_refresh_is_shared_and_failure_keeps_results_then_retry_recovers(self):
        entered, release = threading.Event(), threading.Event()

        def slow(**kw):
            entered.set()
            release.wait(2)
            return ["local-model"]

        with mock.patch.dict("os.environ", {}, clear=True), \
             mock.patch.object(providers, "ollama_models", side_effect=slow) as probe, \
             mock.patch.object(bridges, "bridge_status", return_value={"running": True, "models": ["bridge-model"]}):
            server.refresh_models()
            self.assertTrue(entered.wait(1))
            server.refresh_models()
            self.assertEqual(probe.call_count, 1)
            self.assertTrue(server.DISCOVERY["refreshing"])
            release.set()
            self.finish_refresh()
            saved = server.DISCOVERY["live"]
            probe.side_effect = TimeoutError()
            server.refresh_models()
            self.finish_refresh()
            self.assertEqual(server.DISCOVERY["live"]["ollama"], saved["ollama"])
            self.assertIn("Ollama", server.DISCOVERY["error"])
            probe.side_effect = None
            probe.return_value = ["new-model"]
            server.refresh_models()
            self.finish_refresh()
            self.assertEqual(server.DISCOVERY["live"]["ollama"], ["new-model"])
            self.assertEqual(server.DISCOVERY["error"], "")

    def test_first_failure_is_not_a_successful_empty_catalog(self):
        with mock.patch.dict("os.environ", {}, clear=True), \
             mock.patch.object(providers, "ollama_models", side_effect=TimeoutError()), \
             mock.patch.object(bridges, "bridge_status", side_effect=ConnectionError()):
            server.refresh_models()
            self.finish_refresh()
            self.assertFalse(server.DISCOVERY["ready"])
            self.assertTrue(server.DISCOVERY["error"])

    def test_saved_choices_stay_visible_without_service_and_settings_are_not_written(self):
        s = {"model": "saved-model", "ask_model": "saved-ask", "providers": []}
        with mock.patch.object(models, "load_settings", return_value=s), \
             mock.patch.object(models, "save_settings") as save, \
             mock.patch.object(server.engine, "status", return_value={}):
            d = server.models_payload()
        self.assertEqual(d["selected"], "saved-model")
        self.assertEqual(d["askModel"], "saved-ask")
        self.assertTrue({"saved-model", "saved-ask"} <= {m["id"] for m in d["models"]})
        save.assert_not_called()
