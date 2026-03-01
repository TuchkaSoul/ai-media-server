from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from db.database import Base, engine, get_db
from db.models import Camera, Video


app = FastAPI(title="VKR API (ORM)", version="0.1.0")


class CameraCreate(BaseModel):
    name: str
    stream_url: str
    location: Optional[str] = None
    owner: Optional[str] = None
    resolution: str = "720p"
    fps: int = 15
    is_active: bool = True


class CameraRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    stream_url: str
    location: Optional[str]
    owner: Optional[str]
    resolution: Optional[str]
    fps: Optional[int]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class VideoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    camera_id: UUID
    start_time: datetime
    end_time: datetime
    file_path: str
    status: str


@app.on_event("startup")
def startup() -> None:
    # Для MVP: создаем таблицы из ORM. Для прод-среды используйте Alembic.
    Base.metadata.create_all(bind=engine)


@app.get("/health/db")
def health_db(db: Session = Depends(get_db)) -> dict:
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.post("/cameras", response_model=CameraRead, status_code=status.HTTP_201_CREATED)
def create_camera(payload: CameraCreate, db: Session = Depends(get_db)) -> Camera:
    camera = Camera(**payload.model_dump())
    db.add(camera)
    db.commit()
    db.refresh(camera)
    return camera


@app.get("/cameras", response_model=List[CameraRead])
def list_cameras(
    active_only: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> List[Camera]:
    stmt = select(Camera).order_by(Camera.created_at.desc())
    if active_only:
        stmt = stmt.where(Camera.is_active.is_(True))
    return list(db.scalars(stmt).all())


@app.get("/videos/{video_id}", response_model=VideoRead)
def get_video(video_id: UUID, db: Session = Depends(get_db)) -> Video:
    video = db.scalar(select(Video).where(Video.id == video_id))
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return video

