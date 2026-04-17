import re

# --- Variant A: current (dashed-only) ------------------------------------------
NEXT_SECTION_DASHED_ONLY = re.compile(r"(?im)^\s*-+\s*sh(?:ow)?\b")

# --- Variant B: dashed OR prompt-based (hostname#show) -------------------------
NEXT_SECTION_DASHED_OR_PROMPT = re.compile(
    r"""(?im)^\s*(?:-+\s*sh(?:ow)?\b|\S+[>#]\s*sh(?:ow)?\b)"""
)

# --- Show version start detectors (copied from your logic) ---------------------
SHOW_VER_START = re.compile(r"(?im)^\s*-+\s*sh(?:ow)?\s+ver(?:sion)?\s*-+\s*$")
SHOW_VER_ECHO = re.compile(r"(?im)^.*?\bsh(?:ow)?\s+ver(?:sion)?\s*$")


def scope_show_version(text: str, next_section_regex: re.Pattern) -> str:
    """
    Minimal replica of your _scope_show_version but with injectable next-section regex,
    so we can unit-test which boundary regex is safer.
    """
    if not text:
        return ""

    m = SHOW_VER_START.search(text) or SHOW_VER_ECHO.search(text)
    if not m:
        return ""

    start = m.end()
    n = next_section_regex.search(text, pos=start)
    end = n.start() if n else len(text)
    return text[start:end]


# ------------------------------------------------------------------------------
# Test Fixtures
# ------------------------------------------------------------------------------

DASHED_LOG = """\
----- show version -----
Cisco IOS XE Software, Version 17.9.7a
System image file is "bootflash:packages.conf"

Some normal output line
----- show inventory -----
NAME: "Chassis", DESCR: "Cisco ASR1004"
PID: ASR1004 , VID: V05 , SN: FOX1421GBWY
"""

PROMPT_LOG_NO_DASHES = """\
SYNARL_06A_BMS_AS01#show version
Cisco IOS Software, C3750 Software (C3750-IPBASEK9-M), Version 12.2(55)SE12

SYNARL_06A_BMS_AS01#show inventory
NAME: "1", DESCR: "WS-C3750-48P"
PID: WS-C3750-48P , VID: V05 , SN: FOC1234ABCD
"""

# This is the critical case:
# The file contains dashed headers, but within the show version output there is a line
# that *looks like* a prompt command at start-of-line (e.g., pasted troubleshooting notes).
# A "dashed OR prompt" next-section regex will falsely treat this as the next section boundary
# and will truncate the show version block too early.
DASHED_LOG_WITH_PROMPT_LIKE_LINE_INSIDE_OUTPUT = """\
----- show version -----
Cisco IOS XE Software, Version 17.9.7a
Uptime is 2 weeks, 3 days

SYNARL_06A_BMS_AS01#show module
(This line is NOT a new section header; it's embedded text)

More show version output that should be included...
----- show inventory -----
PID: ASR1004 , SN: FOX1421GBWY
"""


# ------------------------------------------------------------------------------
# Tests: Dashed-only is safest when dashed section markers exist
# ------------------------------------------------------------------------------

def test_dashed_only_scopes_until_next_dashed_header():
    scoped = scope_show_version(DASHED_LOG, NEXT_SECTION_DASHED_ONLY)

    # should include the show version output
    assert "Cisco IOS XE Software" in scoped
    assert 'System image file is "bootflash:packages.conf"' in scoped

    # should NOT include inventory section
    assert "show inventory" not in scoped
    assert "PID: ASR1004" not in scoped


def test_dashed_or_prompt_also_works_for_pure_dashed_logs():
    scoped = scope_show_version(DASHED_LOG, NEXT_SECTION_DASHED_OR_PROMPT)

    assert "Cisco IOS XE Software" in scoped
    assert "PID: ASR1004" not in scoped  # should still stop at dashed inventory


def test_dashed_only_is_safer_when_prompt_like_line_appears_inside_output():
    scoped = scope_show_version(
        DASHED_LOG_WITH_PROMPT_LIKE_LINE_INSIDE_OUTPUT,
        NEXT_SECTION_DASHED_ONLY
    )

    # Dashed-only should NOT treat the prompt-like line as a new section
    assert "Cisco IOS XE Software" in scoped
    assert "SYNARL_06A_BMS_AS01#show module" in scoped
    assert "More show version output that should be included..." in scoped

    # Still should stop before inventory
    assert "PID: ASR1004" not in scoped


def test_dashed_or_prompt_can_be_unsafe_truncates_on_prompt_like_line_inside_output():
    scoped = scope_show_version(
        DASHED_LOG_WITH_PROMPT_LIKE_LINE_INSIDE_OUTPUT,
        NEXT_SECTION_DASHED_OR_PROMPT
    )

    # It will likely truncate early (this proves the risk)
    assert "Cisco IOS XE Software" in scoped

    # The "prompt-like" line becomes the false boundary; content after it is lost
    assert "More show version output that should be included..." not in scoped

    # inventory is still not included, but scope is incorrectly cut short
    assert "PID: ASR1004" not in scoped


# ------------------------------------------------------------------------------
# Tests: coverage gap (dashed-only won't separate prompt-based logs)
# ------------------------------------------------------------------------------

def test_prompt_logs_no_dashes_dashed_only_cannot_find_a_next_section_boundary():
    scoped = scope_show_version(PROMPT_LOG_NO_DASHES, NEXT_SECTION_DASHED_ONLY)

    # Because dashed-only can't find a "next section" delimiter,
    # it will likely include everything after show version, including inventory.
    assert "Cisco IOS Software" in scoped
    assert "show inventory" in scoped
    assert "PID: WS-C3750-48P" in scoped


def test_prompt_logs_no_dashes_dashed_or_prompt_can_stop_at_next_prompt_show():
    scoped = scope_show_version(PROMPT_LOG_NO_DASHES, NEXT_SECTION_DASHED_OR_PROMPT)

    # This variant can detect the "hostname#show inventory" boundary
    assert "Cisco IOS Software" in scoped
    assert "show inventory" not in scoped
    assert "PID: WS-C3750-48P" not in scoped
