# platform_detect.py
from __future__ import annotations
import os, re
from typing import Any, Dict, Optional, Tuple

# ---------- SIGNALS ----------
SIG_POS = {
    "IOS_XE": [
        r"\bcisco\s+ios\s+xe\s+software\b",
        r"\bios-?xe\b",
        r"\bpackages\.conf\b",
        r"\bcat9k\w*iosxe\b",
        r"\bsmart licensing using policy\b",
    ],
    "IOS_CLASSIC": [
        r"\bcisco\s+ios\s+software\b",
        r"\bflash:\S+\.bin\b",
    ],
    "IOS_XE_ROUTER_ISR": [
        r"\bisr\s?4\d{2,3}\b",
        r"\bisr\s?1\d{2,3}\b",
    ],
    "IOS_XE_ROUTER_ASR": [
        r"\basr\s?100\d\b",
        r"\basr1k\b",
    ],
}

SIG_NEG = [
    r"\bnx-os\b",
    r"\badaptive\s+security\s+appliance\b",
    r"\basa\s+software\b",
]

HINT_SWITCH = [
    r"\bcat9k(_lite)?\b",
    r"\bC9\d{3}\b",
    r"\bcatalyst\s+9\d{3}\b",
]
HINT_ROUTER = [
    r"\basr\s?100\d\b",
    r"\bisr\s?(1|4)\d{2,3}\b",
]

_VERSION = re.compile(
    r"(?mi)^\s*(?:Cisco IOS(?: XE)? Software.*?\bVersion\s+([^\s,]+)"
    r"|Cisco IOS XE Software,\s*Version\s+([^\s,]+))"
)

def _score_patterns(text: str, pats: list[str], weight: float) -> Tuple[float, list[str]]:
    hits, ev = 0.0, []
    for p in pats:
        if re.search(p, text, flags=re.IGNORECASE):
            hits += 1.0
            ev.append(p)
    return hits * weight, ev

def _extract_version(text: str) -> Tuple[Optional[str], Optional[str]]:
    m = _VERSION.search(text or "")
    if not m:
        return None, None
    raw = (m.group(1) or m.group(2) or "").strip()
    mj = None
    k = re.match(r"\s*(\d{1,2})", raw)
    if k:
        mj = k.group(1).zfill(2)
    return raw, mj

def detect_family(text: str, filename: Optional[str] = None) -> Dict[str, Any]:
    t = text or ""
    ev: Dict[str, Any] = {"filename": filename}
    evidence_hits: Dict[str, list[str]] = {}

    # anti-signals
    for n in SIG_NEG:
        if re.search(n, t, flags=re.IGNORECASE):
            ev["why"] = "Negative signature matched (NX-OS/ASA)."
            return {"family": "UNKNOWN", "confidence": 1.0, "version_raw": None,
                    "version_major": None, "evidence": ev}

    # base scores
    scores = {"IOS_XE": 0.0, "IOS_CLASSIC": 0.0,
              "IOS_XE_ROUTER_ISR": 0.0, "IOS_XE_ROUTER_ASR": 0.0}

    # strong signatures
    for fam, pats in SIG_POS.items():
        s, hits = _score_patterns(t, pats, weight=2.0)
        scores[fam] += s
        if hits:
            evidence_hits[fam] = hits

    # contextual nudges
    sw_score, _ = _score_patterns(t, HINT_SWITCH, weight=0.5)
    rt_score, _ = _score_patterns(t, HINT_ROUTER, weight=0.5)
    scores["IOS_XE"] += sw_score
    scores["IOS_XE_ROUTER_ISR"] += rt_score
    scores["IOS_XE_ROUTER_ASR"] += rt_score

    # encourage XE switching for majors 16/17
    ver_raw, ver_maj = _extract_version(t)
    if ver_maj in {"16", "17"}:
        scores["IOS_XE"] += 0.75

    # pick best
    fam, best = max(scores.items(), key=lambda kv: kv[1])

    final_family = fam
    if fam == "IOS_XE":
        final_family = "IOS_XE_SWITCH"  # default to switching for XE
        if scores["IOS_XE_ROUTER_ISR"] > scores["IOS_XE"] + 0.25:
            final_family = "IOS_XE_ROUTER_ISR"
        elif scores["IOS_XE_ROUTER_ASR"] > scores["IOS_XE"] + 0.25:
            final_family = "IOS_XE_ROUTER_ASR"

    conf = max(0.0, min(1.0, best / 3.0))  # squash to 0..1

    ev.update({
        "why": f"Scores={scores}",
        "hits": evidence_hits,
        "version_line": ver_raw,
    })
    return {"family": final_family, "confidence": conf,
            "version_raw": ver_raw, "version_major": ver_maj,
            "evidence": ev}

def detect_family_from_file(path: str) -> Dict[str, Any]:
    try:
        if not path or not os.path.exists(path):
            return {"family": "UNKNOWN", "confidence": 0.0, "version_raw": None,
                    "version_major": None, "evidence": {"why": "File not found", "filename": path}}
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            txt = f.read()
        return detect_family(txt, filename=os.path.basename(path))
    except Exception as e:
        return {"family": "UNKNOWN", "confidence": 0.0, "version_raw": None,
                "version_major": None, "evidence": {"why": f"Error opening/parsing file: {e}", "filename": path}}