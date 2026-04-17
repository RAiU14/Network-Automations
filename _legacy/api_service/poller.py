import asyncio
import sqlite3
import random
import logging
from datetime import datetime, timezone
from pathlib import Path

# Fix imports for package support
import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))
from api_service.core.config import settings
from api_service.core.utils import log_event

try:

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def poll_snmp(ip, community, oid, mock_mode=False, **kwargs):
    if mock_mode:
        # Return fake data
        if '1.3.6.1.2.1.1.5.0' in oid:
            return f"Mock-Router-{ip.split('.')[-1]}"
        if '1.3.6.1.2.1.1.3.0' in oid:
            return str(random.randint(1000, 100000))
        if '1.3.6.1.2.1.2.2.1.10' in oid: # ifInOctets
             return str(random.randint(50000, 5000000))
        if '1.3.6.1.2.1.2.2.1.16' in oid: # ifOutOctets
             return str(random.randint(50000, 5000000))
        if '1.3.6.1.2.1.2.2.1.6.1' in oid:
             return f"00:1A:2B:3C:4D:{ip.split('.')[-1]}"
        return "fake_value"
    
    # Real SNMP polling
    try:
        errorIndication, errorStatus, errorIndex, varBinds = await getCmd(
            SnmpEngine(),
            CommunityData(community),
            UdpTransportTarget((ip, 161), timeout=5, retries=2),
            ContextData(),
            ObjectType(ObjectIdentity(oid))
        )
        if errorIndication or errorStatus:
            logger.warning(f"SNMP error for {ip} OID {oid}: {errorIndication or errorStatus}")
            return None
        return varBinds[0][1]
    except Exception as e:
        logger.error(f"Exception polling {ip}: {e}")
        return None

async def poll_device(device, semaphore, mock_mode, **kwargs):
    async with semaphore:
        dev_id = device['id']
        ip = device['ip']
        community = device['snmp_community']
        sysName = await poll_snmp(ip, community, '1.3.6.1.2.1.1.5.0', mock_mode)
        sysUpTime = await poll_snmp(ip, community, '1.3.6.1.2.1.1.3.0', mock_mode)
        in_traffic = await poll_snmp(ip, community, '1.3.6.1.2.1.2.2.1.10.1', mock_mode)
        out_traffic = await poll_snmp(ip, community, '1.3.6.1.2.1.2.2.1.16.1', mock_mode)
        
        mac = None
        if kwargs.get('full_inventory'):
             mac = await poll_snmp(ip, community, '1.3.6.1.2.1.2.2.1.6.1', mock_mode)
             
        return dev_id, sysName, sysUpTime, in_traffic, out_traffic, mac

async def force_poll_device(device_id, config_override=None):
    """Poll a single device immediately and update DB."""
    # Use global settings if no override provided
    mock_mode = settings.MOCK_MODE if config_override is None else config_override.get('mock_mode', settings.MOCK_MODE)
    db_path = settings.DB_FILE if config_override is None else config_override.get('database', {}).get('path', settings.DB_FILE)
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM devices WHERE id=?", (device_id,))
    device = cursor.fetchone()
    conn.close()
    
    if not device: return False
    
    semaphore = asyncio.Semaphore(1)
    res = await poll_device(dict(device), semaphore, mock_mode, full_inventory=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    dev_id, sysName, sysUpTime, in_traffic, out_traffic, mac = res
    
    if sysName: cursor.execute("INSERT INTO metrics (device_id, metric_name, value, polled_at) VALUES (?,?,?,?)", (dev_id, 'sysName', sysName, now))
    if sysUpTime: cursor.execute("INSERT INTO metrics (device_id, metric_name, value, polled_at) VALUES (?,?,?,?)", (dev_id, 'sysUpTime', sysUpTime, now))
    if in_traffic: cursor.execute("INSERT INTO metrics (device_id, metric_name, value, polled_at) VALUES (?,?,?,?)", (dev_id, 'in_traffic', in_traffic, now))
    if out_traffic: cursor.execute("INSERT INTO metrics (device_id, metric_name, value, polled_at) VALUES (?,?,?,?)", (dev_id, 'out_traffic', out_traffic, now))
    if mac: cursor.execute("UPDATE devices SET mac_address=? WHERE id=?", (mac, dev_id))
    
    log_event(db_path, "FORCE_POLL", f"Manual poll for {device['name']} ({device['ip']})")
    conn.commit()
    conn.close()
    return True

async def poll_all(**kwargs):
    mock_mode = settings.MOCK_MODE
    db_path = settings.DB_FILE
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, ip, snmp_community FROM devices WHERE is_active=1")
    devices = [{'id': row[0], 'ip': row[1], 'snmp_community': row[2]} for row in cursor.fetchall()]
    conn.close()

    if not devices:
        logger.info("No active devices found.")
        return

    semaphore = asyncio.Semaphore(10) # Default to 10
    tasks = [poll_device(dev, semaphore, mock_mode, **kwargs) for dev in devices]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    full_inv = kwargs.get('full_inventory', False)
    
    for res in results:
        if isinstance(res, Exception):
            logger.error(f"Task error: {res}")
            log_event(db_path, "ERROR", f"Polling task exception: {res}")
            continue
        
        dev_id, sysName, sysUpTime, in_traffic, out_traffic, mac = res
        
        if any(v is None for v in [sysName, sysUpTime]):
            log_event(db_path, "POLLING_FAIL", f"Device ID {dev_id} polling failed.")
            continue

        if sysName is not None:
            cursor.execute("INSERT INTO metrics (device_id, metric_name, value, polled_at) VALUES (?,?,?,?)",
                           (dev_id, 'sysName', sysName, now))
        if sysUpTime is not None:
            cursor.execute("INSERT INTO metrics (device_id, metric_name, value, polled_at) VALUES (?,?,?,?)",
                           (dev_id, 'sysUpTime', sysUpTime, now))
        if in_traffic is not None:
            cursor.execute("INSERT INTO metrics (device_id, metric_name, value, polled_at) VALUES (?,?,?,?)",
                           (dev_id, 'in_traffic', in_traffic, now))
        if out_traffic is not None:
            cursor.execute("INSERT INTO metrics (device_id, metric_name, value, polled_at) VALUES (?,?,?,?)",
                           (dev_id, 'out_traffic', out_traffic, now))
        if mac is not None:
             cursor.execute("UPDATE devices SET mac_address=? WHERE id=?", (mac, dev_id))
    
    cycle_type = "HEAVY" if full_inv else "LIGHT"
    log_event(db_path, "SYSTEM", f"{cycle_type} polling cycle completed.")
    conn.commit()
    conn.close()
    logger.info("Polling completed.")

if __name__ == '__main__':
    asyncio.run(poll_all())
