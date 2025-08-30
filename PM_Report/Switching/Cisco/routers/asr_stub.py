# Switching/Cisco/routers/asr_stub.py
from __future__ import annotations
from typing import Dict
import Cisco_IOS_XE as XE

def parse_file_asr(path: str) -> Dict:
    row = XE._placeholder_entry(path, reason_text="IOS-XE ASR (stub)")
    row["Remark"] = ["IOS-XE ASR detected (stub parser)"]
    return row
