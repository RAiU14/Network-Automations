import os
import pandas as pd
import logging
import re
from datetime import datetime, timedelta
from dateutil import parser
import openpyxl
from openpyxl.styles import PatternFill, Alignment, Font
import json  # for export_json
from tempfile import NamedTemporaryFile
from openpyxl.utils import get_column_letter

# --- make import work both as package and as standalone ---
try:
    # when imported as part of a package (e.g., PM_Report.Data_to_Excel)
    from . import Cisco_IOS_XE  # type: ignore
except Exception:
    # when imported as a top-level module (e.g., from Data_to_Excel import ...)
    import Cisco_IOS_XE  # type: ignore
# ---------------------------------------------------------


# ----- version banner so you can confirm the right module is loaded -----
PHASE2_VERSION = "Phase2-final-2025-08-17.hotfix1"
try:
    logging.info(f"[Data_to_Excel] Loaded module version: {PHASE2_VERSION}")
except Exception:
    pass
# -----------------------------------------------------------------------

MAIN_SHEET = "Preventive Maintanance"  # exact spelling as requested
SUMMARY_SHEET = "Summary"

def _unwrap_value(val):
    while isinstance(val, list) and len(val) == 1:
        val = val[0]
    return val

def _safe_save_wb(wb, path):
    """
    Atomic save to avoid partial/corrupt archives.
    """
    parent = os.path.dirname(path)
    os.makedirs(parent, exist_ok=True) if parent else None
    with NamedTemporaryFile(delete=False, dir=parent or None, suffix=".xlsx") as tmp:
        tmp_path = tmp.name
    try:
        wb.save(tmp_path)
        os.replace(tmp_path, path)
    except Exception:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        finally:
            raise

# This function is used to write/append values to excel.
def append_to_excel(ticket_number, data_list, file_path=None, column_order=None):
    logging.debug(f"Appending to Excel for ticket{ticket_number}")
    if column_order is None:
        column_order = [
            'File name', 'Host name', 'Model number', 'Serial number', 'Interface ip address',
            'Uptime', 'Current s/w version', 'Current SW EOS', 'Suggested s/w ver', 's/w release date',
            'Latest S/W version', 'Production s/w is deffered or not?', 'Last Reboot Reason', 'Any Debug?',
            'CPU Utilization', 'Total memory', 'Used memory', 'Free memory', 'Memory Utilization (%)',
            'Total flash memory', 'Used flash memory', 'Free flash memory', 'Used Flash (%)',
            'Fan status', 'Temperature status', 'PowerSupply status', 'Available Free Ports',
            'End-of-Sale Date: HW', 'Last Date of Support: HW', 'End of Routine Failure Analysis Date:  HW',
            'End of Vulnerability/Security Support: HW', 'End of SW Maintenance Releases Date: HW',
            'Any Half Duplex', 'Interface/Module Remark', 'Config Status', 'Config Save Date',
            'Critical logs', 'Remark'
        ]
    if file_path is None:
        file_path = f"{ticket_number}_network_analysis.xlsx"

    formatted_data = []

    if isinstance(data_list, dict):
        data_list = [data_list]

    for data in data_list:
        if not isinstance(data, dict):
            logging.error(f"Skipping invalid data: {type(data)} for {ticket_number}.")
            continue
        if not data:
            continue
        data_length = 1
        for value in data.values():
            if isinstance(value, list) and len(value) > 0:
                data_length = len(value)
                break
        for i in range(data_length):
            row_data = {}
            for key in column_order:
                if key in data:
                    value = data[key]
                    if isinstance(value, list):
                        unwrapped_value = _unwrap_value(value[i] if i < len(value) else 'Not available')
                        row_data[key] = unwrapped_value
                    else:
                        unwrapped_value = _unwrap_value(value)
                        row_data[key] = unwrapped_value
                else:
                    row_data[key] = 'Not available'
            formatted_data.append(row_data)

    if not formatted_data:
        logging.warning("No data to write to Excel.")
        return None

    df = pd.DataFrame(formatted_data)
    df = df[column_order]

    # Ensure parent folder exists
    try:
        parent = os.path.dirname(file_path)
        if parent and not os.path.exists(parent):
            os.makedirs(parent, exist_ok=True)
    except Exception as e:
        logging.warning(f"Could not ensure parent folder for Excel: {e}")

    # Write/append Excel (always ensure main sheet name is correct)
    try:
        if os.path.exists(file_path):
            logging.info(f"Appending to existing Excel file: {file_path}")
            # Read current main sheet only, append, then rewrite main sheet (Summary is recreated later)
            try:
                existing_df = pd.read_excel(file_path, sheet_name=MAIN_SHEET)
            except Exception:
                # Fallback to first sheet if main missing/corrupt
                existing_df = pd.read_excel(file_path)
            combined_df = pd.concat([existing_df, df], ignore_index=True)
            with pd.ExcelWriter(file_path, engine="openpyxl", mode="w") as writer:
                combined_df.to_excel(writer, index=False, sheet_name=MAIN_SHEET)
        else:
            logging.info(f"Creating new Excel file: {file_path}")
            with pd.ExcelWriter(file_path, engine="openpyxl", mode="w") as writer:
                df.to_excel(writer, index=False, sheet_name=MAIN_SHEET)

        logging.debug(f"Successfully wrote {len(df)} rows to Excel file and saved in {file_path}")
    except Exception as e:
        logging.error(f"Error writing to Excel for case {ticket_number}: {str(e)}")
        return None

    # Style + remarks + summary
    try:
        process_and_style_excel(file_path)
    except Exception as e:
        logging.warning(f"Excel styling step failed inside append_to_excel: {e}")

    try:
        add_summary_sheet(file_path)  # Ensures 1) Preventive Maintanance, 2) Summary
    except Exception as e:
        logging.warning(f"Summary sheet step failed inside append_to_excel: {e}")

    return file_path

