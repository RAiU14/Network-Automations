import os
import sqlite3
import django
from pathlib import Path

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core_service.settings')
django.setup()

from automation.models import Device

def migrate_devices():
    old_db = Path("db/nms.db")
    if not old_db.exists():
        print("No legacy database found at db/nms.db. Skipping device migration.")
        return

    print("Migrating devices from legacy database...")
    conn = sqlite3.connect(old_db)
    cursor = conn.cursor()
    cursor.execute("SELECT name, ip, snmp_community, is_active, mac_address FROM devices")
    
    count = 0
    for row in cursor.fetchall():
        name, ip, community, active, mac = row
        obj, created = Device.objects.get_or_create(
            ip=ip,
            defaults={
                'name': name,
                'snmp_community': community,
                'is_active': bool(active),
                'mac_address': mac
            }
        )
        if created:
            count += 1
            print(f"Imported: {name} ({ip})")
        else:
            print(f"Skipped (exists): {ip}")
    
    conn.close()
    print(f"Migration complete. {count} new devices imported.")

if __name__ == "__main__":
    migrate_devices()
