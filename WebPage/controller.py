# controller.py - Business Logic Layer
import os
import sys
import json
import time
import logging
import datetime
import shutil
import zipfile
from typing import Dict, Any
from pathlib import Path

# Setup paths
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
pm_report_dir = os.path.join(parent_dir, 'PM_Report')
eox_dir = os.path.join(parent_dir, 'EOX')

if os.path.exists(pm_report_dir):
    sys.path.insert(0, pm_report_dir)
if os.path.exists(eox_dir):
    sys.path.insert(0, eox_dir)

# Setup logging
root_dir = os.path.dirname(current_dir)
log_dir = os.path.join(root_dir, "Logs")
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    filename=os.path.join(log_dir, f"Controller_Logs_{datetime.datetime.today().strftime('%Y-%m-%d')}.log"),
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Import modules
try:
    import Cisco_EOX
    import Switching.Cisco_IOS_XE as Cisco_IOS_XE
    import Switching.Data_to_Excel as Data_to_Excel
    logging.info("All modules imported successfully")
except ImportError as e:
    logging.error(f"Module import failed: {e}")
    
    class MockModule:
        @staticmethod
        def eox_tes():
            logging.warning("Mock EOX test - real module not available")
            return "Mock test completed"
        
        @staticmethod
        def request_EOX_data_from_online(excel_file_path, technology):
            logging.warning("Mock EOX processing - real module not available")
            return True
        
        @staticmethod
        def sub_controller(data, unique_pid, technology):
            logging.warning("Mock sub_controller - real module not available")
            return data
    
    if 'Cisco_EOX' not in globals():
        Cisco_EOX = MockModule()

def extract_zip_flatten_structure(zip_file_path):
    """Extract zip file with flattened structure"""
    try:
        if not os.path.exists(zip_file_path):
            return {
                'success': False,
                'error': f'Zip file not found: {zip_file_path}',
                'extracted_files': []
            }
        
        zip_directory = os.path.dirname(zip_file_path)
        zip_filename = os.path.basename(zip_file_path)
        extract_folder_name = zip_filename.rsplit('.', 1)[0] + '_extracted'
        extract_path = os.path.join(zip_directory, extract_folder_name)
        
        os.makedirs(extract_path, exist_ok=True)
        extracted_files = []
        
        with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
            for file_info in zip_ref.infolist():
                if file_info.is_dir():
                    continue
                
                original_filename = os.path.basename(file_info.filename)
                if not original_filename:
                    continue
                
                final_filename = original_filename
                counter = 1
                while os.path.exists(os.path.join(extract_path, final_filename)):
                    name, ext = os.path.splitext(original_filename)
                    final_filename = f"{name}_{counter}{ext}"
                    counter += 1
                
                with zip_ref.open(file_info) as source:
                    target_path = os.path.join(extract_path, final_filename)
                    with open(target_path, 'wb') as target:
                        target.write(source.read())
                
                extracted_files.append(target_path)
        
        return {
            'success': True,
            'extract_path': extract_path,
            'extracted_files': extracted_files,
            'file_count': len(extracted_files)
        }
    
    except zipfile.BadZipFile:
        return {'success': False, 'error': 'Invalid or corrupted zip file'}
    except PermissionError:
        return {'success': False, 'error': 'Permission denied - cannot extract files'}
    except Exception as e:
        return {'success': False, 'error': f'Extraction error: {str(e)}'}

def check_module_availability():
    """Check which modules are available"""
    return {
        'Cisco_IOS_XE': hasattr(Cisco_IOS_XE, 'process_directory') if 'Cisco_IOS_XE' in globals() else False,
        'Data_to_Excel': hasattr(Data_to_Excel, 'append_to_excel') if 'Data_to_Excel' in globals() else False,
        'Cisco_EOX': hasattr(Cisco_EOX, 'eox_tes') if 'Cisco_EOX' in globals() else False,
        'extract_zip_flatten_structure': True
    }

def process_upload(request_data: Dict[str, Any], file_obj, upload_folder: str) -> bool:
    logging.info("Starting upload processing")
    
    try:
        ticket = request_data.get('ticket', '').strip()
        comment = request_data.get('comment', '')
        technology = request_data.get('technology', '')
        
        modules = check_module_availability()
        
        if not modules['extract_zip_flatten_structure']:
            logging.critical('File processing module unavailable')
            return False
        
        # Create folder and save file
        ticket_folder = Path(upload_folder) / ticket
        ticket_folder.mkdir(parents=True, exist_ok=True)
        
        file_path = ticket_folder / f"{ticket}.zip"
        file_obj.save(str(file_path))
        
        # Save metadata
        metadata_path = ticket_folder / 'metadata.json'
        upload_info = {
            'ticket': ticket,
            'comment': comment,
            'technology': technology,
            'file_path': str(file_path),
            'filename': file_obj.filename,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'modules': modules
        }
        
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(upload_info, f, indent=4, ensure_ascii=False)
        
        # Extract ZIP file
        extraction_result = extract_zip_flatten_structure(str(file_path))
        if not extraction_result or not extraction_result.get('success', False):
            logging.error("ZIP extraction failed")
            return False
        
        # Process with Cisco_IOS_XE
        if not modules['Cisco_IOS_XE']:
            logging.error("Cisco_IOS_XE module unavailable")
            return False
            
        try:
            data = Cisco_IOS_XE.process_directory(extraction_result['extract_path'])
        except Exception as e:
            logging.error(f"Cisco_IOS_XE processing failed: {e}")
            return False
        
        # Excel processing
        # print("Initial data :\n", data)
        if not modules['Data_to_Excel']:
            logging.warning("Data_to_Excel module unavailable")
            return True
        
        try:
            unique_values = Data_to_Excel.unique_model_numbers_and_serials(data)
            unique_pid = []
            for values in unique_values:
                unique_pid.append(values[0])
            fresh_data = Cisco_EOX.sub_controller(data, unique_pid, technology)
            # print("Fresh data :\n", fresh_data)
        except Exception as e:
            logging.error(f"EOX sub_controller failed: {e}")
            fresh_data = data  # Use original data if EOX fails
        
        excel_path = ticket_folder / f"{ticket}_analysis.xlsx"
        
        try:
            Data_to_Excel.append_to_excel(ticket, fresh_data, str(excel_path))
            
            if not excel_path.exists():
                logging.error("Excel file not created")
                return False
        
            Data_to_Excel.process_and_style_excel(str(excel_path)) 
               
        except Exception as e:
            logging.error(f"Excel creation failed: {e}")
            return False
        
        # Create copy for EOX
        try:
            copy_path = excel_path.parent / f"copy_{excel_path.name}"
            shutil.copy2(str(excel_path), str(copy_path))
            
            # EOX processing on copy
            if copy_path.exists() and modules['Cisco_EOX']:
                try:
                    Cisco_EOX.request_EOX_data_from_online(excel_file_path=str(copy_path), technology=technology)
                except Exception as e:
                    logging.error(f"EOX processing failed: {e}")
            
        except Exception as e:
            logging.error(f"Copy creation failed: {e}")
        
        logging.info(f"Upload processing completed successfully for ticket: {ticket}")
        return True
        
    except Exception as e:
        logging.exception(f'Upload processing error: {str(e)}')
        return False
