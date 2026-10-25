"""A question looked up on the web (#66). An agent on this computer runs as a one-shot text generator: no tools, a
scratch folder. With the switch beside a question on (a passage's or the whole text's, as the reader needs it), it
answers with its own web tools and nothing else: no tool that reads or changes a file or runs a command, no MCP
server, its own system prompt with ours after it. A service has no tools of its own: nothing changes for it. The answer
cites the pages it drew on as links, says it was made so, and its time to answer is longer. The commands are looked
at, not run: no agent and no network.

Run from the repo root:
    python3 -m unittest discover tests
"""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from textfold import agents, llm, local, models, notes, store

SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}


class Runs:
    """subprocess.run as the agents' runners call it: the commands kept, a reply each understands."""
    def __init__(self):
        self.cmds = []

    def __call__(self, cmd, **kw):
        self.cmds.append(cmd)
        if "-o" in cmd:   # codex exec writes its answer to the file named
            Path(cmd[cmd.index("-o") + 1]).write_text('{"ok": true}', encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if "--mode" in cmd:   # pi's events
            end = {"type": "agent_end", "messages": [{"role": "assistant", "content": [{"type": "text", "text": '{"ok": true}'}]}]}
            return SimpleNamespace(returncode=0, stdout=json.dumps(end), stderr="")
        return SimpleNamespace(returncode=0, stdout=json.dumps({"structured_output": {"ok": True}, "type": "result"}), stderr="")


class Commands(unittest.TestCase):
    def run_agent(self, runtime, tools):
        runs = Runs()
        with mock.patch.object(agents, "path_of", lambda r: f"/bin/{r}"), mock.patch.object(agents, "argv", lambda p: [p]), \
             mock.patch("subprocess.run", runs), mock.patch.object(agents, "env_for", lambda p: {}), \
             mock.patch.object(agents, "child_env", lambda: {}):   # (no login shell asked for its PATH)
            spec = {"kind": "agent", "runtime": runtime, "model": "m", "id": f"x/{runtime}/m", **({"tools": True} if tools else {})}
            out, _ = llm._once("Say ok.", SCHEMA, spec, 60, "You answer with JSON only.")
        self.assertEqual(out, {"ok": True})
        return runs.cmds[0]

    def test_claude_code(self):
        off, on = self.run_agent("claude-code", False), self.run_agent("claude-code", True)
        self.assertEqual(off[off.index("--tools") + 1], "")
        self.assertIn("--setting-sources", off)   # (its user's settings and CLAUDE.md stay out of a generation)
        self.assertEqual(on[on.index("--tools") + 1], "WebSearch,WebFetch")   # (no Read, Edit, Write or Bash)
        self.assertEqual(on[on.index("--allowedTools") + 1], "WebSearch,WebFetch")
        self.assertIn("--strict-mcp-config", on)   # (no MCP server's tools either)
        self.assertIn("--append-system-prompt", on)   # (its own system prompt, which knows its tools, stays)
        for flag in ("--dangerously-skip-permissions", "--system-prompt"):
            self.assertNotIn(flag, on)

    def test_codex(self):
        off, on = self.run_agent("codex", False), self.run_agent("codex", True)
        self.assertNotIn("--search", off)
        self.assertLess(on.index("--search"), on.index("exec"))   # (a flag of codex itself, before exec)
        for cmd in (off, on):
            self.assertEqual(cmd[cmd.index("-s") + 1], "read-only")
        self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", on)

    def test_pi(self):
        off, on = self.run_agent("pi", False), self.run_agent("pi", True)
        self.assertIn("--no-tools", off)
        self.assertIn("--no-builtin-tools", on)   # (no read, bash, edit or write: its extensions' tools alone)
        self.assertNotIn("--system-prompt", on)
        self.assertIn("--append-system-prompt", on)
        self.assertIn("--no-session", on)

    def test_codebuddy(self):
        off, on = self.run_agent("codebuddy", False), self.run_agent("codebuddy", True)
        self.assertEqual(off[off.index("--tools") + 1], "StructuredOutput")
        self.assertEqual(on[on.index("--tools") + 1], "WebSearch,WebFetch,StructuredOutput")
        self.assertIn("--strict-mcp-config", on)
        self.assertNotIn("--dangerously-skip-permissions", on)


class Switch(unittest.TestCase):
    def spec(self, kind, on):
        with mock.patch.object(models, "ask_choice", lambda s=None, cat=None: (None, None)), \
             mock.patch.object(models, "resolve", lambda m, s=None: {"kind": kind, "id": "x", "runtime": "codex", "model": "m"}):
            return models.ask_spec(models.load_settings(), tools=on)

    def test_only_an_agent_and_only_when_asked(self):
        self.assertTrue(self.spec("agent", True).get("tools"))
        self.assertFalse(self.spec("agent", False).get("tools"))
        self.assertFalse(self.spec("api", True).get("tools"))   # (a service has no harness)

    def test_its_answers_are_kept_apart(self):
        calls = []
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(llm, "_once", lambda *a: calls.append(a[2].get("tools")) or ({"ok": True}, 0)):
            spec = {"kind": "agent", "runtime": "codex", "model": "m", "id": "x/codex/m"}
            llm.call("Say ok.", SCHEMA, spec, Path(tmp))
            llm.call("Say ok.", SCHEMA, {**spec, "tools": True}, Path(tmp))   # (not the reply kept without tools)
            llm.call("Say ok.", SCHEMA, {**spec, "tools": True}, Path(tmp))
        self.assertEqual(calls, [None, True])


class Ask(unittest.TestCase):
    def test_the_prompt_asks_for_links_and_waits_longer(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(store, "DATA", Path(tmp)):
            pid = local.import_text("# A note\n\nOne paragraph, about folding.\n", "a.md")
            uid = next(iter(store.assemble(pid)["units"]))
            notes.put(pid, {"id": "n-1", "kind": "ask", "anchor": {"unit": uid, "level": 4, "tokens": [0, 1]}, "thread": []})
            seen = []
            reply = lambda text, schema, spec, cache, timeout=300, system=None: seen.append((text, timeout)) or (
                {"out": {"answer": "It is [[?]] [a page](https://example.org).", "takeaway": "t", "next": []}}, False)
            with mock.patch.object(llm, "call", reply):
                notes.ask(pid, "n-1", "Who did this first?", {"kind": "agent", "id": "x/codex/m"})
                note = notes.ask(pid, "n-1", "And then?", {"kind": "agent", "id": "x/codex/m", "tools": True})
        self.assertEqual([t.get("tools") for t in note["thread"]], [None, True])   # (the answer says it was made so)
        (plain, t1), (tooled, t2) = seen
        self.assertNotIn("search the web", plain)
        self.assertIn("search the web", tooled)
        self.assertIn("Markdown link", tooled)
        self.assertEqual((t1, t2), (300, 900))


if __name__ == "__main__":
    unittest.main()
