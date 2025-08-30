# Cisco_IOS_XE.py
# Fully instrumented with structured logging via logging_setup.configure_logging

from __future__ import annotations

import os
import re
import datetime
import pprint as pp

# central logging initializer
from logging_setup import configure_logging
logger = configure_logging(__file__)

# NOTE: keep this as an absolute/flat import if you run this as a script next to IOS_XE_Stack_Switch.py
# If this lives inside a package, change to: from . import IOS_XE_Stack_Switch
try:
    # when used as a package (e.g., from Switching or PM_Report)
    from . import IOS_XE_Stack_Switch  # type: ignore
    logger.debug("Imported IOS_XE_Stack_Switch via relative import (package mode).")
except Exception:
    try:
        import Cisco_IOS_XE  # type: ignore
        logger.debug("Imported IOS_XE_Stack_Switch via flat import (script mode).")
    except Exception as e:
        logger.error(f"Unable to import Cisco_IOS_XE: {e}")


# ---------- Static strings ----------
NA = "Not available"
YET_TO_CHECK = "Yet to check"

# ---------- Regex helpers ----------
_INTERFACE_BLOCK_RE = re.compile(r'(?ms)^interface\s+\S+.*?(?=^interface\s+\S+|\Z)')
_MGMT_MARKERS = (
    r'no\s+ip\s+redirects',
    r'no\s+ip\s+unreachables',
    r'no\s+ip\s+proxy-arp',
    r'no\s+ip\s+route-cache',
)
_IP_LINE_RE = re.compile(
    r'^\s*ip\s+address\s+'
    r'(?P<ip>\d{1,3}(?:\.\d{1,3}){3})'
    r'(?:\s+(?:\d{1,3}(?:\.\d{1,3}){3}|/\d{1,2}))?'
    r'(?:\s+secondary)?\s*$',
    re.IGNORECASE | re.MULTILINE
)
_PREFER_NAME_RE = re.compile(r'(?im)^interface\s+(?:(?:vlan\d+)|(?:loopback0)|(?:bdi\d+))\b')
_DESC_MGMT_RE   = re.compile(r'(?im)^\s*description\s+.*\b(mgmt|manage|management)\b')
_IP_RE = re.compile(r'^\s*(\d+)\.(\d+)\.(\d+)\.(\d+)\s*$')


# ==========================
# Utility helpers
# ==========================

def _marker_score(block: str) -> int:
    """Score a stanza by how many management-hardening markers it contains."""
    score = 0
    for pat in _MGMT_MARKERS:
        if re.search(pat, block, flags=re.IGNORECASE):
            score += 1
    logger.debug(f"_marker_score: {score} for block header={block.splitlines()[0:1]}")
    return score

def _prefer_rank(block: str) -> int:
    """
    Lower is better.
    0: SVI/Loopback/BDI with 'management' hint in description
    1: SVI/Loopback/BDI without desc hint
    2: Anything else with desc hint
    3: Anything else
    """
    is_pref_if = bool(_PREFER_NAME_RE.search(block))
    has_mgmt_desc = bool(_DESC_MGMT_RE.search(block))
    if is_pref_if and has_mgmt_desc:
        rank = 0
    elif is_pref_if:
        rank = 1
    elif has_mgmt_desc:
        rank = 2
    else:
        rank = 3
    logger.debug(f"_prefer_rank: rank={rank} (is_pref_if={is_pref_if}, has_mgmt_desc={has_mgmt_desc})")
    return rank

def sanitize_ipv4(value: str) -> str:
    """
    Normalize IPv4 (strip, remove leading zeros, drop CIDR).
    Returns:
      - normalized IPv4 string
      - "Not available" for empty-ish
      - "Require Manual Check" for malformed
    """
    logger.debug(f"sanitize_ipv4: raw={value!r}")
    if value is None:
        return "Not available"
    s = str(value).strip()
    if s == "" or s.lower() in {"n/a", "na", "not available", "unavailable"}:
        return "Not available"

    # strip CIDR / trailing junk
    if "/" in s:
        s = s.split("/", 1)[0].strip()
    elif " " in s and _IP_RE.search(s.split(" ")[0] or ""):
        s = s.split(" ", 1)[0].strip()

    m = _IP_RE.match(s)
    if not m:
        logger.debug(f"sanitize_ipv4: malformed token={s!r}")
        return "Require Manual Check"

    octets = [int(x) for x in m.groups()]
    if any(o < 0 or o > 255 for o in octets):
        logger.debug(f"sanitize_ipv4: octet out of range={octets}")
        return "Require Manual Check"

    s_norm = ".".join(str(o) for o in octets)
    if s_norm in {"0.0.0.0", "255.255.255.255"}:
        logger.debug(f"sanitize_ipv4: unusable address={s_norm}")
        return "Require Manual Check"

    logger.debug(f"sanitize_ipv4: normalized={s_norm}")
    return s_norm

def _is_valid_ipv4(addr: str) -> bool:
    try:
        parts = addr.split(".")
        if len(parts) != 4:
            return False
        for p in parts:
            if not p.isdigit():
                return False
            n = int(p)
            if n < 0 or n > 255:
                return False
        return True
    except Exception:
        return False


# ==========================
# Primitive field extractors
# ==========================

def log_type(log_data):
    if not isinstance(log_data, str):
        logger.error("Invalid input type for log_data")
        return "Not a .txt or .log file"
    return "OK"

def get_hostname(log_data):
    logger.info("get_hostname: start")
    try:
        match = re.search(r"hostname\s+(\S+)", log_data)
        out = match.group(1) if match else "Require Manual Check"
        logger.debug(f"get_hostname: result={out}")
        return out
    except Exception as e:
        logger.exception("get_hostname: exception")
        return f"Error in get_hostname: {e}"

