"""InstaDeck - a visual batch installer for the Windows Package Manager.

A native Windows window (Edge WebView2 via pywebview) driving the `winget`
CLI in background threads. Run with:  python app.py
"""

import json
import os
import sys
import threading
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone

if sys.platform != "win32":
    sys.exit("InstaDeck targets Windows: winget is a Windows-only tool.")

try:
    import webview
except ImportError:
    sys.exit(
        "pywebview is required.\n"
        "    pip install pywebview\n"
        f"(current interpreter: {sys.executable})"
    )

from core import catalog, winget
from core.winget import WingetEngine

# When frozen by PyInstaller the web assets are unpacked next to the bootloader
# stub in sys._MEIPASS, not beside the script.
HERE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(HERE, "web", "index.html")


# Native resize support for the otherwise borderless WinForms host. Returning
# the standard hit-test values lets Windows own the live resize loop.
WM_NCHITTEST = 0x0084
GWLP_WNDPROC = -4
GWL_STYLE = -16
WS_THICKFRAME = 0x00040000
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_FRAMECHANGED = 0x0020
HTLEFT, HTRIGHT, HTTOP, HTTOPLEFT = 10, 11, 12, 13
HTTOPRIGHT, HTBOTTOM, HTBOTTOMLEFT, HTBOTTOMRIGHT = 14, 15, 16, 17
LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, ctypes.c_uint,
                             ctypes.c_size_t, ctypes.c_ssize_t)


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


_native_resize_hooks = []  # Keep callback references alive for the window life.


