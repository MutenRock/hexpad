"""
Auto-bootstrap HexPad local config.

Python imports `sitecustomize` automatically at startup when this file is on the
import path. Keeping this tiny hook at repository root lets `python gui.py` work
on a fresh clone even though `config.json` is intentionally git-ignored.
"""
from pathlib import Path

try:
    from modules.config_defaults import ensure_local_config

    root = Path.cwd()
    # Only act inside the HexPad project root.
    if (root / "gui.py").exists():
        ensure_local_config(root, silent=True)
except Exception:
    # Never block Python startup. gui.py will still show its own config error if
    # something is seriously wrong.
    pass
