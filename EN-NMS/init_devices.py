import sqlite3
import yaml

# Load config
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

db_path = config['database']['path']
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Insert device from config.yaml (if not already present)
devices = config.get('devices', [])
for dev in devices:
    cursor.execute('''
        INSERT OR IGNORE INTO devices (name, ip, snmp_community, snmp_version, is_active)
        VALUES (?, ?, ?, ?, ?)
    ''', (dev['name'], dev['ip'], dev['snmp_community'], dev['snmp_version'], dev.get('is_active', True)))

conn.commit()
conn.close()
print("Devices inserted successfully.")