def export_json(ticket_number, data_list, file_path=None, column_order=None, coerce_percentages=True):
    logging.debug(f"Exporting JSON for ticket {ticket_number}")
    if column_order is None:
        column_order = [
            'File name', 'Host name', 'Model number', 'Serial number', 'Interface ip address',
            'Uptime', 'Current s/w version', 'Current SW EOS', 'Suggested s/w ver', 's/w release date',
            'Latest S/W version', 'Production s/w is deffered or not?', 'Last Reboot Reason', 'Any Debug?',
            'CPU Utilization', 'Total memory', 'Used memory', 'Free memory', 'Memory Utilization (%)',
            'Total flash memory', 'Used flash memory', 'Free flash memory', 'Used Flash (%)',
            'Fan status', 'Temperature status', 'PowerSupply status', 'Available Free Ports',
            'End-of-Sale Date: HW', 'Last Date of Support: HW', 'End of Routine Failure Analysis Date:  HW',
            'End of Vulnerability/Security Support: HW', 'End of SW Maintenance Releases Date: HW',
            'Any Half Duplex', 'Interface/Module Remark', 'Config Status', 'Config Save Date',
            'Critical logs', 'Remark'
        ]

    if file_path is None:
        file_path = f"{ticket_number}_network_analysis.json"

    formatted_rows = []
    if isinstance(data_list, dict):
        data_list = [data_list]

    for data in data_list:
        if not isinstance(data, dict) or not data:
            logging.warning(f"Skipping invalid/empty data item for JSON export: {type(data)}")
            continue

        data_length = 1
        for v in data.values():
            if isinstance(v, list) and len(v) > 0:
                data_length = len(v)
                break

        for i in range(data_length):
            row_obj = {}
            for key in column_order:
                if key in data:
                    value = data[key]
                    if isinstance(value, list):
                        val = _unwrap_value(value[i] if i < len(value) else 'Not available')
                    else:
                        val = _unwrap_value(value)
                else:
                    val = 'Not available'
                row_obj[key] = val
            formatted_rows.append(row_obj)

    if coerce_percentages:
        percent_cols = ["CPU Utilization", "Memory Utilization (%)", "Used Flash (%)"]
        def _to_fraction(val):
            try:
                if isinstance(val, (int, float)):
                    return float(val) if val <= 1 else val
                if isinstance(val, str):
                    s = val.strip()
                    m = re.match(r'^(\d+(?:\.\d+)?)\s*%$', s)
                    if m:
                        return float(m.group(1)) / 100.0
            except Exception:
                pass
            return val

        for row in formatted_rows:
            for c in percent_cols:
                if c in row:
                    row[c] = _to_fraction(row[c])

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(formatted_rows, f, ensure_ascii=False, indent=2)
        logging.info(f"JSON exported: {file_path} ({len(formatted_rows)} rows)")
        return file_path
    except Exception as e:
        logging.error(f"Error exporting JSON for case {ticket_number}: {str(e)}")
        return None

