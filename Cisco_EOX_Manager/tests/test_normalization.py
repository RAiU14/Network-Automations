from __future__ import annotations

from app.services.normalization import clean_pid_list, normalize_pid


def test_normalize_pid_removes_spacing_and_case_noise() -> None:
    assert normalize_pid(" c9300-24t ") == "C9300-24T"
    assert normalize_pid("AIR CT5520 K9") == "AIRCT5520K9"


def test_clean_pid_list_deduplicates_in_order() -> None:
    assert clean_pid_list(["C9300-24T", " c9300-24t ", "N9K-C93180YC-FX"]) == ["C9300-24T", "N9K-C93180YC-FX"]
