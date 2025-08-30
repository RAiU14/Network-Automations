# Switching/dispatcher.py
# Detect → route to the right adapter → normalize rows
from __future__ import annotations

import os
import glob
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, Iterable, List, Optional, Union

# central logger (shared helper you already created)
from logging_setup import configure_logging
logger = configure_logging(__file__)

# platform detector (the one we built with evidence dict)
try:
    from platform_detect import detect_family
    logger.debug("dispatcher: imported platform_detect.detect_family")
except Exception as e:
    logger.exception(f"dispatcher: could not import platform_detect.detect_family: {e}")
    raise

# ----- Adapters (prefer package import, fall back to flat import) -----
XE_ADAPTER = None
try:
    # package-style
    from Switching.Cisco.ios_xe.ios_xe_adapter import parse_file_xe as _parse_file_xe
    XE_ADAPTER = _parse_file_xe
    logger.debug("dispatcher: loaded XE adapter via package import.")
except Exception:
    try:
        # flat-style (when running from project root as scripts)
        from Cisco.ios_xe.ios_xe_adapter import parse_file_xe as _parse_file_xe  # type: ignore
        XE_ADAPTER = _parse_file_xe
        logger.debug("dispatcher: loaded XE adapter via flat import.")
    except Exception as e:
        logger.warning(f"dispatcher: XE adapter not available yet: {e}")

# Optional stubs (classic IOS / routers) — they can be fleshed out later
def _stub_parser(_path: str) -> Dict[str, Any]:
    """
    Minimal placeholder for families we don't support yet.
    """
    return _unsupported_row(_path, reason="Stub parser (not implemented)")


# ==========================
# Utilities
# ==========================

SUPPORTED_SUFFIXES = (".txt", ".log", ".cfg")

def collect_paths(input_path: str,
                  includes: Optional[List[str]] = None,
                  excludes: Optional[List[str]] = None) -> List[str]:
    """
    Accepts a directory OR a single file and returns a sorted list of files to process.
    """
    logger.info(f"collect_paths: start path={input_path}, includes={includes}, excludes={excludes}")

    if os.path.isfile(input_path):
        base = os.path.basename(input_path)
        if includes and not any(glob.fnmatch.fnmatch(base, pat) for pat in includes):
            logger.debug(f"collect_paths: single file excluded by include patterns: {base}")
            return []
        if excludes and any(glob.fnmatch.fnmatch(base, pat) for pat in excludes):
            logger.debug(f"collect_paths: single file excluded by exclude patterns: {base}")
            return []
        logger.debug(f"collect_paths: single file accepted: {base}")
        return [input_path]

    if not os.path.isdir(input_path):
        logger.error(f"collect_paths: not found or not a directory: {input_path}")
        raise FileNotFoundError(f"Input path is neither file nor directory: {input_path}")

    out: List[str] = []
    for n in os.listdir(input_path):
        if n.startswith(("~$", ".")):
            continue
        if not n.lower().endswith(SUPPORTED_SUFFIXES):
            continue
        if includes and not any(glob.fnmatch.fnmatch(n, pat) for pat in includes):
            continue
        if excludes and any(glob.fnmatch.fnmatch(n, pat) for pat in excludes):
            continue
        out.append(os.path.join(input_path, n))

    out_sorted = sorted(out)
    logger.info(f"collect_paths: found {len(out_sorted)} eligible files.")
    return out_sorted


def _unsupported_row(file_path: str, reason: str = "Unsupported IOS") -> Dict[str, Any]:
    """
    One-row data dict for files that were skipped or failed.
    Mirrors your _placeholder_entry() shape from Cisco_IOS_XE, but keeps it local to dispatcher.
    """
    fname = os.path.basename(file_path)
    U = "Unsupported IOS"
    row = {
        "File name": [fname],
        "Host name": [U],
        "Model number": [U],
        "Serial number": [U],
        "Interface ip address": [U],
        "Uptime": [U],
        "Current s/w version": [U],
        "Last Reboot Reason": [U],
        "Any Debug?": [U],
        "CPU Utilization": [U],
        "Total memory": [U],
        "Used memory": [U],
        "Free memory": [U],
        "Memory Utilization (%)": [U],
        "Total flash memory": [U],
        "Used flash memory": [U],
        "Free flash memory": [U],
        "Used Flash (%)": [U],
        "Fan status": [U],
        "Temperature status": [U],
        "PowerSupply status": [U],
        "Available Free Ports": [U],
        "Any Half Duplex": [U],
        "Interface/Module Remark": [U],
        "Config Status": [U],
        "Config Save Date": [U],
        "Critical logs": [U],
        "Current SW EOS": [U],
        "Suggested s/w ver": [U],
        "s/w release date": [U],
        "Latest S/W version": [U],
        "Production s/w is deffered or not?": [U],
        "End-of-Sale Date: HW": [U],
        "Last Date of Support: HW": [U],
        "End of Routine Failure Analysis Date:  HW": [U],
        "End of Vulnerability/Security Support: HW": [U],
        "End of SW Maintenance Releases Date: HW": [U],
        "Remark": [reason],
    }
    logger.debug(f"_unsupported_row: created placeholder for {fname} reason='{reason}'")
    return row


