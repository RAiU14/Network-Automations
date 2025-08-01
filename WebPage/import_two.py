# import_two.py - Level 2 imports (Switching modules) - Not independently runnable
import os
import sys
import logging
import datetime

# Setup logging
log_dir = os.path.join(os.path.dirname(__file__), "import_two_logs")
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(log_dir, f"{datetime.datetime.today().strftime('%Y-%m-%d')}.log"),
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Path setup
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)

# Add Switching directory to Python path
switching_dir = os.path.join(parent_dir, 'PM_Report', 'Switching')
if switching_dir not in sys.path:
    sys.path.insert(0, switching_dir)
    logging.debug(f"Added to path: {switching_dir}")
else:
    logging.debug(f"Path already exists: {switching_dir}")

# Module tracking
imported_modules = {}

# Your actual modules from the Switching folder
modules_to_import = [
    'Cisco_IOS_XE',        # Cisco_IOS_XE.py
    'Data_to_Excel',       # Data_to_Excel.py
    'IOS_Stack_Switch',    # IOS_Stack_Switch.py  
    'IOS_XE_Stack_Switch', # IOS_XE_Stack_Switch.py
    'NX_OS'                # NX_OS.py
]

successful_imports = 0
failed_imports = 0

logging.info("=== Starting module imports for import_two ===")
logging.info(f"Target directory: {switching_dir}")
logging.info(f"Modules to import: {modules_to_import}")

for module_name in modules_to_import:
    try:
        logging.debug(f"Attempting to import {module_name}...")
        imported_module = __import__(module_name)
        imported_modules[module_name] = imported_module
        globals()[module_name] = imported_module
        logging.info(f"✅ {module_name} imported successfully")
        successful_imports += 1
        
        # Log module attributes for debugging
        if hasattr(imported_module, '__file__'):
            logging.debug(f"Module {module_name} loaded from: {getattr(imported_module, '__file__', 'Unknown')}")
        
        # Log key functions/classes available in the module
        module_attrs = [attr for attr in dir(imported_module) if not attr.startswith('_')]
        if module_attrs:
            logging.debug(f"Available attributes in {module_name}: {', '.join(module_attrs[:10])}{'...' if len(module_attrs) > 10 else ''}")
        
    except ImportError as e:
        error_msg = f"{module_name} import failed: {e}"
        logging.warning(f"⚠️ {error_msg}")
        failed_imports += 1
        
        # Additional debugging for ImportError
        logging.debug(f"Python path when importing {module_name}: {sys.path[:3]}...")  # Show first 3 paths
        module_file_path = os.path.join(switching_dir, f"{module_name}.py")
        if os.path.exists(module_file_path):
            logging.debug(f"Module file exists at: {module_file_path}")
        else:
            logging.warning(f"Module file not found at expected location: {module_file_path}")
            
    except Exception as e:
        error_msg = f"{module_name} unexpected error during import: {e}"
        logging.error(f" {error_msg}")
        logging.exception(f"Full traceback for {module_name} import error:")
        failed_imports += 1

# Export configuration
__all__ = list(imported_modules.keys())

# Summary logging
logging.info("=== Import Summary ===")
logging.info(f"📦 import_two.py loaded: {successful_imports} successful, {failed_imports} failed")
logging.info(f"📋 Successfully imported modules ({len(imported_modules)}): {', '.join(__all__)}")

if failed_imports > 0:
    logging.warning(f"⚠️ {failed_imports} modules failed to import - some functionality may be limited")
    logging.info("Check the debug logs above for detailed error information")
else:
    logging.info("🎉 All modules imported successfully!")

# Log system information for debugging
logging.debug(f"Python version: {sys.version}")
logging.debug(f"Current working directory: {os.getcwd()}")
logging.debug(f"Script location: {current_dir}")
logging.debug(f"Parent directory: {parent_dir}")
logging.debug(f"Switching directory exists: {os.path.exists(switching_dir)}")

# Validate critical modules
critical_modules = ['Cisco_IOS_XE', 'Data_to_Excel']
missing_critical = [module for module in critical_modules if module not in imported_modules]
if missing_critical:
    logging.critical(f"🚨 Critical modules missing: {missing_critical} - This may cause application failures")
else:
    logging.info("✅ All critical modules loaded successfully")

logging.info("=== import_two.py initialization complete ===")
