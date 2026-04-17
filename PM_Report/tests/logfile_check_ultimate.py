import os
import json
from pathlib import Path
import pytest

# Import your functions (adjust module name if needed)
from PM_Report.pipeline import detect_os_from_file, extract


# --------- Configure these keys as per your row contract ----------
REQUIRED_KEYS = {
    "File name",
    "Host name", "Model number", "Serial number",
    "Interface ip address", "Uptime", "Current s/w version",
    "Last Reboot Reason", "Any Debug?", "CPU Utilization",
    "Total memory", "Used memory", "Free memory", "Memory Utilization (%)",
    "Total flash memory", "Used flash memory", "Free flash memory", "Used Flash (%)",
    "Fan status", "Temperature status", "PowerSupply status", "Available Free Ports",
    "End-of-Sale Date: HW", "Last Date of Support: HW", "End of Routine Failure Analysis Date:  HW",
    "End of Vulnerability/Security Support: HW", "End of SW Maintenance Releases Date: HW",
    "Any Half Duplex", "Interface/Module Remark", "Config Status", "Config Save Date",
    "Critical logs",
    "Current SW EOS", "Suggested s/w ver", "s/w release date",
    "Latest S/W version", "Production s/w is deffered or not?",
    "Remark",
    "__os_kind",
}


def _get_logs_dir() -> Path:
    """
    Point this to your folder with 1222 files.
    Recommended: set env var PM_LOGS_DIR so tests are portable.
    """
    p = os.environ.get(r"C:\Users\girish.n\Downloads\PM logs sets\Ultimate_logs")
    if not p:
        pytest.skip("Set PM_LOGS_DIR to the folder containing the 1222 logs.")
    d = Path(p)
    if not d.exists() or not d.is_dir():
        pytest.skip(f"PM_LOGS_DIR path invalid: {d}")
    return d


def _list_log_files(d: Path):
    return sorted([p for p in d.iterdir() if p.is_file() and p.suffix.lower() in (".txt", ".log")])


# ------------------------------------------------------------------------------
# 1) Smoke test: OS detection should not crash on any file
# ------------------------------------------------------------------------------
def test_detect_os_on_all_files_no_crash():
    d = _get_logs_dir()
    files = _list_log_files(d)
    assert len(files) > 0, "No .txt/.log files found in PM_LOGS_DIR"

    results = {"ios": 0, "ios_xe": 0, "other": 0}
    for fp in files:
        kind = detect_os_from_file(str(fp))
        assert isinstance(kind, str)
        if kind == "ios":
            results["ios"] += 1
        elif kind == "ios_xe":
            results["ios_xe"] += 1
        else:
            results["other"] += 1

    # At minimum, prove everything classified into some bucket
    assert sum(results.values()) == len(files)


# ------------------------------------------------------------------------------
# 2) Full pipeline: extract() should return one row per candidate and schema-safe
# ------------------------------------------------------------------------------
def test_extract_schema_and_counts():
    d = _get_logs_dir()
    rows = extract(str(d))

    # extract() only considers .txt/.log in the directory root (not recursive)
    candidates = _list_log_files(d)

    assert len(candidates) > 0
    # Depending on your filter/skip behavior, this should typically match
    assert len(rows) == len(candidates), (
        f"Row count mismatch: rows={len(rows)} candidates={len(candidates)}"
    )

    # Schema & type checks
    for row in rows:
        assert isinstance(row, dict)
        missing = REQUIRED_KEYS - set(row.keys())
        assert not missing, f"Missing keys: {sorted(missing)}"

        # Basic sanity: File name is a list with one string (per your contract)
        assert isinstance(row["File name"], list) and row["File name"], "Bad File name field"
        assert isinstance(row["File name"][0], str)

        # __os_kind must be string
        assert isinstance(row["__os_kind"], str)


# ------------------------------------------------------------------------------
# 3) Stability test: extract results should be deterministic (order + __os_kind)
# ------------------------------------------------------------------------------
def test_extract_deterministic_os_kind():
    d = _get_logs_dir()

    rows1 = extract(str(d))
    rows2 = extract(str(d))

    # Compare (filename, os_kind) sequences
    sig1 = [(r["File name"][0], r["__os_kind"]) for r in rows1]
    sig2 = [(r["File name"][0], r["__os_kind"]) for r in rows2]

    assert sig1 == sig2, "extract() results differ between runs (non-deterministic)"


# ------------------------------------------------------------------------------
# 4) Optional: drift guard using expected counts
#    Set env vars once you know the baseline counts.
# ------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "env_key,expected_type",
    [("PM_EXPECT_IOS", int), ("PM_EXPECT_IOSXE", int), ("PM_EXPECT_OTHER", int)],
)
def test_expected_counts_env_optional(env_key, expected_type):
    # This test only runs if you set the env var.
    val = os.environ.get(env_key)
    if val is None:
        pytest.skip(f"{env_key} not set; skipping drift guard test")
    int(val)  # validate convertible


def test_expected_counts_guard_optional():
    d = _get_logs_dir()
    files = _list_log_files(d)

    exp_ios = os.environ.get("PM_EXPECT_IOS")
    exp_xe = os.environ.get("PM_EXPECT_IOSXE")
    exp_other = os.environ.get("PM_EXPECT_OTHER")
    if not (exp_ios and exp_xe and exp_other):
        pytest.skip("Set PM_EXPECT_IOS, PM_EXPECT_IOSXE, PM_EXPECT_OTHER to enable this drift guard.")

    results = {"ios": 0, "ios_xe": 0, "other": 0}
    for fp in files:
        kind = detect_os_from_file(str(fp))
        if kind == "ios":
            results["ios"] += 1
        elif kind == "ios_xe":
            results["ios_xe"] += 1
        else:
            results["other"] += 1

    assert results["ios"] == int(exp_ios)
    assert results["ios_xe"] == int(exp_xe)
    assert results["other"] == int(exp_other)
