import requests
import re
import logging
from bs4 import BeautifulSoup
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class EoxScraperService:
    BASE_URL = "https://www.cisco.com"

    @staticmethod
    def get_categories() -> Dict[str, str]:
        """Fetch primary Cisco support categories"""
        url = f"{EoxScraperService.BASE_URL}/c/en/us/support/all-products.html"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            categories = {}
            for link in soup.select('ul.product-list a'):
                categories[link.text.strip()] = link['href']
            return categories
        except Exception as e:
            logger.error(f"Failed to fetch Cisco categories: {e}")
            return {}

    @staticmethod
    def check_eox_announcement(product_link: str) -> Optional[Dict[str, str]]:
        """Parses a product support page for EOX announcements"""
        try:
            response = requests.get(f"{EoxScraperService.BASE_URL}{product_link}", timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            eox_link = soup.find('a', string=re.compile(r'End-of-Life and End-of-Sale Notices', re.I))
            if eox_link:
                return {"announcement_url": eox_link['href'], "title": eox_link.text}
            return None
        except Exception as e:
            logger.error(f"EOX check failed for {product_link}: {e}")
            return None
