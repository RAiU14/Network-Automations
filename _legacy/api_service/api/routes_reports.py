from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from pathlib import Path
from typing import List
from api_service.services.report_pipeline import ReportPipelineService

router = APIRouter(prefix="/reports", tags=["Reporting Pipeline"])

def get_service() -> ReportPipelineService:
    return ReportPipelineService()

@router.post("/upload")
async def upload_logs(
    ticket: str = Form(...),
    technology: str = Form(...),
    file: UploadFile = File(...),
    svc: ReportPipelineService = Depends(get_service)
):
    """Upload a ZIP of logs and start background processing"""
    if not ticket.startswith("SVR"):
        raise HTTPException(status_code=400, detail="Ticket must start with SVR")
    
    # Save the file temporarily
    target_dir = Path(svc.upload_dir) / ticket
    target_dir.mkdir(exist_ok=True)
    file_path = target_dir / f"{ticket}.zip"
    
    with open(file_path, "wb") as buffer:
        shutil_content = await file.read()
        buffer.write(shutil_content)
    
    # Trigger non-blocking pipeline
    await svc.process_upload(ticket, technology, file_path)
    
    return {"status": "success", "message": f"Pipeline started for {ticket}"}

@router.get("/status/{ticket}")
async def check_status(ticket: str, svc: ReportPipelineService = Depends(get_service)):
    return svc.get_status(ticket)

@router.get("/technologies")
async def get_technologies():
    return ["Wireless", "Switches", "Security", "Others"]
