import os
import shutil
import pandas as pd
import logging
import Cisco_IOS_XE
from datetime import datetime

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
            'End-of-Sale Date: HW', 'Last Date of Support: HW', 'End of Routine Failure Analysis Date: HW',
            'End of Vulnerability/Security Support: HW', 'End of SW Maintenance Releases Date: HW',
            'Any Half Duplex', 'Interface/Module Remark', 'Config Status', 'Config Save Date',
            'Critical logs', 'Remark'
        ]
    if file_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = f"{ticket_number}_network_analysis_{timestamp}.xlsx"

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
                        row_data[key] = value[i] if i < len(value) else 'NA'
                    else:
                        row_data[key] = value
                else:
                    row_data[key] = 'NA'
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

# This is to make a copy of excel. 
def process_eox_analysis(original_excel_path):
    logging.info(f"Creating copy of {original_excel_path}")
    try:
        directory = os.path.dirname(original_excel_path)
        filename = os.path.basename(original_excel_path)
        copy_filename = f"copy_{filename}"
        copy_excel_path = os.path.join(directory, copy_filename)
        shutil.copy2(original_excel_path, copy_excel_path)
        logging.debug(f"Created copy: {copy_excel_path}")
        return {
            'status': 'success',
            'copy_excel_path': copy_excel_path
        }
    except Exception as e:
        logging.error(f"Copy creation failed: {e}")
        return {
            'status': 'failed',
            'copy_excel_path': None
        }

def unique_model_numbers(data_list):
    """
    Extract unique model numbers from processed data
    
    Args:
        data_list: List of dictionaries or single dictionary containing switch data
    
    Returns:
        List of unique model numbers
    """
    try:
        model_numbers = set()
        
        # ✅ FIXED: Handle both single dict and list of dicts
        if isinstance(data_list, dict):
            data_list = [data_list]
        
        for data in data_list:
            if isinstance(data, dict) and "Model number" in data:
                model_value = data["Model number"]
                
                if isinstance(model_value, list):
                    # Handle list of model numbers (multiple switches)
                    model_numbers.update([model for model in model_value if model and model != 'NA'])
                elif model_value and model_value != 'NA':
                    # Handle single model number
                    model_numbers.add(model_value)
        
        return list(model_numbers)
    except Exception as e:
        print(f"❌ Error extracting model numbers: {str(e)}")
        return []

def get_unique_serial_numbers(data_list):
    """
    Extract unique serial numbers from processed data
    """
    try:
        serial_numbers = set()
        
        if isinstance(data_list, dict):
            data_list = [data_list]
        
        for data in data_list:
            if isinstance(data, dict) and "Serial number" in data:
                serial_value = data["Serial number"]
                
                if isinstance(serial_value, list):
                    serial_numbers.update([serial for serial in serial_value if serial and serial != 'NA'])
                elif serial_value and serial_value != 'NA':
                    serial_numbers.add(serial_value)
        
        return list(serial_numbers)
    except Exception as e:
        print(f"❌ Error extracting serial numbers: {str(e)}")
        return []

def process_and_export(ticket_number, directory_path, output_file_path=None):
    try:
        print(f"🔄 Processing directory: {directory_path}")
        
        # Process the directory
        data_list = Cisco_IOS_XE.process_directory(directory_path)
        
        if not data_list:
            return {"success": False, "error": "No data processed from directory"}
        
        print(f"✅ Processed {len(data_list)} data sets")
        
        # Extract unique information
        model_numbers = unique_model_numbers(data_list)
        serial_numbers = get_unique_serial_numbers(data_list)
        
        # Export to Excel
        excel_file = append_to_excel(ticket_number, data_list, output_file_path)
        
        return {
            "success": True,
            "excel_file": excel_file,
            "data_count": len(data_list),
            "unique_models": model_numbers,
            "unique_serials": serial_numbers,
            "summary": f"Processed {len(data_list)} switches with {len(model_numbers)} unique models"
        }
        
    except Exception as e:
        print(f"❌ Error in processing pipeline: {str(e)}")
        return {"success": False, "error": str(e)}

def main():
    """Test function"""
    try:
        # Test with single file
        SVR = "SVR3333333333"
        file_path = r"C:\Users\girish.n\OneDrive - NTT\Desktop\Desktop\Live Updates\Uptime\Tickets-Mostly PM\R&S\SVR137436091\9200\Temp\UOBM-9200L-JOT-L03-05_10.31.99.14.txt"
        
        if os.path.exists(file_path):
            print("🔄 Testing single file processing...")
            data_dict = Cisco_IOS_XE.process_file(file_path)
            print(f"📊 Data type: {type(data_dict)}")
            
            if data_dict:
                model_numbers = unique_model_numbers(data_dict)
                print(f"🔧 Unique model numbers: {model_numbers}")
                
                # Test Excel export
                excel_result = append_to_excel(SVR, data_dict, f"{SVR}_test.xlsx")
                if excel_result:
                    print(f"✅ Excel file created: {excel_result}")
            else:
                print("❌ No data returned from file processing")
        else:
            print(f"❌ File not found: {file_path}")
            
    except Exception as e:
        print(f"❌ Error in main: {str(e)}")

if __name__ == "__main__":
    main()
