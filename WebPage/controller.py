# controller.py - Business Logic Layer
import os
import json
import re
import time
import logging
import datetime
from typing import Dict, Any, Optional
from pathlib import Path

# Import from your custom import files
from import_one import *    # Database + EOX modules  
from import_two import *    # Switching modules
from file_processing import extract_zip_flatten_structure

# Setup logging
log_dir = os.path.join(os.path.dirname(__file__), "controller")
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(log_dir, f"{datetime.datetime.today().strftime('%Y-%m-%d')}.log"),
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Get logger for this module
logger = logging.getLogger(__name__)

class UploadController:
    def __init__(self, upload_folder: str, allowed_extensions: set):
        self.upload_folder = Path(upload_folder)
        self.allowed_extensions = allowed_extensions
        
        # Ensure upload folder exists
        self.upload_folder.mkdir(parents=True, exist_ok=True)
        logging.info(f"UploadController initialized with upload folder: {self.upload_folder}")
    
    def allowed_file(self, filename: str) -> bool:
        """Check if file extension is allowed"""
        if not filename or '.' not in filename:
            logging.warning(f"Invalid filename format: {filename}")
            return False
        
        extension = filename.rsplit('.', 1)[1].lower()
        is_allowed = extension in self.allowed_extensions
        
        logging.debug(f"File extension check - {filename}: {extension} - Allowed: {is_allowed}")
        return is_allowed
    
    def validate_ticket_number(self, ticket: str) -> bool:
        """Validate ticket number format"""
        if not ticket:
            logging.warning("Empty ticket number provided")
            return False
        
        pattern = r'^SVR\d+$'
        is_valid = bool(re.match(pattern, ticket))
        
        if is_valid:
            logging.debug(f"Ticket number validation passed: {ticket}")
        else:
            logging.warning(f"Invalid ticket number format: {ticket}")
        
        return is_valid
    
    def check_module_availability(self) -> Dict[str, bool]:
        """Check which modules are available for processing"""
        modules = {
            'Cisco_IOS_XE': 'Cisco_IOS_XE' in globals(),
            'Data_to_Excel': 'Data_to_Excel' in globals(),
            'Cisco_EOX': 'Cisco_EOX' in globals(),
            'extract_zip_flatten_structure': 'extract_zip_flatten_structure' in globals()
        }
        
        logging.info("Module availability check:")
        for module, available in modules.items():
            status = "✅ Available" if available else "❌ Not available"
            logging.info(f"  {module}: {status}")
        
        return modules
    
    def process_upload(self, request_data: Dict[str, Any], file_obj) -> Dict[str, Any]:
        """Main upload processing function"""
        logging.info("=== Starting upload processing ===")
        
        result = {
            'success': False,
            'message': '',
            'errors': [],
            'redirect_to': 'index'
        }
        
        try:
            # Extract and validate form data
            ticket = request_data.get('ticket', '').strip()
            comment = request_data.get('comment', '')
            technology = request_data.get('technology', '')
            
            logging.info(f"Processing upload for ticket: {ticket}, technology: {technology}")
            logging.debug(f"Request data: {request_data}")
            
            # Validation
            validation_result = self._validate_request(ticket, file_obj, technology)
            if not validation_result['valid']:
                result['errors'] = validation_result['errors']
                result['message'] = validation_result['message']
                logging.error(f"Validation failed: {validation_result['message']}")
                return result
            
            # Check module availability
            modules = self.check_module_availability()
            if not modules['extract_zip_flatten_structure']:
                error_msg = 'File processing module not available.'
                result['errors'].append(error_msg)
                result['message'] = 'System error: Processing module unavailable.'
                logging.critical(error_msg)
                return result
            
            # Create upload folder structure and save file
            ticket_folder = self._setup_ticket_folder(ticket)
            file_path = self._save_uploaded_file(file_obj, ticket, ticket_folder)
            
            # Create and save metadata
            metadata = self._create_metadata(ticket, comment, technology, file_path, file_obj.filename, modules)
            meta_path = ticket_folder / 'metadata.json'
            self._save_metadata(metadata, meta_path)
            
            # Process the file
            logging.info(f"Starting file processing for {file_path}")
            processing_result = self._process_file(file_path, ticket_folder, ticket, technology, metadata, modules)
            
            # Update final metadata
            self._save_metadata(metadata, meta_path)
            
            if processing_result['success']:
                result['success'] = True
                result['message'] = f'Logs uploaded and processed successfully for ticket {ticket}.'
                logging.info(f"Upload processing completed successfully for ticket: {ticket}")
            else:
                result['message'] = processing_result['message']
                result['errors'] = processing_result['errors']
                logging.error(f"Processing failed for ticket {ticket}: {result['message']}")
            
            return result
            
        except Exception as e:
            error_msg = f'Unexpected error during upload processing: {str(e)}'
            result['errors'].append(error_msg)
            result['message'] = 'An unexpected error occurred during processing.'
            logging.exception(error_msg)
            return result
    
    def _validate_request(self, ticket: str, file_obj, technology: str) -> Dict[str, Any]:
        """Validate the upload request"""
        errors = []
        
        if not ticket:
            errors.append('Ticket Number is required.')
        elif not self.validate_ticket_number(ticket):
            errors.append('Ticket number must start with "SVR" followed by numbers.')
        
        if not file_obj or not hasattr(file_obj, 'filename') or file_obj.filename == '':
            errors.append('No file selected.')
        elif not self.allowed_file(file_obj.filename):
            errors.append('Only zip files are allowed.')
        
        if not technology:
            errors.append('Please select a technology.')
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'message': errors[0] if errors else ''
        }
    
    def _setup_ticket_folder(self, ticket: str) -> Path:
        """Create and setup ticket folder"""
        ticket_folder = self.upload_folder / ticket
        ticket_folder.mkdir(parents=True, exist_ok=True)
        logging.info(f"Created/verified ticket folder: {ticket_folder}")
        return ticket_folder
    
    def _save_uploaded_file(self, file_obj, ticket: str, ticket_folder: Path) -> Path:
        """Save uploaded file to ticket folder"""
        filename = f"{ticket}.zip"
        file_path = ticket_folder / filename
        
        try:
            file_obj.save(str(file_path))
            file_size = file_path.stat().st_size
            logging.info(f"File saved successfully: {file_path} (Size: {file_size} bytes)")
            return file_path
        except Exception as e:
            logging.error(f"Failed to save file {filename}: {str(e)}")
            raise
    
    def _create_metadata(self, ticket: str, comment: str, technology: str, 
                        file_path: Path, filename: str, modules: Dict[str, bool]) -> Dict[str, Any]:
        """Create metadata dictionary"""
        metadata = {
            'ticket_number': ticket,
            'comment': comment,
            'technology': technology,
            'file_path': str(file_path),
            'filename': filename,
            'upload_timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'module_availability': modules,
            'processing_status': 'initialized'
        }
        logging.debug(f"Created metadata for ticket {ticket}")
        return metadata
    
    def _save_metadata(self, metadata: Dict[str, Any], meta_path: Path) -> None:
        """Save metadata to JSON file"""
        try:
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=4, ensure_ascii=False)
            logging.debug(f"Metadata saved to: {meta_path}")
        except Exception as e:
            logging.error(f"Failed to save metadata to {meta_path}: {str(e)}")
            raise
    
    def _process_file(self, file_path: Path, ticket_folder: Path, ticket: str, 
                     technology: str, metadata: Dict[str, Any], modules: Dict[str, bool]) -> Dict[str, Any]:
        """Private method to handle file processing"""
        logging.info(f"Starting file processing for: {file_path}")
        result = {'success': False, 'message': '', 'errors': []}
        
        try:
            # Extract file
            logging.info("Starting file extraction...")
            extraction_result = extract_zip_flatten_structure(str(file_path))
            
            if extraction_result['success']:
                logging.info(f"Extraction successful: {extraction_result['message']}")
                
                metadata['extraction'] = {
                    'extracted': True,
                    'extract_path': extraction_result['extract_path'],
                    'file_count': extraction_result['file_count'],
                    'structure': 'flattened',
                    'extracted_files': [os.path.basename(f) for f in extraction_result['extracted_files']],
                    'extraction_timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
                }
                
                # Process with Cisco_IOS_XE
                if modules['Cisco_IOS_XE'] and hasattr(Cisco_IOS_XE, 'process_directory'):
                    logging.info("Starting Cisco_IOS_XE processing...")
                    try:
                        data = Cisco_IOS_XE.process_directory(extraction_result['extract_path'])
                        logging.info(f"Cisco_IOS_XE processing completed. Data type: {type(data)}, Count: {len(data) if isinstance(data, list) else 1}")
                        
                        metadata['processing'] = {
                            'status': 'completed',
                            'data_count': len(data) if isinstance(data, list) else 1,
                            'processed_at': time.strftime('%Y-%m-%d %H:%M:%S')
                        }
                        
                        # Excel processing
                        if modules['Data_to_Excel']:
                            excel_result = self._process_excel(data, ticket, ticket_folder, technology, metadata, modules)
                            if not excel_result['success']:
                                result['errors'].extend(excel_result['errors'])
                        else:
                            logging.warning("Data_to_Excel module not available - skipping Excel export")
                            metadata['excel_export'] = {'status': 'skipped', 'reason': 'module_not_available'}
                        
                    except Exception as e:
                        error_msg = f"Cisco_IOS_XE processing failed: {str(e)}"
                        logging.error(error_msg)
                        result['errors'].append(error_msg)
                        metadata['processing'] = {'status': 'failed', 'error': str(e)}
                
                else:
                    error_msg = "Cisco_IOS_XE module not available or missing process_directory method"
                    logging.error(error_msg)
                    result['errors'].append(error_msg)
                    metadata['processing'] = {'status': 'failed', 'error': 'module_not_available'}
                
                if not result['errors']:
                    result['success'] = True
                    result['message'] = 'File processing completed successfully'
                    logging.info("File processing completed successfully")
                
            else:
                error_msg = f"Extraction failed: {extraction_result['error']}"
                logging.error(error_msg)
                result['errors'].append(error_msg)
                metadata['extraction'] = {
                    'extracted': False, 
                    'error': extraction_result['error'],
                    'extraction_timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
                }
                
        except Exception as e:
            error_msg = f"File processing error: {str(e)}"
            logging.exception(error_msg)
            result['errors'].append(error_msg)
            metadata['extraction'] = {
                'extracted': False, 
                'error': str(e),
                'extraction_timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            }
        
        return result
    
    def _process_excel(self, data: Any, ticket: str, ticket_folder: Path, 
                      technology: str, metadata: Dict[str, Any], modules: Dict[str, bool]) -> Dict[str, Any]:
        """Private method to handle Excel processing"""
        logging.info("Starting Excel processing...")
        result = {'success': False, 'errors': []}
        
        try:
            excel_path = ticket_folder / f"{ticket}_analysis.xlsx"
            
            # Create Excel file
            logging.info(f"Creating Excel file: {excel_path}")
            Data_to_Excel.append_to_excel(ticket, data, str(excel_path))
            
            if excel_path.exists():
                file_size = excel_path.stat().st_size
                logging.info(f"Excel export completed: {excel_path} (Size: {file_size} bytes)")
                metadata['excel_export'] = {
                    'status': 'completed', 
                    'file_path': str(excel_path),
                    'file_size': file_size,
                    'created_at': time.strftime('%Y-%m-%d %H:%M:%S')
                }
            else:
                raise FileNotFoundError(f"Excel file was not created: {excel_path}")
            
            # Create copy for EOX analysis
            logging.info("Creating copy for EOX analysis...")
            copy_result = Data_to_Excel.process_eox_analysis(str(excel_path))
            metadata['copy_creation'] = copy_result
            
            # Run EOX test
            logging.info("Running EOX test...")
            Cisco_EOX.eox_tes()
            
            # EOX Processing
            if copy_result.get('status') == 'success' and modules['Cisco_EOX']:
                logging.info(f"Starting EOX processing for: {excel_path} with technology: {technology}")
                try:
                    eox_result = Cisco_EOX.eox_pull(excel_file_path=str(excel_path), technology=technology)
                    metadata['eox_processing'] = {
                        'status': 'completed',
                        'result': eox_result,
                        'processed_at': time.strftime('%Y-%m-%d %H:%M:%S')
                    }
                    logging.info("EOX processing completed successfully")
                except Exception as eox_error:
                    error_msg = f"EOX processing failed: {str(eox_error)}"
                    logging.error(error_msg)
                    metadata['eox_processing'] = {
                        'status': 'failed',
                        'error': str(eox_error),
                        'failed_at': time.strftime('%Y-%m-%d %H:%M:%S')
                    }
                    result['errors'].append(error_msg)
            elif not modules['Cisco_EOX']:
                logging.warning("Cisco_EOX module not available - skipping EOX processing")
                metadata['eox_processing'] = {'status': 'skipped', 'reason': 'module_not_available'}
            else:
                logging.warning("Copy creation failed - skipping EOX processing")
                result['errors'].append("Copy creation failed, EOX processing skipped")
            
            result['success'] = True
            
        except Exception as excel_error:
            error_msg = f"Excel processing failed: {str(excel_error)}"
            logging.exception(error_msg)
            metadata['excel_export'] = {
                'status': 'failed', 
                'error': str(excel_error),
                'failed_at': time.strftime('%Y-%m-%d %H:%M:%S')
            }
            result['errors'].append(error_msg)
        
        return result


def get_controller(upload_folder: str, allowed_extensions: set) -> UploadController:
    """Factory function to create controller with proper configuration"""
    logging.info(f"Creating UploadController with folder: {upload_folder}, extensions: {allowed_extensions}")
    return UploadController(upload_folder, allowed_extensions)
