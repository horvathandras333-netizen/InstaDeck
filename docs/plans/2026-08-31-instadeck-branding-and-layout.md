# InstaDeck Branding and Layout Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rename Forge Setup to InstaDeck, give it a functional modern-utility window chrome, and ensure card metadata never leaves a card.

**Architecture:** Make the pywebview window frameless and expose guarded native minimise/close methods through the existing `Api` bridge. The web layer owns the bespoke title bar and designated drag region. Card metadata wraps inside its available flex column, and an available upgrade supersedes the redundant installed badge.

**Tech Stack:** Python 3, pywebview EdgeChromium, vanilla HTML/CSS/JavaScript, PyInstaller, Inno Setup, `unittest`.

---

### Task 1: Capture the UI and window-contract regression tests

**Files:**
- Create: `tests/test_ui_contract.py`
- Test: `tests/test_ui_contract.py`

**Step 1: Write failing tests**

Add source-contract tests asserting the metadata row wraps, the upgrade branch does not append an Installed chip, the custom controls are present and wired, and the window is frameless with native minimise/close API methods.

**Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_ui_contract -v`

Expected: failures for missing custom controls, wrapping, and native window methods.

**Step 3: Implement the minimal UI and API contracts**

Implement the title bar, CSS, bridge methods, and card metadata conditions in Tasks 2–3.

**Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_ui_contract -v`

Expected: all tests pass.

### Task 2: Implement the custom InstaDeck window chrome

**Files:**
- Modify: `app.py`
- Modify: `web/index.html`
- Modify: `web/styles.css`
- Modify: `web/app.js`

**Step 1: Expose native controls**

Add `Api.window_minimize()` and `Api.window_close()` methods that safely act only when the window is ready. Create the pywebview window with `frameless=True`, `easy_drag=False`, and a Windows shadow.

**Step 2: Build the title bar**

Use an InstaDeck geometric mark, product/subtitle identity, engine status, theme toggle, and labelled accessible minimise/close buttons. Assign only the empty header area the `pywebview-drag-region` class.

**Step 3: Style and wire it**

Use a compact 44px modern-utility bar, visible focus/hover states, and an alert-red close state. Wire controls via the existing async bridge without propagating drag events through buttons.

### Task 3: Fix card metadata containment

**Files:**
- Modify: `web/app.js`
- Modify: `web/styles.css`

**Step 1: Remove redundant chip state**

For an upgradeable installed application, emit `Update v…` only; otherwise emit `Installed`.

**Step 2: Permit metadata to reflow**

Set the metadata line to wrap with row/column gaps and constrain it to its card flex column. Preserve no-wrap inside individual chips so each badge remains readable.

### Task 4: Rename product and build artifacts

**Files:**
- Rename: `ForgeSetup.spec` to `InstaDeck.spec`
- Rename: `ForgeSetup.iss` to `InstaDeck.iss`
- Modify: `app.py`, `README.md`, `build.bat`, `build-installer.bat`, `run-dev.bat`, `core/history.py`, `web/icons/README.md`

**Step 1: Rename outward-facing identifiers**

Use InstaDeck in titles, application data folders, profile labels/formats/extensions, share scheme, executable name, installer name, and documentation.

**Step 2: Preserve old user data**

Read legacy `forge://` links, `.forge.json` files, and local-storage keys in addition to the InstaDeck names. Write only new InstaDeck forms.

### Task 5: Verify

**Files:**
- Test: `tests/test_ui_contract.py`

**Step 1: Run regression tests**

Run: `python -m unittest tests.test_ui_contract -v`

**Step 2: Run syntax and packaging checks**

Run: `python -m py_compile app.py core/*.py` and `node --check web/app.js`.

**Step 3: Inspect changes**

Run: `git diff --check` and `git diff --stat`.

**Step 4: Build if local toolchain is available**

Run: `build.bat` and record the resulting executable name; do not run the generated installer.
