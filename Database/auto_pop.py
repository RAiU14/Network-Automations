import os
import datetime
import logging
import sys
import json

# Setup logging
current_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
log_dir = os.path.join(current_dir, "auto_pop_logs")
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    filename=os.path.join(log_dir, f"{datetime.datetime.today().strftime('%Y-%m-%d')}.log"),
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Add the parent directory to Python path
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from EOX.Cisco_EOX import *

# Global storage variables
all_available_devices = {}
all_devices = {}
eox_devices = {}
eox_data = {}
categories = {}

def initialize_categories():
    """Initialize categories from Cisco EOX module"""
    global categories
    try:
        categories = category()
        logging.info("Categories initialized successfully")
    except Exception as e:
        logging.error(f"Failed to initialize categories: {str(e)}")
        raise

def load_categories():
    """Load all available devices from categories"""
    global all_available_devices, categories
    try:
        logging.info("Loading categories...")
        for link in categories.keys():
            try:
                all_available_devices[link] = open_cat(categories[link])
                logging.debug(f"Loaded category: {link}")
            except Exception as e:
                logging.error(f"Failed to load category {link}: {str(e)}")
                continue
        
        logging.info(f"Categories loaded successfully. Total: {len(all_available_devices)}")
        
    except Exception as e:
        logging.error(f"Error in load_categories: {str(e)}")
        raise

def process_devices():
    """Process devices and separate regular devices from EOX devices"""
    global all_available_devices, all_devices, eox_devices
    try:
        logging.info("Processing devices...")
        processed_count = 0
        eox_count = 0
        
        for technology in all_available_devices:
            try:
                device_data = all_available_devices[technology]
                if len(device_data) == 1:
                    # Only Series List is Available
                    for key in device_data[0]['series']:
                        all_devices[key] = device_data[0]['series'][key]
                        processed_count += 1
                else:
                    # Both Device List and EOX are available
                    for key in device_data[0]['series']:
                        all_devices[key] = device_data[0]['series'][key]
                        processed_count += 1
                    
                    for key in device_data[1]['eox']:
                        eox_devices[key] = device_data[1]['eox'][key]
                        eox_count += 1
                        
                logging.debug(f"Processed technology: {technology}")
                
            except Exception as e:
                logging.error(f"Error processing technology {technology}: {str(e)}")
                continue
        
        logging.info(f"Device processing completed. Devices: {processed_count}, EOX Devices: {eox_count}")
        
    except Exception as e:
        logging.error(f"Error in process_devices: {str(e)}")
        raise

def scrape_eox_data():
    """Scrape EOX data from Cisco website"""
    global eox_devices, eox_data
    try:
        total_devices = len(eox_devices)
        logging.info(f"Starting EOX scraping process for {total_devices} devices")
        
        if total_devices == 0:
            logging.warning("No EOX devices to process")
            return
        
        processed_count = 0
        success_count = 0
        
        for device_name in eox_devices:
            try:
                logging.debug(f"Processing EOX for device: {device_name}")
                
                url = link_check(eox_devices[device_name])
                if not url:
                    logging.debug(f"No valid URL found for device: {device_name}")
                    processed_count += 1
                    continue
                
                eox_links = eox_check(url)
                if eox_links:
                    if not eox_links[0]:
                        eox_data[device_name] = eox_links[1]
                        success_count += 1
                        logging.debug(f"Direct EOX data retrieved for: {device_name}")
                    else:
                        try:
                            urls = eox_details(eox_links[1]['url'])
                            if urls:
                                for link_key in urls:
                                    try:
                                        eox_result = eox_scrapping(urls[link_key])
                                        if eox_result: 
                                            for dev in eox_result[1]:
                                                eox_data[dev] = eox_result[0]
                                                success_count += 1
                                            logging.debug(f"Scraped EOX data for: {link_key}")
                                    except Exception as scrape_error:
                                        logging.error(f"Error scraping {link_key}: {str(scrape_error)}")
                                        continue
                        except Exception as detail_error:
                            logging.error(f"Error getting EOX details for {device_name}: {str(detail_error)}")
                            continue
                
                processed_count += 1
                
                # Progress logging every 10 devices
                if processed_count % 10 == 0:
                    logging.info(f"Progress: {processed_count}/{total_devices} devices processed")
                    
            except Exception as e:
                logging.error(f"Error processing device {device_name}: {str(e)}")
                processed_count += 1
                continue
        
        logging.info(f"EOX scraping completed. Total data retrieved: {len(eox_data)} entries")
        logging.info(f"Summary: {processed_count} processed, {success_count} successful extractions")
        
    except Exception as e:
        logging.error(f"Critical error in scrape_eox_data: {str(e)}")
        raise

