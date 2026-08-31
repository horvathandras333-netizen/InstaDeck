"""Regression contracts for InstaDeck's desktop window and card layout."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


def source(path):
    return (ROOT / path).read_text(encoding="utf-8")


class UiContractTests(unittest.TestCase):
    def test_card_metadata_wraps_inside_its_flex_column(self):
        css = source("web/styles.css")
        self.assertRegex(css, r"\.card-meta\s*\{[^}]*flex-wrap:\s*wrap")
        self.assertRegex(css, r"\.card-id\s*\{[^}]*min-width:\s*0")

    def test_upgrade_badge_replaces_the_installed_badge(self):
        js = source("web/app.js")
        self.assertRegex(
            js,
            r"if \(isUpgradeable\(app\.id\)\)\s*\{[\s\S]*?Update v[\s\S]*?\}\s*"
            r"else if \(installed\)",
        )

    def test_bulk_and_selected_updates_share_the_upgrade_queue(self):
        html = source("web/index.html")
        js = source("web/app.js")
        self.assertIn('id="updateAll"', html)
        self.assertIn("function upgradeableIds()", js)
        self.assertIn("Update all available apps?", js)
        self.assertIn("startRun(ids, 'upgrade')", js)
        self.assertIn("api(operation, ids, completion)", js)

    def test_custom_window_controls_are_present_and_wired(self):
        html = source("web/index.html")
        js = source("web/app.js")
        self.assertIn('id="windowMinimize"', html)
        self.assertIn('id="windowClose"', html)
        self.assertIn("api('window_minimize')", js)
        self.assertIn("api('window_close')", js)

    def test_titlebar_uses_the_app_logo_and_native_resize_hook(self):
        html = source("web/index.html")
        js = source("web/app.js")
        app = source("app.py")
        self.assertIn('src="app-icon.png"', html)
        self.assertNotIn('data-resize-edge="', html)
        self.assertNotIn("api('window_resize'", js)
        self.assertNotIn("def window_resize(self, width, height, anchor):", app)
        self.assertIn("WM_NCHITTEST", app)
        self.assertIn("SetWindowLongPtrW", app)
        self.assertIn("events.shown += _install_native_resize", app)

    def test_python_window_is_frameless_with_native_controls(self):
        app = source("app.py")
        self.assertIn("def window_minimize(self):", app)
        self.assertIn("def window_close(self):", app)
        self.assertRegex(app, r"frameless\s*=\s*True")
        self.assertRegex(app, r"easy_drag\s*=\s*False")


if __name__ == "__main__":
    unittest.main()
