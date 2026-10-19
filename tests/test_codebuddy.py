"""CodeBuddy, and WorkBuddy's copy of it: found inside the app before one on PATH, run on the app's Electron as node
with WorkBuddy's settings folder and its quiet switches, its models as its --help lists them, and a generation called
as claude -p is, with CodeBuddy's three differences (its user settings, the one tool its structured output needs, a
list of messages for an output). A fake WorkBuddy and a fake CodeBuddy (Python scripts) stand in; no model, no
network.

Run from the repo root:
    python3 -m unittest discover tests
"""
import json
import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

from textfold import agents, llm, models

CLI = '''\
import json, os, sys
args = sys.argv[1:]
log = os.environ.get("FAKE_LOG")
if log:
    with open(log, "a", encoding="utf-8") as f:
        f.write(json.dumps({"args": args, "cwd": os.getcwd(), "stdin": "" if "-p" not in args else sys.stdin.read(),
                            "env": {k: v for k, v in os.environ.items() if k.startswith(("CODEBUDDY_", "ELECTRON_"))}}) + "\\n")
if "--version" in args:
    print("2.115.0")
elif "--help" in args:
    print("  --effort <level>    Reasoning effort level (minimal, low, high)")
    print("  --model <model>     Model for the current session. Currently supported: (auto, glm-5.1, kimi-k2.7)")
elif "-p" in args and os.environ.get("FAKE_SIGNED_OUT"):
    print("Authentication required. Please use /login command to sign in to your account")
elif "-p" in args:
    bad = bool(os.environ.get("FAKE_ERROR"))
    print(json.dumps([{"type": "message", "role": "user", "content": []},
                      {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "{}"}]},
                      {"type": "result", "subtype": "success", "is_error": bad, "result": "quota exceeded" if bad else "done",
                       "structured_output": None if bad else {"takeaway": "Folded"}, "total_cost_usd": 0}]))
'''

# the app's Electron: as node only when asked to be (else it would open the app), it runs the script it is given
ELECTRON = '''\
import os, subprocess, sys
if os.environ.get("ELECTRON_RUN_AS_NODE") != "1":
    sys.exit("the app would open")
sys.exit(subprocess.run([sys.executable, *sys.argv[1:]]).returncode)
'''


