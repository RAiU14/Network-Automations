import sqlite3
from pathlib import Path
from api_service.core.config import settings

# Integration with root tools
import Alive_Checks

router = APIRouter(prefix="/devices", tags=["Devices"])

def get_db():
    conn = sqlite3.connect(settings.DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

@router.get("/")
async def get_devices():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, ip, is_active, mac_address FROM devices")
    devices = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return devices

@router.get("/{device_id}/ping")
async def ping_device(device_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT ip FROM devices WHERE id = ?", (device_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Device not found")
    
    if settings.MOCK_MODE:
         return {"device_id": device_id, "ip": row["ip"], "reachable": True}

    result = Alive_Checks.alive_check(row["ip"])
    return {"device_id": device_id, "ip": row["ip"], "reachable": "Passed" in result}
