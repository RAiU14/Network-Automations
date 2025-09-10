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

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]  # .../Cisco_Automations
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    # import strictly as packages
    from PM_Report import pipeline, Data_to_Excel
    from EOX import Cisco_EOX
    logging.info("All modules imported successfully")
except ImportError as e:
    logging.error(f"Module import failed: {e}")

    # fallback mock to keep flows usable
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

def backup_old_zip_file(ticket_folder: Path, ticket: str) -> bool:
    """Create backup of existing zip file before overwriting"""
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
    """Safely remove directory - generic Unix/Linux approach"""
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
    """Clear existing extraction directory"""
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
    """Create backup of existing Excel file"""
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
    """Get extraction path, creating unique one if needed"""
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
    """Extract zip file with flattened structure"""
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
    """Check which modules + required functions are available"""
    pipeline_ok = 'pipeline' in globals() and hasattr(pipeline, 'extract')
    d2x_ok = 'Data_to_Excel' in globals() and all(
        hasattr(Data_to_Excel, fn)
        for fn in ('append_to_excel', 'process_and_style_excel', 'unique_model_numbers_and_serials')
    )
    eox_ok = 'Cisco_EOX' in globals() and all(
        hasattr(Cisco_EOX, fn)
        for fn in ('eox_tes', 'request_EOX_data_from_online', 'sub_controller')
    )
    return {
        'pipeline': pipeline_ok,
        'Data_to_Excel': d2x_ok,
        'Cisco_EOX': eox_ok,
        'extract_zip_flatten_structure': True
    }

def cleanup_old_extractions(ticket_folder: Path, ticket: str, keep_count: int = 5):
    """Clean up old extraction directories to prevent disk space issues"""
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

