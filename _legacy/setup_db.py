import sqlite3
import random
from datetime import datetime, timezone
from pathlib import Path
import sys

# Move to root to import config
sys.path.append(str(Path(__file__).resolve().parent))
from config import settings

def init_db():
    db_path = settings.DB_FILE
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print(f"Initializing database at {db_path}...")
    
    # Devices Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            ip TEXT NOT NULL UNIQUE,
            snmp_community TEXT DEFAULT 'public',
            snmp_version INTEGER DEFAULT 2,
            is_active BOOLEAN DEFAULT 1,
            mac_address TEXT,
            hardware_info TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Metrics Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id INTEGER NOT NULL,
            metric_name TEXT NOT NULL,
            value TEXT,
            polled_at TIMESTAMP NOT NULL,
            FOREIGN KEY (device_id) REFERENCES devices(id)
        )
    ''')
    
    # Audit Logs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Seed data if empty
    cursor.execute("SELECT COUNT(*) FROM devices")
    if cursor.fetchone()[0] == 0:
        print("Seeding database with professional mock data...")
        mock_devices = [
            ("London-Core-R01", "10.0.0.1", "public", 2, "Cisco ISR 4451", "00:1A:2B:3C:4D:01"),
            ("London-Edge-S02", "10.0.0.2", "public", 2, "Cisco Catalyst 9300", "00:1A:2B:3C:4D:02"),
            ("Tokyo-Core-R01", "172.16.0.1", "secret", 2, "Cisco ISR 4331", "00:1A:2B:3C:4D:03"),
            ("NY-Distribution-S01", "192.168.10.1", "public", 2, "Nexus 9K", "00:1A:2B:3C:4D:04"),
            ("Berlin-WAP-03", "192.168.50.3", "secret", 2, "Cisco Aironet", "00:1A:2B:3C:4D:05")
        ]
        cursor.executemany(
            "INSERT INTO devices (name, ip, snmp_community, snmp_version, hardware_info, mac_address) VALUES (?,?,?,?,?,?)",
            mock_devices
        )
        
        # Seed mock metrics for last 24h
        print("Generating mock performance history...")
        from datetime import timedelta
        devices = [1, 2, 3, 4, 5]
        metrics = ['in_traffic', 'out_traffic', 'cpu_usage', 'memory_usage']
        now = datetime.now(timezone.utc)
        
        for dev_id in devices:
            for i in range(24):
                polled_at = (now - timedelta(hours=i)).isoformat()
                for m in metrics:
                    val = random.randint(10, 95) if 'usage' in m else random.randint(1000, 1000000)
                    cursor.execute("INSERT INTO metrics (device_id, metric_name, value, polled_at) VALUES (?,?,?,?)",
                                   (dev_id, m, str(val), polled_at))

        cursor.execute("INSERT INTO audit_logs (event_type, message) VALUES (?,?)", ("SYSTEM", "Professional mock environment initialized."))
        
    conn.commit()
    conn.close()
    print("Database initialization complete.")

if __name__ == "__main__":
    init_db()
