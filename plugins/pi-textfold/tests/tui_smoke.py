"""
End-to-end verification battery for the TextFold-for-Pi extension (D3 port).
Stages:
  S1 startup • S2 real model reply • S3 level keys (Brief/Gist/Full) •
  S4 width re-fold • S5 prep+resume restore • S6 digit-guard (--textfold-digits)
Run: python3 tui_smoke.py                    (all stages)
     TEXTFOLD_SMOKE_STAGES=S1,S3,S6 python3 tui_smoke.py   (selected stages)
     TEXTFOLD_SMOKE_RUNID=<id> python3 tui_smoke.py        (resume a run)
Env: TEXTFOLD_PI_CLI, TEXTFOLD_PI_NODE, TEXTFOLD_PI_DEBUG (tap), TEXTFOLD_PI_PROVIDER/MODEL.
Artifacts: /tmp/textfold-verify/<runid>/{bin,clean}/<stage>.* and checkpoint.json
Exit 0 = every requested stage passed; a partial run prints an exact resume line.
S1..S4 are one live session; S5-resume needs the checkpoint's session uuid from
S5-prep; S6 is independent (fresh session). Budgets cap every wait loop, and the
whole script belongs under `timeout`.
"""
import glob, json, os, pty, re, select, signal, struct, fcntl, termios, sys, time, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ansiclean import clean  # noqa: E402

EXT = os.path.join(HERE, "..", "extension", "index.ts")
RUNID = os.environ.get("TEXTFOLD_SMOKE_RUNID") or time.strftime("%Y%m%d-%H%M%S")
ART = os.path.join("/tmp/textfold-verify", RUNID)
os.makedirs(os.path.join(ART, "bin"), exist_ok=True)
os.makedirs(os.path.join(ART, "clean"), exist_ok=True)
CKPT = os.path.join(ART, "checkpoint.json")

PROVIDER = os.environ.get("TEXTFOLD_PI_PROVIDER", "")
MODEL = os.environ.get("TEXTFOLD_PI_MODEL", "")

def find_cli():
    want = os.environ.get("TEXTFOLD_PI_CLI")
    if want: return want
    npx_copies = sorted(glob.glob(os.path.expanduser(
        "~/.npm/_npx/*/node_modules/@earendil-works/pi-coding-agent")), reverse=True)
    installed = os.path.expanduser(
        "~/.npm-global/lib/node_modules/@earendil-works/pi-coding-agent/dist/bundle/cli.js")
    if os.path.isfile(installed):
        return installed  # the installed pi is the thing under test; npx copies are stale caches
    for b in npx_copies:
        if os.path.isdir(b):
            return os.path.join(b, "dist", "bundle", "cli.js")
    return installed

# pi needs Node 22.15+: default the child to the local node22 when it exists (coded in,
# not left to the invoking shell — the S1 lesson).
_node22 = os.path.expanduser("~/.local/node22/bin")
NODE_PREFIX = os.environ.get(
    "TEXTFOLD_PI_NODE", f"PATH={_node22}:$PATH " if os.path.isdir(_node22) else "")
cli = find_cli()
# Any directory works: the battery spawns its own sessions. The default is simply
# the invoking one.
cwd = os.getcwd()

base_args = ["--no-extensions", "--extension", EXT]
if PROVIDER: base_args += ["--extension", PROVIDER]
if MODEL: base_args += ["--model", MODEL]

env = dict(os.environ); env["TERM"] = "xterm-256color"
DEBUGFILE = env.get("TEXTFOLD_PI_DEBUG_FILE") or "/tmp/textfold-pi-debug.log"
if env.get("TEXTFOLD_PI_DEBUG"):
    env["TEXTFOLD_PI_DEBUG_FILE"] = DEBUGFILE

FOLD_MARKER = r"(?:Full|Brief|Points|Outline|Gist) · \d+ of \d+ words"

def load_ckpt():
    try:
        return json.load(open(CKPT))
    except (OSError, ValueError):
        return {"completed": [], "uuid": "", "entries_before": None}

STATE = load_ckpt()
STATE.setdefault("timings", {})
STATE.setdefault("completed", [])

def save_ckpt():
    tmp = CKPT + ".tmp"
    json.dump(STATE, open(tmp, "w"), indent=1)
    os.replace(tmp, CKPT)

failures = []
want = [s for s in os.environ.get("TEXTFOLD_SMOKE_STAGES", "").split(",") if s]
resume_mode = bool(os.environ.get("TEXTFOLD_SMOKE_RUNID"))

def wanted(name):
    return not want or name in want

# ── pty plumbing ─────────────────────────────────────────────────────────────
buf = b""
pid = fd = 0
stage_t0 = time.time()
frames: list[str] = []  # cleaned capture per session; the report scans all of them

