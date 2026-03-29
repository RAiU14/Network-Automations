from pathlib import Path
import sqlite3
import yaml

def init_db(db_path):
    # Ensure the parent directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''\
        CREATE TABLE IF NOT EXISTS devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            ip TEXT NOT NULL,
            snmp_community TEXT,
            snmp_version INTEGER,
            is_active BOOLEAN DEFAULT 1,
            mac_address TEXT,
            hardware_info TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''\
        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id INTEGER NOT NULL,
            metric_name TEXT NOT NULL,
            value TEXT,
            polled_at TIMESTAMP NOT NULL,
            FOREIGN KEY (device_id) REFERENCES devices(id)
        )
    ''')
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_device_time ON metrics(device_id, polled_at)")

    # Audit Logs for "Accounting" and traceability
    cursor.execute('''\
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def log_event(db_path, event_type, message):
    """Helper to log an event to the audit_logs table."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO audit_logs (event_type, message) VALUES (?, ?)", (event_type, message))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Failed to log event: {e}")

def load_config(config_path):
    with open(config_path) as f:
        return yaml.safe_load(f)