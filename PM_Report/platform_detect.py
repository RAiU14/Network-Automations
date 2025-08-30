# platform_detect.py
from __future__ import annotations

import os
import re
from typing import Dict, Any, Optional

from logging_setup import configure_logging

logger = configure_logging(__name__)

# --- regex library ---------------------------------------------------------
_RE_VERSION = re.compile(
    r'(?mi)^\s*(?:Cisco IOS(?: XE)? Software.*?Version\s+([^\s,]+)|Cisco IOS XE Software,\s*Version\s+([^\s,]+))'
)
_SIG_IOS_XE = re.compile(r'(?i)\bios[- ]?xe\b')
_SIG_IOS    = re.compile(r'(?i)\bcisco\s+ios\s+software\b')
_SIG_NXOS   = re.compile(r'(?i)\bnx-os\b')
_SIG_ASA    = re.compile(r'(?i)\bAdaptive Security Appliance|ASA\s+Software\b')

# Hints (not exclusive, just boost scoring)
_HINTS = {
    "IOS_XE": [
        r'\bcisco\s+ios\s+xe\s+software\b',
        r'\bios-?xe\b',
        r'\bpackages\.conf\b',
        r'\bsmart licensing using policy\b',
        r'\bcat9k\w*iosxe\b',
        r'\bC9\d{2,}.*IOS[- ]?XE\b',
    ],
    "IOS_CLASSIC": [
        r'\bcisco\s+ios\s+software\b',
    ],
    "IOS_XE_ROUTER_ISR": [
        r'\bISR[ -]?(?:11|29|4\d{2,})\b',
        r'\bIntegrated Services Router\b',
    ],
    "IOS_XE_ROUTER_ASR": [
        r'\bASR\s?100\d\b',
        r'\bASR1K\b',
    ]
}


def _first_line(t: str) -> str:
    try:
        return t.strip().splitlines()[0][:200]
    except Exception:
        return ""


def _extract_version(text: str) -> Dict[str, Optional[str]]:
    m = _RE_VERSION.search(text or "")
    if not m:
        return {'raw': None, 'major': None, 'matched': None}
    raw = m.group(1) or m.group(2)
    mj = None
    if raw:
        k = re.match(r'\s*(\d{1,2})', raw)
        if k:
            mj = k.group(1).zfill(2)
    return {'raw': raw, 'major': mj, 'matched': m.group(0)}


def _score_family(text: str) -> Dict[str, float]:
    """
    Simple heuristic scorer:
      - Base scores from explicit signatures
      - Add boosts for hint hits
    """
    scores = {
        "IOS_XE": 0.0,
        "IOS_CLASSIC": 0.0,
        "IOS_XE_ROUTER_ISR": 0.0,
        "IOS_XE_ROUTER_ASR": 0.0,
        "UNKNOWN": 0.0,
    }

    # Signatures (higher weight)
    if _SIG_IOS_XE.search(text):
        scores["IOS_XE"] += 10.0
    if _SIG_IOS.search(text):
        scores["IOS_CLASSIC"] += 8.0
    if _SIG_NXOS.search(text):
        # Out of scope; keep UNKNOWN high to block other families
        scores["UNKNOWN"] += 12.0
    if _SIG_ASA.search(text):
        scores["UNKNOWN"] += 12.0

    # Hints (lower weight, accumulative)
    hits: Dict[str, list[str]] = {k: [] for k in _HINTS.keys()}
    for fam, patterns in _HINTS.items():
        for pat in patterns:
            if re.search(pat, text, flags=re.IGNORECASE | re.MULTILINE):
                scores[fam if fam in scores else "UNKNOWN"] += 1.25
                hits[fam].append(pat)

    logger.debug("Detection scores=%s", scores)
    logger.debug("Detection hits=%s", hits)
    return scores, hits


