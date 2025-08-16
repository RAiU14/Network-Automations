import os
import pandas as pd
import logging
# from . 
import Cisco_IOS_XE
import re
from datetime import datetime, timedelta
from dateutil import parser
import openpyxl
from openpyxl.styles import PatternFill, Alignment, Font

def _unwrap_value(val):
    while isinstance(val, list) and len(val) == 1:
        val = val[0]
    return val

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
        # timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # file_path = f"{ticket_number}_network_analysis_{timestamp}.xlsx"
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
                    # Unwrap the value here
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

    try:
        if os.path.exists(file_path):
            logging.info(f"Appending to existing Excel file: {file_path}")
            existing_df = pd.read_excel(file_path)
            combined_df = pd.concat([existing_df, df], ignore_index=True)
            combined_df.to_excel(file_path, index=False)
        else:
            logging.info(f"Creating new Excel file: {file_path}")
            df.to_excel(file_path, index=False)
        logging.debug(f"Successfully wrote {len(df)} rows to Excel file and saved in {file_path}")
        return file_path
    except Exception as e:
        logging.error(f"Error writing to Excel for case {ticket_number}: {str(e)}")
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
                            if model not in model_serials:
                                model_serials[model] = serial
                elif model_value and model_value != 'Not available' and serial_value and serial_value != 'Not available':
                    if model_value not in model_serials:
                        model_serials[model_value] = serial_value
        
        return [[model, serial] for model, serial in model_serials.items()]
    except Exception as e:
        print(f"Error extracting model numbers and serials: {str(e)}")
        return []

