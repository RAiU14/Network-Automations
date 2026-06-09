#!/usr/bin/env python3
"""Generate a Cisco EOX Manager preset PID database.

The old Auto_Pop flow depended completely on Cisco's public
``/support/all-products.html`` page. That page is useful when Cisco allows the
request, but it can return 403 or change layout. This exporter now supports a
safer workflow:

1. Import one or more local PID files with ``--input-file``.
2. Optionally crawl Cisco categories when available.
3. Fall back to the bundled preset instead of failing empty.
4. Optionally crawl series pages for model names with ``--crawl-models``.
5. Optionally crawl EOX announcement pages with ``--crawl-eox``.

Supported ``--input-file`` formats:
- TXT: one PID per line
- CSV: columns such as pid, product_name, technology, product_url, is_eox
- JSON: either a Cisco_EOX_Manager preset, a list of strings/dicts, or a legacy
  {"PID": {...milestones...}} cache.
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

PRODUCT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PRODUCT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.cisco_scraper import CiscoEoxScraperService  # noqa: E402
from app.services.normalization import normalize_pid  # noqa: E402

DEFAULT_OUTPUT = PRODUCT_ROOT / "data" / "presets" / "eox_pid_seed.json"
LOG_DIR = PRODUCT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "auto_pop_pid_database.log", encoding="utf-8"),
    ],
)
LOGGER = logging.getLogger("auto_pop_pid_database")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty_seed() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "generated_at": _now(),
        "source": "auto_pop_pid_database.py",
        "metadata": {
            "categories_seen": 0,
            "catalog_records": 0,
            "eox_records": 0,
            "include_eox_links": True,
            "crawl_eox": False,
            "crawl_models": False,
            "fallback_used": False,
            "notes": [],
        },
        "categories": {},
        "pid_catalog": [],
        "eox_records": [],
    }


def _record(
    kind: str,
    name: str,
    url: str | None,
    category: str,
    is_eox: bool,
    *,
    source: str = "auto_pop",
    product_name: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    name = str(name or "").strip()
    category = str(category or "Imported").strip() or "Imported"
    merged_payload = {"kind": kind}
    if url:
        merged_payload["source_url"] = url
    if payload:
        merged_payload.update(payload)
    return {
        "pid": name,
        "normalized_pid": normalize_pid(name),
        "product_name": product_name or name,
        "technology": category,
        "category_name": category,
        "product_url": url,
        "is_eox": bool(is_eox),
        "source": source,
        "payload": merged_payload,
    }


def _dedupe_catalog(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str, str]] = set()
    output: list[dict[str, Any]] = []
    for record in records:
        pid = str(record.get("pid") or record.get("name") or record.get("product_name") or "").strip()
        if not pid:
            continue
        technology = str(record.get("technology") or record.get("category_name") or "Imported")
        kind = str((record.get("payload") or {}).get("kind") or record.get("kind") or "catalog")
        url = str(record.get("product_url") or record.get("url") or "")
        key = (normalize_pid(pid), technology.lower(), kind.lower(), url.lower())
        if key in seen:
            continue
        seen.add(key)
        clean = dict(record)
        clean["pid"] = pid
        clean.setdefault("normalized_pid", normalize_pid(pid))
        clean.setdefault("product_name", pid)
        clean.setdefault("technology", technology)
        clean.setdefault("category_name", technology)
        clean.setdefault("source", "auto_pop")
        clean.setdefault("payload", {"kind": kind})
        clean["is_eox"] = bool(clean.get("is_eox", False))
        output.append(clean)
    return output


def _merge_seed(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    base.setdefault("pid_catalog", [])
    base.setdefault("eox_records", [])
    base.setdefault("categories", {})
    base.setdefault("metadata", {})
    if isinstance(incoming.get("categories"), dict):
        base["categories"].update(incoming["categories"])
    if isinstance(incoming.get("pid_catalog"), list):
        base["pid_catalog"].extend(incoming["pid_catalog"])
    if isinstance(incoming.get("eox_records"), list):
        base["eox_records"].extend(incoming["eox_records"])
    return base


def _is_eox_payload(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    keys = " ".join(str(key).lower() for key in payload.keys())
    return any(token in keys for token in ("end", "eox", "eol", "sale", "support", "milestone"))


def _seed_from_json(data: Any, *, source: str, default_technology: str = "Imported") -> dict[str, Any]:
    seed = _empty_seed()
    seed["source"] = source

    if isinstance(data, dict) and ("pid_catalog" in data or "eox_records" in data):
        return _merge_seed(seed, data)

    if isinstance(data, list):
        for item in data:
            if isinstance(item, str):
                seed["pid_catalog"].append(_record("input", item, None, default_technology, False, source=source))
            elif isinstance(item, dict):
                pid = item.get("pid") or item.get("name") or item.get("product_name") or item.get("model")
                if not pid:
                    continue
                seed["pid_catalog"].append(
                    _record(
                        str(item.get("kind") or "input"),
                        str(pid),
                        item.get("product_url") or item.get("url"),
                        str(item.get("technology") or item.get("category_name") or default_technology),
                        bool(item.get("is_eox", False)),
                        source=str(item.get("source") or source),
                        product_name=item.get("product_name") or item.get("name"),
                        payload={key: value for key, value in item.items() if key not in {"pid", "name", "product_name", "model"}},
                    )
                )
        return seed

    if isinstance(data, dict):
        # Legacy cache shape: {"PID": {milestones...}}
        for pid, payload in data.items():
            if str(pid).startswith("_"):
                continue
            if _is_eox_payload(payload):
                seed["eox_records"].append(
                    {
                        "pid": str(pid),
                        "normalized_pid": normalize_pid(str(pid)),
                        "technology": default_technology,
                        "source": source,
                        "payload": payload if isinstance(payload, dict) else {"value": payload},
                    }
                )
            else:
                seed["pid_catalog"].append(_record("legacy-json", str(pid), None, default_technology, False, source=source))
    return seed


def _seed_from_csv(path: Path, *, source: str, default_technology: str = "Imported") -> dict[str, Any]:
    seed = _empty_seed()
    seed["source"] = source
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            lower = {str(key).strip().lower(): value for key, value in row.items() if key is not None}
            pid = lower.get("pid") or lower.get("product_id") or lower.get("model") or lower.get("product_name") or lower.get("name")
            if not pid:
                continue
            is_eox_value = str(lower.get("is_eox") or lower.get("eox") or "").strip().lower()
            seed["pid_catalog"].append(
                _record(
                    "csv",
                    pid,
                    lower.get("product_url") or lower.get("url") or lower.get("source_url"),
                    lower.get("technology") or lower.get("category_name") or default_technology,
                    is_eox_value in {"true", "1", "yes", "y", "eox", "eol"},
                    source=source,
                    product_name=lower.get("product_name") or lower.get("name") or pid,
                    payload={"csv_row": row},
                )
            )
    return seed


def _seed_from_txt(path: Path, *, source: str, default_technology: str = "Imported") -> dict[str, Any]:
    seed = _empty_seed()
    seed["source"] = source
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        pid = line.strip()
        if not pid or pid.startswith("#"):
            continue
        seed["pid_catalog"].append(_record("txt", pid, None, default_technology, False, source=source))
    return seed


def load_input_file(path_value: str) -> dict[str, Any]:
    path = Path(path_value).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    suffix = path.suffix.lower()
    source = f"input:{path.name}"
    if suffix == ".json":
        return _seed_from_json(json.loads(path.read_text(encoding="utf-8-sig")), source=source)
    if suffix == ".csv":
        return _seed_from_csv(path, source=source)
    return _seed_from_txt(path, source=source)


def _parse_category_url(values: list[str]) -> dict[str, str]:
    output: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError("--category-url must use NAME=URL format")
        name, url = value.split("=", 1)
        name = name.strip()
        url = url.strip()
        if not name or not url:
            raise ValueError("--category-url requires a non-empty name and URL")
        output[name] = url
    return output


def _load_fallback_preset() -> dict[str, Any] | None:
    if not DEFAULT_OUTPUT.exists():
        return None
    try:
        data = json.loads(DEFAULT_OUTPUT.read_text(encoding="utf-8"))
    except Exception as exc:
        LOGGER.warning("Bundled fallback preset exists but is unreadable: %s", exc)
        return None
    seed = _seed_from_json(data, source="bundled-preset-fallback")
    seed.setdefault("metadata", {})["fallback_used"] = True
    notes = seed.setdefault("metadata", {}).setdefault("notes", [])
    if isinstance(notes, list):
        notes.append("Cisco online category discovery failed or was skipped; bundled preset was used instead.")
    return seed


def _build_from_cisco(
    *,
    categories: list[str],
    category_urls: dict[str, str],
    limit_categories: int | None,
    include_eox_links: bool,
    crawl_models: bool,
    limit_series: int | None,
) -> dict[str, Any]:
    scraper = CiscoEoxScraperService()
    category_links = dict(category_urls)
    if not category_links:
        category_links = scraper.category()
    if not category_links:
        return _empty_seed()

    selected = categories or list(category_links.keys())
    selected = [name for name in selected if name in category_links]
    if limit_categories:
        selected = selected[:limit_categories]

    records: list[dict[str, Any]] = []
    categories_seen: dict[str, str] = {}
    series_pages_opened = 0

    for index, category_name in enumerate(selected, start=1):
        LOGGER.info("[%s/%s] Opening category: %s", index, len(selected), category_name)
        opened = scraper.open_cat(category_links[category_name])
        if not opened:
            LOGGER.warning("No data found for category: %s", category_name)
            continue
        categories_seen[category_name] = category_links[category_name]
        series, eox = opened

        for name, url in series.items():
            is_eox = bool(eox and name in eox)
            records.append(_record("series", name, url, category_name, is_eox, payload={"status_hint": "eox" if is_eox else "active_or_unknown"}))

            if crawl_models and url and (limit_series is None or series_pages_opened < limit_series):
                series_pages_opened += 1
                LOGGER.info("    Extracting models from series page: %s", name)
                for model_name in scraper.extract_models_from_series_page(url):
                    records.append(
                        _record(
                            "model",
                            model_name,
                            url,
                            category_name,
                            is_eox,
                            payload={"parent_series": name, "parent_series_url": url},
                        )
                    )

        if include_eox_links and eox:
            for name, url in eox.items():
                records.append(_record("eox_series", name, url, category_name, True))

    seed = _empty_seed()
    seed["categories"] = categories_seen
    seed["pid_catalog"] = _dedupe_catalog(records)
    seed["metadata"].update(
        {
            "categories_seen": len(categories_seen),
            "catalog_records": len(seed["pid_catalog"]),
            "include_eox_links": include_eox_links,
            "crawl_models": crawl_models,
            "series_pages_opened": series_pages_opened,
        }
    )
    return seed


def build_catalog(
    *,
    categories: list[str],
    category_urls: dict[str, str],
    limit_categories: int | None,
    include_eox_links: bool,
    input_files: list[str],
    crawl_cisco: bool,
    crawl_models: bool,
    limit_series: int | None,
    fallback_preset: bool,
    allow_empty: bool,
) -> dict[str, Any]:
    seed = _empty_seed()
    seed["metadata"]["include_eox_links"] = include_eox_links
    seed["metadata"]["crawl_models"] = crawl_models

    for input_file in input_files:
        LOGGER.info("Loading input file: %s", input_file)
        _merge_seed(seed, load_input_file(input_file))

    if crawl_cisco:
        online_seed = _build_from_cisco(
            categories=categories,
            category_urls=category_urls,
            limit_categories=limit_categories,
            include_eox_links=include_eox_links,
            crawl_models=crawl_models,
            limit_series=limit_series,
        )
        _merge_seed(seed, online_seed)
    else:
        seed["metadata"].setdefault("notes", []).append("Cisco online crawl was skipped by --no-cisco-crawl.")

    seed["pid_catalog"] = _dedupe_catalog(seed.get("pid_catalog", []))
    seed["metadata"]["categories_seen"] = len(seed.get("categories") or {})
    seed["metadata"]["catalog_records"] = len(seed.get("pid_catalog") or [])
    seed["metadata"]["eox_records"] = len(seed.get("eox_records") or [])

    if not seed["pid_catalog"] and not seed["eox_records"] and fallback_preset and not allow_empty:
        fallback = _load_fallback_preset()
        if fallback:
            LOGGER.warning("No online/input records were discovered. Using bundled preset fallback.")
            return fallback

    if not seed["pid_catalog"] and not seed["eox_records"] and not allow_empty:
        raise RuntimeError(
            "No PID data was discovered. Cisco may have blocked the request or the page layout may have changed. "
            "Try: --input-file pids.txt, --category-url Switches=https://www.cisco.com/c/en/us/support/switches/category.html, "
            "or --allow-empty if you only want to test the exporter."
        )

    return seed


def enrich_eox_records(seed: dict[str, Any], *, limit_eox: int | None) -> dict[str, Any]:
    scraper = CiscoEoxScraperService()
    eox_records: list[dict[str, Any]] = list(seed.get("eox_records") or [])
    eox_candidates = [item for item in seed.get("pid_catalog", []) if item.get("is_eox")]
    if limit_eox:
        eox_candidates = eox_candidates[:limit_eox]

    if not eox_candidates:
        LOGGER.warning("No EOX candidate series were available for --crawl-eox")

    for index, item in enumerate(eox_candidates, start=1):
        url = item.get("product_url")
        name = item.get("pid")
        LOGGER.info("[%s/%s] Scraping EOX page: %s", index, len(eox_candidates), name)
        if not url:
            continue
        checked = scraper.eox_check(url)
        if not checked:
            continue
        has_link, details = checked
        if not has_link:
            if isinstance(details, dict):
                eox_records.append(
                    {
                        "pid": name,
                        "normalized_pid": normalize_pid(str(name)),
                        "technology": item.get("technology") or item.get("category_name") or "Imported",
                        "source": "auto_pop",
                        "announcement_name": None,
                        "announcement_url": details.get("url"),
                        "payload": details,
                    }
                )
            continue
        announcements = scraper.eox_details(details.get("url", "")) or {}
        for announcement_name, announcement_url in announcements.items():
            scraped = scraper.eox_scraping(announcement_url)
            if not scraped:
                continue
            milestones, affected_pids = scraped
            for pid in affected_pids:
                eox_records.append(
                    {
                        "pid": pid,
                        "normalized_pid": normalize_pid(pid),
                        "technology": item.get("technology") or item.get("category_name") or "Imported",
                        "source": "auto_pop",
                        "announcement_name": announcement_name,
                        "announcement_url": announcement_url,
                        "payload": milestones,
                    }
                )
    seed["eox_records"] = eox_records
    seed.setdefault("metadata", {})["crawl_eox"] = True
    seed.setdefault("metadata", {})["eox_records"] = len(eox_records)
    return seed


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=False), encoding="utf-8")
    LOGGER.info("Wrote %s", path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Cisco EOX Manager PID preset JSON")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output JSON file path")
    parser.add_argument("--category", action="append", default=[], help="Cisco category name to include. Can be used more than once.")
    parser.add_argument("--category-url", action="append", default=[], help="Manual category in NAME=URL format. Useful when all-products.html is blocked.")
    parser.add_argument("--limit-categories", type=int, default=None, help="Limit categories for testing")
    parser.add_argument("--no-eox-links", action="store_true", help="Do not collect category EOX links")
    parser.add_argument("--crawl-eox", action="store_true", help="Also open EOX announcement pages and collect affected PIDs/milestones")
    parser.add_argument("--limit-eox", type=int, default=None, help="Limit EOX pages when --crawl-eox is used")
    parser.add_argument("--crawl-models", action="store_true", help="Open series pages and collect model names from the Select Model section")
    parser.add_argument("--limit-series", type=int, default=None, help="Limit number of series pages opened when --crawl-models is used")
    parser.add_argument("--input-file", action="append", default=[], help="TXT/CSV/JSON file to merge into the preset. Can be used more than once.")
    parser.add_argument("--no-cisco-crawl", action="store_true", help="Skip Cisco online category discovery. Use with --input-file for offline generation.")
    parser.add_argument("--no-fallback-preset", action="store_true", help="Do not use the bundled preset when online discovery fails")
    parser.add_argument("--allow-empty", action="store_true", help="Write an empty preset instead of failing when nothing is discovered")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        seed = build_catalog(
            categories=args.category,
            category_urls=_parse_category_url(args.category_url),
            limit_categories=args.limit_categories,
            include_eox_links=not args.no_eox_links,
            input_files=args.input_file,
            crawl_cisco=not args.no_cisco_crawl,
            crawl_models=args.crawl_models,
            limit_series=args.limit_series,
            fallback_preset=not args.no_fallback_preset,
            allow_empty=args.allow_empty,
        )
        if args.crawl_eox:
            seed = enrich_eox_records(seed, limit_eox=args.limit_eox)
        seed.setdefault("metadata", {})["catalog_records"] = len(seed.get("pid_catalog", []))
        seed.setdefault("metadata", {})["eox_records"] = len(seed.get("eox_records", []))
        seed["generated_at"] = _now()
        write_json(Path(args.output), seed)
        LOGGER.info(
            "Done. Catalog=%s, EOX=%s, fallback_used=%s",
            len(seed.get("pid_catalog", [])),
            len(seed.get("eox_records", [])),
            seed.get("metadata", {}).get("fallback_used", False),
        )
        return 0
    except Exception as exc:
        LOGGER.exception("Auto-pop failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
