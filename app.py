"""Forge Setup - a visual batch installer for the Windows Package Manager.

A native Windows window (Edge WebView2 via pywebview) driving the `winget`
CLI in background threads. Run with:  python app.py
"""

import json
import os
import sys
import threading

if sys.platform != "win32":
    sys.exit("Forge Setup targets Windows: winget is a Windows-only tool.")

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

    def install(self, ids):
        return self._engine.start_queue(list(ids or []))

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
        "Forge Setup - winget batch installer",
        INDEX,
        js_api=api,
        width=1400,
        height=940,
        min_size=(1040, 700),
        background_color="#08080a",
        text_select=False,
    )
    webview.start(gui="edgechromium", debug="--debug" in sys.argv)


if __name__ == "__main__":
    main()
