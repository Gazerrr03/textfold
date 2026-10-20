"""README-flow smoke for the D3 port: after `pi install ./plugins/pi-textfold`,
a PLAIN `pi` (no --extension anywhere) must fold.

Two runs, driven by argv:
  base    fresh session: package loads, Alt+2 folds+panel, /fold 4 then /fold
          off work; ends after Alt+3 so a textfold-level entry lands on disk and
          its full uuid is written to /tmp/textfold-verify/pi-install/uuid.txt
  digits  fresh session with --textfold-digits: `ab 4` reinserts, ctrl+c then `3`
          folds an empty prompt (Points); resume mode: --session <uuid> restores
          Points with the panel header and a folded reply render.
Env: PI_CLI for a nonstandard binary. Needs the model configured (one real turn
in base mode). Exit 0 = all checks of that mode pass.
Artifacts: /tmp/textfold-verify/pi-install/<mode>.bin
"""
import glob, os, pty, re, select, signal, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ansiclean import clean, flat  # noqa: E402

CLI = os.environ.get("PI_CLI", os.path.expanduser("~/.npm-global/bin/pi"))
NODE22 = os.path.expanduser("~/.local/node22/bin")
ENV = {**os.environ, "TERM": "xterm-256color", "PATH": f"{NODE22}:{os.environ.get('PATH','')}"}
ART = "/tmp/textfold-verify/pi-install"
os.makedirs(ART + "/bin", exist_ok=True)

mode = sys.argv[1] if len(sys.argv) > 1 else "base"
uuid = sys.argv[2] if len(sys.argv) > 2 else ""

def spawn(args, cwd):
    pid, fd = pty.fork()
    if pid == 0:
        os.chdir(cwd)
        os.execvpe("bash", ["bash", "-c",
            f'exec node "{CLI}" ' + " ".join(repr(a) for a in args)], ENV)
    return pid, fd

mode_specs = {
    "base":   ({"bin": "base"}, os.path.expanduser("~")),
    "digits": ({"bin": "digits"}, os.path.expanduser("~")),
    "resume": ({"bin": "resume"}, os.path.expanduser("~")),  # same project as the base session, or pi offers to fork
}
ART_KEYS, cwd = mode_specs[mode]

pid, fd = spawn([], cwd) if mode == "base" else spawn(
    ["--textfold-digits"] if mode == "digits" else ["--session", uuid], cwd)

buf = b""
def read_for(sec):
    global buf
    end = time.time() + sec
    while time.time() < end:
        r, _, _ = select.select([fd], [], [], 0.5)
        if r:
            try: c = os.read(fd, 65536)
            except OSError: break
            if not c: break
            buf += c
            end = time.time() + 2
    return buf

def kill():
    try: os.kill(pid, signal.SIGKILL); os.waitpid(pid, 0)
    except (ChildProcessError, ProcessLookupError): pass

read_for(12); read_for(2)
t = clean(buf)
checks = []
if mode == "base":
    checks.append(("package loads (row renders)", bool(re.search(r"fold\s+1 Full\s+2 Brief\s+3 Points", t))))
    checks.append(("panel installs pre-reply", "TextFold · Full" in t))
    os.write(fd, b"\x1b2"); read_for(3)
    t1 = clean(buf)
    checks.append(("alt+2 folds (notifies Brief, panel refreshes)", "Fold: Brief" in t1 and "TextFold · Brief" in t1))
    os.write(fd, b"/fold 4\r"); read_for(3)
    t2 = clean(buf)
    checks.append(("/fold 4 -> Outline", "Fold: Outline" in t2))
    os.write(fd, b"/fold off\r"); read_for(3)
    t3 = clean(buf)
    checks.append(("/fold off -> Full", "Fold: Full" in t3))
    # the real prompt: a reply long enough to fold (short replies stay whole),
    # then Alt+3 so the entry reaches disk
    os.write(fd, b"Write two short paragraphs about why reading less but keeping structure is good.\r")
    end = time.time() + 120
    while time.time() < end:
        n = len(buf); read_for(2)
        if len(buf) == n: break
    os.write(fd, b"\x1b3"); read_for(3)
    t4 = clean(buf)
    checks.append(("alt+3 persists (Points notify)", "Fold: Points" in t4))
    kill()
    best, mtime = "", 0
    for p in glob.glob(os.path.expanduser("~/.pi/agent/sessions/**/*.jsonl"), recursive=True):
        try: body = open(p, encoding="utf-8", errors="replace").read()
        except OSError: continue
        if '"textfold-level"' in body and os.path.getmtime(p) > mtime:
            best, mtime = p, os.path.getmtime(p)
    # pi 1.3.0 matches --session by the session-file name prefix, dashes significant:
    # pass the full uuid (VH7).
    uuid = os.path.basename(best)[:-6].split("_", 1)[1] if best else ""
    open(f"{ART}/uuid.txt", "w").write(uuid)
    checks.append(("session entry on disk", bool(uuid)))
    print(f"uuid: {uuid}")
elif mode == "digits":
    n0 = len(clean(buf))
    os.write(fd, b"ab "); read_for(2)
    os.write(fd, b"4"); read_for(2)
    t1 = clean(buf)[n0:]
    checks.append(("draft digit reinserts (ab 4)", "ab4" in clean(buf).replace(" ", "")))
    os.write(fd, b"\x03"); read_for(2)   # ctrl+c clears the editor on pi 1.3.0
    n1 = len(clean(buf))
    os.write(fd, b"3"); read_for(2)
    t2 = clean(buf)[n1:]
    checks.append(("empty-prompt digit folds to Points", "Fold: Points" in t2))
    kill()
else:  # resume
    read_for(15); read_for(2)
    t = clean(buf)
    checks.append(("row marks the restored level", bool(re.search(r"3 Points", t))))
    checks.append(("panel restores Points", "TextFold · Points" in t))
    checks.append(("replies re-render folded", re.search(r"(?:Full|Brief|Points|Outline|Gist) · \d+ of \d+ words", t) is not None))
    kill()

open(f"{ART}/{mode}.bin", "wb").write(buf)
ok = True
for name, passed in checks:
    print(f"{name}: {'PASS' if passed else 'FAIL'}")
    ok &= passed
sys.exit(0 if ok else 1)
