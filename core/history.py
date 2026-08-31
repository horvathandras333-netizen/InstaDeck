"""Small, local-only install history store."""

import json
import os
from pathlib import Path


def _path(app_name="InstaDeck"):
    root = Path(os.environ.get("LOCALAPPDATA", Path.home())) / app_name
    return root / "history.json"


def read():
    try:
        data = json.loads(_path().read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except (OSError, ValueError):
        pass
    try:
        data = json.loads(_path("Forge Setup").read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def append(entry):
    items = read()
    items.insert(0, entry)
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items[:60], indent=2), encoding="utf-8")
