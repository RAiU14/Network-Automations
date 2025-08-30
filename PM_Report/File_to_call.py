# File_to_call.py  (root of project)

from __future__ import annotations
from typing import Dict, List, Optional

from Switching.dispatcher import collect_paths, parse_file_via_dispatcher
from Data_to_Excel import append_to_excel, export_json


def run_on_path(
    path: str,
    ticket: str,
    out_xlsx: Optional[str] = None,
    out_json: Optional[str] = None,
) -> Dict[str, int]:
    """
    Run the pipeline on a single file OR a folder.
    Collects device rows, writes Excel (and JSON if requested),
    and returns a small summary dict.
    """
    paths = collect_paths(path)  # normalize to list of files
    rows: List[Dict] = [parse_file_via_dispatcher(p) for p in paths]

    # Excel always written
    xlsx = out_xlsx or f"{ticket}_network_analysis.xlsx"
    append_to_excel(ticket, rows, file_path=xlsx)

    # Optional JSON
    if out_json:
        export_json(ticket, rows, file_path=out_json)

    return {"total": len(paths), "written": len(rows), "skipped": 0}


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Run PM pipeline on file or folder")
    ap.add_argument("path", help="File or folder of logs")
    ap.add_argument("--ticket", required=True, help="Ticket number")
    ap.add_argument("--out-xlsx", help="Output Excel path")
    ap.add_argument("--out-json", help="Optional JSON output path")
    args = ap.parse_args()

    summary = run_on_path(
        args.path,
        ticket=args.ticket,
        out_xlsx=args.out_xlsx,
        out_json=args.out_json,
    )
    print(summary)


if __name__ == "__main__":
    main()
