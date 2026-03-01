import asyncio
import ipaddress
import json
import logging
import os
import socket
from datetime import datetime
from typing import Any, Dict, List, Optional

import cv2
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from .video_source_manager import (
    FrameData,
    MultiSourceManager,
    VideoSourceConfig,
    VideoSourceFactory,
    VideoSourceType,
)

logger = logging.getLogger(__name__)


class SourceConfigModel(BaseModel):
    source_type: str = Field(..., description="Тип источника (usb_camera, ip_camera_rtsp, ...)")
    source_uri: str = Field(..., description="URI источника")
    source_id: str = Field(..., description="Уникальный ID источника")
    camera_id: Optional[int] = None
    rtsp_username: Optional[str] = None
    rtsp_password: Optional[str] = None
    rtsp_channel: int = 0
    frame_width: int = 1280
    frame_height: int = 720
    fps: int = 25
    buffer_size: int = 100
    reconnect_attempts: int = 3
    reconnect_delay: float = 2.0
    timeout_sec: float = 10.0
    use_gpu: bool = False
    codec: str = "h264"
    additional_params: Dict[str, Any] = Field(default_factory=dict)


class IntegrationStats(BaseModel):
    enabled: bool
    backend: str
    queue_name: str
    pushed_messages: int
    last_error: Optional[str]


class RedisMetadataBridge:
    """Легкий bridge в сторону будущего analysis-worker через Redis список."""

    def __init__(self) -> None:
        self.enabled = os.getenv("VIDEO_STREAM_PUSH_METADATA", "false").lower() == "true"
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.queue_name = os.getenv("VIDEO_STREAM_METADATA_QUEUE", "video:frames:metadata")
        self.pushed_messages = 0
        self.last_error: Optional[str] = None
        self._client = None
        self._backend = "disabled"

        if self.enabled:
            try:
                import redis

                self._client = redis.Redis.from_url(self.redis_url, decode_responses=True)
                self._backend = "redis"
            except Exception as exc:
                self.last_error = str(exc)
                self.enabled = False
                self._backend = "disabled"
                logger.exception("Redis bridge init error: %s", exc)

    def handle_frame(self, frame_data: FrameData) -> None:
        if not self.enabled or not self._client:
            return

        payload = {
            "source_id": frame_data.source_id,
            "frame_number": frame_data.frame_number,
            "timestamp": frame_data.timestamp,
            "metadata": frame_data.metadata,
        }
        try:
            self._client.lpush(self.queue_name, json.dumps(payload, ensure_ascii=False))
            self.pushed_messages += 1
        except Exception as exc:
            self.last_error = str(exc)
            logger.exception("Redis bridge push error: %s", exc)

    def stats(self) -> IntegrationStats:
        return IntegrationStats(
            enabled=self.enabled,
            backend=self._backend,
            queue_name=self.queue_name,
            pushed_messages=self.pushed_messages,
            last_error=self.last_error,
        )


app = FastAPI(title="Video Capture API", version="1.1.0")
source_manager = MultiSourceManager()
metadata_bridge = RedisMetadataBridge()


@app.on_event("startup")
async def startup_event() -> None:
    source_manager.register_frame_handler(metadata_bridge.handle_frame)

    auto_discover = os.getenv("VIDEO_STREAM_AUTO_DISCOVER_USB", "true").lower() == "true"
    if not auto_discover:
        logger.info("USB auto-discovery disabled")
        return

    usb_cameras = source_manager.auto_discover_usb_cameras()
    for cam_info in usb_cameras:
        source_manager.add_source(
            VideoSourceConfig(
                source_type=VideoSourceType.USB_CAMERA,
                source_uri="",
                source_id=cam_info["source_id"],
                camera_id=cam_info["camera_index"],
                frame_width=640,
                frame_height=480,
                fps=15,
            )
        )

    source_manager.start_all()
    logger.info("USB cameras discovered: %s", len(usb_cameras))


@app.on_event("shutdown")
async def shutdown_event() -> None:
    source_manager.stop_all()


@app.get("/")
async def root() -> Dict[str, str]:
    return {"message": "Video Capture API", "version": "1.1.0"}


