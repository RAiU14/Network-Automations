# This is a branched version from Database.py

import json
import os
import logging

# Write data
def saver(data, filename):
    try:
        path = r"Mention Path Here"
        if os.path.exists(os.path.join(path, filename)):
            return False
        else:
            with open(os.path.join(path, filename), 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logging.error(f"Error writing to file {filename}: {e}")
        return None