def _install_native_resize(window):
    """Give the frameless Windows form normal edge and corner resize behaviour."""
    hwnd = int(window.native.Handle.ToInt64())
    user32 = ctypes.windll.user32
    user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
    user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
    user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
    user32.CallWindowProcW.argtypes = [ctypes.c_ssize_t, wintypes.HWND,
                                       ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
    user32.CallWindowProcW.restype = LRESULT

    original = user32.GetWindowLongPtrW(hwnd, GWLP_WNDPROC)
    style = user32.GetWindowLongPtrW(hwnd, GWL_STYLE)
    user32.SetWindowLongPtrW(hwnd, GWL_STYLE, style | WS_THICKFRAME)
    user32.SetWindowPos(hwnd, None, 0, 0, 0, 0,
                         SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_FRAMECHANGED)

    @WNDPROC
    def resize_wndproc(handle, message, w_param, l_param):
        if message == WM_NCHITTEST:
            rect = RECT()
            user32.GetWindowRect(handle, ctypes.byref(rect))
            x = ctypes.c_short(l_param & 0xFFFF).value
            y = ctypes.c_short((l_param >> 16) & 0xFFFF).value
            border = 8
            left = x < rect.left + border
            right = x >= rect.right - border
            top = y < rect.top + border
            bottom = y >= rect.bottom - border
            if top and left:
                return HTTOPLEFT
            if top and right:
                return HTTOPRIGHT
            if bottom and left:
                return HTBOTTOMLEFT
            if bottom and right:
                return HTBOTTOMRIGHT
            if left:
                return HTLEFT
            if right:
                return HTRIGHT
            if top:
                return HTTOP
            if bottom:
                return HTBOTTOM
        return user32.CallWindowProcW(original, handle, message, w_param, l_param)

    user32.SetWindowLongPtrW(hwnd, GWLP_WNDPROC,
                              ctypes.cast(resize_wndproc, ctypes.c_void_p).value)
    _native_resize_hooks.append((original, resize_wndproc))


class Api:
    """Every method here is callable from JavaScript as pywebview.api.<name>().

    pywebview serves these over a threaded local endpoint, so a slow call
    (a repository search, a full installed-package scan) never blocks the UI.
    """

    def __init__(self):
        self._window = None
        self._engine = WingetEngine(self._push)
        self._engine_info = None
        self._push_lock = threading.Lock()

    # -- Python -> JS ----------------------------------------------------
    def _push(self, event):
        """Hand one engine event to the frontend."""
        if not self._window:
            return
        payload = json.dumps(event, ensure_ascii=False)
        with self._push_lock:
            try:
                self._window.evaluate_js(f"window.__push({payload})")
            except Exception:
                # The window can go away mid-run; a dropped event is not fatal.
                pass

    # -- JS -> Python ----------------------------------------------------
    def bootstrap(self):
        """Catalog, categories, presets and engine status in one round trip."""
        if self._engine_info is None:
            self._engine_info = self._engine.probe()
        return {
            "apps": catalog.APPS,
            "categories": catalog.CATEGORIES,
            "presets": catalog.PRESETS,
            "legend": catalog.LEGEND,
            "engine": self._engine_info,
            "system": winget.system_info(),
        }

    def installed(self):
        return self._engine.list_installed()

    def search(self, query):
        return self._engine.search(query)

    def install(self, ids, completion=None):
        return self._engine.start_queue(list(ids or []), "install", completion)

    def upgrade(self, ids, completion=None):
        return self._engine.start_queue(list(ids or []), "upgrade", completion)

    def preflight(self, ids, estimated_mb=0, operation="install"):
        return self._engine.preflight(list(ids or []), estimated_mb, operation)

    def history(self):
        return self._engine.history()

    def window_minimize(self):
        """Minimise the custom-framed application window."""
        if self._window:
            self._window.minimize()
        return {"ok": bool(self._window)}

    def window_close(self):
        """Close the custom-framed application window."""
        if self._window:
            self._window.destroy()
        return {"ok": bool(self._window)}

    def export_profile(self, name, ids):
        if not self._window:
            return {"ok": False, "error": "Window is not ready."}
        safe_name = "".join(c for c in str(name or "InstaDeck profile") if c.isalnum() or c in " -_").strip() or "InstaDeck profile"
        path = self._window.create_file_dialog(
            webview.SAVE_DIALOG,
            save_filename=f"{safe_name}.instadeck.json",
            file_types=("InstaDeck profiles (*.instadeck.json;*.forge.json)", "JSON files (*.json)"),
        )
        if not path:
            return {"ok": False, "cancelled": True}
        payload = {"format": "instadeck-profile/v1", "name": safe_name,
                   "created_at": datetime.now(timezone.utc).isoformat(),
                   "apps": [str(item) for item in (ids or []) if item]}
        try:
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
            return {"ok": True, "path": path, "count": len(payload["apps"])}
        except OSError as exc:
            return {"ok": False, "error": str(exc)}

    def import_profile(self):
        if not self._window:
            return {"ok": False, "error": "Window is not ready."}
        paths = self._window.create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=False,
            file_types=("InstaDeck profiles (*.instadeck.json;*.forge.json;*.json)",),
        )
        if not paths:
            return {"ok": False, "cancelled": True}
        path = paths[0] if isinstance(paths, (list, tuple)) else paths
        try:
            with open(path, encoding="utf-8") as handle:
                payload = json.load(handle)
            apps = payload.get("apps", [])
            if not isinstance(apps, list) or not all(isinstance(app, str) for app in apps):
                raise ValueError("This is not a valid InstaDeck profile.")
            return {"ok": True, "name": payload.get("name") or "Imported profile", "apps": apps}
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return {"ok": False, "error": str(exc)}

    def cancel(self):
        return self._engine.cancel()

    # -- queue control ---------------------------------------------------
    def queue_move(self, pkg_id, delta):
        return self._engine.move(pkg_id, int(delta))

    def queue_skip(self, pkg_id):
        return self._engine.skip(pkg_id)

    def queue_requeue(self, pkg_id):
        return self._engine.requeue(pkg_id)

    def queue_resume(self):
        return self._engine.resume()

    def queue_pause(self):
        return self._engine.pause()


def main():
    if not os.path.exists(INDEX):
        sys.exit(f"UI assets are missing: {INDEX}")

    api = Api()
    api._window = webview.create_window(
        "InstaDeck - winget batch installer",
        INDEX,
        js_api=api,
        width=1400,
        height=940,
        min_size=(1040, 700),
        frameless=True,
        easy_drag=False,
        shadow=True,
        background_color="#08080a",
        text_select=False,
    )
    api._window.events.shown += _install_native_resize
    webview.start(gui="edgechromium", debug="--debug" in sys.argv)


if __name__ == "__main__":
    main()