def get_model_number(log_data):
    logger.info("get_model_number: start")
    try:
        match = re.search(r"Model Number\s+:\s+(\S+)", log_data)
        out = match.group(1) if match else "Require Manual Check"
        logger.debug(f"get_model_number: result={out}")
        return out
    except Exception as e:
        logger.exception("get_model_number: exception")
        return f"Error in get_model_number: {e}"

def get_serial_number(log_data):
    logger.info("get_serial_number: start")
    try:
        match = re.search(r"System Serial Number\s+:\s+(\S+)", log_data)
        out = match.group(1) if match else "Require Manual Check"
        logger.debug(f"get_serial_number: result={out}")
        return out
    except Exception as e:
        logger.exception("get_serial_number: exception")
        return f"Error in get_serial_number: {e}"

def get_uptime(log_data):
    logger.info("get_uptime: start")
    try:
        hostname = get_hostname(log_data)
        if not hostname or hostname == "Not available":
            logger.debug("get_uptime: hostname unavailable → Not available")
            return "Not available"
        pattern = rf"{re.escape(hostname)}\s+uptime is\s+(.+)"
        match = re.search(pattern, log_data)
        out = match.group(1).strip() if match else "Require Manual Check"
        logger.debug(f"get_uptime: result={out}")
        return out
    except Exception as e:
        logger.exception("get_uptime: exception")
        return f"Error in get_uptime: {e}"

def get_current_sw_version(log_data):
    """
    Returns IOS-XE/IOS version string from 'show version' banner variants.
    """
    logger.info("get_current_sw_version: start")
    try:
        if not log_data:
            logger.debug("get_current_sw_version: empty log → Not available")
            return "Not available"

        m = re.search(r'(?mi)^\s*Cisco\s+IOS\s+XE\s+Software,\s*Version\s+([^\s,]+)', log_data)
        if m:
            out = m.group(1).strip()
            logger.debug(f"get_current_sw_version: XE explicit → {out}")
            return out

        m = re.search(r'(?mi)^\s*Cisco\s+IOS\s+Software.*?\bVersion\s+([^\s,]+)', log_data)
        if m:
            out = m.group(1).strip()
            logger.debug(f"get_current_sw_version: classic banner → {out}")
            return out

        m = re.search(r'(?mi)\bIOS[- ]?XE\s+Software.*?\bVersion\s+([^\s,]+)', log_data)
        if m:
            out = m.group(1).strip()
            logger.debug(f"get_current_sw_version: safety net → {out}")
            return out

        head = "\n".join(log_data.splitlines()[:50])
        m = re.search(r'(?mi)\bVersion\s+([0-9A-Za-z.\(\)]+)', head)
        out = m.group(1).strip() if m else "Not available"
        logger.debug(f"get_current_sw_version: head scan → {out}")
        return out
    except Exception as e:
        logger.exception("get_current_sw_version: exception")
        return "Not available"

def get_last_reboot_reason(log_data):
    logger.info("get_last_reboot_reason: start")
    try:
        match = re.search(r"Last reload reason:\s+(.+)", log_data)
        out = match.group(1) if match else "Require Manual Check"
        logger.debug(f"get_last_reboot_reason: result={out}")
        return out
    except Exception as e:
        logger.exception("get_last_reboot_reason: exception")
        return f"Error in get_last_reboot_reason: {e}"

def get_cpu_utilization(log_data):
    logger.info("get_cpu_utilization: start")
    try:
        match = re.search(r"five minutes:\s+(\d+)%", log_data)
        out = (match.group(1) + "%") if match else "Require Manual Check"
        logger.debug(f"get_cpu_utilization: result={out}")
        return out
    except Exception as e:
        logger.exception("get_cpu_utilization: exception")
        return f"Error in get_cpu_utilization: {e}"


# ==========================
# IP discovery helpers
# ==========================

def get_ip(log_data: str):
    """
    Heuristic mgmt IPv4 selection from interface stanzas.
    """
    logger.info("get_ip: start")
    try:
        if not log_data:
            logger.debug("get_ip: empty log")
            return None

        blocks = _INTERFACE_BLOCK_RE.findall(log_data)
        logger.debug(f"get_ip: found interface blocks={len(blocks)}")

        candidates = []
        for blk in blocks:
            if re.search(r'(?im)^\s*ip\s+address\s+dhcp\b', blk):
                continue

            ips_in_block = []
            for m in _IP_LINE_RE.finditer(blk):
                ip = m.group('ip')
                line_str = m.group(0)
                if re.search(r'\bsecondary\b', line_str, flags=re.IGNORECASE):
                    continue
                ips_in_block.append(ip)

            if not ips_in_block:
                continue

            score = _marker_score(blk)
            rank = _prefer_rank(blk)
            candidates.append((score, rank, ips_in_block, blk.splitlines()[0] if blk else ""))

        logger.debug(f"get_ip: candidates={[(s, r, ips, hdr) for s, r, ips, hdr in candidates]}")

        if candidates:
            candidates.sort(key=lambda t: (-t[0], t[1]))
            best = candidates[0]
            _, _, ips, hdr = best
            logger.debug(f"get_ip: best block hdr={hdr}, ips={ips}")
            for raw_ip in ips:
                ip_norm = sanitize_ipv4(raw_ip)
                if ip_norm not in {"Not available", "Require Manual Check"}:
                    logger.info(f"get_ip: selected={ip_norm}")
                    return ip_norm

        # fallback: any IPv4-ish token
        any_ip = re.search(r'(\d{1,3}(?:\.\d{1,3}){3}(?:/\d{1,2})?)', log_data)
        if any_ip:
            ip_norm = sanitize_ipv4(any_ip.group(1))
            if ip_norm not in {"Not available", "Require Manual Check"}:
                logger.info(f"get_ip: fallback selected={ip_norm}")
                return ip_norm

        logger.debug("get_ip: no candidate found")
        return None
    except Exception:
        logger.exception("get_ip: exception")
        return None