@app.post("/api/sources/add")
async def add_source(config: SourceConfigModel) -> JSONResponse:
    try:
        source_type = VideoSourceType(config.source_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Неверный тип источника: {exc}") from exc

    video_config = VideoSourceConfig(
        source_type=source_type,
        source_uri=config.source_uri,
        source_id=config.source_id,
        camera_id=config.camera_id,
        rtsp_username=config.rtsp_username,
        rtsp_password=config.rtsp_password,
        rtsp_channel=config.rtsp_channel,
        frame_width=config.frame_width,
        frame_height=config.frame_height,
        fps=config.fps,
        buffer_size=config.buffer_size,
        reconnect_attempts=config.reconnect_attempts,
        reconnect_delay=config.reconnect_delay,
        timeout_sec=config.timeout_sec,
        use_gpu=config.use_gpu,
        codec=config.codec,
        additional_params=config.additional_params,
    )

    if not source_manager.add_source(video_config):
        raise HTTPException(status_code=400, detail="Не удалось добавить источник")

    return JSONResponse(
        {"status": "success", "message": f"Источник {config.source_id} добавлен", "source_id": config.source_id}
    )


@app.delete("/api/sources/{source_id}")
async def remove_source(source_id: str) -> JSONResponse:
    source_manager.remove_source(source_id)
    return JSONResponse({"status": "success", "message": f"Источник {source_id} удален"})


@app.get("/api/sources")
async def list_sources() -> JSONResponse:
    sources_info = source_manager.get_all_source_info()
    return JSONResponse({"status": "success", "sources": sources_info, "count": len(sources_info)})


@app.get("/api/sources/{source_id}/status")
async def get_source_status(source_id: str) -> JSONResponse:
    info = source_manager.get_source_info(source_id)
    if not info:
        raise HTTPException(status_code=404, detail="Источник не найден")
    return JSONResponse(info)


@app.post("/api/sources/{source_id}/start")
async def start_source(source_id: str) -> JSONResponse:
    if not source_manager.start_source(source_id):
        raise HTTPException(status_code=404, detail="Источник не найден")
    return JSONResponse({"status": "success", "message": f"Источник {source_id} запущен"})


@app.post("/api/sources/{source_id}/restart")
async def restart_source(source_id: str) -> JSONResponse:
    info = source_manager.get_source_info(source_id)
    if not info:
        raise HTTPException(status_code=404, detail="Источник не найден")

    config_dict = info["config"]
    config = VideoSourceFactory.config_from_dict(config_dict)
    if config is None:
        raise HTTPException(status_code=400, detail="Некорректная конфигурация источника")

    source_manager.remove_source(source_id)
    if not source_manager.add_source(config):
        raise HTTPException(status_code=500, detail="Ошибка перезапуска источника")

    if source_manager.running:
        source_manager.start_source(source_id)

    return JSONResponse({"status": "success", "message": f"Источник {source_id} перезапущен"})


@app.get("/api/sources/{source_id}/frame")
async def get_source_frame(source_id: str, format: str = "jpeg", quality: int = 85) -> StreamingResponse:
    frame_data = source_manager.get_frame(source_id, timeout=2.0)
    if not frame_data:
        raise HTTPException(status_code=404, detail="Кадр не доступен")

    frame = frame_data.frame
    fmt = format.lower()

    if fmt == "jpeg":
        success, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        media_type = "image/jpeg"
        if not success:
            raise HTTPException(status_code=500, detail="Ошибка кодирования изображения")
        data = encoded.tobytes()
    elif fmt == "png":
        success, encoded = cv2.imencode(".png", frame)
        media_type = "image/png"
        if not success:
            raise HTTPException(status_code=500, detail="Ошибка кодирования изображения")
        data = encoded.tobytes()
    elif fmt == "raw":
        media_type = "application/octet-stream"
        data = frame.tobytes()
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Поддерживаются только jpeg, png, raw")

    return StreamingResponse(
        iter([data]),
        media_type=media_type,
        headers={
            "Frame-Number": str(frame_data.frame_number),
            "Timestamp": str(frame_data.timestamp),
            "Source-ID": source_id,
        },
    )


@app.websocket("/ws/sources/{source_id}/stream")
async def websocket_stream(websocket: WebSocket, source_id: str) -> None:
    if not source_manager.has_source(source_id):
        await websocket.close(code=1008, reason="Источник не найден")
        return

    await websocket.accept()
    try:
        while True:
            frame_data = source_manager.get_frame(source_id, timeout=0.3)
            if frame_data:
                success, encoded = cv2.imencode(".jpg", frame_data.frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
                if success:
                    await websocket.send_bytes(encoded.tobytes())
                    await websocket.send_json(
                        {
                            "frame_number": frame_data.frame_number,
                            "timestamp": frame_data.timestamp,
                            "source_id": source_id,
                        }
                    )
            await asyncio.sleep(0.03)
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: %s", source_id)
    except Exception as exc:
        logger.exception("WebSocket stream error for %s: %s", source_id, exc)
        await websocket.close()


@app.get("/api/discover/usb")
async def discover_usb_cameras() -> JSONResponse:
    cameras = source_manager.auto_discover_usb_cameras()
    return JSONResponse({"status": "success", "cameras": cameras, "count": len(cameras)})


@app.post("/api/discover/network")
async def discover_network_cameras(network_range: str = "192.168.1.0/24") -> JSONResponse:
    discovered: List[Dict[str, Any]] = []
    try:
        network = ipaddress.ip_network(network_range, strict=False)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Некорректный диапазон сети: {exc}") from exc

    common_ports = [80, 443, 554, 8554, 1935]
    for ip in network.hosts():
        ip_str = str(ip)
        for port in common_ports:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                sock.settimeout(0.2)
                result = sock.connect_ex((ip_str, port))
                if result == 0:
                    discovered.append({"ip": ip_str, "port": port, "type": _guess_camera_type(port)})
            except OSError:
                pass
            finally:
                sock.close()

    return JSONResponse({"status": "success", "discovered": discovered, "count": len(discovered)})


def _guess_camera_type(port: int) -> str:
    port_map = {80: "http", 443: "https", 554: "rtsp", 8554: "rtsp", 1935: "rtmp"}
    return port_map.get(port, "unknown")


@app.get("/api/stats")
async def get_system_stats() -> JSONResponse:
    sources_info = source_manager.get_all_source_info()
    total_frames = 0
    total_dropped = 0
    active_sources = 0

    for _, info in sources_info.items():
        stats = info.get("stats", {})
        total_frames += stats.get("frames_received", 0)
        total_dropped += stats.get("frames_dropped", 0)
        if stats.get("running", False):
            active_sources += 1

    return JSONResponse(
        {
            "status": "success",
            "stats": {
                "total_sources": len(sources_info),
                "active_sources": active_sources,
                "total_frames_received": total_frames,
                "total_frames_dropped": total_dropped,
                "timestamp": datetime.now().isoformat(),
            },
        }
    )


@app.get("/api/integration/status", response_model=IntegrationStats)
async def integration_status() -> IntegrationStats:
    return metadata_bridge.stats()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)

