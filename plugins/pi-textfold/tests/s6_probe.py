"""S6 digit-guard live probe on the installed pi (no model call).
(a) digits reinsert when the editor has text: `ab ` then `3` -> editor shows `ab 3`
(b) digit on empty editor changes level: notify `Fold: Points` (level 3)
Pass if both (a) and (b) are seen. Writes /tmp/s6final.bin.
"""
import os, pty, re, select, time, sys

CLI = os.environ.get("PI_CLI", os.path.expanduser("~/.npm-global/bin/pi"))
EXT = "/tmp/textfold/plugins/pi-textfold/extension/index.ts"
env = dict(os.environ); env["TERM"] = "xterm-256color"
if os.environ.get("TEXTFOLD_PI_DEBUG"): env["TEXTFOLD_PI_DEBUG"] = "1"

pid, fd = pty.fork()
if pid == 0:
    os.chdir(os.path.expanduser("~"))
    os.execvpe(CLI, [CLI, "--extension", EXT, "--textfold-digits"], env)

buf = b""
def read_for(sec):
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

def send(d, wait=1.5): os.write(fd, d); read_for(wait)

def clean_all(x):
    txt = x.decode("utf-8", "replace")
    txt = re.sub(r"\x1b(?:\[[0-9;?]*[a-zA-Z]|\][^\x07\x1b]*(?:\x07|\x1b\\)|[()][A-Z0-9]|[=>])", "", txt)
    return re.sub(r"[\s]", "", txt)

read_for(10); read_for(2)
before = len(buf)
send(b"ab ", 1.5)
send(b"3", 2)          # digit with non-empty editor -> reinsert → "ab 3"
send(b"\x03", 1.5)     # ctrl+c clears the editor (pi 1.3.0 help: "ctrl+c/ctrl+d clear/exit")
send(b"\x1b2", 1.5)    # alt+2 sanity: unconditional Alt path → Fold: Brief
send(b"3", 2)          # digit on (now) empty editor → Fold: Points
send(b"\x1b1", 1.5)    # unfold back for cleanliness
send(b"\x03", 1.0)
time.sleep(1); read_for(1)
try: os.kill(pid, 9); os.waitpid(pid, 0)
except ChildProcessError: pass

clean = re.sub(r"\x1b(?:\[[0-9;?]*[a-zA-Z]|\][^\x07\x1b]*(?:\x07|\x1b\\)|[()][A-Z0-9]|[=>])", "", buf.decode("utf-8", "replace"))
open("/tmp/s6final.bin", "wb").write(buf)
seg = clean.replace(" ", "")
reinsert_ok = "ab3" in seg
level_ok = "Fold:Points" in seg
alt_ok = "Fold:Brief" in seg
print("reinsert_ok:", reinsert_ok)
print("level_ok:", level_ok)
print("alt_ok:", alt_ok)
if os.environ.get("TEXTFOLD_PI_DEBUG"):
    try: print("debuglog:", open("/tmp/textfold-pi-debug.log").read()[-800:])
    except OSError: pass
sys.exit(0 if (reinsert_ok and level_ok and alt_ok) else 1)
