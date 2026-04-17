import re
import os
import datetime
import logging

# ============================================================
# PHASE 0 — LOGGING & BASIC SETUP
# ============================================================

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)

log_dir = os.path.join(root_dir, "Logs")
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    filename=os.path.join(
        log_dir,
        f"Controller_Logs_{datetime.datetime.today().strftime('%Y-%m-%d')}.log"
    ),
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# ============================================================
# PHASE 0 — UTILITY HELPERS
# ============================================================

def _unwrap_one(value):
    while isinstance(value, (list, tuple)) and len(value) == 1:
        value = value[0]
    return value


def _normalize_list(values, expected_length):
    values = values if isinstance(values, list) else []
    normalized = [_unwrap_one(v) for v in values]

    if len(normalized) == 1 and expected_length > 1:
        normalized *= expected_length
    if len(normalized) < expected_length:
        normalized += [None] * (expected_length - len(normalized))

    return normalized[:expected_length]


# ============================================================
# PHASE 1 — FAULT DETECTION (ONLY SOURCE OF TRUTH)
# ============================================================

FAULT_REGEX = re.compile(r"\bNOT\s+OK\b", re.IGNORECASE)

def has_fault(value):
    """
    Returns TRUE only if the raw value explicitly contains 'NOT OK'
    EVERYTHING ELSE IS SAFE
    """
    value = _unwrap_one(value)
    if value is None:
        return False
    return bool(FAULT_REGEX.search(str(value)))


# ============================================================
# PHASE 2 — REMARK SANITIZER (FINAL KILL SWITCH)
# ============================================================

def sanitize_env_remarks(remark, raw_temp, raw_psu, raw_fan):
    """
    FINAL AUTHORITY:
    Removes temp / psu / fan remarks unless raw value contains 'NOT OK'
    """
    if not remark:
        return remark

    cleaned = []
    for line in remark.split("\n"):
        l = line.lower()

        if "temperature" in l:
            if has_fault(raw_temp):
                cleaned.append(line)

        elif "power supply" in l:
            if has_fault(raw_psu):
                cleaned.append(line)

        elif "fan" in l:
            if has_fault(raw_fan):
                cleaned.append(line)

        else:
            cleaned.append(line)

    return "\n".join(cleaned)


# ============================================================
# PHASE 3 — MAIN CONTROLLER
# ============================================================

def sub_controller(data, eox_eos_data=None):

    for device in data:

        models = device.get("Model number", [])
        n = len(models)
        device["Remark"] = [""] * n

        raw_temp = _normalize_list(device.get("Temperature status", []), n)
        raw_psu  = _normalize_list(device.get("PowerSupply status", []), n)
        raw_fan  = _normalize_list(device.get("Fan status", []), n)

        for i in range(n):
            remarks = []

            # ----------------------------------------------------
            # ENVIRONMENT CHECKS — ONLY FAULT-BASED
            # ----------------------------------------------------

            if has_fault(raw_temp[i]):
                remarks.append("High temperature detected")

            if has_fault(raw_psu[i]):
                remarks.append("Abnormalities detected in Power Supply functionality")

            if has_fault(raw_fan[i]):
                remarks.append("Abnormalities detected in FAN functionality")

            device["Remark"][i] = "\n".join(remarks)

            # ----------------------------------------------------
            # DEBUG — TRACE RAW VALUES
            # ----------------------------------------------------

            logger.debug(
                f"IDX={i} | "
                f"TEMP_RAW={raw_temp[i]!r} | "
                f"PSU_RAW={raw_psu[i]!r} | "
                f"FAN_RAW={raw_fan[i]!r} | "
                f"REMARK_BEFORE_SANITIZE={device['Remark'][i]!r}"
            )

        # --------------------------------------------------------
        # FINAL SANITATION PASS (ABSOLUTE)
        # --------------------------------------------------------

        for i in range(n):
            device["Remark"][i] = sanitize_env_remarks(
                device["Remark"][i],
                raw_temp[i],
                raw_psu[i],
                raw_fan[i]
            )

            logger.debug(
                f"IDX={i} | REMARK_AFTER_SANITIZE={device['Remark'][i]!r}"
            )

    return data
