import os
import shutil
import pandas as pd
import logging
# from . 
import Cisco_IOS_XE
from datetime import datetime
from test import *

# Setup logging
log_dir = os.path.join(os.path.dirname(__file__), "Data_to_Excel")
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(filename=os.path.join(log_dir, f"{datetime.datetime.today().strftime('%Y-%m-%d')}.log"), level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

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
                    if isinstance(value, list):
                        row_data[key] = value[i] if i < len(value) else 'Not available'
                    else:
                        row_data[key] = value
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

def main():
    try:
        file_path = r"C:\Users\girish.n\OneDrive - NTT\Desktop\Desktop\Live Updates\Uptime\Tickets-Mostly PM\R&S\SVR135977300\DRC01CORESW01_10.20.253.5.txt"
        directory_path = r"C:\Users\girish.n\OneDrive - NTT\Desktop\Desktop\Live Updates\Uptime\Tickets-Mostly PM\R&S\SVR137436091\9200\Temp"
        # pp.pprint(Cisco_IOS_XE.process_file(file_path))
        data = Cisco_IOS_XE.process_directory(directory_path)
        print(append_to_excel("SVR3456789", data))
    except Exception as e:
        print(f"Error in main: {str(e)}")

if __name__ == "__main__":
    main()