def spawn(extra):
    global buf, pid, fd
    # per-session buffers reset at spawn: retain the previous session's cleaned
    # capture in `frames` so widget evidence from earlier stages stays countable
    if buf:
        frames.append(clean(buf))
    buf = b""
    pid, fd = pty.fork()
    if pid == 0:
        os.chdir(cwd)
        os.execvpe("bash", ["bash", "-c", f'{NODE_PREFIX}exec node {cli!r} ' +
            " ".join(repr(a) for a in [*base_args, *extra])], env)
    return pid, fd

def read_for(fd, sec):
    global buf
    end = time.time() + sec
    while time.time() < end:
        r, _, _ = select.select([fd], [], [], 0.5)
        if r:
            try: chunk = os.read(fd, 65536)
            except OSError: break
            if not chunk: break
            buf += chunk
            end = time.time() + 2
    return buf

def settle_fd(fd, quiet_budget=8):
    """Read until the pty goes quiet (max `quiet_budget`): a fixed short read
    once cut a level change's full-screen redraw short and flaked S4."""
    end = time.time() + quiet_budget
    while time.time() < end:
        n = len(buf); read_for(fd, 1.5)
        if len(buf) == n: break

def resize(fd, rows, cols=100):
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))

def snap(name):
    open(os.path.join(ART, "bin", name + ".bin"), "wb").write(buf)
    open(os.path.join(ART, "clean", name + ".txt"), "w").write(clean(buf))
    if env.get("TEXTFOLD_PI_DEBUG") and os.path.isfile(DEBUGFILE):
        shutil.copy(DEBUGFILE, os.path.join(ART, name + ".debug.log"))

def stage(name, ok, detail=""):
    global stage_t0
    STATE["timings"][name] = round(time.time() - stage_t0, 2)
    if ok:
        STATE["completed"].append(name)
    else:
        failures.append(f"{name}: {detail}")
    save_ckpt()
    print(f"[stage {name}] {STATE['timings'][name]}s " + ("PASS" if ok else "FAIL " + detail), flush=True)
    stage_t0 = time.time()
    return ok

def kill():
    try: os.kill(pid, signal.SIGKILL); os.waitpid(pid, 0)
    except (ChildProcessError, ProcessLookupError): pass

def newest_entry_session():
    """The newest session jsonl carrying at least one textfold-level entry."""
    best, best_mtime, count = "", 0, 0
    session_dir = os.path.expanduser("~/.pi/agent/sessions")
    for p in glob.glob(os.path.join(session_dir, "**", "*.jsonl"), recursive=True):
        try: body = open(p, encoding="utf-8", errors="replace").read()
        except OSError: continue
        c = body.count('"textfold-level"')
        if c and os.path.getmtime(p) > best_mtime:
            best, best_mtime, count = p, os.path.getmtime(p), c
    return best, count

need_first_session = not resume_mode or any(
    s not in set(STATE["completed"]) for s in
    ("S1-startup", "S2-reply", "S3-level-keys", "S4-width-refold", "S5-prep"))

if need_first_session:
    stage_t0 = time.time()
    spawn([])
    read_for(fd, 10); read_for(fd, 2)
    snap("S1-startup")
    t0 = clean(buf)
    S1 = stage("S1-startup", "Warning:" not in t0[:2000] and "TextFold" in t0, "startup frame")

    if wanted("S2"):
        os.write(fd, b"Write three short paragraphs about why reading less but keeping structure is good.\r")
        end = time.time() + 120
        while time.time() < end:
            n = len(buf); read_for(fd, 2)
            if len(buf) == n: break
        snap("S2-reply")
        t1 = clean(buf)
        # At Full nothing folds (the fold needs a level change); what must hold is
        # that the reply landed and the panel refreshed to "TextFold · Full".
        S2 = stage("S2-reply", "TextFold · Full" in t1 and len(t1) > 800, "reply landed + panel refresh")

    mark = len(clean(buf))  # char offset into the cleaned capture (never byte-slice)
    os.write(fd, b"\x1b2"); settle_fd(fd)     # alt+2 Brief
    os.write(fd, b"\x1b5"); settle_fd(fd)     # alt+5 Gist
    os.write(fd, b"\x1b1"); settle_fd(fd)     # alt+1 Full
    snap("S3-level-keys")
    t2 = clean(buf)[mark:]
    S3 = stage("S3-level-keys",
               all(k in t2 for k in ("Fold: Brief", "Fold: Gist", "Fold: Full", "TextFold · Brief", "TextFold · Gist")),
               "expected Brief/Gist notifies and panel headers")

    if wanted("S4"):
        m2 = len(clean(buf))
        os.write(fd, b"\x1b2"); settle_fd(fd)  # Brief first: the fold marker must exist to re-render
        resize(fd, 42); settle_fd(fd); resize(fd, 40); settle_fd(fd)
        snap("S4-width-refold")
        t3 = clean(buf)[m2:]
        # The whole post-press window IS this stage's evidence: markers carry their
        # level in the text, so stale frames from other levels cannot masquerade —
        # a Brief marker here can only come from this stage's alt+2 (S3 ended at
        # Full, where nothing folds). A pty frame can also precede its notify, so
        # no slicing by the notify.
        brief_markers = re.findall(r"Brief · \d+ of \d+ words", t3)
        if not brief_markers:
            settle_fd(fd, 10)  # one honest observation extension: the redraw may lag
            snap("S4-width-refold-retry")
            t3 = clean(buf)[m2:]
            brief_markers = re.findall(r"Brief · \d+ of \d+ words", t3)
        S4 = stage("S4-width-refold", len(brief_markers) >= 1,
                   f"Brief re-renders: {len(brief_markers)} (window had: {re.findall(FOLD_MARKER, t3)})")

    # ── S5 prep: Alt+3 persists Points; the session file is the checkpoint ──────
    if wanted("S5") and (not resume_mode or "S5-prep" not in set(STATE["completed"])):
        m3 = len(clean(buf))
        os.write(fd, b"\x1b3"); settle_fd(fd)
        read_for(fd, 2)
        snap("S5-prep")
        t4 = clean(buf)[m3:]
        lvl_ok = "Fold: Points" in t4
        session_file, entries_before = newest_entry_session()
        uuid = os.path.basename(session_file)[:-6].split("_", 1)[1] if session_file else ""
        STATE["session"] = session_file
        STATE["uuid"] = uuid
        STATE["entries_before"] = entries_before
        kill()
        save_ckpt()
        stage("S5-prep", lvl_ok and bool(uuid),
              f"level-notify={'Fold: Points' in t4} uuid={uuid or 'none'}")
    else:
        kill()