def process_and_style_excel(file_path):
    try:
        df = pd.read_excel(file_path, engine='openpyxl', keep_default_na=False, na_values=[])
        logging.info("Excel file loaded successfully.")
    except Exception as e:
        logging.error(f"Failed to load Excel file: {e}")
        raise

     # --- NEW: safe accessor so index-based lookups don't crash if layout changes ---
    def _safe_iloc(row, idx, default=""):
        try:
            # pandas Series has .iloc and a length; if idx is valid, return the value
            return row.iloc[idx] if 0 <= idx < len(row) else default
        except Exception:
            return default

    # --- NEW: Coerce percentage-like strings to numeric fractions ---
    # Keep column names aligned with your existing styling/threshold logic
    percentage_columns = ["CPU Utilization", "Memory Utilization (%)", "Used Flash (%)"]

    def _to_fraction(val):
        try:
            # Already numeric? If it's <= 1, assume it's already a fraction; if > 1 and not a % string, leave as-is
            if isinstance(val, (int, float)):
                return float(val) if val <= 1 else val
            if isinstance(val, str):
                s = val.strip()
                # Match e.g. "83%", "83.00%", "  83.5 % "
                m = re.match(r'^(\d+(?:\.\d+)?)\s*%$', s)
                if m:
                    return float(m.group(1)) / 100.0
        except Exception as e:
            logging.debug(f"Percentage coercion skipped for value '{val}': {e}")
        return val

    for col in percentage_columns:
        if col in df.columns:
            df[col] = df[col].apply(_to_fraction)
    # --- END NEW BLOCK ---

    # Recommendation functions
    def uptime(row):
        try:
            text = str(_safe_iloc(row, 5, ""))
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
        except Exception as e:
            logging.warning(f"Error in uptime: {e}")
        return None

    def simple_check(row, index, trigger, message):
        try:
            value = str(_safe_iloc(row, index, "")).strip()
            if value == trigger:
                return message
        except Exception as e:
            logging.warning(f"Error in check at index {index}: {e}")
        return None

    def threshold_check(row, index, threshold, message):
        try:
            val = _safe_iloc(row, index, None)
            if isinstance(val, (int, float)) and val >= threshold:
                return message
        except Exception as e:
            logging.warning(f"Error in threshold check at index {index}: {e}")
        return None

    def psu_check(row):
        try:
            value = str(_safe_iloc(row, 25, "")).strip()
            if value != "OK":
                return "PSU functionalities are abnormal, try to reseat the PSU and verify the status."
        except Exception as e:
            logging.warning(f"Error in PSU check: {e}")
        return None

    def fan_check(row):
        try:
            value = str(_safe_iloc(row, 23, "")).strip()
            if value != "OK":
                return "Error noticed in fan functionality, kindly review."
        except Exception as e:
            logging.warning(f"Error in fan check: {e}")
        return None

    def temperature_check(row):
        try:
            value = str(_safe_iloc(row, 24, "")).strip()
            if value != "OK":
                return "Abnormalities noticed in device temperature, suggested to check the fan status and also room temperature if required."
        except Exception as e:
            logging.warning(f"Error in temperature check: {e}")
        return None

    def hardware_recommendations(row):
        try:
            today = datetime.today()
            one_year_later = today + timedelta(days=365)
            has_passed = is_approaching = False
            for i in range(27, 32):
                try:
                    date = parser.parse(str(_safe_iloc(row, i, "")), fuzzy=True)
                    if date < today:
                        has_passed = True
                    elif today <= date <= one_year_later:
                        is_approaching = True
                except (ValueError, TypeError):
                    continue
            if has_passed and is_approaching:
                return "One of the EOS milestones has already passed for the device model, please consider a hardware refresh."
            if has_passed:
                return "Device has already passed the last date of support from vendor, please consider hardware refresh."
            if is_approaching:
                return "Device is approaching the EOS soon, please consider a hardware refresh."
        except Exception as e:
            logging.warning(f"Error in hardware_recommendations: {e}")
        return None

    def duplex_check(row):
        return simple_check(row, 32, "YES", "Enable full duplex mode on all applicable interfaces to prevent performance issues.")

    def config_check(row):
        return simple_check(row, 34, "YES", "Unsaved configuration detected, recommended to save configurations to prevent loss during reboot.")

    def logs_check(row):
        return simple_check(row, 36, "YES", "Critical logs found in the device, please review.")

    def debug_check(row):
        return simple_check(row, 13, "YES", "The debug is enabled, please review the debug configurations and disable it as needed.")

    def memory_check(row):
        return threshold_check(row, 18, 0.8, "Memory utilization is found to be high, please review top processes consuming more memory.")

    def flash_check(row):
        return threshold_check(row, 22, 0.8, "Flash memory utilization is observed to be high, kindly review the top processes or files contributing to elevated flash usage.")

    def generate_comment(row):
        comments = []
        for func in [
            uptime, debug_check, memory_check, flash_check,
            psu_check, fan_check, temperature_check,
            hardware_recommendations, duplex_check,
            config_check, logs_check
        ]:
            try:
                result = func(row)
                if result:
                    comments.append(result)
            except Exception as e:
                logging.warning(f"Error executing function: {e}")
        if not comments:
            return "Device operating with good parameters."
        return "\n".join(comments)

    try:
        remark_col = "Remark"
        if remark_col not in df.columns:
            # Create the column if missing
            df[remark_col] = ""

        df[remark_col] = df.apply(generate_comment, axis=1)
        df.to_excel(file_path, index=False, engine='openpyxl')
        logging.info("Excel file updated with recommendations.")
    except Exception as e:
        logging.error(f"Failed to update Excel file: {e}")
        raise

    # Post-processing: styling, formatting, highlighting
    try:
        wb = openpyxl.load_workbook(file_path)
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
            header = [cell.value for cell in sheet[1]]
            percent_indexes = [header.index(col) for col in percentage_columns if col in header]
            date_indexes = [header.index(col) for col in date_columns if col in header]

            for cell in sheet[1]:
                cell.fill = purple_fill
                cell.alignment = center_wrap_align
                cell.font = bold_font

            for row in sheet.iter_rows(min_row=2):
                for cell in row:
                    val = cell.value
                    mark_red = False
                    if isinstance(val, str):
                        s = val.strip()
                        # Expanded variants & common typos, without changing upstream logic/strings
                        red_markers = {
                            "Unavailable",
                            "Invalid inner data format",
                            "Invalid data format",
                            "Check manually",
                            "Require Manual Check",
                            "Yet to check",
                            "Command not found",
                            "Command not found.",      # trailing period variant
                            "Not available",
                            "NA",
                            "Not avialable",          # common typo seen in remarks
                        }
                        if s in red_markers or s.startswith("Error:"):
                            mark_red = True
                    if mark_red:
                        cell.fill = red_fill
                    cell.alignment = center_wrap_align

                for idx in percent_indexes:
                    cell = row[idx]
                    if isinstance(cell.value, (int, float)):
                        cell.number_format = '0.00%'

                for idx in date_indexes:
                    cell = row[idx]
                    if isinstance(cell.value, datetime):
                        cell.number_format = 'mmmm dd, yyyy'

            for col in sheet.columns:
                max_length = max((len(str(cell.value)) for cell in col if cell.value), default=0)
                sheet.column_dimensions[col[0].column_letter].width = max_length + 2

        wb.save(file_path)
        logging.info("Post-processing completed: styling, formatting, highlighting.")
    except Exception as e:
        logging.error(f"Post-processing failed: {e}")
        raise

def main():

    try:
        file_path = r"C:\Users\girish.n\OneDrive - NTT\Desktop\Desktop\Live Updates\Uptime\Tickets-Mostly PM\R&S\SVR135977300\DRC01CORESW01_10.20.253.5.txt"
        directory_path = r"C:\Users\girish.n\OneDrive - NTT\Desktop\Desktop\Live Updates\Uptime\Tickets-Mostly PM\R&S\SVR136818637\CBJ_SVR136818637\New folder"
        # pp.pprint(Cisco_IOS_XE.process_file(file_path))
        data = Cisco_IOS_XE.process_directory(directory_path)
        print(append_to_excel("SVR3456789", data))
    except Exception as e:
        print(f"Error in main: {str(e)}")

if __name__ == "__main__":
    main()