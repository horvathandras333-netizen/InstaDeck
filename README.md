# Forge Setup

A visual batch installer for Windows that drives the Windows Package Manager
(`winget`) in the background. Pick packages from a curated catalog or search the
whole winget repository, then install them in one queued run with live progress,
reordering and per-package retry.

The interface implements the **Modernist** design system imported from the
Claude Design project *Windows installer UI mockup* (`Installer.dc.html`):
zero corner radius, 2px structural borders, hairline grid seams, Archivo
throughout, and a four-hue category legend over an electric-orange accent.

---

## Run it

**Portable — no install, no Python:**

```
dist\ForgeSetup.exe
```

One self-contained 15 MB file. Copy it anywhere — a USB stick, a fresh machine —
and double-click. It needs only `winget` (ships with Windows 11) and the Edge
WebView2 runtime (also preinstalled on Windows 11).

Right-click → **Run as administrator** to install machine-wide packages without
a UAC prompt per package. The sidebar's Target block shows whether you are
elevated.

**From source:**

```
run-dev.bat            (or:  python app.py  --debug for WebView2 devtools)
```

**Rebuild the portable file:**

```
build.bat              (or:  python -m PyInstaller ForgeSetup.spec --noconfirm)
```

### Interpreter note

Both `.bat` launchers prefer `%LOCALAPPDATA%\Programs\Python\Python310\python.exe`
if it exists and fall back to whatever `python` resolves to on `PATH`. Any
interpreter works as long as `pywebview` is installed into it — if your default
Python is newer than pywebview supports, install into an older one:

```
pip install -r requirements.txt
```

---

## Layout

```
app.py             pywebview window + the JS <-> Python bridge (class Api)
core/winget.py     all subprocess work: probe, list, search, install queue
core/catalog.py    45 curated packages, 7 categories, 5 bundles, hue legend
web/               index.html · styles.css · app.js · fonts/archivo.woff2
ForgeSetup.spec    PyInstaller recipe for the single-file build
app.ico            generated 6-resolution icon
```

---

## How it works

**Threading.** pywebview serves `Api` methods over a threaded local endpoint, so
a slow call (a repository search, a full installed-package scan) runs on its own
thread and never blocks the UI. Installs run on a worker thread that streams
events back through `Api._push` → `window.__push(event)` in JS.

**Why the queue is sequential.** winget takes a global machine lock; two
concurrent installs would only deadlock. The queue is a lock-guarded list and
the worker always pulls the first entry still marked `queued`, which is what
makes live reordering and skipping possible mid-run.

**Pause vs. abort.** *Pause queue* sets a flag so the worker stops after the
package currently installing — nothing is killed. *Abort* on the active row
terminates the running winget process and its installer children via
`taskkill /T`. Two different buttons because they are two different promises.

**Progress parsing.** winget rewrites its progress bar in place with carriage
returns, so `_install_one` reads the raw byte stream and splits on `\r` *and*
`\n` rather than reading lines. Percentages come from the `12.4 MB / 78.9 MB`
counter — the only progress signal winget emits once stdout is a pipe. The
`Verifying hash` state is real: it fires on winget's own
"Successfully verified installer hash" line, between download and install.

**Command used.**

```
winget install --id <AppID> -e --silent
               --accept-package-agreements --accept-source-agreements
               --disable-interactivity
```

**Installed detection.** One `winget list` call, parsed with column offsets taken
from the header row (package names contain single spaces, so splitting on
whitespace is unsafe), reduced to `{id: {version, available}}`. That is where the
version chips on installed cards come from.

**Failure reporting.** Exit codes are trusted only where unambiguous
(`0x8A150014` no package found, `0x80070005` access denied, MSI `1602/1603/1618`,
and `3010/1641` which mean success-pending-reboot). Otherwise the row shows
winget's own error line. The "relaunch as administrator" hint appears only when
the failure actually implicates elevation, never as a blanket guess.

---

## A note on "Official source"

The mockup labelled every package **Signed** or **Unsigned** and filtered on it.
winget does not expose installer signature status through its CLI, so presenting
one would have meant inventing a security claim in a security-adjacent filter.

What winget *does* tell you is the **source** a manifest came from. So the shield
row reports provenance instead:

- **Official source** — `winget` (the community repo, where manifests are
  reviewed and installer hashes are pinned) or `msstore`.
- **Third-party source** — any other repository added to the machine.

The integrity guarantee that *is* real — winget verifying the installer hash
against the manifest before running it — is surfaced as the `Verifying hash`
state in the install queue.

---

## Features beyond the catalog

- **Bundles** — five built-in (Fresh laptop, Gaming rig, Streaming rig, Dev box,
  Hardened) plus *+ Save selection*, which persists your own to `localStorage`.
  A bundle highlights when it exactly matches the current selection.
- **Share strings** — the selection encodes to `forge://Pkg.One+Pkg.Two`. Paste
  one in to restore it; already-installed packages are dropped on parse, the same
  rule card clicks and bundles follow.
- **Queue control** — reorder pending rows, cancel one before it downloads,
  retry a failure, requeue a skip, abort the active install.
- **Themes** — dark is the designed default; light is built from the design
  system's own light tokens (`#f3f2f2` / `#201e1d` / `#ec3013`). Persists to
  `localStorage` under `forge-theme`.

### Shortcuts

| Key | Action |
| --- | --- |
| `Ctrl` `F` | Focus search |
| `Esc` | Clear search |
| ``Ctrl` `` | Toggle the console |

---

## Design tokens

| Role | Dark | Light |
| --- | --- | --- |
| Accent | `#ff5c1a` | `#ec3013` |
| Page | `#08080a` | `#e2dfdf` |
| Window | `#0f0f11` | `#f8f4f4` |
| Rail / panel | `#0b0b0d` | `#f3f2f2` |
| Structural border (2px) | `#23232a` | `#c6c2c2` |
| Card | `#101014` | `#f8f4f4` |
| Text | `#f6f6f5` → `#5f5f68` | `#201e1d` → `#9b9797` |

Category hues are shared by both themes, because they *are* the legend:
blue `#5b8cff` browsers/dev · amber `#ffb020` media/security ·
green `#3ddc84` gaming · orange `#ff5c1a` utilities.

---

## Extending the catalog

Add an entry to `APPS` in [core/catalog.py](core/catalog.py):

```python
_app("Publisher.AppId", "App Name", "Publisher", "utils",
     "One-line description.", 120, "#2F67BA", "AB")
```

`120` is the approximate installer size in MB (used for the selection estimate)
and `"AB"` is the monogram on the tile. The category id picks up its hue
automatically. Bundles reference packages by winget id.