def get_ip_address(file_path):
    """
    Returns (file_name, ip_or_status).
    Priority: filename → content scan → stanza heuristic → Require Manual Check
    """
    logger.info(f"get_ip_address: start path={file_path}")
    try:
        file_name = os.path.basename(file_path) if isinstance(file_path, str) else str(file_path)

        filename_candidates = re.findall(r"(\d{1,3}(?:\.\d{1,3}){3}(?:/\d{1,2})?)", file_name)
        logger.debug(f"get_ip_address: filename candidates={filename_candidates}")
        for cand in filename_candidates:
            ip_norm = sanitize_ipv4(cand)
            if ip_norm not in {"Not available", "Require Manual Check"}:
                logger.info(f"get_ip_address: from filename → {ip_norm}")
                return (file_name, ip_norm)

        try:
            with open(file_path, "r", errors="ignore") as f:
                log_data = f.read()
            content_candidates = re.findall(r"(\d{1,3}(?:\.\d{1,3}){3}(?:/\d{1,2})?)", log_data)
            logger.debug(f"get_ip_address: content candidates={len(content_candidates)}")
            for cand in content_candidates:
                ip_norm = sanitize_ipv4(cand)
                if ip_norm not in {"Not available", "Require Manual Check"}:
                    logger.info(f"get_ip_address: from content → {ip_norm}")
                    return (file_name, ip_norm)

            from_content = get_ip(log_data)
            ip_norm = sanitize_ipv4(from_content)
            if ip_norm not in {"Not available", "Require Manual Check"}:
                logger.info(f"get_ip_address: from heuristic → {ip_norm}")
                return (file_name, ip_norm)
        except Exception as inner:
            logger.warning(f"get_ip_address: content read failed: {inner}")

        logger.info("get_ip_address: no valid IP → Require Manual Check")
        return (file_name, "Require Manual Check")

    except Exception as e:
        logger.exception("get_ip_address: exception")
        safe_name = os.path.basename(file_path) if isinstance(file_path, str) else "Unknown"
        return (safe_name, "Require Manual Check")


# ==========================
# Stack detection
# ==========================

def check_stack(log_data):
    logger.info("check_stack: start")
    try:
        cleared_data_start = re.search('show version', log_data, re.IGNORECASE)
        if not cleared_data_start:
            logger.debug("check_stack: no 'show version' found")
            return False

        cleared_data_end = re.search('show', log_data[cleared_data_start.span()[1] + 1:], re.IGNORECASE)
        if not cleared_data_end:
            req_data = log_data[cleared_data_start.span()[1]:]
        else:
            req_data = log_data[cleared_data_start.span()[1]:cleared_data_start.span()[1] + cleared_data_end.span()[0]]

        start_point = re.search(r"System Serial Number\s+:\s+(\S+)", req_data)
        if not start_point:
            logger.debug("check_stack: no 'System Serial Number' found")
            return False

        next_start_end_point = re.search(r"Switch\s+(\S+)", req_data[start_point.span()[1]:])
        if not next_start_end_point:
            logger.debug("check_stack: no 'Switch <n>' block found")
            return False

        stack_details = IOS_XE_Stack_Switch.parse_ios_xe_stack_switch(log_data)
        logger.debug(f"check_stack: parsed stack_details keys={list(stack_details.keys())}")
        return stack_details
    except Exception as e:
        logger.exception("check_stack: exception")
        return f"Error in check_stack: {e}"


# ==========================
# Memory / Flash
# ==========================

def get_memory_info(log_data):
    """
    Returns [total, used, free, "XX.XX%"] or "Not available" list on failure.
    """
    logger.info("get_memory_info: start")
    try:
        if not log_data:
            logger.debug("get_memory_info: empty log")
            return [NA, NA, NA, NA]

        def _parse_num_with_unit(token: str) -> int | None:
            if not token:
                return None
            s = token.strip().replace(",", "")
            m = re.match(r'^(\d+(?:\.\d+)?)([KkMmGg])?$', s)
            if not m:
                if s.isdigit():
                    try:
                        return int(s)
                    except Exception:
                        return None
                return None
            num = float(m.group(1))
            unit = m.group(2).upper() if m.group(2) else None
            mult = 1
            if unit == 'K':
                mult = 1024
            elif unit == 'M':
                mult = 1024 ** 2
            elif unit == 'G':
                mult = 1024 ** 3
            return int(num * mult)

        m = re.search(r'(?mi)^\s*Processor\s+\S+\s+(\d+)\s+(\d+)\s+(\d+)\b', log_data)
        if m:
            total = int(m.group(1)); used = int(m.group(2)); free = int(m.group(3))
            if total <= 0:
                logger.error("get_memory_info: total is zero in Processor table")
                return [NA, NA, NA, NA]
            util = (used / total) * 100.0
            out = [total, used, free, f"{util:.2f}%"]
            logger.debug(f"get_memory_info: Processor table → {out}")
            return out

        m2 = re.search(
            r'(?mi)^\s*System\s+memory\s*:\s*'
            r'(?P<total>[0-9,]+[KkMmGg]?)\s+total,\s*'
            r'(?P<used>[0-9,]+[KkMmGg]?)\s+used,\s*'
            r'(?P<free>[0-9,]+[KkMmGg]?)\s+free', log_data
        )
        if m2:
            total = _parse_num_with_unit(m2.group('total'))
            used  = _parse_num_with_unit(m2.group('used'))
            free  = _parse_num_with_unit(m2.group('free'))
            if total is None or used is None or free is None or total <= 0:
                logger.error("get_memory_info: parse failure in System memory")
                return [NA, NA, NA, NA]
            util = (used / total) * 100.0
            out = [total, used, free, f"{util:.2f}%"]
            logger.debug(f"get_memory_info: System memory summary → {out}")
            return out

        logger.debug("get_memory_info: no pattern matched")
        return [NA, NA, NA, NA]
    except Exception as e:
        logger.exception("get_memory_info: exception")
        return [NA, NA, NA, NA]

