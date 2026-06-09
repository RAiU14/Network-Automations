#!/usr/bin/env python3
"""Compatibility wrapper for the fixed Cisco EOX Manager Auto_Pop exporter.

The maintained Auto_Pop workflow now lives at:
    Cisco_EOX_Manager/tools/auto_pop_pid_database.py

Examples:
    python Database/auto_pop.py --output Cisco_EOX_Manager/data/presets/eox_pid_seed.json
    python Database/auto_pop.py --limit-categories 2
    python Database/auto_pop.py --crawl-eox
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL = REPO_ROOT / "Cisco_EOX_Manager" / "tools" / "auto_pop_pid_database.py"

if not TOOL.exists():
    raise SystemExit(f"Auto_Pop tool not found: {TOOL}")

# Default to the product preset path when the caller does not specify --output.
if "--output" not in sys.argv:
    sys.argv.extend(["--output", str(REPO_ROOT / "Cisco_EOX_Manager" / "data" / "presets" / "eox_pid_seed.json")])

sys.argv[0] = str(TOOL)
runpy.run_path(str(TOOL), run_name="__main__")
