from __future__ import annotations

import pytest


def test_build_autopop_command_contains_safe_limits():
    pytest.importorskip("sqlalchemy")
    from app.services.autopop_jobs import build_autopop_command

    command = build_autopop_command({
        "limit_categories": 1,
        "limit_series_eox": 10,
        "limit_announcements": 2,
        "parse_workers": 3,
        "delay": 1,
        "category_break": 15,
        "force_refresh": True,
    })
    assert "auto_pop_pid_database.py" in command[1]
    assert "--limit-categories" in command
    assert "--parse-workers" in command
    assert "--force-refresh" in command
