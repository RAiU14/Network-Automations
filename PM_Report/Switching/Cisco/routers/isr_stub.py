# Switching/Cisco/routers/isr_stub.py
from __future__ import annotations
from typing import Dict
import Cisco_IOS_XE as XE

def parse_file_isr(path: str) -> Dict:
    row = XE._placeholder_entry(path, reason_text="IOS-XE ISR (stub)")
    row["Remark"] = ["IOS-XE ISR detected (stub parser)"]
    return row
