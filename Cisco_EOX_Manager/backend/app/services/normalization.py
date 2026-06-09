from __future__ import annotations

import re
from collections.abc import Iterable


def normalize_pid(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "").strip().upper())


def clean_pid_list(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items or []:
        pid = str(item).strip()
        normalized = normalize_pid(pid)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        output.append(pid)
    return output


def mask_secret(value: str | None, visible: int = 4) -> str | None:
    if not value:
        return None
    if len(value) <= visible:
        return "*" * len(value)
    return f"{'*' * max(4, len(value) - visible)}{value[-visible:]}"