def generate_filename(base_filename):
    """Generate filename with current date appended"""
    try:
        current_date = datetime.datetime.now().strftime('%Y-%m-%d')
        
        if '.' in base_filename:
            base, ext = base_filename.rsplit('.', 1)
            filename_with_date = f"{base}_{current_date}.{ext}"
        else:
            filename_with_date = f"{base_filename}_{current_date}"
        
        logging.debug(f"Generated filename: {filename_with_date}")
        return filename_with_date
        
    except Exception as e:
        logging.error(f"Error generating filename: {str(e)}")
        return base_filename

def save_eox_data(base_filename='new_eox_pid.json'):
    """Save EOX data to JSON file in the 'JSON Files' directory"""
    global eox_data
    try:
        # Get the directory where the script is located
        script_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
        
        # Create path to 'JSON Files' directory
        json_files_dir = os.path.join(script_dir, "JSON_Files")
        
        # Create the directory if it doesn't exist
        if not os.path.exists(json_files_dir):
            os.makedirs(json_files_dir, exist_ok=True)
            logging.info(f"Created JSON Files directory: {json_files_dir}")
        
        # Generate filename with date
        filename_with_date = generate_filename(base_filename)
        
        # Create full output path
        output_path = os.path.join(json_files_dir, filename_with_date)
        
        logging.info(f"Output file will be: {output_path}")
        
        # Write JSON data to file
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(eox_data, f, ensure_ascii=False, indent=4)
        
        # Verify file creation and get size
        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            logging.info(f"EOX data written successfully to: {output_path}")
            logging.info(f"File size: {file_size} bytes")
            logging.info(f"Total EOX entries: {len(eox_data)}")
            return output_path, file_size
        else:
            raise FileNotFoundError("File was not created successfully")
            
    except Exception as e:
        logging.error(f"Error saving EOX data: {str(e)}")
        raise

def main(base_filename='new_eox_pid.json'):
    """
    Main function to execute the complete EOX data retrieval process
    
    Args:
        base_filename (str): Base filename for output (date will be appended)
    
    Returns:
        dict: Results of the operation
    """
    start_time = datetime.datetime.now()
    logging.info("Starting EOX Device List Retrieval Process")
    
    try:
        # Execute main process steps
        initialize_categories()
        load_categories()
        process_devices()
        scrape_eox_data()
        
        # Save data to file - FIXED: Remove second argument
        output_path, file_size = save_eox_data(base_filename)
        
        # Calculate execution time
        end_time = datetime.datetime.now()
        execution_time = end_time - start_time
        
        logging.info("EOX Device List Retrieval Process Completed Successfully")
        logging.info(f"Total execution time: {execution_time}")
        
        return {
            'success': True,
            'output_file': output_path,
            'total_entries': len(eox_data),
            'execution_time': str(execution_time),
            'file_size': file_size
        }
        
    except Exception as e:
        error_msg = f"Critical error in main process: {str(e)}"
        logging.error(error_msg)
        logging.exception("Full traceback:")
        
        return {
            'success': False,
            'error': error_msg,
            'output_file': None,
            'total_entries': len(eox_data) if 'eox_data' in globals() else 0
        }

if __name__ == "__main__":
    try:
        logging.info("=" * 50)
        logging.info("Starting Auto_Pop EOX Retrieval")
        logging.info("=" * 50)
        
        # FIXED: Remove output_dir parameter
        result = main(base_filename='new_eox_pid.json')
        
        if result['success']:
            print(f"Success! File created: {result['output_file']}")
            print(f"Total entries: {result['total_entries']}")
            print(f"Execution time: {result['execution_time']}")
        else:
            print(f"Failed: {result['error']}")
            
    except Exception as e:
        logging.critical(f"Application failed to start: {str(e)}")
        print(f"Application failed: {str(e)}")
