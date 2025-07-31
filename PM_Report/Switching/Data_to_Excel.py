import os
import shutil
import pandas as pd
import Cisco_IOS_XE
from datetime import datetime

def append_to_excel(ticket_number, data_list, file_path=None, column_order=None):
    """
    Append processed network data to Excel file
    
    Args:
        ticket_number: Ticket number (e.g., SVR123456789)
        data_list: List of dictionaries containing switch data
        file_path: Path to Excel file (optional, will generate if not provided)
        column_order: List of column names in desired order
    """
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

    # Generate file path if not provided
    if file_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = f"{ticket_number}_network_analysis_{timestamp}.xlsx"

    # Create a list to store the formatted data
    formatted_data = []

    # ✅ FIXED: Handle both single dict and list of dicts
    if isinstance(data_list, dict):
        data_list = [data_list]  # Convert single dict to list
    
    # Iterate over the data list
    for data in data_list:
        if not isinstance(data, dict):
            print(f"⚠️ Skipping invalid data: {type(data)}")
            continue
            
        # Determine the length of the data (number of switches/rows)
        if not data:
            continue
            
        # Get the length from the first non-empty value
        data_length = 1
        for value in data.values():
            if isinstance(value, list) and len(value) > 0:
                data_length = len(value)
                break

        # Create rows for each switch
        for i in range(data_length):
            row_data = {}
            for key in column_order:
                if key in data:
                    value = data[key]
                    if isinstance(value, list):
                        # Handle list values (e.g., multiple switches)
                        row_data[key] = value[i] if i < len(value) else 'NA'
                    else:
                        # Handle single values
                        row_data[key] = value
                else:
                    row_data[key] = 'NA'
            formatted_data.append(row_data)

    if not formatted_data:
        print("⚠️ No data to write to Excel")
        return None

    # Create a DataFrame
    df = pd.DataFrame(formatted_data)

    # Reorder the columns
    df = df[column_order]

    # Write to Excel
    try:
        if os.path.exists(file_path):
            print(f"📝 Appending to existing Excel file: {file_path}")
            existing_df = pd.read_excel(file_path)
            combined_df = pd.concat([existing_df, df], ignore_index=True)
            combined_df.to_excel(file_path, index=False)
        else:
            print(f"📄 Creating new Excel file: {file_path}")
            df.to_excel(file_path, index=False)
        
        print(f"✅ Successfully wrote {len(df)} rows to Excel file")
        return file_path
        
    except Exception as e:
        print(f"❌ Error writing to Excel: {str(e)}")
        return None

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
    """
    Complete processing pipeline: process directory and export to Excel
    
    Args:
        ticket_number: Ticket number
        directory_path: Path to directory containing log files
        output_file_path: Optional path for Excel output
    
    Returns:
        Dictionary with processing results
    """
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