def calculate_flash_utilization(available_bytes, used_bytes):
    logger.debug(f"calculate_flash_utilization: available={available_bytes}, used={used_bytes}")
    total = available_bytes + used_bytes
    free = available_bytes
    used = total - free
    if total == 0:
        logger.error("calculate_flash_utilization: total is zero")
        utilization = 0
    else:
        utilization = (used / total) * 100
    out = (total, used, free, utilization)
    logger.debug(f"calculate_flash_utilization: result={out}")
    return out

def get_flash_info(log_data):
    logger.info("get_flash_info: start")
    try:
        total_flashes = re.findall(r"show\s+flash(?:-\d+)?:\s*all", log_data)
        flash_information = {}
        if total_flashes:
            for item in total_flashes:
                start_index = re.search(item, log_data)
                if start_index:
                    end_index = re.search(r"show\s", log_data[start_index.span()[1]:])
                    if end_index:
                        flash_data = log_data[start_index.span()[1]:start_index.span()[1] + end_index.span()[0]]
                        m = re.findall(r'^\s*(\d+)\s+bytes\s+available\s+\((\d+)\s+bytes\s+used\)', flash_data, re.MULTILINE)
                        if m:
                            for available_str, used_str in m:
                                available_bytes = int(available_str)
                                used_bytes = int(used_str)
                                total, used, free, utilization = calculate_flash_utilization(available_bytes, used_bytes)
                                flash_number = re.findall(r'\d+', item)
                                key = flash_number[0] if flash_number else '1'
                                flash_information[key] = [total, used, free, utilization]
            logger.debug(f"get_flash_info: parsed → {flash_information}")
            return flash_information if flash_information else "No flash information found"
        logger.debug("get_flash_info: no 'show flash' sections")
        return "No flash information found"
    except Exception as e:
        logger.exception("get_flash_info: exception")
        return f"Error in get_flash_info: {e}"


# ==========================
# Environment (Fans / Temp / PSU)
# ==========================

def get_temperature_status(log_data: str):
    """
    Returns ["OK"/"Not OK", ...] per switch or ["Not available"].
    """
    logger.info("get_temperature_status: start")
    try:
        per_switch_ok = {}

        m_sys = re.findall(r'(?mi)^\s*SYSTEM\s+(?:INLET|OUTLET|HOTSPOT)\s+(\d+)\s+([A-Z]+)', log_data)
        if m_sys:
            tmp = {}
            for sw_str, state in m_sys:
                sw = int(sw_str)
                state_up = state.strip().upper()
                prev = tmp.get(sw, True)
                tmp[sw] = prev and (state_up == "GREEN")
            per_switch_ok.update(tmp)
            logger.debug(f"get_temperature_status: 17.x blocks → {tmp}")

        m_legacy = re.findall(r'(?mi)^\s*Switch\s+(\d+):\s*SYSTEM\s+TEMPERATURE\s+is\s+([A-Za-z ]+)\s*$', log_data)
        if m_legacy:
            tmp = {}
            for sw_str, status_text in m_legacy:
                sw = int(sw_str)
                ok = (status_text.strip().upper() == "OK")
                prev = tmp.get(sw, True)
                tmp[sw] = prev and ok
            for sw, ok in tmp.items():
                per_switch_ok[sw] = per_switch_ok.get(sw, True) and ok
            logger.debug(f"get_temperature_status: legacy blocks → {tmp}")

        if not per_switch_ok:
            logger.debug("get_temperature_status: no matches")
            return ["Not available"]

        result = ["OK" if per_switch_ok[sw] else "Not OK" for sw in sorted(per_switch_ok.keys())]
        logger.debug(f"get_temperature_status: result={result}")
        return result if result else ["Not available"]
    except Exception as e:
        logger.exception("get_temperature_status: exception")
        return [f"Error in get_temperature_status: {e}"]


def get_fan_status(log_data: str):
    """
    Returns ["OK"/"Not OK", ...] per switch or ["Not available"].
    Newer 17.x tables and legacy "Switch N FAN X is OK" are supported.
    """
    logger.info("get_fan_status: start")
    try:
        per_switch_ok = {}

        # legacy: "Switch 1 FAN 2 is OK"
        m_legacy = re.findall(r'(?mi)^\s*Switch\s+(\d+)\s+FAN\s+\d+\s+is\s+([A-Za-z ]+)\s*$', log_data)
        if m_legacy:
            tmp = {}
            for sw_str, state_text in m_legacy:
                sw = int(sw_str)
                st = state_text.strip().upper()
                is_ok = (st == "OK" or st == "NOT PRESENT")
                prev = tmp.get(sw, True)
                tmp[sw] = prev and is_ok
            per_switch_ok.update(tmp)
            logger.debug(f"get_fan_status: legacy → {tmp}")

        # 17.x table header
        if re.search(r'(?mi)^\s*Switch\s+FAN\s+Speed\s+State\s+Airflow\s+direction\s*$', log_data):
            blocks = re.split(r'(?mi)^\s*Switch\s+FAN\s+Speed\s+State\s+Airflow\s+direction\s*$', log_data)
            tmp = {}
            for blk in blocks[1:]:
                for raw in blk.splitlines():
                    line = raw.strip()
                    if not line or line.startswith('-'):
                        continue
                    cols = line.split()
                    if len(cols) >= 3 and cols[0].isdigit() and cols[1].isdigit():
                        sw = int(cols[0])
                        st = cols[2].upper()
                        is_ok = (st == "OK")
                        prev = tmp.get(sw, True)
                        tmp[sw] = prev and is_ok
            for sw, ok in tmp.items():
                per_switch_ok[sw] = per_switch_ok.get(sw, True) and ok
            logger.debug(f"get_fan_status: 17.x table → {tmp}")

        if not per_switch_ok:
            logger.debug("get_fan_status: no matches")
            return ["Not available"]

        result = ["OK" if per_switch_ok[sw] else "Not OK" for sw in sorted(per_switch_ok.keys())]
        logger.debug(f"get_fan_status: result={result}")
        return result if result else ["Not available"]
    except Exception as e:
        logger.exception("get_fan_status: exception")
        return [f"Error in get_fan_status: {e}"]


