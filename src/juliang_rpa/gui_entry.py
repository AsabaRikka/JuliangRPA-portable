from __future__ import annotations

from pathlib import Path
import sys
import traceback


if __name__ == "__main__":
    try:
        from juliang_rpa.gui import main

        main()
    except Exception:  # noqa: BLE001 - startup failures must be visible for packaged builds.
        root = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path.cwd()
        (root / "startup_error.log").write_text(traceback.format_exc(), encoding="utf-8")
        raise
