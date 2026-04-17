import asyncio
from api_service.core.config import settings

# Integration with root tools
import Alive_Checks
import Log_Capture

router = APIRouter(prefix="/tools", tags=["Automation Tools"])

@router.post("/log-capture")
async def run_log_capture(ip: str, commands: list[str] = Body(...)):
    """Triggers the Log_Capture utility for a specific IP."""
    if settings.MOCK_MODE:
        return {"status": "mock_success", "message": f"Collected logs for {ip} (Mocked)"}
    
    try:
        # Wrapping sync tool in executor
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, Log_Capture.exec_command, ip, commands)
        return {"status": "success", "message": f"Log collection initiated for {ip}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/ping/{ip}")
async def ping_tool(ip: str):
    if settings.MOCK_MODE:
        return {"ip": ip, "reachable": True}
    
    result = Alive_Checks.alive_check(ip)
    return {"ip": ip, "reachable": "Passed" in result, "raw": result}
