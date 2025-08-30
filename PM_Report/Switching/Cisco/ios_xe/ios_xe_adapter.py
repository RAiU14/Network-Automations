# Switching/Cisco/ios_xe/ios_xe_adapter.py
from __future__ import annotations
from typing import Dict
import Cisco_IOS_XE as XE  # reuse your hardened XE parser as-is

def parse_file_xe(path: str) -> Dict:
    """
    Thin adapter around your existing IOS-XE parser.
    Always returns a one-device row dict (or a placeholder on failure).
    """
    try:
        row = XE.process_file(path)
        if isinstance(row, dict) and row:
            return row
        # If the XE parser returned nothing, still emit a row to keep pipeline stable
        bad = XE._placeholder_entry(path, reason_text="XE parse returned empty")
        bad["Remark"] = ["XE adapter: empty result"]
        return bad
    except Exception:
        bad = XE._placeholder_entry(path, reason_text="XE adapter exception")
        bad["Remark"] = ["XE adapter: exception while parsing"]
        return bad