def unique_model_numbers_and_serials(data_list):
    try:
        model_serials = {}
        if isinstance(data_list, dict):
            data_list = [data_list]
        for data in data_list:
            if isinstance(data, dict) and "Model number" in data and "Serial number" in data:
                model_value = data["Model number"]
                serial_value = data["Serial number"]
                if isinstance(model_value, list) and isinstance(serial_value, list):
                    for model, serial in zip(model_value, serial_value):
                        if model and model != 'Not available' and serial and serial != 'Not available':
                            model_serials.setdefault(model, serial)
                elif model_value and model_value != 'Not available' and serial_value and serial_value != 'Not available':
                    model_serials.setdefault(model_value, serial_value)
        return [[model, serial] for model, serial in model_serials.items()]
    except Exception as e:
        print(f"Error extracting model numbers and serials: {str(e)}")
        return []

def process_and_style_excel(file_path):
    """
    - Ensure main sheet exists/named correctly.
    - Update 'Remark' IN-PLACE (no sheet delete).
    - Style headers/cells and format percentage/date columns.
    - Save atomically.
    """
    # Load workbook
    wb = openpyxl.load_workbook(file_path)
    # Ensure main sheet name
    if MAIN_SHEET in wb.sheetnames:
        ws = wb[MAIN_SHEET]
    else:
        # rename first sheet if needed
        first = wb[wb.sheetnames[0]]
        first.title = MAIN_SHEET
        ws = first

    # Map headers
    headers = [c.value for c in ws[1]]
    name_to_idx = {name: idx for idx, name in enumerate(headers)}  # 0-based

    # Helpers
    def _safe_cell(r, c):
        try:
            return ws.cell(row=r, column=c+1).value
        except Exception:
            return ""

    def _as_percent_fraction(val):
        try:
            if isinstance(val, (int, float)):
                return float(val) if val <= 1 else None
            if isinstance(val, str):
                s = val.strip()
                m = re.match(r'^(\d+(?:\.\d+)?)\s*%$', s)
                if m:
                    return float(m.group(1)) / 100.0
        except Exception:
            return None
        return None

    # Column index lookups by name (fallback -1 if missing)
    def col(name):
        return name_to_idx.get(name, -1)

    idx_uptime = col("Uptime")

    # Checks ported from prior logic but now work on row values
    def build_row_accessor(r):
        """Return a function like iloc(idx) using current headers order."""
        def _iloc(i):
            if i < 0 or i >= len(headers):
                return ""
            return _safe_cell(r, i)
        return _iloc

    def uptime_comment(_iloc):
        try:
            text = str(_iloc(idx_uptime))
            matches = re.findall(r'(\d+)\s+(year|week|day|hour|minute|second)s?', text)
            time_dict = {unit: int(value) for value, unit in matches}
            if time_dict.get('year', 0) > 1 or (
                time_dict.get('year', 0) == 1 and any(unit in time_dict for unit in ['week', 'day', 'hour', 'minute', 'second'])
            ):
                return "Consider to power cycle the device at the nearest maintenance window."
            total_days = (
                time_dict.get('week', 0) * 7 +
                time_dict.get('day', 0) +
                time_dict.get('hour', 0) / 24 +
                time_dict.get('minute', 0) / 1440 +
                time_dict.get('second', 0) / 86400
            )
            if total_days > 366:
                return "Consider to power cycle the device at the nearest maintenance window"
        except Exception:
            pass
        return None

    def simple_check(_iloc, index_name, trigger, message):
        i = col(index_name)
        if i < 0:
            return None
        try:
            value = str(_iloc(i)).strip()
            if value == trigger:
                return message
        except Exception:
            pass
        return None

    def threshold_check(_iloc, index_name, threshold, message):
        i = col(index_name)
        if i < 0:
            return None
        try:
            v = _iloc(i)
            if isinstance(v, (int, float)):
                frac = v if v <= 1 else None
            else:
                frac = _as_percent_fraction(v)
            if frac is not None and frac >= threshold:
                return message
        except Exception:
            pass
        return None

    def psu_check(_iloc):
        return simple_check(_iloc, "PowerSupply status", "OK", None) or \
               ("PSU functionalities are abnormal, try to reseat the PSU and verify the status."
                if str(_iloc(col("PowerSupply status"))).strip() not in ("OK",) else None)

    def fan_check(_iloc):
        return simple_check(_iloc, "Fan status", "OK", None) or \
               ("Error noticed in fan functionality, kindly review."
                if str(_iloc(col("Fan status"))).strip() not in ("OK",) else None)

    def temperature_check(_iloc):
        return simple_check(_iloc, "Temperature status", "OK", None) or \
               ("Abnormalities noticed in device temperature, suggested to check the fan status and also room temperature if required."
                if str(_iloc(col("Temperature status"))).strip() not in ("OK",) else None)

    def hardware_recommendations(_iloc):
        try:
            today = datetime.today()
            one_year_later = today + timedelta(days=365)
            has_passed = is_approaching = False
            for name in ["End-of-Sale Date: HW", "Last Date of Support: HW",
                         "End of Routine Failure Analysis Date:  HW",
                         "End of Vulnerability/Security Support: HW",
                         "End of SW Maintenance Releases Date: HW"]:
                i = col(name)
                if i < 0:
                    continue
                val = _iloc(i)
                try:
                    date = parser.parse(str(val), fuzzy=True)
                    if date < today:
                        has_passed = True
                    elif today <= date <= one_year_later:
                        is_approaching = True
                except Exception:
                    continue
            if has_passed and is_approaching:
                return "One of the EOS milestones has already passed for the device model, please consider a hardware refresh."
            if has_passed:
                return "Device has already passed the last date of support from vendor, please consider hardware refresh."
            if is_approaching:
                return "Device is approaching the EOS soon, please consider a hardware refresh."
        except Exception:
            pass
        return None

    def duplex_check(_iloc):
        return simple_check(_iloc, "Any Half Duplex", "YES",
                            "Enable full duplex mode on all applicable interfaces to prevent performance issues.")

    def config_check(_iloc):
        return simple_check(_iloc, "Config Status", "YES",
                            "Unsaved configuration detected, recommended to save configurations to prevent loss during reboot.")

    def logs_check(_iloc):
        return simple_check(_iloc, "Critical logs", "YES",
                            "Critical logs found in the device, please review.")

    def debug_check(_iloc):
        return simple_check(_iloc, "Any Debug?", "YES",
                            "The debug is enabled, please review the debug configurations and disable it as needed.")

    def memory_check(_iloc):
        return threshold_check(_iloc, "Memory Utilization (%)", 0.8,
                               "Memory utilization is found to be high, please review top processes consuming more memory.")

    def flash_check(_iloc):
        return threshold_check(_iloc, "Used Flash (%)", 0.8,
                               "Flash memory utilization is observed to be high, kindly review the top processes or files contributing to elevated flash usage.")

    # Fill Remark only when blank/placeholder
    remark_ci = col("Remark")
    if remark_ci < 0:
        # create a new Remark column at the end if somehow missing
        remark_ci = len(headers)
        ws.cell(row=1, column=remark_ci+1, value="Remark")
        headers.append("Remark")

    placeholders = {"", "Yet to check", "Not available", "NA", "Unsupported IOS"}

    for r in range(2, ws.max_row + 1):
        _iloc = build_row_accessor(r)
        cur_val = ws.cell(row=r, column=remark_ci+1).value
        s = (str(cur_val).strip() if cur_val is not None else "")
        if s == "" or s.casefold() in {p.casefold() for p in placeholders} or s.startswith("Error:"):
            comments = []
            for fn in (uptime_comment, debug_check, memory_check, flash_check,
                       psu_check, fan_check, temperature_check,
                       hardware_recommendations, duplex_check,
                       config_check, logs_check):
                try:
                    msg = fn(_iloc)
                    if msg:
                        comments.append(msg)
                except Exception:
                    continue
            ws.cell(row=r, column=remark_ci+1, value=("\n".join(comments) if comments else "Device operating with good parameters."))

    # Styling & formatting on all sheets
    red_fill = PatternFill(start_color="bc4f5e", end_color="bc4f5e", fill_type="solid")
    purple_fill = PatternFill(start_color="CBC3E3", end_color="CBC3E3", fill_type="solid")
    center_wrap_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    bold_font = Font(bold=True)
    percentage_columns = ["CPU Utilization", "Memory Utilization (%)", "Used Flash (%)"]
    date_columns = [
        "s/w release date", "End-of-Sale Date: HW", "Last Date of Support: HW",
        "End of Routine Failure Analysis Date:  HW", "End of Vulnerability/Security Support: HW",
        "End of SW Maintenance Releases Date: HW"
    ]

    for sheet in wb.worksheets:
        header_cells = [cell.value for cell in sheet[1]]
        pct_idx = [header_cells.index(c) for c in percentage_columns if c in header_cells]
        date_idx = [header_cells.index(c) for c in date_columns if c in header_cells]

        # Header style
        for cell in sheet[1]:
            cell.fill = purple_fill
            cell.alignment = center_wrap_align
            cell.font = bold_font

        # Cells styling
        for row in sheet.iter_rows(min_row=2):
            for cell in row:
                val = cell.value
                mark_red = False
                if isinstance(val, str):
                    s = val.strip()
                    red_markers = {
                        "Unavailable",
                        "Invalid inner data format",
                        "Invalid data format",
                        "Check manually",
                        "Require Manual Check",
                        "Yet to check",
                        "Command not found",
                        "Command not found.",
                        "NA",
                        "Non-IOS_XE",
                        "Unsupported IOS",
                        "Unsupported version",
                    }
                    if s in red_markers or s.startswith("Error:"):
                        mark_red = True
                if mark_red:
                    cell.fill = red_fill
                cell.alignment = center_wrap_align

            # percentage formats
            for idx in pct_idx:
                c = row[idx]
                if isinstance(c.value, (int, float)):
                    c.number_format = '0.00%'

            # date formats
            for idx in date_idx:
                c = row[idx]
                if isinstance(c.value, datetime):
                    c.number_format = 'mmmm dd, yyyy'

        # Auto width
        for col_cells in sheet.columns:
            max_length = max((len(str(c.value)) for c in col_cells if c.value is not None), default=0)
            sheet.column_dimensions[col_cells[0].column_letter].width = max_length + 2

    # Atomic save
    _safe_save_wb(wb, file_path)
    logging.info("Post-processing completed: remarks updated, styling applied, saved atomically.")