def get_power_supply_status(log_data: str):
    """
    Returns list per switch:
      - "OK" | "<slot>: Not Present" | "<slot>: NOT OK" | "UNKNOWN" | "Not available"
    """
    logger.info("get_power_supply_status: start")
    try:
        lines = log_data.splitlines()
        per_switch_slots = {}
        in_psu_table = False

        header_re = re.compile(r'(?mi)^\s*SW\s+PID\s+.*Serial#\s+.*Status')
        row_slot_re = re.compile(r'^\s*(\d+[A-Z])\b', re.IGNORECASE)

        for idx, line in enumerate(lines):
            if not in_psu_table:
                if header_re.search(line):
                    in_psu_table = True
                    logger.debug(f"PSU header found at line {idx}: {line.strip()}")
                    continue
            else:
                if not line.strip() or re.search(r'-{3,}', line) or line.strip().startswith(('Sensor List:', 'Switch FAN')):
                    continue

                m = row_slot_re.match(line)
                if not m:
                    continue

                slot = m.group(1).upper()
                sw = int(slot[:-1])
                norm = line.strip()

                if re.search(r'(?i)\bNot\s+Present\b', norm):
                    status = "Not Present"
                elif re.search(r'(?i)\bOK\b', norm):
                    status = "OK"
                elif re.search(r'(?i)\b(BAD|FAIL|NO\s+INPUT\s+POWER|ALARM)\b', norm):
                    status = "NOT OK"
                else:
                    status = "UNKNOWN"

                per_switch_slots.setdefault(sw, []).append((slot, status))

        if not per_switch_slots:
            logger.warning("get_power_supply_status: no table rows matched")
            return ["Not available"]

        result = []
        for sw in sorted(per_switch_slots.keys()):
            slots = per_switch_slots[sw]
            if any(status == "NOT OK" for _, status in slots):
                bad_slot = next(slot for slot, status in slots if status == "NOT OK")
                result.append(f"{bad_slot}: NOT OK")
            elif any(status == "Not Present" for _, status in slots):
                missing_slot = next(slot for slot, status in slots if status == "Not Present")
                result.append(f"{missing_slot}: Not Present")
            elif all(status == "OK" for _, status in slots):
                result.append("OK")
            else:
                result.append("UNKNOWN")

        logger.debug(f"get_power_supply_status: result={result}")
        return result

    except Exception as e:
        logger.exception("get_power_supply_status: exception")
        return [f"Error in get_power_supply_status: {e}"]


# ==========================
# Other checks
# ==========================

def get_debug_status(log_data):
    logger.info("get_debug_status: start")
    try:
        match = re.search(r"sh|show\w*\s*de\w*", log_data, re.IGNORECASE)
        if match:
            hostname = get_hostname(log_data)
            if hostname == "Not available" or not hostname:
                logger.debug("get_debug_status: hostname not found")
                return "Hostname not found"
            end_anchor = rf"\n{re.escape(hostname)}#"
            debug_section_match = re.search(
                rf"Ip Address\s+Port\s*-+\|----------\s*([\s\S]*?){end_anchor}",
                log_data[match.end():],
                re.IGNORECASE
            )
            if debug_section_match and debug_section_match.group(1).strip():
                logger.debug("get_debug_status: debug present → Require Manual Check")
                return "Require Manual Check"
            else:
                logger.debug("get_debug_status: command not found")
                return "Command not found"
        else:
            logger.debug("get_debug_status: no debug command detected")
            return "Command not found"
    except Exception as e:
        logger.exception("get_debug_status: exception")
        return f"Error in get_debug_status: {e}"

def get_available_ports(log_data):
    logger.info("get_available_ports: start")
    try:
        start_marker = "------------------ show interfaces status ------------------"
        end_marker = "------------------ show "
        match = re.search(f"{re.escape(start_marker)}(.*?){re.escape(end_marker)}", log_data, re.DOTALL)
        if match:
            section = match.group(1)
            ports = {}
            for line in section.strip().splitlines()[1:]:
                parts = line.split()
                if 'notconnect' in parts and '1' in parts:
                    try:
                        interface = parts[0]
                        switch_number = int(interface.split('/')[0].replace('Gi', '').replace('Te', '').replace('Ap', ''))
                        ports.setdefault(switch_number, []).append(interface)
                    except (ValueError, IndexError):
                        continue

            max_switch = max(ports.keys()) if ports else 0
            if max_switch > 0:
                port_list = [[int(len(ports.get(i, [])))] for i in range(1, max_switch + 1)]
                logger.debug(f"get_available_ports: per-switch counts={port_list}")
                return port_list

            logger.debug("get_available_ports: no available ports found")
            return [[0]]
        else:
            logger.debug("get_available_ports: section markers not found")
            return [[0]]
    except Exception as e:
        logger.exception("get_available_ports: exception")
        return [[str(e)]]

