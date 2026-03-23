from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_media_query_service
from app.schemas import DetectionRead, EventRead, FrameMetadataRead, SegmentRead
from app.services.media_service import MediaQueryService

router = APIRouter(tags=["media"])

MediaServiceDep = Annotated[MediaQueryService, Depends(get_media_query_service)]


@router.get(
    "/segments",
    response_model=list[SegmentRead],
    summary="List segments",
    description="Returns persisted video segments, optionally filtered by camera.",
)
def list_segments(
    service: MediaServiceDep,
    camera_id: int | None = None,
    limit: int = 100,
) -> list[SegmentRead]:
    return service.list_segments(camera_id=camera_id, limit=limit)


@router.get(
    "/segments/{segment_id}",
    response_model=SegmentRead,
    summary="Get segment",
    description="Returns one persisted segment by identifier.",
)
def get_segment(segment_id: int, service: MediaServiceDep) -> SegmentRead:
    segment = service.get_segment(segment_id)
    if segment is None:
        raise HTTPException(status_code=404, detail="Segment not found")
    return segment


@router.get(
    "/frames",
    response_model=list[FrameMetadataRead],
    summary="List frames",
    description="Returns persisted frame metadata, optionally filtered by camera or segment.",
)
def list_frames(
    service: MediaServiceDep,
    camera_id: int | None = None,
    segment_id: int | None = None,
    limit: int = 100,
) -> list[FrameMetadataRead]:
    return service.list_frames(camera_id=camera_id, segment_id=segment_id, limit=limit)


@router.get(
    "/frames/{frame_id}",
    response_model=FrameMetadataRead,
    summary="Get frame metadata",
    description="Returns one persisted frame metadata record by identifier.",
)
def get_frame(frame_id: int, service: MediaServiceDep) -> FrameMetadataRead:
    frame = service.get_frame(frame_id)
    if frame is None:
        raise HTTPException(status_code=404, detail="Frame metadata not found")
    return frame


@router.get(
    "/detections",
    response_model=list[DetectionRead],
    summary="List detections",
    description="Returns persisted detections, optionally filtered by frame or camera.",
)
def list_detections(
    service: MediaServiceDep,
    frame_id: int | None = None,
    camera_id: int | None = None,
    limit: int = 100,
) -> list[DetectionRead]:
    return service.list_detections(frame_id=frame_id, camera_id=camera_id, limit=limit)


@router.get(
    "/events",
    response_model=list[EventRead],
    summary="List events",
    description="Returns persisted domain events, optionally filtered by camera or segment.",
)
def list_events(
    service: MediaServiceDep,
    camera_id: int | None = None,
    segment_id: int | None = None,
    limit: int = 100,
) -> list[EventRead]:
    return service.list_events(camera_id=camera_id, segment_id=segment_id, limit=limit)
