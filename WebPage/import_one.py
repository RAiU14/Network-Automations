# import_one.py - Level 1 imports (Database + EOX modules) - Not independently runnable
import os
import sys
import logging
import datetime

# Setup logging
log_dir = os.path.join(os.path.dirname(__file__), "import_one_log")
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(log_dir, f"{datetime.datetime.today().strftime('%Y-%m-%d')}.log"),
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
# Path setup
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
database_dir = os.path.join(parent_dir, 'Database')
eox_dir = os.path.join(parent_dir, 'EOX')

sys.path.insert(0, database_dir)
sys.path.insert(0, eox_dir)

# Module tracking
imported_modules = {}

# Import modules with detailed error tracking
modules_to_import = {
    'Integration': 'Database module',
    'json_fun': 'Database module', 
    'EOX_Integrate': 'Database module',
    'Online_scrapping': 'Database module',
    'Cisco_EOX_Scrapper': 'EOX module',
    'Cisco_PID_Retriever': 'EOX module',
    'Cisco_EOX': 'EOX module'  # Critical module
}

for module_name, description in modules_to_import.items():
    try:
        imported_module = __import__(module_name)
        imported_modules[module_name] = imported_module
        globals()[module_name] = imported_module
        logging.info(f"✅ {module_name} imported successfully ({description})")
    except ImportError as e:
        logging.warning(f"⚠️ {module_name} import failed ({description}): {e}")
    except Exception as e:
        logging.error(f"⚠️ {module_name} unexpected error ({description}): {e}")

# Check critical modules
if 'Cisco_EOX' not in imported_modules:
    logging.error(" CRITICAL: Cisco_EOX module failed to import - EOX functionality will be disabled")

# Export configuration
__all__ = list(imported_modules.keys())

# Summary logging
logging.info(f"📦 import_one.py loaded: {len(imported_modules)} modules available")
logging.info(f"📋 Available modules: {', '.join(__all__)}")
