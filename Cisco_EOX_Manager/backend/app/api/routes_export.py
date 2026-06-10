from __future__ import annotations

from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.export_service import DATASETS, dataset_field_options, export_dataset

router = APIRouter(prefix="/export", tags=["Export"])


@router.get("/options/{dataset}")
def export_options(
    dataset: str,
    search: str | None = Query(default=None),
    limit: int = Query(default=5000, ge=1, le=100000),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    if dataset not in DATASETS:
        raise HTTPException(status_code=400, detail=f"Unsupported dataset. Use one of: {', '.join(sorted(DATASETS))}")
    try:
        fields = dataset_field_options(db, dataset, search=search, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "dataset": dataset,
        "fields": fields,
        "default_fields": [item["key"] for item in fields if item.get("default")],
        "supports_all_fields": True,
    }


@router.get("/{dataset}")
def export_table(
    dataset: str,
    format: str = Query(default="xlsx", pattern="^(csv|xlsx)$"),
    search: str | None = Query(default=None),
    limit: int = Query(default=10000, ge=1, le=100000),
    fields: list[str] | None = Query(default=None),
    include_all: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    if dataset not in DATASETS:
        raise HTTPException(status_code=400, detail=f"Unsupported dataset. Use one of: {', '.join(sorted(DATASETS))}")
    try:
        content, filename, media_type, row_count = export_dataset(
            db,
            dataset=dataset,
            format=format,
            search=search,
            limit=limit,
            fields=fields,
            include_all=include_all,
            requested_by="gui",
        )
    except ImportError as exc:
        raise HTTPException(status_code=500, detail="XLSX export requires openpyxl") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    headers = {"Content-Disposition": f'attachment; filename="{filename}"', "X-Row-Count": str(row_count)}
    return StreamingResponse(BytesIO(content), media_type=media_type, headers=headers)