def get_half_duplex_ports(log_data):
    logger.info("get_half_duplex_ports: start")
    current_stack_size = IOS_XE_Stack_Switch.stack_size(log_data)
    try:
        match = re.findall(r"^(\S+).*a-half.*$", log_data, re.IGNORECASE | re.MULTILINE)
        if match:
            switch_interfaces = {}
            for interface in match:
                try:
                    switch_number = re.search(r'\D+(\d+)/', interface).group(1)
                except AttributeError:
                    continue
                switch_interfaces.setdefault(switch_number, []).append(interface)

            max_switch_number = max(map(int, switch_interfaces.keys()), default=0)
            half_duplex_ports_per_switch = [[int(len(switch_interfaces.get(str(i), [])))] for i in range(1, max_switch_number + 1)]
            logger.debug(f"get_half_duplex_ports: per-switch counts={half_duplex_ports_per_switch}")
            return half_duplex_ports_per_switch
        else:
            logger.debug("get_half_duplex_ports: no matches → zeros")
            return [[0]] * current_stack_size
    except Exception as e:
        logger.exception("get_half_duplex_ports: exception")
        return [["Error"]] * current_stack_size

def get_interface_remark(log_data):
    logger.info("get_interface_remark: start")
    current_stack_size = IOS_XE_Stack_Switch.stack_size(log_data)
    try:
        match = re.findall(r"^(\S+).*a-half.*$", log_data, re.IGNORECASE | re.MULTILINE)
        if match:
            switch_interfaces = {}
            for interface in match:
                m = re.search(r'\D+(\d+)/', interface)
                if not m:
                    continue
                switch_number = m.group(1)
                switch_interfaces.setdefault(switch_number, []).append(interface)

            max_switch_number = max(map(int, switch_interfaces.keys()), default=0)
            interface_remark = [switch_interfaces.get(str(i), []) for i in range(1, max_switch_number + 1)]
            interface_remark = [sublist if sublist else ['Not avialable'] for sublist in interface_remark]
            logger.debug(f"get_interface_remark: result={interface_remark}")
            return interface_remark
        else:
            logger.debug("get_interface_remark: no matches")
            return [["Not available"]] * current_stack_size
    except Exception as e:
        logger.exception("get_interface_remark: exception")
        return [[f"Error in get_interface_remark: {e}"]] * IOS_XE_Stack_Switch.stack_size(log_data)

def get_nvram_config_update(log_data):
    logger.info("get_nvram_config_update: start")
    try:
        match = re.search(r"NVRAM\s+config\s+last\s+updated\s+at\s+(.+)", log_data, re.IGNORECASE)
        if match:
            when = match.group(1).strip().split('by')[0].strip()
            out = ["Yes", when]
            logger.debug(f"get_nvram_config_update: result={out}")
            return out
        else:
            logger.debug("get_nvram_config_update: not found")
            return ["No", "Not available"]
    except Exception as e:
        logger.exception("get_nvram_config_update: exception")
        return [f"Error: {e}", "Not available"]

def get_critical_logs(log_data):
    logger.info("get_critical_logs: start")
    if not isinstance(log_data, str) or not log_data:
        logger.error("get_critical_logs: invalid input")
        return "Error in get_critical_logs: Invalid input"
    try:
        match = re.search(r'(sh|show)\s+(log|logging)\s*-+\n(.*?)(?=\n-+\s*show|\Z)', log_data, re.DOTALL | re.IGNORECASE)
        if match:
            logging_section = match.group(0)
            yes = any(f"-{i}-" in logging_section for i in range(3))
            out = "YES" if yes else "NO"
            logger.debug(f"get_critical_logs: result={out}")
            return out
        else:
            logger.debug("get_critical_logs: no logging section")
            return "No logging section found!"
    except Exception as e:
        logger.exception("get_critical_logs: exception")
        return False


# ==========================
# Orchestration (single file)
# ==========================

def print_data(data):
    logger.info("print_data: start")
    try:
        for key, value in data.items():
            if isinstance(value, dict):
                print(f"{key}:")
                for k, v in value.items():
                    print(f"  {k}: {v}")
            else:
                print(f"{key}: {value}")
        print("\n")
        logger.debug("print_data: printed one device row")
    except Exception as e:
        logger.exception("print_data: exception")

def ios_xe_check(log_data):
    logger.info("ios_xe_check: start")
    try:
        ver = get_current_sw_version(log_data)
        ok = bool(ver and ver != "Not available")
        logger.debug(f"ios_xe_check: version={ver}, is_xe={ok}")
        return ok
    except Exception as e:
        logger.exception("ios_xe_check: exception")
        return False

def _placeholder_entry(file_path, reason_text="Non-IOS_XE"):
    """
    One-row data dict for files that were skipped or failed.
    For Non-IOS-XE rows we fill ALL attributes with 'Unsupported IOS'.
    """
    logger.info(f"_placeholder_entry: start for {file_path}, reason={reason_text}")
    try:
        fname, _ = get_ip_address(file_path)
    except Exception:
        fname = os.path.basename(file_path)

    U = "Unsupported IOS"
    row = {
        "File name": [fname],
        "Host name": [U],
        "Model number": [U],
        "Serial number": [U],
        "Interface ip address": [U],
        "Uptime": [U],
        "Current s/w version": [U],
        "Last Reboot Reason": [U],
        "Any Debug?": [U],
        "CPU Utilization": [U],
        "Total memory": [U],
        "Used memory": [U],
        "Free memory": [U],
        "Memory Utilization (%)": [U],
        "Total flash memory": [U],
        "Used flash memory": [U],
        "Free flash memory": [U],
        "Used Flash (%)": [U],
        "Fan status": [U],
        "Temperature status": [U],
        "PowerSupply status": [U],
        "Available Free Ports": [U],
        "Any Half Duplex": [U],
        "Interface/Module Remark": [U],
        "Config Status": [U],
        "Config Save Date": [U],
        "Critical logs": [U],
        "Current SW EOS": [U],
        "Suggested s/w ver": [U],
        "s/w release date": [U],
        "Latest S/W version": [U],
        "Production s/w is deffered or not?": [U],
        "End-of-Sale Date: HW": [U],
        "Last Date of Support: HW": [U],
        "End of Routine Failure Analysis Date:  HW": [U],
        "End of Vulnerability/Security Support: HW": [U],
        "End of SW Maintenance Releases Date: HW": [U],
        "Remark": [reason_text],
    }
    logger.debug(f"_placeholder_entry: row keys={list(row.keys())}")
    return row

