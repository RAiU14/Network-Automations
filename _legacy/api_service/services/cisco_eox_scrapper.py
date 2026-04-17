from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import bs4
import requests
from langdetect import detect

from core.config import CISCO_BASE_URL, HTTP_TIMEOUT_SECONDS, USER_AGENT, DEFAULT_EOX_DB_PATH
from core.log import get_logger

logger = get_logger("cisco_eox_scraper")


@dataclass
class CiscoEoxScraperService:
    base_url: str = CISCO_BASE_URL
    timeout: int = HTTP_TIMEOUT_SECONDS
    db_path: Path = DEFAULT_EOX_DB_PATH

    def __post_init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    # -------------------------
    # Helpers
    # -------------------------
    def _get(self, url: str) -> str:
        resp = self.session.get(url, timeout=self.timeout)
        resp.raise_for_status()
        return resp.text

    def _abs(self, link: str) -> str:
        if link.startswith("http"):
            return link
        return f"{self.base_url}{link}"

    def link_check(self, link: str) -> Optional[str]:
        if not link:
            return None

        new_link = link
        for url in [self.base_url, "https://www.cisco.com", "//www.cisco.com", "https://cisco.com"]:
            if url in new_link:
                new_link = new_link.replace(url, "")

        for bad_url in ["https://help.", "https://supportforums."]:
            if bad_url in link:
                return None

        return new_link

    # -------------------------
    # Public methods (API-facing)
    # -------------------------
    def category(self) -> Dict[str, str]:
        url = f"{self.base_url}/c/en/us/support/all-products.html"
        soup = bs4.BeautifulSoup(self._get(url), "lxml")

        tech: Dict[str, str] = {}
        header = soup.find("h3", string="All Product and Technology Categories")
        if not header:
            return tech

        table = header.find_next("table")
        if not table:
            return tech

        for a in table.find_all("a"):
            name = (a.text or "").strip()
            href = a.get("href")
            if name and href:
                tech[name] = href
        return tech

    def open_cat(self, link: str) -> Optional[Tuple[Dict[str, str], Optional[Dict[str, str]]]]:
        """
        Returns: (series_dict, optional_eox_dict)
        """
        try:
            soup = bs4.BeautifulSoup(self._get(self._abs(link)), "lxml")
            series: Dict[str, str] = {}
            eox: Dict[str, str] = {}

            # Your original logic condensed but consistent
            if soup.find(id="allSupportedProducts"):
                for a in soup.find(id="allSupportedProducts").find_all("a"):
                    name = (a.text or "").strip()
                    href = self.link_check(a.get("href"))
                    if name and href:
                        series[name] = href

                if soup.find(id="eos"):
                    for tr in soup.find(id="eos").find_all("tr"):
                        links = tr.find_all("a")
                        if not links:
                            continue
                        a = links[0]
                        n = (a.text or "").strip()
                        h = self.link_check(a.get("href"))
                        if n and h:
                            eox[n] = h
                    return series, (eox or None)

                return series, None

            # Fallback: try to find device links in common containers
            # (you can keep your detailed branches here; this is a simpler safe fallback)
            for a in soup.find_all("a"):
                name = (a.text or "").strip()
                href = a.get("href")
                href = self.link_check(href)
                if name and href and "/support/" in href:
                    series.setdefault(name, href)

            return series, None

        except Exception as ex:
            logger.exception("open_cat failed")
            return None

    def eox_check(self, product_link: str) -> Optional[Tuple[bool, Dict[str, str]]]:
        """
        Checks a product page for EOX info and returns:
        (has_eox_url, eol_data_dict)
        """
        try:
            soup = bs4.BeautifulSoup(self._get(self._abs(product_link)), "lxml")
            tables = soup.find_all("table", class_="birth-cert-table")
            if not tables:
                return None

            # pick table index similarly to your code
            idx = 0
            if len(tables) >= 2 and len(tables[1].find_all("th")) > 0:
                idx = 1

            table = tables[idx]
            eol_data: Dict[str, str] = {}

            # collect date fields if present
            for tr in table.find_all("tr"):
                th = tr.find("th")
                td = tr.find("td")
                if not th or not td:
                    continue
                label = th.text.strip()
                if label in ("Series Release Date", "End-of-Sale Date", "End-of-Support Date"):
                    eol_data[label] = td.text.strip()

            status_row = table.find("tr", class_="birth-cert-status")
            a = status_row.find("a") if status_row else None
            if a:
                href = self.link_check(a.get("href"))
                if href:
                    eol_data["url"] = href
                    return True, eol_data

            return False, eol_data

        except Exception:
            logger.exception("eox_check failed")
            return None

    def eox_details(self, redirect_link: str) -> Optional[Dict[str, str]]:
        """
        From an EOX redirect/listing page, find the announcement URLs.
        """
        try:
            soup = bs4.BeautifulSoup(self._get(self._abs(redirect_link)), "lxml")
            ul = soup.find("ul", class_="listing")
            if not ul:
                return {}

            urls: Dict[str, str] = {}
            for li in ul.find_all("li"):
                a = li.find("a")
                if not a:
                    continue
                text = (a.text or "").strip()
                if not text:
                    continue

                # language filter
                try:
                    if detect(text) != "en":
                        continue
                except Exception:
                    # langdetect can throw; don’t fail the whole call
                    continue

                if any(k in text for k in ["Software", "Release", "IOS"]):
                    continue

                title = text.replace("End-of-Sale and End-of-Life Announcement for the Cisco ", "")
                href = a.get("href")
                if href:
                    urls[title] = href
            return urls

        except Exception:
            logger.exception("eox_details failed")
            return None

    def eox_scrapping(self, announcement_link: str) -> Optional[Tuple[Dict[str, str], List[str]]]:
        """
        Scrape the EOX announcement page: milestones + affected devices list.
        """
        try:
            soup = bs4.BeautifulSoup(self._get(self._abs(announcement_link)), "lxml")
            tables = soup.find_all("table")
            if len(tables) < 2:
                return None

            # find milestone table (your original logic)
            idx = 0
            for i, t in enumerate(tables):
                body = t.find("tbody")
                if not body:
                    continue
                first_row = body.find("tr")
                if first_row and first_row.find("td") and first_row.find("td").text.strip().lower() == "milestone":
                    idx = i
                    break

            milestone_table = tables[idx]
            devices_table = tables[idx + 1] if idx + 1 < len(tables) else None
            if not devices_table:
                return None

            milestones: Dict[str, str] = {}
            for tr in milestone_table.find("tbody").find_all("tr"):
                tds = tr.find_all("td")
                if len(tds) >= 3:
                    milestones[tds[0].text.strip()] = tds[2].text.strip()
            milestones.pop("Milestone", None)

            devices: List[str] = []
            for tr in devices_table.find("tbody").find_all("tr"):
                td = tr.find("td")
                if td:
                    devices.append(td.text.strip())
            if devices and devices[0].lower().startswith("end-of-sale product"):
                devices.pop(0)

            return milestones, devices

        except Exception:
            logger.exception("eox_scrapping failed")
            return None

    # -------------------------
    # PID helpers
    # -------------------------
    def get_possible_series(self, pid: str) -> List[str]:
        numbers = re.search(r"(\d+)", pid)
        if not numbers:
            return [pid]

        num = int(numbers.group(1))
        candidates = [str(num)]
        if num >= 100:
            candidates.append(str((num // 100) * 100))
        if num >= 1000:
            candidates.append(str((num // 1000) * 1000))

        seen = set()
        out = []
        for c in candidates:
            if c not in seen:
                seen.add(c)
                out.append(c)
        return out

    def find_device_series_link(self, pid: str, technology: str) -> Optional[str]:
        """
        Your logic for 'Routing and Switching' preserved, but wrapped cleanly.
        """
        try:
            available_category = self.category()
            data: Dict[str, str] = {}

            if technology == "Routing and Switching":
                for tech in ["Switches", "Routers"]:
                    tech_link = available_category.get(tech)
                    if not tech_link:
                        continue

                    opened = self.open_cat(tech_link)
                    if not opened:
                        continue
                    series, _ = opened

                    for cand in self.get_possible_series(pid):
                        for device_name, url in series.items():
                            if cand in device_name:
                                data[device_name] = url

            if not data:
                return None

            clean_pid = pid.replace("-", "").upper()

            # exact key match
            if pid in data:
                return data[pid]

            # best match
            def score(k: str) -> int:
                kk = k.replace("-", "").replace(" ", "").upper()
                return len(kk) if kk in clean_pid else 0

            best = max(data.keys(), key=score, default=None)
            return data.get(best) or next(iter(data.values()))

        except Exception:
            logger.exception("find_device_series_link failed")
            return None

    # -------------------------
    # Optional JSON cache
    # -------------------------
    def load_cache(self) -> Dict[str, Any]:
        if not self.db_path.exists():
            return {}
        try:
            return json.loads(self.db_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def save_cache(self, data: Dict[str, Any]) -> None:
        self.db_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