# ── S5 resume+restore: needs the checkpointed uuid ───────────────────────────
if wanted("S5") and (not resume_mode or "S5-resume" not in set(STATE["completed"])):
    uuid = STATE.get("uuid", "")
    if not uuid:
        print("S5-resume needs the checkpoint's uuid: run S5-prep first", flush=True)
        failures.append("S5-resume without a checkpointed uuid")
    else:
        spawn(["--session", uuid])
        read_for(fd, 15); read_for(fd, 2)
        snap("S5-resume")
        t5 = clean(buf)
        entries_after = 0
        if STATE.get("session") and os.path.isfile(STATE["session"]):
            entries_after = open(STATE["session"], encoding="utf-8", errors="replace").read().count('"textfold-level"')
        restored = ("TextFold · Points" in t5
                    and re.search(FOLD_MARKER, t5) is not None
                    and entries_after == STATE.get("entries_before"))
        notify_seen = "TextFold level restored: Points" in t5
        kill()
        print(f"  (notify seen: {notify_seen}; durable evidence is the assertion)", flush=True)
        stage("S5-resume", restored,
              "panel=%s refold=%s entries=%s(before %s)" % (
                  "TextFold · Points" in t5,
                  re.search(FOLD_MARKER, t5) is not None, entries_after, STATE.get("entries_before")))

# ── S6 digit-guard: model-free; needs --textfold-digits ─────────────────────
if wanted("S6") and (not resume_mode or "S6-digits" not in set(STATE["completed"])):
    spawn(["--textfold-digits"])
    read_for(fd, 10); read_for(fd, 2)
    m4 = len(clean(buf))
    os.write(fd, b"ab "); read_for(fd, 2)   # letters into the editor
    os.write(fd, b"4"); read_for(fd, 2)     # digit with a draft: reinsert expected
    read_for(fd, 1)
    seg_digits = clean(buf)[m4:]
    reinsert_ok = "ab4" in seg_digits.replace(" ", "") or "ab4" in clean(buf).replace(" ", "")
    os.write(fd, b"\x03"); read_for(fd, 2)  # ctrl+c clears the editor (pi 1.3.0)
    os.write(fd, b"3"); read_for(fd, 2)     # digit on an empty prompt: fold to Points
    read_for(fd, 2)
    snap("S6-digits")
    t6 = clean(buf)
    level_ok = "Fold: Points" in t6
    kill()
    stage("S6-digits", reinsert_ok and level_ok, f"reinsert={reinsert_ok} level-change={level_ok}")

# ── report ───────────────────────────────────────────────────────────────────
if buf:
    frames.append(clean(buf))
allt = "\n".join(frames)
report = {
    "row_widgets": bool(re.search(r"fold\s+1 Full\s+2 Brief\s+3 Points", allt)),
    "brief_widget": "TextFold · Brief" in allt,
    "gist_widget": "TextFold · Gist" in allt,
    "in_place_folds": len(re.findall(FOLD_MARKER, allt)),
}
for k, v in report.items(): print(f"{k}: {v}", flush=True)
if failures:
    for f in failures: print("FAIL:", f, flush=True)
save_ckpt()

ALL_STAGES = ("S1-startup", "S2-reply", "S3-level-keys", "S4-width-refold", "S5-prep", "S5-resume", "S6-digits")
done = set(STATE["completed"])
requested = want or list(ALL_STAGES)
pending = [s for s in requested if s not in done and s in ALL_STAGES]
if pending and not failures:
    print("RESUME: TEXTFOLD_SMOKE_RUNID=" + RUNID + " STAGES=" + ",".join(pending), flush=True)
sys.exit(0 if not failures else 1)