def process_file(file_path):
    logger.info(f"process_file: start path={file_path}")
    try:
        with open(file_path, 'r', errors="ignore") as file:
            log_data = file.read()
        logger.debug(f"process_file: log_data size={len(log_data)}")

        stack = check_stack(log_data)
        logger.debug(f"process_file: stack={bool(stack)}")

        if not stack:
            memory_info = get_memory_info(log_data)
            flash_info = get_flash_info(log_data)
            if isinstance(flash_info, dict):
                flash_info = flash_info.get('1', [NA, NA, NA, NA])
            elif isinstance(flash_info, str):
                flash_info = [NA, NA, NA, NA]

            row = {
                "File name": [get_ip_address(file_path)[0]],
                "Host name": [get_hostname(log_data)],
                "Model number": [get_model_number(log_data)],
                "Serial number": [get_serial_number(log_data)],
                "Interface ip address": [get_ip_address(file_path)[1]],
                "Uptime": [get_uptime(log_data)],
                "Current s/w version": [get_current_sw_version(log_data)],
                "Last Reboot Reason": [get_last_reboot_reason(log_data)],
                "Any Debug?": [get_debug_status(log_data)],
                "CPU Utilization": [get_cpu_utilization(log_data)],
                "Total memory": [memory_info[0]],
                "Used memory": [memory_info[1]],
                "Free memory": [memory_info[2]],
                "Memory Utilization (%)": [memory_info[3]],
                "Total flash memory": [flash_info[0]],
                "Used flash memory": [flash_info[1]],
                "Free flash memory": [flash_info[2]],
                "Used Flash (%)": [f"{flash_info[3]:.2f}%" if isinstance(flash_info[3], (int, float)) else flash_info[3]],
                "Fan status": [get_fan_status(log_data)],
                "Temperature status": [get_temperature_status(log_data)],
                "PowerSupply status": [get_power_supply_status(log_data)],
                "Available Free Ports": [get_available_ports(log_data)],
                "Any Half Duplex": [get_half_duplex_ports(log_data)],
                "Interface/Module Remark": [get_interface_remark(log_data)],
                "Config Status": [get_nvram_config_update(log_data)[0]],
                "Config Save Date": [get_nvram_config_update(log_data)[1]],
                "Critical logs": [get_critical_logs(log_data)],
                # Defaults
                "Current SW EOS": [YET_TO_CHECK],
                "Suggested s/w ver": [YET_TO_CHECK],
                "s/w release date": [YET_TO_CHECK],
                "Latest S/W version": [YET_TO_CHECK],
                "Production s/w is deffered or not?": [YET_TO_CHECK],
                "End-of-Sale Date: HW": [YET_TO_CHECK],
                "Last Date of Support: HW": [YET_TO_CHECK],
                "End of Routine Failure Analysis Date:  HW": [YET_TO_CHECK],
                "End of Vulnerability/Security Support: HW": [YET_TO_CHECK],
                "End of SW Maintenance Releases Date: HW": [YET_TO_CHECK],
                "Remark": [YET_TO_CHECK]
            }
            logger.debug(f"process_file: single member row built")
            return row

        else:
            data = {}
            file_name, hostname, model_number, serial_number, ip_address, uptime = [], [], [], [], [], []
            current_sw, last_reboot, cpu, memo, flash, critical = [], [], [], [], [], []
            total_memory, used_memory, free_memory, memory_utilization = [], [], [], []
            total_flash, used_flash, free_flash, flash_utilization = [], [], [], []
            avail_free, duplex, interface_remark, config_status, config_date = [], [], [], [], []

            current_stack_size = IOS_XE_Stack_Switch.stack_size(log_data)
            stack_switch_data = IOS_XE_Stack_Switch.parse_ios_xe_stack_switch(log_data)
            flash_memory_details = get_flash_info(log_data)

            logger.debug(f"process_file: stack size={current_stack_size}")

            for item in range(current_stack_size):
                if item == 0:
                    file_name.append(get_ip_address(file_path)[0])
                    model_number.append(get_model_number(log_data))
                    serial_number.append(get_serial_number(log_data))
                    uptime.append(get_uptime(log_data))
                    last_reboot.append(get_last_reboot_reason(log_data))
                else:
                    file_name.append(get_ip_address(file_path)[0] + (f"_Stack_{str(item+1)}"))
                    model_number.append(stack_switch_data.get(f'stack switch {item + 1} Model_Number', NA))
                    serial_number.append(stack_switch_data.get(f'stack switch {item + 1} Serial_Number', NA))
                    uptime.append(stack_switch_data.get(f'stack switch {item + 1} Uptime', NA))
                    last_reboot.append(stack_switch_data.get(f'stack switch {item + 1} Last Reboot', NA))

                memo = get_memory_info(log_data)
                total_memory.append(memo[0]); used_memory.append(memo[1]); free_memory.append(memo[2]); memory_utilization.append(memo[3])

                if isinstance(flash_memory_details, dict) and str(item+1) in flash_memory_details:
                    flash = flash_memory_details[str(item+1)]
                elif isinstance(flash_memory_details, dict) and '1' in flash_memory_details:
                    flash = flash_memory_details['1']
                else:
                    flash = [NA, NA, NA, NA]
                total_flash.append(flash[0]); used_flash.append(flash[1]); free_flash.append(flash[2])
                flash_utilization.append(f"{flash[3]:.2f}%" if isinstance(flash[3], (int, float)) else flash[3])

                hostname.append(get_hostname(log_data))
                ip_address.append(get_ip_address(file_path)[1])
                current_sw.append(get_current_sw_version(log_data))
                cpu.append(get_cpu_utilization(log_data))

                fan = get_fan_status(log_data)
                temp = get_temperature_status(log_data)
                psu = get_power_supply_status(log_data)
                critical.append(get_critical_logs(log_data))

                avail_free = get_available_ports(log_data)
                duplex = get_half_duplex_ports(log_data)
                interface_remark = get_interface_remark(log_data)

                config_status.append(get_nvram_config_update(log_data)[0])
                config_date.append(get_nvram_config_update(log_data)[1])

            data["File name"] = file_name
            data["Host name"] = hostname
            data["Model number"] = model_number
            data["Serial number"] = serial_number
            data["Interface ip address"] = ip_address
            data["Uptime"] = uptime
            data["Current s/w version"] = current_sw
            data["Last Reboot Reason"] = last_reboot
            data["Any Debug?"] = [get_debug_status(log_data) for _ in range(current_stack_size)]
            data["CPU Utilization"] = cpu
            data["Total memory"] = total_memory
            data["Used memory"] = used_memory
            data["Free memory"] = free_memory
            data["Memory Utilization (%)"] = memory_utilization
            data["Total flash memory"] = total_flash
            data["Used flash memory"] = used_flash
            data["Free flash memory"] = free_flash
            data["Used Flash (%)"] = flash_utilization
            data["Fan status"] = fan
            data["Temperature status"] = temp
            data["PowerSupply status"] = psu
            data["Critical logs"] = critical
            data["Available Free Ports"] = avail_free
            data["Any Half Duplex"] = duplex
            data["Interface/Module Remark"] = interface_remark
            data["Config Status"] = config_status
            data["Config Save Date"] = config_date
            data["Current SW EOS"] = [YET_TO_CHECK] * current_stack_size
            data["Suggested s/w ver"] = [YET_TO_CHECK] * current_stack_size
            data["s/w release date"] = [YET_TO_CHECK] * current_stack_size
            data["Latest S/W version"] = [YET_TO_CHECK] * current_stack_size
            data["Production s/w is deffered or not?"] = [YET_TO_CHECK] * current_stack_size
            data["End-of-Sale Date: HW"] = [YET_TO_CHECK] * current_stack_size
            data["Last Date of Support: HW"] = [YET_TO_CHECK] * current_stack_size
            data["End of Routine Failure Analysis Date:  HW"] = [YET_TO_CHECK] * current_stack_size
            data["End of Vulnerability/Security Support: HW"] = [YET_TO_CHECK] * current_stack_size
            data["End of SW Maintenance Releases Date: HW"] = [YET_TO_CHECK] * current_stack_size
            data["Remark"] = [YET_TO_CHECK] * current_stack_size

            logger.debug("process_file: stacked row built")
            return data

    except Exception as e:
        logger.exception("process_file: exception")
        return _placeholder_entry(file_path, reason_text=f"ErrorProcessingFailure: {e}")