def _normalize_to_rows(result: Union[None, Dict[str, Any], List[Dict[str, Any]]],
                       file_path: str,
                       on_empty_reason: str) -> List[Dict[str, Any]]:
    """
    Accepts:
      - None → placeholder row
      - dict (single row as wide dict with list values) → [dict]
      - list[dict] → untouched
    """
    if result is None:
        logger.warning(f"_normalize_to_rows: adapter returned None for {file_path}")
        return [_unsupported_row(file_path, reason=on_empty_reason)]
    if isinstance(result, dict):
        return [result]
    if isinstance(result, list) and all(isinstance(d, dict) for d in result):
        return result
    logger.error(f"_normalize_to_rows: invalid adapter result type={type(result)} for {file_path}")
    return [_unsupported_row(file_path, reason="Adapter returned invalid structure")]


# ==========================
# Routing
# ==========================

class DispatchController:
    def __init__(self, max_workers: int = 12) -> None:
        self.max_workers = max_workers
        logger.info(f"DispatchController: initialized with max_workers={max_workers}")

    def _route_one(self, path: str) -> List[Dict[str, Any]]:
        """
        Read file, detect family, call adapter, normalize to list[dict].
        """
        fname = os.path.basename(path)
        logger.info(f"_route_one: start {fname}")
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
        except Exception as e:
            logger.exception(f"_route_one: could not read {fname}: {e}")
            return [_unsupported_row(path, reason="Error: could not read file")]

        try:
            info = detect_family(text, filename=fname)
            family = info.get("family", "UNKNOWN")
            evidence = info.get("evidence", {}) or {}
            logger.debug(
                "detect_family: file=%s family=%s version_raw=%s major=%s why=%s",
                fname, family, info.get("version_raw"), info.get("version_major"),
                evidence.get("why")
            )
            # log extra evidence if present (scores/hits)
            if "scores" in evidence:
                logger.debug("detect_family: scores=%s", evidence.get("scores"))
            if "hits" in evidence:
                logger.debug("detect_family: hits=%s", evidence.get("hits"))
        except Exception as e:
            logger.exception(f"_route_one: detect_family crashed for {fname}: {e}")
            return [_unsupported_row(path, reason="Error: detection failure")]

        try:
            # ----- IOS-XE (switches/routers share the same XE adapter for now) -----
            if family in ("IOS_XE_SWITCH", "IOS_XE_ROUTER_ISR", "IOS_XE_ROUTER_ASR"):
                if XE_ADAPTER is None:
                    logger.error("_route_one: XE_ADAPTER not available for %s", fname)
                    return [_unsupported_row(path, reason="XE adapter not available")]

                logger.info("_route_one: routing → XE adapter for %s", fname)
                out = XE_ADAPTER(path)
                rows = _normalize_to_rows(out, path, on_empty_reason="XE adapter: empty result")
                logger.debug("_route_one: XE rows=%d for %s", len(rows), fname)
                return rows

            # ----- Classic IOS (stub) -----
            if family == "IOS_CLASSIC":
                logger.info("_route_one: routing → IOS classic stub for %s", fname)
                return [_stub_parser(path)]

            # ----- Unknown / out-of-scope -----
            logger.warning("_route_one: UNKNOWN family for %s → placeholder row", fname)
            return [_unsupported_row(path, reason="Non-IOS_XE")]
        except Exception as e:
            logger.exception(f"_route_one: adapter crashed for {fname}: {e}")
            return [_unsupported_row(path, reason="Error: adapter failure")]

    def process_files(self, paths: Iterable[str]) -> List[Dict[str, Any]]:
        """
        Concurrently process many files. Returns a flat list of rows.
        """
        paths = list(paths)
        if not paths:
            logger.warning("process_files: no paths supplied.")
            return []

        logger.info("process_files: starting %d files with max_workers=%d", len(paths), self.max_workers)
        rows: List[Dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as ex:
            fut_map = {ex.submit(self._route_one, p): p for p in paths}
            for fut in as_completed(fut_map):
                p = fut_map[fut]
                try:
                    res = fut.result()
                    if isinstance(res, list):
                        rows.extend(res)
                    else:
                        logger.error("process_files: unexpected result from %s type=%s", p, type(res))
                        rows.extend(_normalize_to_rows(res, p, on_empty_reason="Adapter returned invalid structure"))
                except Exception as e:
                    logger.exception("process_files: worker crashed for %s: %s", p, e)
                    rows.append(_unsupported_row(p, reason="Error: worker exception"))

        logger.info("process_files: completed. total_rows=%d", len(rows))
        return rows


# ==========================
# Convenience single-file API
# ==========================

def parse_file_via_dispatcher(path: str) -> Dict[str, Any]:
    """
    Convenience helper that returns **one** row for a single file.
    If an adapter returns multiple rows, the first is returned.
    """
    logger.info("parse_file_via_dispatcher: path=%s", path)
    ctrl = DispatchController(max_workers=1)
    rows = ctrl.process_files([path])
    if not rows:
        logger.warning("parse_file_via_dispatcher: no rows produced, returning placeholder.")
        return _unsupported_row(path, reason="No rows produced")
    if len(rows) > 1:
        logger.debug("parse_file_via_dispatcher: adapter returned %d rows; returning first.", len(rows))
    return rows[0]


__all__ = [
    "collect_paths",
    "DispatchController",
    "parse_file_via_dispatcher",
]
