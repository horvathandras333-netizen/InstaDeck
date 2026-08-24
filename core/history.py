"""Small, local-only install history store."""

import json
import os
from pathlib import Path


def _path():
    root = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Forge Setup"
    return root / "history.json"


def read():
    try:
        data = json.loads(_path().read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def append(entry):
    items = read()
    items.insert(0, entry)
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items[:60], indent=2), encoding="utf-8")
