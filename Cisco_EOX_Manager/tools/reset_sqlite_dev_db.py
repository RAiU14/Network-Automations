from __future__ import annotations

import argparse
from pathlib import Path

PRODUCT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PRODUCT_ROOT / "data"


def main() -> int:
    parser = argparse.ArgumentParser(description="Delete the local SQLite dev database and sidecar files.")
    parser.add_argument("--path", default=str(DATA_DIR / "eox_dev.db"), help="SQLite DB path to delete")
    parser.add_argument("--yes", action="store_true", help="Do not ask for confirmation")
    args = parser.parse_args()
    db_path = Path(args.path)
    targets = [db_path, Path(f"{db_path}-journal"), Path(f"{db_path}-wal"), Path(f"{db_path}-shm")]
    existing = [path for path in targets if path.exists()]
    if not existing:
        print("No SQLite files found.")
        return 0
    print("Files to delete:")
    for path in existing:
        print(f"  {path}")
    if not args.yes:
        answer = input("Delete these files? Type YES to continue: ")
        if answer != "YES":
            print("Cancelled.")
            return 1
    for path in existing:
        path.unlink()
        print(f"Deleted {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
