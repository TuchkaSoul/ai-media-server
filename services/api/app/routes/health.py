from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.dependencies import get_db

router = APIRouter(tags=["system"])


@router.get("/")
def root() -> dict[str, str]:
    return {
        "service": "api",
        "status": "ok",
        "message": "MediaHub unified capture pipeline",
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "healthy"}
