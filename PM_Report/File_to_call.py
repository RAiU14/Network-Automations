# File_to_call.py
from __future__ import annotations
from typing import Dict, List, Optional
import os

from logging_setup import configure_logging
logger = configure_logging(__file__)

from Switching.dispatcher import collect_paths, parse_file_via_dispatcher
from Data_to_Excel import append_to_excel, export_json


def run_on_path(path: str,
                ticket: str,
                out_xlsx: Optional[str] = None,
                out_json: Optional[str] = None) -> Dict[str, int]:
    """
    Run pipeline on one file or folder.
    """
    logger.info("run_on_path: start path=%s ticket=%s", path, ticket)

    paths = collect_paths(path)
    logger.debug("run_on_path: %d files collected", len(paths))

    rows: List[Dict] = [parse_file_via_dispatcher(p) for p in paths]

    # Write Excel always
    xlsx = out_xlsx or f"{ticket}_network_analysis.xlsx"
    append_to_excel(ticket, rows, file_path=xlsx)
    logger.info("run_on_path: Excel written to %s", xlsx)

    # Optional JSON
    if out_json:
        export_json(ticket, rows, file_path=out_json)
        logger.info("run_on_path: JSON written to %s", out_json)

    return {"total": len(paths), "written": len(rows), "skipped": 0}


def main():
    logger.info("File_to_call.main: start")
    try:
        # <<< EDIT THESE AS NEEDED >>>
        input_path = r"C:\Users\girish.n\OneDrive - NTT\Desktop\Desktop\Live Updates\Uptime\Tickets-Mostly PM\R&S\SVR137436091\9200\UOBM-9200L-JOT-L03-05_10.31.99.14.txt"
        ticket_number = "SVR137436091"
        out_xlsx = None  # or r"C:\out\myfile.xlsx"
        out_json = None  # or r"C:\out\myfile.json"
        # <<< END EDIT >>>

        summary = run_on_path(input_path, ticket=ticket_number,
                              out_xlsx=out_xlsx, out_json=out_json)
        print(summary)
    except Exception as e:
        logger.exception("File_to_call.main: exception %s", e)


if __name__ == "__main__":
    main()