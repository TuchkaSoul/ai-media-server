from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.dependencies import get_camera_service
from app.schemas import CameraCreate, CameraRead, CameraRuntimeStatus, CameraUpdate, FrameAnalysisIngest, FrameMetadataRead
from app.services.camera_service import CameraService

router = APIRouter(tags=["cameras"])

CameraServiceDep = Annotated[CameraService, Depends(get_camera_service)]


@router.post("/cameras", response_model=CameraRead, status_code=status.HTTP_201_CREATED)
def create_camera(payload: CameraCreate, service: CameraServiceDep) -> CameraRead:
    return service.create_camera(payload)


@router.get("/cameras", response_model=list[CameraRead])
def list_cameras(
    service: CameraServiceDep,
    active_only: bool = Query(default=False),
) -> list[CameraRead]:
    return service.list_cameras(active_only=active_only)


@router.get("/cameras/{camera_id}", response_model=CameraRead)
def get_camera(camera_id: int, service: CameraServiceDep) -> CameraRead:
    camera = service.get_camera(camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    return camera


@router.patch("/cameras/{camera_id}", response_model=CameraRead)
def update_camera(camera_id: int, payload: CameraUpdate, service: CameraServiceDep) -> CameraRead:
    try:
        return service.update_camera(camera_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/cameras/{camera_id}/start", response_model=CameraRuntimeStatus)
def start_camera(camera_id: int, service: CameraServiceDep) -> CameraRuntimeStatus:
    try:
        return service.start_camera(camera_id)
    except ValueError as exc:
        detail = str(exc)
        raise HTTPException(status_code=404 if "not found" in detail else 400, detail=detail) from exc


@router.post("/cameras/{camera_id}/stop", response_model=CameraRuntimeStatus)
def stop_camera(camera_id: int, service: CameraServiceDep) -> CameraRuntimeStatus:
    try:
        return service.stop_camera(camera_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/cameras/{camera_id}/runtime", response_model=CameraRuntimeStatus)
def camera_runtime(camera_id: int, service: CameraServiceDep) -> CameraRuntimeStatus:
    status_payload = service.get_runtime_status(camera_id)
    if status_payload is None:
        raise HTTPException(status_code=404, detail="Runtime state not found")
    return status_payload


@router.get("/runtime/cameras", response_model=list[CameraRuntimeStatus])
def all_runtime_statuses(service: CameraServiceDep) -> list[CameraRuntimeStatus]:
    return service.list_runtime_statuses()


@router.get("/cameras/{camera_id}/snapshot")
def camera_snapshot(camera_id: int, service: CameraServiceDep, quality: int = 85) -> Response:
    try:
        content = service.get_snapshot_bytes(camera_id, quality=quality)
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if "not found" in detail or "not available" in detail else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return Response(content=content, media_type="image/jpeg")


@router.post("/frames/{frame_id}/analysis", response_model=FrameMetadataRead)
def ingest_frame_analysis(frame_id: int, payload: FrameAnalysisIngest, service: CameraServiceDep) -> FrameMetadataRead:
    try:
        return service.ingest_frame_analysis(frame_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
