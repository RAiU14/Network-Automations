# Setup logging
import os
import datetime
import logging

log_dir = os.path.join(os.path.dirname(__file__), "auto_pop_logs")
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(log_dir, f"{datetime.datetime.today().strftime('%Y-%m-%d')}.log"),
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Auto Populate Program to Create a JSON Database
from json_fun import *

# auto_pop.py
import sys
import json

# Add the parent directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)  # Go up one level to Network-Automations
sys.path.insert(0, parent_dir)

from EOX.Cisco_EOX_Scrapper import *

class Auto_Pop:
    def __init__(self):
        self.all_available_devices = {}
        self.all_devices = {}
        self.eox_devices = {}
        self.eox_links = {}
        self.eox_data = {}
        self.categories = {}
        
        try:
            self.categories = category()
            logging.info(" Auto_Pop initialized successfully")
        except Exception as e:
            logging.error(f" Failed to initialize Auto_Pop: {str(e)}")
            raise
        
    def load_categories(self):
        """Load categories with error handling"""
        try:
            logging.info(" Loading categories...")
            for link in self.categories.keys():
                try:
                    self.all_available_devices[link] = open_cat(self.categories[link])
                    logging.debug(f" Loaded category: {link}")
                except Exception as e:
                    logging.error(f" Failed to load category {link}: {str(e)}")
                    continue
            
            logging.info(f" Categories loaded successfully. Total: {len(self.all_available_devices)}")
            
        except Exception as e:
            logging.error(f" Error in load_categories: {str(e)}")
            raise
        
    def process_devices(self):
        """Process devices with error handling"""
        try:
            logging.info(" Processing devices...")
            processed_count = 0
            eox_count = 0
            
            for technology in self.all_available_devices:
                try:
                    if len(self.all_available_devices[technology]) == 1:
                        # Only Series List is Available
                        for key in self.all_available_devices[technology][0]['series']:
                            self.all_devices[key] = self.all_available_devices[technology][0]['series'][key]
                            processed_count += 1
                    else:
                        # Both Device List and EOX are available
                        for key in self.all_available_devices[technology][0]['series']:
                            self.all_devices[key] = self.all_available_devices[technology][0]['series'][key]
                            processed_count += 1
                        
                        for key in self.all_available_devices[technology][1]['eox']:
                            self.eox_devices[key] = self.all_available_devices[technology][1]['eox'][key]
                            eox_count += 1
                            
                    logging.debug(f" Processed technology: {technology}")
                    
                except Exception as e:
                    logging.error(f" Error processing technology {technology}: {str(e)}")
                    continue
            
            logging.info(f" Device processing completed. Devices: {processed_count}, EOX Devices: {eox_count}")
            
        except Exception as e:
            logging.error(f" Error in process_devices: {str(e)}")
            raise
        
    def scrap_eox_data(self):
        """Scrape EOX data with comprehensive error handling"""
        try:
            total_devices = len(self.eox_devices)
            logging.info(f" Starting EOX Scrapping Process for {total_devices} devices")
            
            if total_devices == 0:
                logging.warning(" No EOX devices to process")
                return
            
            processed_count = 0
            success_count = 0
            
            for device_name in self.eox_devices:
                try:
                    logging.debug(f"Processing EOX for device: {device_name}")
                    
                    url = link_check(self.eox_devices[device_name])
                    if not url:
                        logging.debug(f" No valid URL found for device: {device_name}")
                        processed_count += 1
                        continue
                    
                    eox_links = eox_check(url)
                    if eox_links:
                        if not eox_links[0]:
                            self.eox_data[device_name] = eox_links[1]
                            success_count += 1
                            logging.debug(f" Direct EOX data retrieved for: {device_name}")
                        else:
                            try:
                                urls = eox_details(eox_links[1]['url'])
                                if urls:
                                    for link_key in urls:
                                        try:
                                            eox = eox_scrapping(urls[link_key])
                                            if eox: 
                                                for dev in eox[1]:
                                                    self.eox_data[dev] = eox[0]
                                                    success_count += 1
                                                logging.debug(f" Scraped EOX data for: {link_key}")
                                        except Exception as scrape_error:
                                            logging.error(f" Error scraping {link_key}: {str(scrape_error)}")
                                            continue
                            except Exception as detail_error:
                                logging.error(f" Error getting EOX details for {device_name}: {str(detail_error)}")
                                continue
                    
                    processed_count += 1
                    
                    # Progress logging every 10 devices
                    if processed_count % 10 == 0:
                        logging.info(f"📊 Progress: {processed_count}/{total_devices} devices processed")
                        
                except Exception as e:
                    logging.error(f" Error processing device {device_name}: {str(e)}")
                    processed_count += 1
                    continue
            
            logging.info(f" EOX scraping completed. Total data retrieved: {len(self.eox_data)} entries")
            logging.info(f"📊 Summary: {processed_count} processed, {success_count} successful extractions")
            
        except Exception as e:
            logging.error(f" Critical error in scrap_eox_data: {str(e)}")
            raise

    def _generate_filename(self, base_filename):
        """Generate filename with current date"""
        try:
            # Get current date string
            current_date = datetime.datetime.now().strftime('%Y-%m-%d')
            
            # Split filename and extension
            if '.' in base_filename:
                base, ext = base_filename.rsplit('.', 1)
                filename_with_date = f"{base}_{current_date}.{ext}"
            else:
                filename_with_date = f"{base_filename}_{current_date}"
            
            logging.debug(f"Generated filename: {filename_with_date}")
            return filename_with_date
            
        except Exception as e:
            logging.error(f" Error generating filename: {str(e)}")
            # Fallback to original filename
            return base_filename

    def obtain(self, base_filename='new_eox_pid.json', output_dir=None):
        """
        Main method to obtain EOX data and save to file
        
        Args:
            base_filename (str): Base filename (date will be automatically appended)
            output_dir (str): Optional output directory (defaults to current directory)
        """
        start_time = datetime.datetime.now()
        logging.info(" Starting the EOX Device List Retrieval Process")
        
        try:
            # Generate filename with date
            filename_with_date = self._generate_filename(base_filename)
            
            # Set output path
            if output_dir:
                if not os.path.exists(output_dir):
                    os.makedirs(output_dir, exist_ok=True)
                    logging.info(f"📁 Created output directory: {output_dir}")
                output_path = os.path.join(output_dir, filename_with_date)
            else:
                output_path = filename_with_date
            
            logging.info(f"📄 Output file will be: {output_path}")
            
            # Execute main process steps
            self.load_categories()
            self.process_devices()
            self.scrap_eox_data()
            
            # Write data to file with error handling
            try:
                logging.info("💾 Writing EOX Data to JSON file...")
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(self.eox_data, f, ensure_ascii=False, indent=4)
                
                # Verify file was created and get size
                if os.path.exists(output_path):
                    file_size = os.path.getsize(output_path)
                    logging.info(f" EOX Data written successfully to: {output_path}")
                    logging.info(f"📊 File size: {file_size} bytes")
                    logging.info(f"📈 Total EOX entries: {len(self.eox_data)}")
                else:
                    raise FileNotFoundError("File was not created successfully")
                    
            except PermissionError as e:
                logging.error(f" Permission denied writing to {output_path}: {str(e)}")
                raise
            except OSError as e:
                logging.error(f" OS error writing to {output_path}: {str(e)}")
                raise
            except Exception as e:
                logging.error(f" Unexpected error writing file: {str(e)}")
                raise
            
            # Calculate execution time
            end_time = datetime.datetime.now()
            execution_time = end_time - start_time
            
            logging.info("🎉 EOX Device List Retrieval Process Completed Successfully")
            logging.info(f"⏱️ Total execution time: {execution_time}")
            
            return {
                'success': True,
                'output_file': output_path,
                'total_entries': len(self.eox_data),
                'execution_time': str(execution_time),
                'file_size': file_size
            }
            
        except Exception as e:
            error_msg = f"Critical error in obtain method: {str(e)}"
            logging.error(f" {error_msg}")
            logging.exception("Full traceback:")
            
            return {
                'success': False,
                'error': error_msg,
                'output_file': None,
                'total_entries': len(self.eox_data) if hasattr(self, 'eox_data') else 0
            }


# Example usage
if __name__ == "__main__":
    try:
        logging.info("=" * 50)
        logging.info(" Starting Auto_Pop EOX Retrieval")
        logging.info("=" * 50)
        print(os.getcwd())
        auto_pop = Auto_Pop()
        
        # You can specify a custom base filename and output directory
        result = auto_pop.obtain(
            base_filename='new_eox_pid.json',  # Will become new_eox_pid_2025-08-02.json
            output_dir='output'  # Optional: specify output directory
        )
        
        if result['success']:
            print(f" Success! File created: {result['output_file']}")
            print(f"📊 Total entries: {result['total_entries']}")
            print(f"⏱️ Execution time: {result['execution_time']}")
        else:
            print(f" Failed: {result['error']}")
            
    except Exception as e:
        logging.critical(f" Application failed to start: {str(e)}")
        print(f" Application failed: {str(e)}")
