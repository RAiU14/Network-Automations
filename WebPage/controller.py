# controller.py - Generic File Management for Production Unix/Linux Systems
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
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial


# current file’s directory (Webpage/)
current_dir = os.path.dirname(os.path.abspath(__file__))
# project root (Cisco_Automations/)
root_dir = os.path.dirname(current_dir)

# Setup logging
log_dir = os.path.join(root_dir, "Logs")
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    filename=os.path.join(log_dir, f"Controller_Logs_{datetime.datetime.today().strftime('%Y-%m-%d')}.log"),
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
    
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))    

from EOX import API_Pipeline
from PM_Report import pipeline, Data_to_Excel
from WebPage import postprocess_controller

def backup_old_zip_file(ticket_folder: Path, ticket: str) -> bool:
    try:
        old_zip_path = ticket_folder / f"{ticket}.zip"
        if old_zip_path.exists():
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_zip_name = f"{ticket}_backup_{timestamp}.zip"
            backup_zip_path = ticket_folder / backup_zip_name
            
            shutil.copy2(str(old_zip_path), str(backup_zip_path))
            logging.info(f"Created backup of old zip file: {backup_zip_path}")
            return True
        return False
    except Exception as e:
        logging.error(f"Failed to backup old zip file: {e}")
        return False

def safe_remove_directory(directory_path: Path) -> bool:
    try:
        if not directory_path.exists():
            logging.debug(f"Directory doesn't exist: {directory_path}")
            return True
        
        # Simple removal for Unix systems
        shutil.rmtree(str(directory_path))
        logging.info(f"Successfully removed directory: {directory_path}")
        return True
        
    except PermissionError as e:
        logging.error(f"Permission denied removing directory {directory_path}: {e}")
        return False
    except Exception as e:
        logging.error(f"Failed to remove directory {directory_path}: {e}")
        return False

def clear_extraction_directory(ticket_folder: Path, ticket: str) -> bool:
    try:
        extract_folder_name = f"{ticket}_extracted"
        extract_path = ticket_folder / extract_folder_name
        
        if extract_path.exists():
            logging.info(f"Clearing extraction directory: {extract_path}")
            success = safe_remove_directory(extract_path)
            
            if success:
                logging.info(f"Successfully cleared extraction directory: {extract_path}")
                return True
            else:
                logging.warning(f"Could not clear extraction directory: {extract_path}")
                # Create a new unique directory name instead
                timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                new_extract_name = f"{ticket}_extracted_{timestamp}"
                logging.info(f"Will use alternative extraction directory: {new_extract_name}")
                return True
        else:
            logging.debug(f"Extraction directory doesn't exist: {extract_path}")
            return True
            
    except Exception as e:
        logging.error(f"Failed to clear extraction directory: {e}")
        return False

def backup_existing_excel(excel_path: Path) -> bool:
    try:
        if excel_path.exists():
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_name = f"{excel_path.stem}_backup_{timestamp}.xlsx"
            backup_path = excel_path.parent / backup_name
            shutil.copy2(str(excel_path), str(backup_path))
            logging.info(f"Created backup of existing Excel: {backup_path}")
            return True
        return False
    except Exception as e:
        logging.error(f"Failed to create Excel backup: {e}")
        return False

def get_extraction_path(zip_file_path: str, ticket: str) -> str:
    zip_directory = os.path.dirname(zip_file_path)
    base_extract_name = f"{ticket}_extracted"
    extract_path = os.path.join(zip_directory, base_extract_name)
    
    # If path exists and can't be cleared, create unique one
    if os.path.exists(extract_path):
        if not safe_remove_directory(Path(extract_path)):
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            extract_path = os.path.join(zip_directory, f"{base_extract_name}_{timestamp}")
            logging.info(f"Using alternative extraction path: {extract_path}")
    
    return extract_path

