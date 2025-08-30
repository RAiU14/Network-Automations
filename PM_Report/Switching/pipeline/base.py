# pipeline/base.py
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List


class BaseParser(ABC):
    """
    Contract for all platform parsers.
    Each parser must return a single device row as a dict that matches
    the columns expected by Data_to_Excel.append_to_excel().
    """

    @abstractmethod
    def parse_file(self, path: str) -> Dict:
        """
        Parse a single device log file and return a dict (one row).
        Must never raise for normal parse failures—return a placeholder row instead.
        """
        raise NotImplementedError

    def parse_many(self, paths: List[str]) -> List[Dict]:
        """
        Optional convenience method: parse multiple files sequentially.
        The dispatcher uses its own thread pool; this stays simple.
        """
        out: List[Dict] = []
        for p in paths:
            try:
                row = self.parse_file(p)
                if row:
                    out.append(row)
            except Exception:
                # Let callers decide how to handle unexpected exceptions.
                # Concrete parsers should generally avoid throwing here.
                pass
        return out