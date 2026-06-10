#!/usr/bin/env python3
from __future__ import annotations

import runpy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL = REPO_ROOT / "Cisco_EOX_Manager" / "tools" / "auto_pop_pid_database.py"

if not TOOL.exists():
    raise SystemExit(f"Auto_Pop tool not found: {TOOL}")

sys.argv[0] = str(TOOL)
runpy.run_path(str(TOOL), run_name="__main__")