def extract_zip_flatten_structure(zip_file_path: str, ticket: str = None):
    try:
        if not os.path.exists(zip_file_path):
            return {
                'success': False,
                'error': f'Zip file not found: {zip_file_path}',
                'extracted_files': []
            }
        
        # Get extraction path
        if ticket:
            extract_path = get_extraction_path(zip_file_path, ticket)
        else:
            # Fallback to original method if no ticket provided
            zip_directory = os.path.dirname(zip_file_path)
            zip_filename = os.path.basename(zip_file_path)
            extract_folder_name = zip_filename.rsplit('.', 1)[0] + '_extracted'
            extract_path = os.path.join(zip_directory, extract_folder_name)
            
            # Remove existing if present
            if os.path.exists(extract_path):
                safe_remove_directory(Path(extract_path))
        
        # Create extraction directory
        os.makedirs(extract_path, exist_ok=True)
        extracted_files = []
        
        logging.info(f"Extracting to: {extract_path}")
        
        with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
            for file_info in zip_ref.infolist():
                if file_info.is_dir():
                    continue
                
                original_filename = os.path.basename(file_info.filename)
                if not original_filename:
                    continue
                
                # Handle filename conflicts
                final_filename = original_filename
                counter = 1
                while os.path.exists(os.path.join(extract_path, final_filename)):
                    name, ext = os.path.splitext(original_filename)
                    final_filename = f"{name}_{counter}{ext}"
                    counter += 1
                
                try:
                    with zip_ref.open(file_info) as source:
                        target_path = os.path.join(extract_path, final_filename)
                        with open(target_path, 'wb') as target:
                            target.write(source.read())
                    
                    extracted_files.append(target_path)
                    logging.debug(f"Extracted: {final_filename}")
                    
                except Exception as extract_error:
                    logging.warning(f"Failed to extract {original_filename}: {extract_error}")
                    continue
        
        if extracted_files:
            logging.info(f"Successfully extracted {len(extracted_files)} files to {extract_path}")
            return {
                'success': True,
                'extract_path': extract_path,
                'extracted_files': extracted_files,
                'file_count': len(extracted_files)
            }
        else:
            return {
                'success': False,
                'error': 'No files were extracted from the zip file',
                'extracted_files': []
            }
    
    except zipfile.BadZipFile:
        return {'success': False, 'error': 'Invalid or corrupted zip file'}
    except PermissionError as e:
        logging.error(f"Permission error during extraction: {e}")
        return {'success': False, 'error': f'Permission denied: {str(e)}'}
    except Exception as e:
        logging.error(f"Extraction error: {e}")
        return {'success': False, 'error': f'Extraction error: {str(e)}'}

def check_module_availability():
    pipeline_ok = 'pipeline' in globals() and hasattr(pipeline, 'extract')
    d2x_ok = 'Data_to_Excel' in globals() and all(
        hasattr(Data_to_Excel, fn)
        for fn in ('append_to_excel', 'process_and_style_excel', 'unique_model_numbers_and_serials')
    )
    api_pipeline = 'API_Pipeline' in globals() and all(
        hasattr(API_Pipeline, fn)
        for fn in ('eox_tes', 'request_EOX_data_from_online', 'sub_controller')
    )
    return {
        'pipeline': pipeline_ok,
        'Data_to_Excel': d2x_ok,
        'API_Pipeline': api_pipeline,
        'extract_zip_flatten_structure': True
    }

def cleanup_old_extractions(ticket_folder: Path, ticket: str, keep_count: int = 5):
    try:
        extraction_pattern = f"{ticket}_extracted"
        old_extractions = []
        
        for item in ticket_folder.iterdir():
            if item.is_dir() and item.name.startswith(extraction_pattern):
                old_extractions.append(item)
        
        # Sort by modification time, keep the newest ones
        old_extractions.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        # Remove old ones beyond keep_count
        for old_extract in old_extractions[keep_count:]:
            try:
                safe_remove_directory(old_extract)
                logging.info(f"Cleaned up old extraction directory: {old_extract}")
            except Exception as e:
                logging.warning(f"Failed to clean up {old_extract}: {e}")
                
    except Exception as e:
        logging.warning(f"Failed to cleanup old extractions: {e}")

