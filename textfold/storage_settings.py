"""A local document backend selected for the next application start.

Only papers/, library.json and zotero.json move. The runtime directory and
credentials do not. A copy is verified before selection changes; source files
are never moved or removed. No work happens merely by importing this module.
"""
import hashlib
import json
import os
import shutil
import uuid
import sys
import re
import threading
from pathlib import Path

from ._storage_layout import DirectoryFiles

_lock = threading.RLock()
NAMES = ("papers", "library.json", "zotero.json")
MARKER = ".textfold-migration.json"
NEXT = ".textfold-migration-next.json"


class Refused(ValueError):
    """A folder Settings will not take, and why (code): the page says it in the reader's language (i18n.js,
    storage_err_<code>), the message stays for the log and the tests."""
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _process_alive(pid):
    if not isinstance(pid, int) or pid <= 0:
        return False
    if os.name == "nt":
        # os.kill(pid, 0) terminates processes on Windows; query the handle instead.
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return ctypes.get_last_error() == 5   # access denied: treat as running
        try:
            code = wintypes.DWORD()
            return not kernel.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value == 259
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _check_other_server(runtime):
    try:
        server = json.loads((Path(runtime) / "server.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if not isinstance(server, dict):
        return
    if server.get("format") == "textfold/server" and server.get("pid") != os.getpid() and _process_alive(server.get("pid")):
        raise OSError("Close other TextFold instances, then restart to copy the library")


def config_path(runtime):
    from . import store
    identity = os.environ.get("TEXTFOLD_RUNTIME_ID") or ("source:" + str(store.ROOT.resolve()) if store.SOURCE else "pip:" + str(Path(sys.prefix).resolve()))
    key = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
    return Path(runtime) / ".storage" / (key + ".json")


def _journal(destination, value):
    # The established journal owns this exact staging name. No glob cleanup.
    next_path = destination / NEXT
    if next_path.is_symlink() or getattr(next_path, "is_junction", lambda: False)():
        raise ValueError("Migration journal must not follow links")
    with next_path.open("w", encoding="utf-8") as output:
        json.dump(value, output, ensure_ascii=False)
        output.flush()
        os.fsync(output.fileno())
    os.replace(next_path, destination / MARKER)


def load(home):
    """home is the runtime data directory, never the global settings home."""
    path = config_path(home)
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("backend", "local") != "local":
        raise ValueError("Unsupported document storage configuration")
    if any(key in value and not isinstance(value[key], str) for key in ("path", "pending", "pending_mode", "error")):
        raise ValueError("Invalid library location settings")
    if value.get("pending_mode", "copy") not in ("copy", "existing"):
        raise ValueError("Invalid library location action")
    return value


def active_path(default, home):
    try:
        return Path(load(home).get("path") or default).expanduser().resolve()
    except (OSError, ValueError, TypeError):
        return Path(default).resolve()


def _save(home, value):
    path = config_path(home)
    DirectoryFiles(path.parent).write(path.name, json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8"))


def status(root, home):
    try:
        config = load(home)
    except (OSError, ValueError, TypeError) as error:
        config = {"error": "Library location settings could not be read: " + str(error)}
    return {"backend": "local", "path": str(Path(root).resolve()),
            "pending": config.get("pending") or "", "mode": config.get("pending_mode", "copy"), "error": config.get("error") or ""}


def _target(source, target, mode="copy"):
    if not isinstance(target, str) or not target.strip():
        raise Refused("path", "Enter an absolute folder path")
    path = Path(target.strip()).expanduser()
    if not path.is_absolute():
        raise Refused("path", "The library folder must be an absolute path")
    path, source = path.resolve(), Path(source).resolve()
    if path == source:
        return path
    if path.is_relative_to(source) or source.is_relative_to(path):
        raise Refused("inside", "The new library must not contain, or be inside, the current library")
    if mode not in ("copy", "existing"):
        raise ValueError("Choose copy or existing library")
    if mode == "existing":
        if not (path / "papers").is_dir() or (path / MARKER).exists():
            raise Refused("not_library", "Choose an existing TextFold library containing papers/")
        _files(path)  # reject symbolic links; selection never modifies this library
        return path
    if path.exists() and (not path.is_dir() or any(path.iterdir())):
        raise Refused("not_empty", "Choose an empty folder; existing files will not be overwritten")
    return path


def schedule(root, home, target=None, cancel=False, mode="copy"):
    """Validate now, copy on next start, so current writes stay in one library."""
    with _lock:
        config = load(home)
        root = Path(root).resolve()
        if cancel:
            config.pop("pending", None)
            config.pop("pending_mode", None)
            config.pop("error", None)
        else:
            path = _target(root, target, mode)
            if path == root:
                config.pop("pending", None)
            else:
                config["pending"] = str(path)
                config["pending_mode"] = mode
            config.pop("error", None)
        config.update(backend="local", path=str(root))
        _save(home, config)
        return status(root, home)


def _files(root):
    files = []
    for name in NAMES:
        path = root / name
        if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
            raise Refused("links", "Migration does not follow symbolic links")
        for item in path.rglob("*") if path.is_dir() else [path]:
            if item.is_symlink() or getattr(item, "is_junction", lambda: False)() or not item.resolve().is_relative_to(root):
                raise Refused("links", "Migration does not follow symbolic links")
            if item.is_file():
                files.append(item)
    return files


def _digest(path):
    digest = hashlib.sha256()
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_library(source, destination):
    """Resumable verified copy. Conflicting files always stop the migration."""
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source == destination:
        return
    if destination.is_relative_to(source) or source.is_relative_to(destination):
        raise ValueError("Overlapping library folders")
    marker = destination / MARKER
    if marker.exists():
        journal = json.loads(marker.read_text(encoding="utf-8"))
        if not isinstance(journal, dict) or journal.get("source") != str(source) or journal.get("version") not in (1, 2, 3):
            raise ValueError("This folder belongs to another migration")
    else:
        if not marker.exists() and (destination / NEXT).exists():
            candidate = json.loads((destination / NEXT).read_text(encoding="utf-8"))
            if not isinstance(candidate, dict) or candidate.get("source") != str(source) or candidate.get("version") != 3:
                raise ValueError("Unrecognized migration staging journal")
            os.replace(destination / NEXT, marker)
            return copy_library(source, destination)
        _target(source, str(destination))
        destination.mkdir(parents=True, exist_ok=True)
        journal = {"source": str(source), "version": 3, "files": {}, "next": NEXT}
    temporary = journal.get("temporary")
    extras = {MARKER}
    if temporary and (journal.get("version") != 3 or journal.get("next") != NEXT):
        raise ValueError("Unrecognized temporary migration ownership")
    if journal.get("version") == 3 and journal.get("next") == NEXT:
        extras.add(NEXT)
        if temporary:
            if not isinstance(temporary, str) or not re.fullmatch(r"\.textfold-copy-[0-9a-f]{32}", temporary):
                raise ValueError("Invalid temporary migration path")
            extras.add(temporary)
    if any(p.name not in (*NAMES, *extras) for p in destination.iterdir()):
        raise ValueError("Migration stopped: unexpected files in destination")
    target = DirectoryFiles(destination)
    if temporary:
        target.path(temporary).unlink(missing_ok=True)
    before = {p.relative_to(source).as_posix(): _digest(p) for p in _files(source)}
    existing = {p.relative_to(destination).as_posix(): _digest(p) for p in _files(destination)}
    owned = journal.get("files", {})
    if not isinstance(owned, dict) or any(not isinstance(values, list) or not all(isinstance(v, str) for v in values)
                                          for values in owned.values()):
        raise ValueError("Invalid migration file manifest")
    target = DirectoryFiles(destination)
    for key, digest in existing.items():
        if digest != before.get(key) and digest not in owned.get(key, []):
            raise ValueError(f"Migration stopped: conflicting file {key}")
    # Journal both old and proposed copies before changing anything. A retry
    # can replace/remove only unchanged files that this migration itself owns.
    planned = {key: list(values) for key, values in owned.items()}
    for key, digest in before.items():
        planned[key] = sorted(set(planned.get(key, []) + [digest]))
    journal = {"source": str(source), "version": 3, "files": planned, "next": NEXT}
    _journal(destination, journal)
    for key in existing.keys() - before.keys():
        out = target.path(key)
        if _digest(out) != existing[key]:
            raise ValueError(f"Migration stopped: conflicting file {key}")
        out.unlink()
    for key, digest in before.items():
        if existing.get(key) == digest:
            continue
        out = target.path(key)
        out.parent.mkdir(parents=True, exist_ok=True)
        temporary = ".textfold-copy-" + uuid.uuid4().hex
        journal["temporary"] = temporary
        _journal(destination, journal)  # durable ownership before creating it
        temp = target.path(temporary)
        with temp.open("xb"):
            pass
        try:
            shutil.copy2(source / key, temp)
            if _digest(temp) != digest:
                raise OSError(f"Copy verification failed: {key}")
            if out.exists() and (key not in existing or _digest(out) != existing[key]):
                raise ValueError(f"Migration stopped: conflicting file {key}")
            os.replace(temp, out)
        finally:
            temp.unlink(missing_ok=True)
        journal.pop("temporary", None)
        _journal(destination, journal)
    after = {p.relative_to(source).as_posix(): _digest(p) for p in _files(source)}
    if before != after:
        raise OSError("The original library changed during copying; close other TextFold instances and retry")
    copied = {p.relative_to(destination).as_posix(): _digest(p) for p in _files(destination)}
    if copied != before:
        raise OSError("The copied library changed during verification")
    # The marker is kept until storage.json has selected the verified copy.


def activate(default, home, log=None):
    """Startup only. A failed copy leaves the old library active and readable. log: told before a copy starts (the
    desktop app's window says so, and waits for it: desktop/main.js)."""
    with _lock:
        try:
            config = load(home)
        except (OSError, ValueError, TypeError):
            return Path(default).resolve()  # preserve the damaged file for recovery
        if not config.get("pending"):
            return active_path(default, home)
        source = Path(config.get("path") or default).resolve()
        target = Path(config["pending"]).resolve()
        try:
            _check_other_server(default)
            if config.get("pending_mode", "copy") == "existing":
                _target(source, str(target), "existing")
            else:
                if log:
                    log(f"TextFold is copying the library to {target}: once, before it starts")
                copy_library(source, target)
            selected = {**config, "path": str(target), "backend": "local"}
            selected.pop("pending", None)
            selected.pop("pending_mode", None)
            selected.pop("error", None)
            _save(home, selected)
        except (OSError, ValueError) as error:
            config["error"] = str(error)
            try:
                _save(home, config)
            except OSError:
                pass   # disk full must not prevent reading the original library
            return source
        try:
            if config.get("pending_mode", "copy") == "copy":
                (target / MARKER).unlink(missing_ok=True)
        except OSError:
            pass   # the verified library is already selected; cleanup may wait
        return target
