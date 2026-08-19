"""Asynchronous wrapper around the Windows Package Manager (winget) CLI.

Everything here runs off the UI thread. The engine talks to the frontend by
calling `emit(event_dict)`; it never touches the DOM or the webview directly.

The install queue is a mutable list guarded by a lock: the worker always pulls
the first item still marked "queued", so the UI can reorder or skip pending
entries while an install is in flight.
"""

import ctypes
import os
import re
import subprocess
import threading
import time

CREATE_NO_WINDOW = 0x08000000

# winget rewrites its progress bar in place using carriage returns, so we split
# the raw byte stream on both CR and LF rather than reading whole lines.
_SPLIT = re.compile(rb"[\r\n]")

# "  12.4 MB / 78.9 MB" -- the only progress signal winget emits when its
# stdout is redirected to a pipe.
_BYTES = re.compile(
    r"([\d.]+)\s*(B|KB|MB|GB|TB)\s*/\s*([\d.]+)\s*(B|KB|MB|GB|TB)", re.I)

_UNIT = {"B": 1, "KB": 1024, "MB": 1024 ** 2, "GB": 1024 ** 3, "TB": 1024 ** 4}

# Spinner frames and box-drawing bar glyphs are pure noise in the log drawer.
_NOISE = str.maketrans("", "", "█▒░▀▄")

# Lines winget prints that explain a failure better than any exit code can.
_ERROR_MARKERS = (
    "no package found",
    "no applicable installer",
    "no applicable upgrade",
    "installer failed with exit code",
    "access is denied",
    "does not match",
    "failed to download",
    "downloading the installer failed",
    "an unexpected error occurred",
    "cancelled",
    "requires administrator",
)

# Installer exit codes that are unambiguous regardless of package.
_EXIT_HINTS = {
    0x8A150014: "winget found no package matching that identifier.",
    0x80070005: "Access denied - this package needs an elevated (admin) install.",
    1602: "The installer was cancelled by the user or by a UAC prompt.",
    1603: "The installer reported a fatal error during installation.",
    1618: "Another installation is already in progress. Try again shortly.",
    1641: "Installed successfully - a restart was initiated.",
    3010: "Installed successfully - a restart is required to finish.",
}

# Exit codes that mean the package really did land on disk.
_SOFT_SUCCESS = {0, 1641, 3010}


def _hresult(code):
    """Normalise a Windows process exit code to an unsigned 32-bit int."""
    return code & 0xFFFFFFFF if code is not None else 0


def is_elevated():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def system_info():
    """Facts for the sidebar's Target block."""
    target = os.environ.get("ProgramFiles", r"C:\Program Files")
    name, display, build = "Windows", "", ""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion")
        with key:
            name = winreg.QueryValueEx(key, "ProductName")[0]
            build = str(winreg.QueryValueEx(key, "CurrentBuildNumber")[0])
            try:
                display = winreg.QueryValueEx(key, "DisplayVersion")[0]
            except OSError:
                display = winreg.QueryValueEx(key, "ReleaseId")[0]
    except Exception:
        pass

    # The registry still says "Windows 10" on 11; build 22000+ is the real tell.
    if build.isdigit() and int(build) >= 22000:
        name = name.replace("Windows 10", "Windows 11")

    return {
        "target": target,
        "os": " · ".join(x for x in (name, display) if x) or "Windows",
        "build": build,
        "elevated": is_elevated(),
        "arch": os.environ.get("PROCESSOR_ARCHITECTURE", ""),
    }


def _run(args, timeout=120):
    """Run a winget command to completion and return (returncode, stdout)."""
    proc = subprocess.run(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        creationflags=CREATE_NO_WINDOW,
        timeout=timeout,
    )
    return proc.returncode, proc.stdout.decode("utf-8", "replace")


def _parse_table(text):
    """Parse winget's fixed-width table output into a list of dicts.

    Column boundaries come from the header row, which is the only reliable
    approach: app names routinely contain single spaces.
    """
    lines = [ln.rstrip() for ln in text.splitlines()]
    header_idx = None
    for i, line in enumerate(lines):
        if "Name" in line and "Id" in line and "Version" in line:
            header_idx = i
            break
    if header_idx is None:
        return []

    header = lines[header_idx]
    cols = []
    for name in ("Name", "Id", "Version", "Available", "Match", "Source"):
        pos = header.find(name)
        if pos != -1:
            cols.append((name.lower(), pos))
    cols.sort(key=lambda c: c[1])

    rows = []
    for line in lines[header_idx + 1:]:
        if not line.strip() or set(line.strip()) <= {"-"}:
            continue
        row = {}
        for n, (key, start) in enumerate(cols):
            end = cols[n + 1][1] if n + 1 < len(cols) else len(line)
            row[key] = line[start:end].strip()
        if row.get("id"):
            rows.append(row)
    return rows