def add_summary_sheet(file_path):
    """
    Ensure MAIN_SHEET is first and create/refresh a 'Summary' sheet at index 1.
    """
    wb = openpyxl.load_workbook(file_path)

    # Ensure main sheet is first and named as required
    if MAIN_SHEET in wb.sheetnames:
        main = wb[MAIN_SHEET]
        wb._sheets.remove(main)
        wb._sheets.insert(0, main)
    else:
        first_sheet = wb[wb.sheetnames[0]]
        first_sheet.title = MAIN_SHEET
        main = first_sheet

    # Recreate Summary
    if SUMMARY_SHEET in wb.sheetnames:
        del wb[SUMMARY_SHEET]
    ws = wb.create_sheet(SUMMARY_SHEET, 1)

    headers = [c.value for c in main[1]]
    rows = [[cell for cell in r] for r in main.iter_rows(min_row=2, values_only=True)]

    def col(name):
        try:
            return headers.index(name)
        except ValueError:
            return -1

    idx_cpu   = col("CPU Utilization")
    idx_mem   = col("Memory Utilization (%)")
    idx_flash = col("Used Flash (%)")
    idx_fan   = col("Fan status")
    idx_temp  = col("Temperature status")
    idx_psu   = col("PowerSupply status")
    idx_fname = col("File name")
    idx_crit  = col("Critical logs")
    idx_rem   = col("Remark")

    def _as_frac(v):
        if isinstance(v, (int, float)):
            return float(v) if v <= 1 else None
        if isinstance(v, str):
            s = v.strip()
            m = re.match(r'^(\d+(?:\.\d+)?)\s*%$', s)
            if m:
                return float(m.group(1)) / 100.0
        return None

    def avg(col_idx):
        vals = []
        if col_idx >= 0:
            for r in rows:
                frac = _as_frac(r[col_idx])
                if frac is not None:
                    vals.append(frac)
        return round(sum(vals) / len(vals), 4) if vals else None

    def count_status(col_idx):
        counts = {"OK": 0, "Not OK": 0, "Unsupported version": 0, "Not available": 0, "Other": 0}
        if col_idx >= 0:
            for r in rows:
                v = r[col_idx]
                norm = "OK" if isinstance(v, list) and all(str(x).strip().upper() == "OK" for x in v) else str(v).strip()
                u = norm.upper()
                if u == "OK":
                    counts["OK"] += 1
                elif u in ("NOT OK", "NOT_OK", "NOTOK"):
                    counts["Not OK"] += 1
                elif u in ("UNSUPPORTED VERSION", "UNSUPPORTED IOS"):
                    counts["Unsupported version"] += 1
                elif u in ("NOT AVAILABLE", "NA"):
                    counts["Not available"] += 1
                else:
                    counts["Other"] += 1
        return counts

    total_rows = len(rows)
    stacks = sum(1 for r in rows if idx_fname >= 0 and "_Stack_" in str(r[idx_fname]))
    singles = total_rows - stacks

    fan_c  = count_status(idx_fan)
    temp_c = count_status(idx_temp)
    psu_c  = count_status(idx_psu)
    crit_yes = sum(1 for r in rows if idx_crit >= 0 and str(r[idx_crit]).strip().upper() == "YES")

    def _norm(s):
        if s is None:
            return ""
        return (
            str(s).upper()
            .replace(" ", "")
            .replace("-", "")
            .replace("_", "")
            .replace(":", "")
            .replace("(", "")
            .replace(")", "")
            .strip()
        )

    non_iosxe = 0
    if idx_rem >= 0:
        for r in rows:
            norm = _norm(r[idx_rem] if idx_rem < len(r) else "")
            if "NONIOSXE" in norm:
                non_iosxe += 1
            elif norm.startswith("INFONONIOSXESKIPPED") or norm.startswith("INFONONIOSXE"):
                non_iosxe += 1
            elif norm.startswith("ERRORCOULDNOTREADFILE") or norm.startswith("ERRORPROCESSINGFAILURE"):
                non_iosxe += 1

    summary = [
        ["Metric", "Value"],
        ["Total rows exported", total_rows],
        ["Single members", singles],
        ["Stack members", stacks],
        ["Avg CPU Utilization", avg(idx_cpu)],
        ["Avg Memory Utilization (%)", avg(idx_mem)],
        ["Avg Used Flash (%)", avg(idx_flash)],
        ["Critical logs (YES)", crit_yes],
        [],
        ["Fan — OK", fan_c["OK"]],
        ["Fan — Not OK", fan_c["Not OK"]],
        ["Fan — Unsupported version", fan_c["Unsupported version"]],
        ["Fan — Not available", fan_c["Not available"]],
        ["Fan — Other", fan_c["Other"]],
        [],
        ["Temperature — OK", temp_c["OK"]],
        ["Temperature — Not OK", temp_c["Not OK"]],
        ["Temperature — Unsupported version", temp_c["Unsupported version"]],
        ["Temperature — Not available", temp_c["Not available"]],
        ["Temperature — Other", temp_c["Other"]],
        [],
        ["PSU — OK", psu_c["OK"]],
        ["PSU — Not OK", psu_c["Not OK"]],
        ["PSU — Unsupported version", psu_c["Unsupported version"]],
        ["PSU — Not available", psu_c["Not available"]],
        ["PSU — Other", psu_c["Other"]],
        [],
        ["Non-IOS-XE files (skipped)", non_iosxe],
    ]

    for r_idx, row in enumerate(summary, start=1):
        for c_idx, val in enumerate(row, start=1):
            ws.cell(row=r_idx, column=c_idx, value=val)

    # Auto width for first two columns
    for col_idx in range(1, 3):
        from openpyxl.utils import get_column_letter
        max_len = 0
        for r in range(1, len(summary) + 1):
            val = ws.cell(row=r, column=col_idx).value
            max_len = max(max_len, len(str(val)) if val is not None else 0)
        ws.column_dimensions[get_column_letter(col_idx)].width = max_len + 2

    _safe_save_wb(wb, file_path)
    logging.info("Main/summary sheet order and naming enforced (with Non-IOS_XE counter).")

def main():
    try:
        file_path = r""
        directory_path = r""
        ticket_number = "SVR3456789"

        # 1) Parse all eligible files in the directory
        data = Cisco_IOS_XE.process_directory(directory_path)

        # 2) Create/append Excel (also styles & adds Summary)
        excel_path = append_to_excel(ticket_number, data)  # returns the file path
        print(excel_path)  # keep your original print

        # 3) Optional JSON export
        # json_path = export_json(ticket_number, data, file_path=None)
        # if json_path:
        #     print(json_path)

    except Exception as e:
        print(f"Error in main: {str(e)}")

if __name__ == "__main__":
    main()