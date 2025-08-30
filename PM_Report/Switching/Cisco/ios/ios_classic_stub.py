# Switching/Cisco/ios/ios_classic_stub.py
from __future__ import annotations
from typing import Dict
import Cisco_IOS_XE as XE  # reuse placeholder shape for consistency

def parse_file_ios(path: str) -> Dict:
    row = XE._placeholder_entry(path, reason_text="IOS Classic (stub)")
    row["Remark"] = ["IOS Classic detected (stub parser)"]
    return row