# ==========================
# Directory orchestrator
# ==========================

def process_directory(directory_path):
    logger.info(f"process_directory: start dir={directory_path}")
    if not isinstance(directory_path, str):
        logger.error("process_directory: invalid input type for directory_path")
        return 500

    if not os.path.isdir(directory_path):
        logger.error(f"process_directory: path does not exist or is not a directory: {directory_path}")
        return 500

    data = []
    try:
        candidates = []
        for filename in os.listdir(directory_path):
            if not (filename.endswith('.txt') or filename.endswith('.log')):
                continue
            if filename.startswith('~$') or filename.startswith('.'):
                continue
            candidates.append(os.path.join(directory_path, filename))

        logger.debug(f"process_directory: candidates={len(candidates)}")

        if not candidates:
            logger.warning("process_directory: no .txt or .log files found")
            return data

        def _process_one(file_path):
            logger.info(f"_process_one: start {file_path}")
            try:
                with open(file_path, 'r', errors='ignore') as f:
                    log_data = f.read()
            except Exception as e:
                logger.error(f"_process_one: unreadable file {file_path}: {e}")
                return _placeholder_entry(file_path)

            try:
                if ios_xe_check(log_data):
                    logger.debug(f"_process_one: IOS-XE detected for {os.path.basename(file_path)}")
                    return process_file(file_path)
                else:
                    logger.debug(f"_process_one: Non-IOS-XE row for {os.path.basename(file_path)}")
                    return _placeholder_entry(file_path)
            except Exception as e:
                logger.exception(f"_process_one: exception while processing {file_path}")
                return _placeholder_entry(file_path)

        from concurrent.futures import ThreadPoolExecutor, as_completed
        max_workers = min(16, (os.cpu_count() or 4) * 2)
        futures = []
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            for fp in candidates:
                futures.append(ex.submit(_process_one, fp))
            for fut in as_completed(futures):
                try:
                    result = fut.result()
                    if isinstance(result, dict) and result:
                        data.append(result)
                except Exception as e:
                    logger.exception(f"process_directory: worker raised: {e}")

        logger.info("process_directory: completed")
        return data

    except Exception as e:
        logger.exception("process_directory: exception")
        return 500


# ==========================
# Local test (optional)
# ==========================

def main():
    logger.info("Cisco_IOS_XE.main: start")
    try:
        directory_path = r"C:\Users\girish.n\OneDrive - NTT\Desktop\Desktop\Live Updates\Uptime\Tickets-Mostly PM\R&S\SVR137436091\9200\UOBM-9200L-JOT-L03-05_10.31.99.14.txt"
        data = process_directory(directory_path)
        for item in data:
            print_data(item)
    except Exception as e:
        logger.exception("Cisco_IOS_XE.main: exception")

if __name__ == "__main__":
    main()