def detect_family(log_text: str, filename: Optional[str] = None) -> Dict[str, Any]:
    logger.info("platform_detect.detect_family: start filename=%s", filename)
    text = log_text or ""

    # quick out-of-scope
    if _SIG_NXOS.search(text):
        ev = {'filename': filename, 'why': 'NX-OS detected (out of scope)', 'version_line': None, 'hits': {}}
        logger.info("platform_detect: NX-OS signature found → UNKNOWN")
        return {'family': 'UNKNOWN', 'confidence': 1.0, 'version_raw': None, 'version_major': None, 'evidence': ev}

    if _SIG_ASA.search(text):
        ev = {'filename': filename, 'why': 'ASA detected (out of scope)', 'version_line': None, 'hits': {}}
        logger.info("platform_detect: ASA signature found → UNKNOWN")
        return {'family': 'UNKNOWN', 'confidence': 1.0, 'version_raw': None, 'version_major': None, 'evidence': ev}

    ver = _extract_version(text)
    logger.debug("platform_detect: version_raw=%s, version_major=%s, matched_line=%s",
                 ver['raw'], ver['major'], ver['matched'])

    scores, hits = _score_family(text)

    # Choose primary family bucket
    fam_choice = max(scores.keys(), key=lambda k: scores[k])
    fam_score = scores[fam_choice]
    total = sum(v for v in scores.values() if v > 0) or 1.0
    confidence = round(fam_score / total, 3)

    fam_final = 'UNKNOWN'
    why = f"Scores={scores}"
    # Refine the IOS-XE split (Switch vs Routers) based on extra hints + major
    if fam_choice == "IOS_XE":
        major = (ver['major'] or "").strip()
        if hits["IOS_XE_ROUTER_ASR"]:
            fam_final = 'IOS_XE_ROUTER_ASR'
            why = "IOS-XE + ASR hints"
        elif hits["IOS_XE_ROUTER_ISR"]:
            fam_final = 'IOS_XE_ROUTER_ISR'
            why = "IOS-XE + ISR hints"
        else:
            # default IOS-XE → SWITCH if 16/17 or Cat9k-like hints present
            if major in {"16", "17"} or hits["IOS_XE"]:
                fam_final = 'IOS_XE_SWITCH'
                why = f"IOS-XE + major={major or 'unknown'} with switch-like hints"
            else:
                fam_final = 'IOS_XE_SWITCH'
                why = "IOS-XE detected without strong router hints → default SWITCH"
    elif fam_choice == "IOS_CLASSIC":
        fam_final = 'IOS_CLASSIC'
        why = "Classic IOS signature/hints"
    elif fam_choice in {"IOS_XE_ROUTER_ASR", "IOS_XE_ROUTER_ISR"}:
        fam_final = fam_choice
        why = f"Router family selected by hints: {fam_choice}"
    else:
        fam_final = 'UNKNOWN'
        why = f"No clear signature. First line: {_first_line(text)}"

    evidence = {
        'filename': filename,
        'why': why,
        'hits': hits,
        'version_line': ver['raw'],
    }

    logger.info("platform_detect: decision family=%s confidence=%.3f raw=%s major=%s why=%s",
                fam_final, confidence, ver['raw'], ver['major'], why)
    return {
        'family': fam_final,
        'confidence': confidence,
        'version_raw': ver['raw'],
        'version_major': ver['major'],
        'evidence': evidence,
    }


def detect_family_from_file(path: str) -> Dict[str, Any]:
    logger.info("platform_detect.detect_family_from_file: path=%s", path)
    try:
        if not path or not os.path.exists(path):
            logger.error("platform_detect: file not found: %s", path)
            return {
                'family': 'UNKNOWN', 'confidence': 0.0,
                'version_raw': None, 'version_major': None,
                'evidence': {'why': 'File not found', 'filename': path}
            }
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            txt = f.read()
        return detect_family(txt, filename=os.path.basename(path))
    except Exception as e:
        logger.exception("platform_detect: error opening/parsing file %s: %s", path, e)
        return {
            'family': 'UNKNOWN', 'confidence': 0.0,
            'version_raw': None, 'version_major': None,
            'evidence': {'why': f'Error opening/parsing file: {e}', 'filename': path}
        }


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Quick platform detection test")
    ap.add_argument("path", help="File or directory of device logs")
    args = ap.parse_args()

    if os.path.isdir(args.path):
        for n in os.listdir(args.path):
            if n.lower().endswith((".txt", ".log", ".cfg")):
                p = os.path.join(args.path, n)
                info = detect_family_from_file(p)
                print(n, "→", info['family'], info.get('version_raw'), info['evidence'].get('why'))
    else:
        info = detect_family_from_file(args.path)
        print(os.path.basename(args.path), "→", info['family'], info.get('version_raw'), info['evidence'].get('why'))