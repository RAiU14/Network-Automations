"""Backward-compatible wrapper for the old misspelled module name.

Use EOX_API.services.cisco_eox_scraper for new code.
"""

from EOX_API.services.cisco_eox_scraper import CiscoEoxScraperService

__all__ = ["CiscoEoxScraperService"]