# Helper functions for concurrent operations
def setup_folders_sync(upload_folder, ticket, overwrite_existing):
    try:
        ticket_folder = Path(upload_folder) / ticket
        ticket_folder.mkdir(parents=True, exist_ok=True)
        file_path = ticket_folder / f"{ticket}.zip"
        excel_path = ticket_folder / f"{ticket}_analysis.xlsx"
        
        logging.debug(f"Folder setup completed: {ticket_folder}")
        return ticket_folder, file_path, excel_path
    except Exception as e:
        logging.error(f"Folder setup failed: {e}")
        return None, None, None

def save_file_sync(file_obj, file_path):
    try:
        file_obj.save(str(file_path))
        logging.info(f"Saved file: {file_path}")
        return True
    except Exception as e:
        logging.error(f"Failed to save file: {e}")
        return False

def save_metadata_sync(ticket_folder, request_data, modules):
    try:
        metadata_path = ticket_folder / 'metadata.json'
        
        # Get file info if available
        file_path = ticket_folder / f"{request_data.get('ticket', '')}.zip"
        
        upload_info = {
            'ticket': request_data.get('ticket', ''),
            'comment': request_data.get('comment', ''),
            'technology': request_data.get('technology', ''),
            'file_path': str(file_path),
            'filename': f"{request_data.get('ticket', '')}.zip",
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'overwrite_mode': request_data.get('overwrite_existing', False),
            'modules': modules,
            'system_info': {
                'platform': os.name,
                'python_version': sys.version.split()[0]
            }
        }
        
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(upload_info, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        logging.warning(f"Failed to save metadata: {e}")
        return True  # Non-critical

def process_upload(request_data: Dict[str, Any], file_obj, upload_folder: str, overwrite_existing: bool = False) -> bool:
    logging.info(f"Starting optimized upload processing (overwrite: {overwrite_existing})")
    
    # Quick function availability check
    if not hasattr(API_Pipeline, 'eox_milestones'):
        logging.critical("eox_milestones function not found in API_Pipeline!")
        return False
    
    try:
        # Phase 1: Basic setup (unchanged)
        ticket = request_data.get('ticket', '').strip()
        comment = request_data.get('comment', '')
        technology = request_data.get('technology', '')
        
        # Phase 2: Concurrent I/O operations using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=4) as executor:
            # Submit concurrent tasks
            futures = []
            
            # Module check
            futures.append(executor.submit(check_module_availability))
            
            # Folder setup
            futures.append(executor.submit(setup_folders_sync, upload_folder, ticket, overwrite_existing))
            
            # Wait for completion
            modules = futures[0].result()
            folder_info = futures[1].result()
            
            if not modules['extract_zip_flatten_structure']:
                logging.critical('File processing module unavailable')
                return False
            
            # Validate folder setup
            if folder_info[0] is None:
                logging.error("Folder setup failed")
                return False
                
            ticket_folder, file_path, excel_path = folder_info
            
            # Phase 3: File operations (concurrent)
            file_futures = []
            file_futures.append(executor.submit(save_file_sync, file_obj, file_path))
            file_futures.append(executor.submit(save_metadata_sync, ticket_folder, request_data, modules))
            
            # Handle overwrite operations
            if overwrite_existing:
                file_futures.append(executor.submit(backup_old_zip_file, ticket_folder, ticket))
                file_futures.append(executor.submit(backup_existing_excel, excel_path))
                file_futures.append(executor.submit(clear_extraction_directory, ticket_folder, ticket))
            
            # Wait for file operations
            for future in as_completed(file_futures):
                result = future.result()
                if result is False:  # If any critical operation failed
                    logging.error("Critical file operation failed")
                    return False
            
            # Phase 4: CPU-intensive operations
            extraction_result = extract_zip_flatten_structure(str(file_path), ticket)
            if not extraction_result or not extraction_result.get('success', False):
                logging.error("ZIP extraction failed")
                return False
            
            # Phase 5: Data processing pipeline
            data = pipeline.extract(extraction_result['extract_path'])
            
            # Phase 6: Concurrent API and Excel processing
            processing_futures = []
            
            # Get unique PIDs
            unique_values = Data_to_Excel.unique_model_numbers_and_serials(data)
            
            # Submit EOX processing
            processing_futures.append(
                executor.submit(API_Pipeline.eox_milestones, data, unique_values, technology)
            )
            
            # Submit cleanup task (non-blocking)
            processing_futures.append(
                executor.submit(cleanup_old_extractions, ticket_folder, ticket)
            )
            
            # Get EOX data with proper error handling
            try:
                eox_data = processing_futures[0].result(timeout=300)  # 5 minute timeout
                logging.info("EOX processing completed")
            except Exception as e:
                logging.error(f"EOX processing failed: {e}")
                eox_data = None
            
            # Let cleanup finish in background
            try:
                processing_futures[1].result(timeout=10)  # Give cleanup 10 seconds
            except Exception:
                logging.warning("Cleanup still running in background")
            
            # Process final data
            if not eox_data:
                logging.error("EOX data missing or failed!")
                return False
                
            try:
                final_data = postprocess_controller.sub_controller(data, eox_data)
                if not final_data:
                    logging.error("Post-processing returned empty data!")
                    return False
            except Exception as e:
                logging.error(f"Post-processing failed: {e}")
                return False
            
            # Create Excel file
            try:
                Data_to_Excel.append_to_excel(ticket, final_data, file_path=excel_path)
                logging.info("Excel file created successfully")
                return True
            except Exception as e:
                logging.error(f"Excel creation failed: {e}")
                return False
        
        return False
        
    except Exception as e:
        logging.exception(f'Optimized upload processing error: {str(e)}')
        return False

def main():
    data = []
    # data = pipeline.extract(r"C:\Users\girish.n\Downloads\OneDrive_2025-11-18 1\Cisco R&S")
    file = r"C:\Users\girish.n\Downloads\PM logs sets\Ultimate_logs\C9200_Switches\SMEDC-ITMT-SW01.txt"
    with open(file, "r", errors="ignore") as f:
        text = f.read()

    # 1) check if 'show version' exists at all
    print("Contains 'show version'?:", "show version" in text.lower())

    # 2) find index of first occurrence
    idx = text.lower().find("show version")
    print("Index of 'show version':", idx)

    if idx != -1:
        print("\n--- Context around 'show version' (±200 chars) ---")
        print(text[idx-200 : idx+200])

    # 3) now test your scoper correctly
    ver = pipeline._scope_show_version(text)
    print("\nScoped show version length:", len(ver))
    print("\n--- First 300 chars of scoped block ---")
    print(ver[:300])
    # target_filename = 'TH-MUDA-WHC9407R-01.txt'
    # selected_data = None

    # for item in data:
    #     # Check if the 'File name' key exists and the first element matches
    #     if item.get('File name') and item['File name'][0] == target_filename:
    #         selected_data = item
    #         break  # Exit the loop immediately after finding the match

    # # selected_data now holds the matching dictionary or None
    # print(selected_data)
    # Data_to_Excel.append_to_excel("SVR3", data, file_path = r"C:\Users\girish.n\OneDrive - NTT\Desktop\Github Projects\Workspace_repo\Network_Automation_PM_Report\WebPage\SVR3_analysis.xlsx")
# if __name__ == "__main__":
#     main()


def test_case():
    from PM_Report import pipeline
    from PM_Report.Switching.ios_xe import Cisco_IOS_XE as IOSXE
    from PM_Report.Switching.ios import Cisco_IOS as IOS
    import traceback
    import re

    file = r"C:\Users\girish.n\Downloads\PM logs sets\Ultimate_logs\C8300_Switches\172.18.9.99_details.txt"

    # print("pipeline file:", pipeline.__file__)
    with open(file, "r", errors="ignore") as f:
        text = f.read()
    print("detect_os says:", pipeline.detect_os(open(file, "r", errors="ignore").read()))

    try:
        # out = IOSXE.process_file(file)
        # print("process_file returned type:", type(out))
        # print("process_file returned:", out)

        data = pipeline._process_one(file)
        print("Data extracted:", data)

        # if isinstance(out, dict):
        #     print("process_file ok. Host name:", out.get("Host name"))
        #     print("Remark:", out.get("Remark"))
        # else:
        #     print("process_file returned NON-dict (likely missing return in ios_xe.py)")
    except Exception as e:
        print("process_file exception:", repr(e))
        print(traceback.format_exc())

if __name__ == "__main__":
    test_case()