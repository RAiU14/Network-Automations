from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import urljoin

import bs4
import requests
try:
    from langdetect import detect
except ImportError:  # Optional at import time; requirements.txt includes langdetect.
    detect = None
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.core.config import DEFAULT_EOX_DB_PATH, get_settings
from app.core.logging import get_logger

logger = get_logger("eox.scraper")

DATE_FIELDS = {"Series Release Date", "End-of-Sale Date", "End-of-Support Date"}
SOFTWARE_ANNOUNCEMENT_WORDS = ("Software", "Release", "IOS", "NX-OS", "ASA Software")


@dataclass
class CiscoEoxScraperService:
    """Cisco support-page scraper used when the official API cannot answer a PID lookup."""

    base_url: str | None = None
    timeout: int | None = None
    db_path: Path = DEFAULT_EOX_DB_PATH
    session: requests.Session = field(default_factory=requests.Session, init=False)

    def __post_init__(self) -> None:
        settings = get_settings()
        self.base_url = (self.base_url or settings.cisco_base_url).rstrip("/")
        self.timeout = self.timeout or settings.http_timeout_seconds
        self.db_path = Path(self.db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        retry = Retry(
            total=settings.http_retries,
            connect=settings.http_retries,
            read=settings.http_retries,
            status=settings.http_retries,
            backoff_factor=settings.http_backoff_seconds,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET"}),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.headers.update(
            {
                "User-Agent": settings.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "Referer": "https://www.cisco.com/",
                "Upgrade-Insecure-Requests": "1",
            }
        )

    # ------------------------------------------------------------------
    # HTTP / parsing helpers
    # ------------------------------------------------------------------
    def _get(self, url: str) -> str:
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.text

    def _abs(self, link: str) -> str:
        if not link:
            return self.base_url or "https://www.cisco.com"
        if link.startswith("//"):
            return f"https:{link}"
        if link.startswith("http://") or link.startswith("https://"):
            return link
        return urljoin(f"{self.base_url}/", link.lstrip("/"))

    def link_check(self, link: str | None) -> str | None:
        if not link:
            return None
        link = link.strip()
        if not link or link.startswith("#") or link.startswith("mailto:"):
            return None
        if any(bad in link for bad in ("https://help.", "https://supportforums.", "javascript:")):
            return None

        for prefix in (self.base_url, "https://www.cisco.com", "http://www.cisco.com", "//www.cisco.com", "https://cisco.com"):
            if link.startswith(prefix):
                link = link.replace(prefix, "", 1)
        return link or None

    @staticmethod
    def _text(node: Any) -> str:
        return re.sub(r"\s+", " ", node.get_text(" ", strip=True) if node else "").strip()

    @staticmethod
    def _is_english(text: str) -> bool:
        if detect is None:
            return True
        try:
            return detect(text) == "en"
        except Exception:
            # Short titles can fail language detection. Keep them instead of losing data.
            return True

    @staticmethod
    def _normalise_key(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", value.lower())

    # ------------------------------------------------------------------
    # Public scraping methods
    # ------------------------------------------------------------------
    def category(self) -> dict[str, str]:
        """Return Cisco product/support category links.

        Cisco has used at least two layouts for the all-products page:
        the older table headed "All Product and Technology Categories" and the
        newer list sections headed "Top Product Categories" /
        "All Supported Cisco Products". This method supports both layouts and
        falls back to any Cisco support category links present in the page.
        """
        url = f"{self.base_url}/c/en/us/support/all-products.html"
        try:
            soup = bs4.BeautifulSoup(self._get(url), "lxml")
        except requests.RequestException as exc:
            response = getattr(exc, "response", None)
            status = response.status_code if response is not None else "request-failed"
            logger.warning(
                "Cisco all-products page could not be fetched. status=%s url=%s error=%s. "
                "If this is a 403 or network block, run Auto_Pop with --input-file, --category-url, "
                "or retry from a network/browser session that Cisco allows.",
                status,
                url,
                exc,
            )
            return {}

        categories: dict[str, str] = {}

        # Legacy layout.
        header = soup.find(["h2", "h3", "h4"], string=re.compile(r"All Product and Technology Categories", re.I))
        table = header.find_next("table") if header else None
        if table:
            for anchor in table.find_all("a"):
                name = self._text(anchor)
                href = self.link_check(anchor.get("href"))
                if self._looks_like_category_link(name, href):
                    categories[name] = href

        # Current layout.
        section_patterns = (
            r"Top Product Categories",
            r"All Supported Cisco Products",
            r"Additional Support Categories",
            r"Retired Product Categories",
        )
        for pattern in section_patterns:
            for heading in soup.find_all(["h2", "h3", "h4"], string=re.compile(pattern, re.I)):
                self._collect_category_links_from_heading(heading, categories)

        # Last fallback: any obvious support category links in the document.
        if not categories:
            for anchor in soup.find_all("a"):
                name = self._text(anchor)
                href = self.link_check(anchor.get("href"))
                if self._looks_like_category_link(name, href):
                    categories[name] = href

        if not categories:
            logger.warning("Could not find Cisco product categories in the current page layout")
        return categories

    def _collect_category_links_from_heading(self, heading: Any, output: dict[str, str]) -> None:
        for sibling in heading.find_next_siblings():
            if getattr(sibling, "name", None) in {"h1", "h2", "h3"}:
                break
            for anchor in sibling.find_all("a"):
                name = self._text(anchor)
                href = self.link_check(anchor.get("href"))
                if self._looks_like_category_link(name, href):
                    output.setdefault(name, href)

    def _looks_like_category_link(self, name: str, href: str | None) -> bool:
        if not name or not href:
            return False
        href_lower = href.lower()
        if "/support/" not in href_lower:
            return False
        if href_lower.endswith("/category.html"):
            return True
        if "/support/all-" in href_lower:
            return True
        if any(part in href_lower for part in ("/support/services/", "/support/tools/", "/support/acquisitions/")):
            return True
        return False

    def open_cat(self, link: str) -> tuple[dict[str, str], dict[str, str] | None] | None:
        try:
            soup = bs4.BeautifulSoup(self._get(self._abs(link)), "lxml")
            series: dict[str, str] = {}
            eox: dict[str, str] = {}

            supported = soup.find(id="allSupportedProducts")
            if supported:
                self._collect_links(supported, series)

            eos = soup.find(id="eos")
            if eos:
                self._collect_links(eos, eox)

            if not series:
                all_devices = soup.find(id="allDevices")
                alphabetical = all_devices.find(id="alphabetical") if all_devices else None
                if alphabetical:
                    self._collect_links(alphabetical, series)

            if not series:
                for selector in (
                    {"class_": "productContainers"},
                    {"class_": "tech-container"},
                    {"class_": "col full"},
                    {"class_": "col"},
                ):
                    for container in soup.find_all(**selector):
                        self._collect_links(container, series)

            # Current Cisco category pages are plain grouped lists. Keep every
            # product/series in the catalog, and additionally flag rows whose
            # list item carries an end-of-sale/end-of-support image/text.
            self._collect_current_category_product_links(soup, series, eox)

            # Last safe fallback: Cisco support product links with visible names.
            if not series:
                self._collect_links(soup, series, support_only=True)

            return series, (eox or None)
        except Exception:
            logger.exception("Failed to open Cisco category: %s", link)
            return None

    def _collect_current_category_product_links(self, soup: bs4.BeautifulSoup, series: dict[str, str], eox: dict[str, str]) -> None:
        for item in soup.find_all("li"):
            status = self._product_status_from_node(item)
            for anchor in item.find_all("a"):
                name = self._text(anchor)
                href = self.link_check(anchor.get("href"))
                if not name or not href:
                    continue
                if not self._looks_like_product_series_link(href):
                    continue
                if self._is_noise_product_link(name, href):
                    continue
                series.setdefault(name, href)
                if status:
                    eox.setdefault(name, href)

    @staticmethod
    def _looks_like_product_series_link(href: str | None) -> bool:
        if not href:
            return False
        value = href.lower()
        if "/support/" not in value:
            return False
        if value.endswith("/series.html") or value.endswith("/category.html"):
            return True
        return False

    @staticmethod
    def _is_noise_product_link(name: str, href: str | None) -> bool:
        lowered = name.strip().lower()
        if lowered in {"support", "documentation", "overview", "order", "learn more", "see also", "available switching products"}:
            return True
        if lowered.startswith(("all products", "product support", "cisco eol policy")):
            return True
        return False

    def _product_status_from_node(self, node: Any) -> str | None:
        text = self._text(node).lower()
        alt_text = " ".join(str(img.get("alt", "")) for img in node.find_all("img")).lower()
        combined = f"{text} {alt_text}"
        if any(marker in combined for marker in ("end of sale", "end-of-sale", "end of support", "no longer supported", "end-of-life", "eol")):
            return combined.strip()
        return None

    def extract_models_from_series_page(self, product_link: str) -> list[str]:
        """Extract model names shown on a Cisco product/series page.

        Cisco product pages commonly expose a "Select Model" section. The
        values are not always strict Cisco PIDs, but they are useful seed data
        for the local PID catalog and can be refined later from API/EOX hits.
        """
        try:
            soup = bs4.BeautifulSoup(self._get(self._abs(product_link)), "lxml")
        except Exception:
            logger.exception("Failed to extract models from Cisco series page: %s", product_link)
            return []

        models: set[str] = set()
        for node in soup.find_all(["option", "li"]):
            value = self._text(node)
            if self._looks_like_model_name(value):
                models.add(value)

        capture = False
        for line in soup.get_text("\n", strip=True).splitlines():
            value = re.sub(r"\s+", " ", line).strip()
            if not value:
                continue
            if value.lower() == "select model":
                capture = True
                continue
            if capture and value.lower() in {"software type", "software version", "task", "reset all", "documentation"}:
                break
            if capture and self._looks_like_model_name(value):
                models.add(value)

        return sorted(models)

    @staticmethod
    def _looks_like_model_name(value: str) -> bool:
        value = re.sub(r"\s+", " ", value or "").strip()
        if len(value) < 4 or len(value) > 140:
            return False
        lowered = value.lower()
        if any(bad in lowered for bad in ("applicable to all models", "software", "release notes", "field notice", "data sheet")):
            return False
        if lowered in {"select model", "all models", "task", "collections", "configuration"}:
            return False
        return bool(
            re.search(r"\b(Cisco|Catalyst|Nexus|Aironet|Meraki|UCS|ASA|Firepower|Webex)\b", value, re.I)
            or re.search(r"\b[A-Z]{1,4}[- ]?\d{3,}[A-Z0-9-]*\b", value)
            or re.search(r"\b(C|N|IE|ISR|ASR|AIR|WS|UCS|ASA|FPR)[- ]?[A-Z0-9][A-Z0-9-]{2,}\b", value)
        )

    def _collect_links(self, container: Any, output: dict[str, str], *, support_only: bool = False) -> None:
        for anchor in container.find_all("a"):
            name = self._text(anchor)
            href = self.link_check(anchor.get("href"))
            if not name or not href:
                continue
            if support_only and not self._looks_like_product_series_link(href):
                continue
            if name.lower() in {"learn more", "overview", "support", "documentation"}:
                continue
            output.setdefault(name, href)

    def eox_check(self, product_link: str) -> tuple[bool, dict[str, str]] | None:
        try:
            soup = bs4.BeautifulSoup(self._get(self._abs(product_link)), "lxml")
            table = self._select_birth_cert_table(soup)
            if not table:
                return None

            eol_data = self._extract_birth_cert_dates(table)
            status_text = self._text(table.find("tr", class_="birth-cert-status"))
            status_class = " ".join(table.get("class", [])) + " " + " ".join(
                " ".join(node.get("class", [])) for node in table.find_all(class_=True)
            )

            status_row = table.find("tr", class_="birth-cert-status")
            anchor = status_row.find("a") if status_row else table.find("a", href=re.compile("eos|eol|notice", re.I))
            href = self.link_check(anchor.get("href")) if anchor else None
            if href:
                eol_data["url"] = href
                return True, eol_data

            if "available" in status_text.lower() and "eol" not in status_class.lower() and "eos" not in status_class.lower():
                return False, eol_data

            return False, eol_data
        except Exception:
            logger.exception("Failed to check EOX product page: %s", product_link)
            return None

    def _select_birth_cert_table(self, soup: bs4.BeautifulSoup) -> Any | None:
        tables = soup.find_all("table", class_="birth-cert-table")
        if not tables:
            return None
        scored: list[tuple[int, Any]] = []
        for table in tables:
            text = self._text(table)
            score = sum(1 for field_name in DATE_FIELDS if field_name in text)
            if table.find("tr", class_="birth-cert-status"):
                score += 3
            scored.append((score, table))
        scored.sort(key=lambda item: item[0], reverse=True)
        return scored[0][1]

    def _extract_birth_cert_dates(self, table: Any) -> dict[str, str]:
        dates: dict[str, str] = {}
        for row in table.find_all("tr"):
            label = self._text(row.find("th"))
            value = self._text(row.find("td"))
            if label in DATE_FIELDS and value:
                dates[label] = value
        return dates

    def eox_details(self, redirect_link: str) -> dict[str, str] | None:
        try:
            soup = bs4.BeautifulSoup(self._get(self._abs(redirect_link)), "lxml")
            listing = soup.find("ul", class_="listing") or soup.find("div", class_=re.compile("listing", re.I))
            if not listing:
                return {}

            urls: dict[str, str] = {}
            for anchor in listing.find_all("a"):
                title = self._text(anchor)
                href = self.link_check(anchor.get("href"))
                if not title or not href:
                    continue
                if not self._is_english(title):
                    continue
                if any(word in title for word in SOFTWARE_ANNOUNCEMENT_WORDS):
                    continue
                clean_title = title.replace("End-of-Sale and End-of-Life Announcement for the Cisco ", "").strip()
                urls[clean_title or title] = href
            return urls
        except Exception:
            logger.exception("Failed to fetch EOX details page: %s", redirect_link)
            return None

    def eox_scraping(self, announcement_link: str) -> tuple[dict[str, str], list[str]] | None:
        try:
            soup = bs4.BeautifulSoup(self._get(self._abs(announcement_link)), "lxml")
            tables = soup.find_all("table")
            if not tables:
                return None

            milestone_index = self._find_milestone_table_index(tables)
            if milestone_index is None:
                return None

            milestones = self._parse_milestone_table(tables[milestone_index])
            device_table = self._find_affected_devices_table(tables, milestone_index + 1)
            devices = self._parse_devices_table(device_table) if device_table else []

            return milestones, devices
        except Exception:
            logger.exception("Failed to scrape EOX announcement page: %s", announcement_link)
            return None

    # Backward-compatible spelling used by the original code.
    def eox_scrapping(self, announcement_link: str) -> tuple[dict[str, str], list[str]] | None:
        return self.eox_scraping(announcement_link)

    def _find_milestone_table_index(self, tables: list[Any]) -> int | None:
        for index, table in enumerate(tables):
            text = self._text(table).lower()
            if "milestone" in text and ("date" in text or "last date" in text):
                return index
        return 0 if tables else None

    def _parse_milestone_table(self, table: Any) -> dict[str, str]:
        milestones: dict[str, str] = {}
        body = table.find("tbody") or table
        for row in body.find_all("tr"):
            cells = [self._text(cell) for cell in row.find_all(["td", "th"])]
            cells = [cell for cell in cells if cell]
            if len(cells) < 2:
                continue
            if cells[0].lower() == "milestone":
                continue
            date_value = cells[2] if len(cells) >= 3 else cells[-1]
            milestones[cells[0]] = date_value
        return milestones

    def _find_affected_devices_table(self, tables: list[Any], start_index: int) -> Any | None:
        for table in tables[start_index:]:
            text = self._text(table).lower()
            if any(word in text for word in ("end-of-sale product", "product id", "part number", "affected product")):
                return table
        return tables[start_index] if start_index < len(tables) else None

    def _parse_devices_table(self, table: Any) -> list[str]:
        devices: list[str] = []
        body = table.find("tbody") or table
        for row in body.find_all("tr"):
            cells = [self._text(cell) for cell in row.find_all(["td", "th"])]
            if not cells:
                continue
            first = cells[0]
            if not first or first.lower().startswith(("end-of-sale product", "product id", "part number")):
                continue
            devices.append(first)
        return devices

    # ------------------------------------------------------------------
    # PID workflow helpers
    # ------------------------------------------------------------------
    def get_possible_series(self, pid: str) -> list[str]:
        pid = (pid or "").strip().upper()
        numbers = re.search(r"(\d+)", pid)
        if not numbers:
            return [pid] if pid else []

        number = int(numbers.group(1))
        candidates = [str(number)]
        if number >= 100:
            candidates.append(str((number // 100) * 100))
        if number >= 1000:
            candidates.append(str((number // 1000) * 1000))

        output: list[str] = []
        for candidate in candidates:
            if candidate not in output:
                output.append(candidate)
        return output

    def find_device_series_link(self, pid: str, technology: str) -> str | None:
        try:
            categories = self.category()
            category_names = self._category_names_for_technology(technology, categories)
            candidate_links: dict[str, str] = {}

            for category_name in category_names:
                opened = self.open_cat(categories[category_name])
                if not opened:
                    continue
                series, eox = opened
                combined = dict(series)
                if eox:
                    combined.update(eox)
                for name, href in combined.items():
                    if self._series_candidate_match(pid, name):
                        candidate_links[name] = href

            if not candidate_links:
                return None

            best_name = max(candidate_links, key=lambda name: self._series_score(pid, name))
            return candidate_links[best_name]
        except Exception:
            logger.exception("Failed to find device series link for PID=%s technology=%s", pid, technology)
            return None

    def _category_names_for_technology(self, technology: str, categories: Mapping[str, str]) -> list[str]:
        if not technology:
            return list(categories.keys())

        if technology in categories:
            return [technology]

        if technology.lower() == "routing and switching":
            return [name for name in ("Switches", "Routers") if name in categories]

        needle = technology.lower()
        matches = [name for name in categories if needle in name.lower() or name.lower() in needle]
        return matches or list(categories.keys())

    def _series_candidate_match(self, pid: str, series_name: str) -> bool:
        pid_norm = self._normalise_key(pid)
        name_norm = self._normalise_key(series_name)
        if pid_norm and pid_norm in name_norm:
            return True
        return any(candidate and candidate in series_name for candidate in self.get_possible_series(pid))

    def _series_score(self, pid: str, series_name: str) -> int:
        pid_norm = self._normalise_key(pid)
        name_norm = self._normalise_key(series_name)
        score = 0
        if pid_norm == name_norm:
            score += 1000
        if pid_norm and pid_norm in name_norm:
            score += 500 + len(pid_norm)
        for candidate in self.get_possible_series(pid):
            if candidate in series_name:
                score += len(candidate)
        return score

    def pid_eox_check(self, pid: str, announcement_link: str) -> tuple[bool, dict[str, str] | str] | None:
        scraped = self.eox_scraping(announcement_link)
        if not scraped:
            return None
        milestones, affected_devices = scraped
        if pid in affected_devices:
            return True, milestones
        return False, "Check online"

    def eox_online_scraping(self, pid: str, technology: str) -> dict[str, list[Any]]:
        result: dict[str, list[Any]] = {}
        try:
            series_link = self.find_device_series_link(pid, technology)
            if not series_link:
                result[pid] = [False, "Series Not Found"]
                return result

            checked = self.eox_check(series_link)
            if not checked:
                result[pid] = [False, "Not Announced"]
                return result

            has_link, eol_data = checked
            if not has_link:
                result[pid] = [False, eol_data or "Not Announced"]
                return result

            announcements = self.eox_details(eol_data.get("url", "")) or {}
            if not announcements:
                result[pid] = [True, eol_data]
                return result

            first_scraped: tuple[dict[str, str], list[str]] | None = None
            for announcement_link in announcements.values():
                scraped = self.eox_scraping(announcement_link)
                if not scraped:
                    continue
                if first_scraped is None:
                    first_scraped = scraped
                milestones, affected_devices = scraped
                if pid in affected_devices:
                    result[pid] = [True, milestones]
                    return result

            if first_scraped:
                result[pid] = [True, first_scraped[0]]
            else:
                result[pid] = [False, "EOX announcement not parseable"]
            return result
        except Exception as exc:
            logger.exception("EOX online scraping failed for PID=%s", pid)
            result[pid] = [False, f"Error occurred: {exc}"]
            return result

    # Backward-compatible spelling used by the original code.
    def eox_online_scrapping(self, pid: str, technology: str) -> dict[str, list[Any]]:
        return self.eox_online_scraping(pid, technology)

    # ------------------------------------------------------------------
    # Cache + PM report integration helpers
    # ------------------------------------------------------------------
    def load_cache(self) -> dict[str, Any]:
        if not self.db_path.exists():
            return {}
        try:
            return json.loads(self.db_path.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("Ignoring unreadable EOX cache: %s", self.db_path)
            return {}

    def save_cache(self, data: Mapping[str, Any]) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    def request_eox_data_from_local_db(
        self,
        unique_pid_list: Iterable[str],
        technology: str,
        *,
        db_path: str | Path | None = None,
        update_cache: bool = True,
    ) -> dict[str, Any]:
        if db_path:
            self.db_path = Path(db_path)

        cache = self.load_cache()
        output: dict[str, Any] = {}
        missing: list[str] = []

        for pid in self._clean_pid_list(unique_pid_list):
            if pid in cache:
                output[pid] = [True, cache[pid]]
            else:
                missing.append(pid)

        if missing:
            online = self.request_eox_data_from_online(missing, technology, existing_data=output)
            output.update(online)
            if update_cache:
                for pid, value in output.items():
                    if isinstance(value, list) and len(value) >= 2 and value[0] is True and isinstance(value[1], Mapping):
                        cache[pid] = value[1]
                self.save_cache(cache)
        return output

    def request_eox_data_from_online(
        self,
        unique_pid_list: Iterable[str],
        technology: str,
        *,
        existing_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        output = existing_data.copy() if existing_data else {}
        for pid in self._clean_pid_list(unique_pid_list):
            scraped = self.eox_online_scraping(pid, technology)
            value = scraped.get(pid, [False, "Invalid data format"])
            output[pid] = value
        return output

    @staticmethod
    def _clean_pid_list(items: Iterable[str]) -> list[str]:
        seen: set[str] = set()
        output: list[str] = []
        for item in items or []:
            pid = str(item).strip()
            if not pid or pid in seen:
                continue
            seen.add(pid)
            output.append(pid)
        return output

    def update_lifecycle_data(self, data_list: list[dict[str, Any]], lifecycle_info: Mapping[str, Any]) -> list[dict[str, Any]]:
        field_patterns = {
            "End-of-Sale Date: HW": r"end\s*[\-:]?\s*of\s*[\-:]?\s*sale\s*[\-:]?\s*date\s*[\-:]?\s*(hw)?",
            "Last Date of Support: HW": r"last\s*[\-:]?\s*date\s*[\-:]?\s*of\s*[\-:]?\s*support\s*[\-:]?\s*(hw)?",
            "End of Routine Failure Analysis Date:  HW": r"end\s*[\-:]?\s*of\s*[\-:]?\s*routine\s*[\-:]?\s*failure\s*[\-:]?\s*analysis\s*[\-:]?\s*date\s*[\-:]?\s*(hw)?",
            "End of Vulnerability/Security Support: HW": r"end\s*[\-:]?\s*of\s*[\-:]?\s*(vulnerability|security)\s*[\-:/]?\s*(security|vulnerability)?\s*[\-:]?\s*support\s*[\-:]?\s*(hw)?",
            "End of SW Maintenance Releases Date: HW": r"end\s*[\-:]?\s*of\s*[\-:]?\s*sw\s*[\-:]?\s*maintenance\s*[\-:]?\s*releases\s*[\-:]?\s*date\s*[\-:]?\s*(hw)?",
        }

        fresh_data: list[dict[str, Any]] = []
        for device_dict in data_list or []:
            updated_dict = {key: list(value) if isinstance(value, list) else value for key, value in device_dict.items()}
            models = updated_dict.get("Model number", [])

            for index, model in enumerate(models):
                lifecycle_entry = lifecycle_info.get(model)
                if not lifecycle_entry:
                    self._set_lifecycle_fields(updated_dict, field_patterns.keys(), index, "Unavailable")
                    continue

                if isinstance(lifecycle_entry, list) and lifecycle_entry and lifecycle_entry[0] is False:
                    value = lifecycle_entry[1] if len(lifecycle_entry) > 1 and isinstance(lifecycle_entry[1], str) else "Not Announced"
                    self._set_lifecycle_fields(updated_dict, field_patterns.keys(), index, value)
                    continue

                details = lifecycle_entry[1] if isinstance(lifecycle_entry, list) and len(lifecycle_entry) > 1 else lifecycle_entry
                if not isinstance(details, Mapping):
                    self._set_lifecycle_fields(updated_dict, field_patterns.keys(), index, "Unavailable")
                    continue

                normalised = {re.sub(r"\s+", " ", str(key).strip().lower()): value for key, value in details.items()}
                for canonical_field, pattern in field_patterns.items():
                    matched_value = "Unavailable"
                    for key, value in normalised.items():
                        if re.fullmatch(pattern, key):
                            matched_value = value
                            break
                    self._set_lifecycle_fields(updated_dict, [canonical_field], index, matched_value)

            fresh_data.append(updated_dict)
        return fresh_data

    @staticmethod
    def _set_lifecycle_fields(device_dict: dict[str, Any], fields: Iterable[str], index: int, value: Any) -> None:
        for field_name in fields:
            if field_name in device_dict and isinstance(device_dict[field_name], list) and index < len(device_dict[field_name]):
                device_dict[field_name][index] = value

    def sub_controller(self, raw_data: list[dict[str, Any]], unique_pid: Iterable[str], technology: str) -> list[dict[str, Any]]:
        lifecycle_info = self.request_eox_data_from_local_db(unique_pid, technology)
        return self.update_lifecycle_data(raw_data, lifecycle_info)
