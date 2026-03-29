from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import sqlite3
import yaml
import asyncio
from datetime import datetime, timezone
from poller import force_poll_device

# Load config
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)
DB_PATH = config['database']['path']

app = FastAPI(title="EN-NMS API", version="1.0")

# Allow React dev server to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite default
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/api/devices")
async def get_devices():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, ip, is_active, mac_address FROM devices")
    devices = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return devices

@app.post("/api/devices/{device_id}/poll")
async def manual_poll(device_id: int):
    success = await force_poll_device(device_id, config)
    if not success:
        raise HTTPException(status_code=404, detail="Device not found")
    return {"status": "success", "message": "Manual poll triggered"}

@app.get("/api/analytics")
async def get_analytics():
    conn = get_db()
    cursor = conn.cursor()
    
    # 1. Bandwidth Peaks (Top 5)
    cursor.execute("""
        SELECT d.name, MAX(CAST(m.value AS FLOAT)) as peak
        FROM metrics m
        JOIN devices d ON m.device_id = d.id
        WHERE m.metric_name IN ('in_traffic', 'out_traffic')
        GROUP BY d.name
        ORDER BY peak DESC LIMIT 5
    """)
    peaks = [dict(row) for row in cursor.fetchall()]
    
    # 2. Uptime Summary
    cursor.execute("SELECT COUNT(*) FROM devices WHERE is_active=1")
    up = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM devices")
    total = cursor.fetchone()[0]
    
    # 3. Last 10 Audit Logs for Analytics context
    cursor.execute("SELECT event_type, message, timestamp FROM audit_logs ORDER BY timestamp DESC LIMIT 10")
    recent_logs = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return {
        "bandwidth_peaks": peaks,
        "uptime_stats": {"up": up, "total": total, "percentage": (up/total*100) if total > 0 else 0},
        "recent_activity": recent_logs
    }

@app.get("/api/dashboard/stats")
async def get_dashboard_stats():
    conn = get_db()
    cursor = conn.cursor()
    # Total devices
    cursor.execute("SELECT COUNT(*) FROM devices")
    total_devices = cursor.fetchone()[0]
    # Active devices
    cursor.execute("SELECT COUNT(*) FROM devices WHERE is_active=1")
    active_devices = cursor.fetchone()[0]
    # Total poll events (last 24h)
    cursor.execute("SELECT COUNT(*) FROM metrics WHERE polled_at > datetime('now', '-1 day')")
    total_metrics_24h = cursor.fetchone()[0]
    conn.close()
    return {
        "total_devices": total_devices,
        "active_devices": active_devices,
        "total_metrics_24h": total_metrics_24h,
        "health_score": 98.5 # Mock health score
    }

@app.get("/api/logs")
async def get_logs(limit: int = 50):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, event_type, message, timestamp FROM audit_logs ORDER BY timestamp DESC LIMIT ?", (limit,))
    logs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return logs

@app.get("/api/devices/{device_id}/metrics")
async def get_metrics(device_id: int, limit: int = 100):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT metric_name, value, polled_at
        FROM metrics
        WHERE device_id = ?
        ORDER BY polled_at DESC
        LIMIT ?
    """, (device_id, limit))
    rows = cursor.fetchall()
    conn.close()
    # Group by metric_name for easier frontend consumption
    result = {"timestamps": [], "sysName": [], "sysUpTime": []}
    for row in rows:
        result["timestamps"].append(row["polled_at"])
        if row["metric_name"] == "sysName":
            result["sysName"].append(row["value"])
        elif row["metric_name"] == "sysUpTime":
            result["sysUpTime"].append(row["value"])
    return result

@app.get("/api/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}

# Optional: serve built React files later (for production)
# app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)