def process_upload(request_data: Dict[str, Any], file_obj, upload_folder: str, overwrite_existing: bool = False) -> bool:
    logging.info(f"Starting upload processing (overwrite: {overwrite_existing})")
    
    try:
        ticket = request_data.get('ticket', '').strip()
        comment = request_data.get('comment', '')
        technology = request_data.get('technology', '')
        
        modules = check_module_availability()
        
        if not modules['extract_zip_flatten_structure']:
            logging.critical('File processing module unavailable')
            return False
        
        # Create folder paths
        ticket_folder = Path(upload_folder) / ticket
        ticket_folder.mkdir(parents=True, exist_ok=True)
        
        file_path = ticket_folder / f"{ticket}.zip"
        excel_path = ticket_folder / f"{ticket}_analysis.xlsx"
        
        # Check existing state
        excel_already_exists = excel_path.exists()
        zip_already_exists = file_path.exists()
        
        logging.info(f"Existing state - Excel: {excel_already_exists}, Zip: {zip_already_exists}")
        
        # Handle existing files based on overwrite mode
        if overwrite_existing:
            # Backup old zip file if it exists
            if zip_already_exists:
                backup_success = backup_old_zip_file(ticket_folder, ticket)
                if not backup_success:
                    logging.warning("Failed to backup old zip file, continuing anyway")
            
            # Backup existing Excel file if it exists
            if excel_already_exists:
                backup_success = backup_existing_excel(excel_path)
                if not backup_success:
                    logging.warning("Failed to backup existing Excel file, continuing anyway")
            
            # Clear extraction directory
            clear_success = clear_extraction_directory(ticket_folder, ticket)
            if not clear_success:
                logging.warning("Failed to clear extraction directory, will use alternative")
            
            logging.info("Prepared for overwrite - created backups and cleared directories")
        
        # Save the new uploaded file
        try:
            file_obj.save(str(file_path))
            logging.info(f"Saved new zip file: {file_path}")
        except Exception as save_error:
            logging.error(f"Failed to save zip file: {save_error}")
            return False
        
        # Save metadata
        metadata_path = ticket_folder / 'metadata.json'
        upload_info = {
            'ticket': ticket,
            'comment': comment,
            'technology': technology,
            'file_path': str(file_path),
            'filename': file_obj.filename,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'overwrite_mode': overwrite_existing,
            'excel_existed': excel_already_exists,
            'zip_existed': zip_already_exists,
            'modules': modules,
            'system_info': {
                'platform': os.name,
                'python_version': sys.version.split()[0]
            }
        }
        
        try:
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(upload_info, f, indent=4, ensure_ascii=False)
        except Exception as metadata_error:
            logging.warning(f"Failed to save metadata: {metadata_error}")
        
        # Extract ZIP file - pass ticket for better path management
        extraction_result = extract_zip_flatten_structure(str(file_path), ticket)
        if not extraction_result or not extraction_result.get('success', False):
            logging.error(f"ZIP extraction failed: {extraction_result.get('error', 'Unknown error')}")
            return False
        
        logging.info(f"Successfully extracted {extraction_result['file_count']} files")
        
        # Clean up old extraction directories to prevent disk space issues
        cleanup_old_extractions(ticket_folder, ticket)
        
        # Process with pipeline
        if not modules['pipeline']:
            logging.error("pipeline module unavailable")
            return False

        try:
            data = pipeline.extract(extraction_result['extract_path'])
            logging.info("pipeline processing completed successfully")
        except Exception as e:
            logging.error(f"pipeline processing failed: {e}")
            return False
        
        # Excel processing
        if not modules['Data_to_Excel']:
            logging.warning("Data_to_Excel module unavailable")
            return True
        
        try:
            # Get unique PIDs for EOX processing
            unique_values = Data_to_Excel.unique_model_numbers_and_serials(data)
            unique_pid = []
            for values in unique_values:
                unique_pid.append(values[0])
            
            # Process with EOX sub_controller
            fresh_data = Cisco_EOX.sub_controller(data, unique_pid, technology)
            logging.info("EOX sub_controller processing completed")
        except Exception as e:
            logging.error(f"EOX sub_controller failed: {e}")
            fresh_data = data  # Use original data if EOX fails
        
        try:
            # Remove existing Excel file if overwriting
            if excel_already_exists and overwrite_existing and excel_path.exists():
                excel_path.unlink()
                logging.info(f"Removed existing Excel file for overwrite: {excel_path}")
            
            # Create new Excel file
            Data_to_Excel.append_to_excel(ticket, fresh_data, str(excel_path))
            
            if not excel_path.exists():
                logging.error("Excel file not created")
                return False
        
            # Apply styling
            Data_to_Excel.process_and_style_excel(str(excel_path))
            logging.info(f"Successfully created Excel file: {excel_path}")
               
        except Exception as e:
            logging.error(f"Excel creation failed: {e}")
            return False
        
        # Handle EOX processing with conditional copying
        try:
            if excel_already_exists and overwrite_existing:
                # Create copy for EOX processing when overwriting
                copy_path = excel_path.parent / f"copy_{excel_path.name}"
                shutil.copy2(str(excel_path), str(copy_path))
                logging.info(f"Created copy for EOX processing: {copy_path}")
                
                # EOX processing on copy
                if modules['Cisco_EOX']:
                    try:
                        Cisco_EOX.request_EOX_data_from_online(excel_file_path=str(copy_path), technology=technology)
                        logging.info(f"EOX processing completed on copy: {copy_path}")
                    except Exception as e:
                        logging.error(f"EOX processing failed on copy: {e}")
            else:
                # First time processing - direct EOX processing
                logging.info("First time processing - performing direct EOX processing")
                
                if modules['Cisco_EOX']:
                    try:
                        # Create temporary copy for EOX to avoid modifying main file
                        temp_copy_path = excel_path.parent / f"temp_eox_{excel_path.name}"
                        shutil.copy2(str(excel_path), str(temp_copy_path))
                        
                        Cisco_EOX.request_EOX_data_from_online(excel_file_path=str(temp_copy_path), technology=technology)
                        logging.info(f"EOX processing completed on temporary copy: {temp_copy_path}")
                        
                        # Clean up temporary copy
                        if temp_copy_path.exists():
                            temp_copy_path.unlink()
                            logging.info("Removed temporary EOX copy")
                            
                    except Exception as e:
                        logging.error(f"EOX processing failed: {e}")
                        
        except Exception as e:
            logging.error(f"EOX processing workflow failed: {e}")
        
        logging.info(f"Upload processing completed successfully for ticket: {ticket}")
        return True
        
    except Exception as e:
        logging.exception(f'Upload processing error: {str(e)}')
        return False