def script(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!{sys.executable}\n" + textwrap.dedent(body), encoding="utf-8")
    path.chmod(0o755)
    return path


@unittest.skipIf(os.name == "nt", "the fake app and CLI are POSIX scripts")
class CodeBuddy(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        app = self.tmp / "WorkBuddy.app" / "Contents"
        self.bin = app / "Resources" / "app.asar.unpacked" / "cli" / "bin"
        self.cli = script(self.bin / "codebuddy", CLI)
        self.electron = script(app / "MacOS" / "Electron", ELECTRON)
        self.alone = script(self.tmp / "npm" / "bin" / "codebuddy", CLI)   # one installed on its own
        self.home = self.tmp / "home"
        (self.home / ".workbuddy").mkdir(parents=True)
        self.log = self.tmp / "calls.jsonl"
        for p in (mock.patch.object(agents, "HOME", self.home),
                  mock.patch.dict(os.environ, {"FAKE_LOG": str(self.log)}),
                  mock.patch.object(agents, "search_dirs", return_value=[str(self.tmp / "npm" / "bin")])):
            p.start()
            self.addCleanup(p.stop)
        os.environ.pop("WORKBUDDY_CONFIG_DIR", None)
        os.environ.pop("FAKE_ERROR", None)
        os.environ.pop("FAKE_SIGNED_OUT", None)

    def calls(self):
        return [json.loads(x) for x in self.log.read_text(encoding="utf-8").splitlines()] if self.log.exists() else []

    def test_found_in_the_app_before_one_on_path(self):
        self.assertEqual(agents.locate("codebuddy", [str(self.bin)]), str(self.cli))
        self.assertEqual(agents.locate("codebuddy", []), str(self.alone))
        self.assertEqual(agents.workbuddy_runner(str(self.cli)), str(self.electron))
        self.assertIsNone(agents.workbuddy_runner(str(self.alone)))

    def test_run_as_workbuddy_runs_it(self):
        path = str(self.cli)
        self.assertEqual(agents.argv(path), [str(self.electron), path])
        env = agents.env_for(path)
        self.assertEqual(env["ELECTRON_RUN_AS_NODE"], "1")
        self.assertEqual(env["CODEBUDDY_CONFIG_DIR"], str(self.home / ".workbuddy"))
        self.assertEqual(env["CODEBUDDY_DISABLE_AUTO_MEMORY"], "1")
        alone = agents.env_for(str(self.alone))
        self.assertEqual(agents.argv(str(self.alone)), [str(self.alone)])
        self.assertNotIn("ELECTRON_RUN_AS_NODE", alone)
        self.assertNotIn("CODEBUDDY_CONFIG_DIR", alone)
        self.assertEqual(alone["CODEBUDDY_DISABLE_SYSTEM_REMINDER_MD"], "1")
        self.assertNotIn("CODEBUDDY_DISABLE_AUTO_MEMORY", agents.env_for("/usr/local/bin/claude"))   # (the others as before)

    def test_its_models_as_its_help_lists_them(self):
        got = agents._codebuddy_models(str(self.cli))
        self.assertEqual([m["id"] for m in got], ["codebuddy/codebuddy/auto", "codebuddy/codebuddy/glm-5.1", "codebuddy/codebuddy/kimi-k2.7"])
        self.assertEqual([m["name"] for m in got][:2], ["WorkBuddy · Auto", "WorkBuddy · glm-5.1"])
        self.assertEqual(got[0]["efforts"], ["minimal", "low", "high"])
        self.assertEqual(agents._codebuddy_models(str(self.alone))[1]["name"], "CodeBuddy · glm-5.1")
        self.assertEqual(self.calls()[0]["env"]["ELECTRON_RUN_AS_NODE"], "1")   # (the app's Electron ran it, as node)

    def test_scanned_as_workbuddy(self):
        with mock.patch.object(agents, "REGISTRY", [("codebuddy", "CodeBuddy", "codebuddy", [str(self.bin)], True)]), \
                mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TEXTFOLD_NO_MODELS", None)   # (the build runs the tests with it: this probe is the test)
            row = agents.scan()["agents"][0]
        self.assertEqual((row["label"], row["version"], row["error"]), ("WorkBuddy", "2.115.0", None))
        self.assertEqual(len(row["models"]), 3)

    def test_a_generation(self):
        schema = {"type": "object", "properties": {"takeaway": {"type": "string"}}}
        with mock.patch.object(agents, "path_of", return_value=str(self.cli)):
            self.assertEqual(agents.run_codebuddy("glm-5.1", "Fold this.", schema, "The system.", "off", 30), ({"takeaway": "Folded"}, 0))
        call = self.calls()[-1]
        args = call["args"]
        self.assertEqual(args[:3], ["-p", "--model", "glm-5.1"])
        self.assertEqual(args[args.index("--tools") + 1], "StructuredOutput")
        self.assertEqual(json.loads(args[args.index("--json-schema") + 1]), schema)
        self.assertEqual(args[args.index("--system-prompt") + 1], "The system.")
        self.assertEqual(args[args.index("--effort") + 1], "minimal")   # (it has no level off)
        self.assertIn("--no-session-persistence", args)
        self.assertNotIn("--setting-sources", args)   # without its user settings it has no sign-in, and waits
        self.assertEqual(call["stdin"], "Fold this.")
        self.assertNotEqual(Path(call["cwd"]).resolve(), Path.cwd().resolve())   # a scratch folder
        self.assertEqual(call["env"]["CODEBUDDY_CONFIG_DIR"], str(self.home / ".workbuddy"))

    def test_an_error_it_reports(self):
        with mock.patch.object(agents, "path_of", return_value=str(self.cli)), mock.patch.dict(os.environ, {"FAKE_ERROR": "1"}):
            with self.assertRaises(RuntimeError) as e:
                agents.run_codebuddy("auto", "Fold this.", {"type": "object"}, "s", None, 30)
        self.assertIn("quota exceeded", str(e.exception))

    def test_not_signed_in(self):
        with mock.patch.object(agents, "path_of", return_value=str(self.cli)), mock.patch.dict(os.environ, {"FAKE_SIGNED_OUT": "1"}):
            with self.assertRaises(RuntimeError) as e:
                agents.run_codebuddy("auto", "Fold this.", {"type": "object"}, "s", None, 30)
        self.assertIn("WorkBuddy is not signed in", str(e.exception))


class Ids(unittest.TestCase):
    def test_a_codebuddy_model_id(self):
        spec = models.resolve("codebuddy/codebuddy/glm-5.1", {"model": None})
        self.assertEqual((spec["kind"], spec["runtime"], spec["model"]), ("agent", "codebuddy", "glm-5.1"))
        with mock.patch.object(agents, "run_codebuddy", return_value=({"a": 1}, 0)) as run:
            self.assertEqual(llm._once("p", {}, spec, 30, "s"), ({"a": 1}, 0))
        self.assertEqual(run.call_args.args[:2], ("glm-5.1", "p"))


if __name__ == "__main__":
    unittest.main()