class WingetEngine:
    """Owns all winget subprocess work: probing, querying and the install queue."""

    def __init__(self, emit):
        self._emit = emit
        self._proc = None
        self._cancel = threading.Event()   # hard abort: kills the running install
        self._pause = threading.Event()    # soft stop: finish this one, then halt
        self._lock = threading.Lock()
        self._worker = None
        self._queue = []          # [{"id":…, "state":…}], mutable from the UI

    # -- events ----------------------------------------------------------
    def _log(self, line, stream="out"):
        self._emit({"type": "log", "line": line, "stream": stream,
                    "t": time.strftime("%H:%M:%S")})

    def _status(self, pkg_id, state, pct=None, detail=""):
        self._emit({"type": "status", "id": pkg_id, "state": state,
                    "pct": pct, "detail": detail})

    def _push_queue(self):
        with self._lock:
            order = [dict(item) for item in self._queue]
        self._emit({"type": "queue", "items": order})

    def _set(self, pkg_id, state):
        with self._lock:
            for item in self._queue:
                if item["id"] == pkg_id:
                    item["state"] = state
                    break

    # -- queries ---------------------------------------------------------
    def probe(self):
        """Report whether the winget engine is usable, and at what version."""
        try:
            code, out = _run(["winget", "--version"], timeout=30)
            version = out.strip().splitlines()[0].strip() if out.strip() else ""
            ok = code == 0 and version.startswith("v")
            return {"available": ok, "version": version,
                    "elevated": is_elevated()}
        except FileNotFoundError:
            return {"available": False, "version": "",
                    "elevated": is_elevated(),
                    "error": "winget was not found on PATH. Install 'App Installer' "
                             "from the Microsoft Store."}
        except Exception as exc:
            return {"available": False, "version": "", "elevated": is_elevated(),
                    "error": str(exc)}

    def list_installed(self):
        """Map every installed package id to its version and pending upgrade.

        Returns {id_lower: {"version": str, "available": str}} so cards can show
        a real version chip instead of a placeholder.
        """
        try:
            _, out = _run(
                ["winget", "list", "--accept-source-agreements"], timeout=180)
        except Exception as exc:
            self._log(f"Could not read installed packages: {exc}", "err")
            return {}

        found = {}
        for row in _parse_table(out):
            key = row["id"].lower()
            # A package can appear twice (e.g. two 7-Zip builds); keep the first.
            found.setdefault(key, {
                "version": row.get("version", ""),
                "available": row.get("available", ""),
            })
        return found

    def search(self, query, limit=40):
        """Query the full winget repository and shape results like catalog cards."""
        query = (query or "").strip()
        if len(query) < 2:
            return []
        try:
            _, out = _run(
                ["winget", "search", query, "--accept-source-agreements",
                 "--count", str(limit)],
                timeout=90,
            )
        except Exception as exc:
            self._log(f"Search failed: {exc}", "err")
            return []

        results = []
        for row in _parse_table(out):
            pkg_id = row["id"]
            source = (row.get("source") or "winget").strip() or "winget"
            results.append({
                "id": pkg_id,
                "name": row.get("name") or pkg_id,
                "publisher": _publisher_of(pkg_id),
                "category": "search",
                "desc": f"Package from the {source} repository.",
                "size": 0,
                "color": _tint(pkg_id),
                "hue": "#5b8cff" if source == "winget" else "#ffb020",
                "mark": _mark(row.get("name") or pkg_id),
                "version": row.get("version", ""),
                "source": source,
            })
        return results

    # -- install queue ---------------------------------------------------
    def is_busy(self):
        return self._worker is not None and self._worker.is_alive()

    def snapshot(self):
        with self._lock:
            return [dict(item) for item in self._queue]

    def start_queue(self, pkg_ids):
        """Seed the queue and start the worker. winget takes a global machine
        lock, so packages are installed strictly one at a time."""
        with self._lock:
            if self.is_busy():
                return {"ok": False, "error": "An install run is already active."}
            pkg_ids = [p for p in dict.fromkeys(pkg_ids) if p]
            if not pkg_ids:
                return {"ok": False, "error": "Nothing selected."}
            self._cancel.clear()
            self._pause.clear()
            self._queue = [{"id": p, "state": "queued"} for p in pkg_ids]

        for item in pkg_ids:
            self._status(item, "queued", 0, "Waiting in queue")
        self._push_queue()
        self._spawn()
        return {"ok": True, "count": len(pkg_ids)}

    def _spawn(self):
        self._worker = threading.Thread(target=self._run_queue, daemon=True)
        self._worker.start()

    def pause(self):
        """Stop after the package currently installing. Nothing is killed."""
        self._pause.set()
        return {"ok": True}

    def resume(self):
        """Restart the worker after a pause, or after an item was requeued."""
        with self._lock:
            self._pause.clear()
            if self.is_busy():
                return {"ok": True, "already": True}
            pending = any(i["state"] == "queued" for i in self._queue)
            if not pending:
                return {"ok": False, "error": "Nothing left to install."}
            self._cancel.clear()
        self._spawn()
        return {"ok": True}

    def move(self, pkg_id, delta):
        """Reorder a still-pending entry. Items already past 'queued' are fixed."""
        with self._lock:
            idx = next((i for i, x in enumerate(self._queue)
                        if x["id"] == pkg_id), -1)
            j = idx + delta
            if idx < 0 or j < 0 or j >= len(self._queue):
                return {"ok": False}
            if self._queue[idx]["state"] != "queued" or \
               self._queue[j]["state"] != "queued":
                return {"ok": False}
            self._queue[idx], self._queue[j] = self._queue[j], self._queue[idx]
        self._push_queue()
        return {"ok": True}

    def skip(self, pkg_id):
        """Drop a pending package from the run without touching the machine."""
        with self._lock:
            for item in self._queue:
                if item["id"] == pkg_id and item["state"] == "queued":
                    item["state"] = "skipped"
                    break
            else:
                return {"ok": False}
        self._status(pkg_id, "skipped", 0, "Cancelled before download")
        self._push_queue()
        return {"ok": True}

    def requeue(self, pkg_id):
        """Put a failed or skipped package back in line and resume the worker."""
        with self._lock:
            for item in self._queue:
                if item["id"] == pkg_id and item["state"] in ("failed", "skipped"):
                    item["state"] = "queued"
                    break
            else:
                return {"ok": False}
        self._status(pkg_id, "queued", 0, "Waiting in queue")
        self._push_queue()
        return self.resume()

    def cancel(self):
        """Ask the run to stop, and kill whatever winget is doing right now."""
        self._cancel.set()
        proc = self._proc
        if proc and proc.poll() is None:
            try:
                # taskkill /T reaches the installer children winget spawned.
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL,
                               creationflags=CREATE_NO_WINDOW)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        return {"ok": True}

    def _next_pending(self):
        with self._lock:
            for item in self._queue:
                if item["state"] == "queued":
                    return item["id"]
        return None

    def _run_queue(self):
        while not self._cancel.is_set() and not self._pause.is_set():
            pkg_id = self._next_pending()
            if pkg_id is None:
                break
            self._set(pkg_id, "running")
            self._push_queue()
            state = self._install_one(pkg_id)
            self._set(pkg_id, state)
            self._push_queue()

        snap = self.snapshot()
        summary = {
            "installed": sum(1 for i in snap if i["state"] == "installed"),
            "failed": sum(1 for i in snap if i["state"] == "failed"),
            "skipped": sum(1 for i in snap if i["state"] == "skipped"),
            "pending": sum(1 for i in snap if i["state"] == "queued"),
        }
        paused = (self._pause.is_set() or self._cancel.is_set()) \
            and summary["pending"] > 0
        self._emit({"type": "queue_done", "summary": summary, "paused": paused})
        self._log(
            f"Run {'paused' if paused else 'finished'} - "
            f"{summary['installed']} installed, {summary['failed']} failed, "
            f"{summary['skipped']} skipped.", "sys")

    def _install_one(self, pkg_id):
        args = [
            "winget", "install", "--id", pkg_id, "-e",
            "--silent",
            "--accept-package-agreements",
            "--accept-source-agreements",
            "--disable-interactivity",
        ]
        self._log("> " + " ".join(args), "cmd")
        self._status(pkg_id, "downloading", 0, "Starting")

        try:
            self._proc = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                creationflags=CREATE_NO_WINDOW,
                bufsize=0,
            )
        except FileNotFoundError:
            self._status(pkg_id, "failed", None, "winget not found")
            self._log("winget is not available on PATH.", "err")
            return "failed"

        saw_success = False
        saw_already = False
        reason = ""
        phase = "downloading"
        buf = b""

        def absorb(res):
            nonlocal saw_success, saw_already, reason, phase
            phase = res["phase"]
            saw_success = saw_success or res["success"]
            saw_already = saw_already or res["already"]
            reason = res["reason"] or reason

        while True:
            chunk = self._proc.stdout.read(1)
            if not chunk:
                break
            if _SPLIT.match(chunk):
                line, buf = buf.decode("utf-8", "replace"), b""
                absorb(self._consume(pkg_id, line, phase))
            else:
                buf += chunk

        if buf:
            absorb(self._consume(pkg_id, buf.decode("utf-8", "replace"), phase))

        code = _hresult(self._proc.wait())
        self._proc = None

        if self._cancel.is_set():
            self._status(pkg_id, "skipped", None, "Run cancelled")
            return "skipped"

        if saw_already:
            self._status(pkg_id, "installed", 100, "Already up to date")
            self._log(f"{pkg_id} is already installed.", "sys")
            return "installed"

        if code in _SOFT_SUCCESS or saw_success:
            detail = _EXIT_HINTS.get(code, "Complete")
            self._status(pkg_id, "installed", 100, detail)
            self._log(f"{pkg_id} installed successfully.", "ok")
            return "installed"

        # Prefer, in order: a code we know for certain, winget's own words,
        # then the bare code. Only mention elevation when it is really implicated.
        detail = _EXIT_HINTS.get(code) or reason or ("Exit code 0x%08X" % code)
        if not is_elevated() and _needs_admin(code, reason):
            detail += " Relaunch as administrator and retry."
        self._status(pkg_id, "failed", None, detail)
        self._log(f"{pkg_id} failed: {detail}", "err")
        return "failed"

    def _consume(self, pkg_id, raw, phase):
        """Interpret one winget output fragment; returns updated parse state."""
        line = raw.translate(_NOISE).strip()
        success = already = False
        reason = ""

        if line:
            low = line.lower()
            if "already installed" in low or "no available upgrade" in low:
                already = True
            if "successfully installed" in low:
                success = True
            if any(m in low for m in _ERROR_MARKERS):
                reason = line[:160]

            # winget verifies the installer hash between download and install.
            if "installer hash" in low and "verified" in low:
                phase = "verifying"
                self._status(pkg_id, "verifying", 100, "Installer hash verified")
            elif "starting package install" in low:
                phase = "installing"
                self._status(pkg_id, "installing", None, "Running installer")
            elif low.startswith("found "):
                self._status(pkg_id, "downloading", 0, line[:70])

            # Progress fragments are high-frequency; keep them out of the log.
            if not _BYTES.search(line):
                self._log(line, "out")

        match = _BYTES.search(raw)
        if match and phase == "downloading":
            got = float(match.group(1)) * _UNIT[match.group(2).upper()]
            total = float(match.group(3)) * _UNIT[match.group(4).upper()]
            if total > 0:
                pct = max(0, min(100, round(got / total * 100)))
                self._status(pkg_id, "downloading", pct,
                             f"{match.group(1)} {match.group(2)} / "
                             f"{match.group(3)} {match.group(4)}")

        return {"phase": phase, "success": success, "already": already,
                "reason": reason}


def _needs_admin(code, reason):
    """True only when the failure genuinely points at missing elevation."""
    if code in (0x80070005, 1602):
        return True
    low = (reason or "").lower()
    return "access is denied" in low or "requires administrator" in low


_TINTS = ["#ff5c1a", "#5b8cff", "#3ddc84", "#ffb020", "#ef6853",
          "#8A2BE2", "#0F8CE9", "#F5A623", "#2496ED", "#539E43"]


def _tint(seed):
    return _TINTS[sum(ord(c) for c in seed) % len(_TINTS)]


def _publisher_of(pkg_id):
    """winget search does not return a publisher column; the id's namespace is
    the next best thing (Google.Chrome -> Google)."""
    head = pkg_id.split(".")[0]
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", head) or "Unknown"


def _mark(name):
    parts = [p for p in re.split(r"[\s.\-_]+", name) if p]
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    return (parts[0][:2] if parts else "?").upper()
