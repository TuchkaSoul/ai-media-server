# video_capture/video_source_manager.py
import cv2
import numpy as np
import threading
import time
import logging
from enum import Enum
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from queue import Queue, Empty
import subprocess
import requests
from urllib.parse import urlparse
try:
    from onvif import ONVIFCamera
except Exception:  # optional dependency
    ONVIFCamera = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VideoSourceType(Enum):
    """Типы источников видео"""
    USB_CAMERA = "usb_camera"
    IP_CAMERA_RTSP = "ip_camera_rtsp"
    IP_CAMERA_HTTP = "ip_camera_http"
    IP_CAMERA_ONVIF = "ip_camera_onvif"
    WEB_CAMERA = "web_camera"
    VIDEO_FILE = "video_file"
    MJPEG_STREAM = "mjpeg_stream"
    HLS_STREAM = "hls_stream"
    WEBCAM_API = "webcam_api"
    CUSTOM = "custom"

class ConnectionStatus(Enum):
    """Статус подключения"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    RECONNECTING = "reconnecting"

@dataclass
class VideoSourceConfig:
    """Конфигурация источника видео"""
    source_type: VideoSourceType
    source_uri: str
    source_id: str
    camera_id: Optional[int] = None  # Для USB камер
    rtsp_username: Optional[str] = None
    rtsp_password: Optional[str] = None
    rtsp_channel: int = 0  # Канал для многоканальных камер
    http_auth: Optional[Tuple[str, str]] = None
    frame_width: int = 1280
    frame_height: int = 720
    fps: int = 25
    buffer_size: int = 100  # Размер буфера кадров
    reconnect_attempts: int = 3
    reconnect_delay: float = 2.0
    timeout_sec: float = 10.0
    use_gpu: bool = False
    codec: str = "h264"  # h264, h265, mjpeg, etc
    protocols: List[str] = field(default_factory=lambda: ["tcp", "udp", "rtp"])
    additional_params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_type": self.source_type.value,
            "source_uri": self.source_uri,
            "source_id": self.source_id,
            "camera_id": self.camera_id,
            "rtsp_username": self.rtsp_username,
            "rtsp_password": self.rtsp_password,
            "rtsp_channel": self.rtsp_channel,
            "http_auth": self.http_auth,
            "frame_width": self.frame_width,
            "frame_height": self.frame_height,
            "fps": self.fps,
            "buffer_size": self.buffer_size,
            "reconnect_attempts": self.reconnect_attempts,
            "reconnect_delay": self.reconnect_delay,
            "timeout_sec": self.timeout_sec,
            "use_gpu": self.use_gpu,
            "codec": self.codec,
            "protocols": self.protocols,
            "additional_params": self.additional_params,
        }

@dataclass
class FrameData:
    """Данные кадра"""
    frame: np.ndarray
    timestamp: float
    frame_number: int
    source_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)

class VideoSource:
    """Базовый класс источника видео"""
    
    def __init__(self, config: VideoSourceConfig):
        self.config = config
        self.status = ConnectionStatus.DISCONNECTED
        self.cap = None
        self.frame_queue = Queue(maxsize=config.buffer_size)
        self.running = False
        self.frame_count = 0
        self.last_frame_time = 0
        self.thread = None
        self.lock = threading.Lock()
        self.frame_callbacks = []
        self._fps_calc_time = time.time()
        self._fps_calc_frames = 0
        self.stats = {
            'frames_received': 0,
            'frames_dropped': 0,
            'connection_errors': 0,
            'avg_fps': 0.0
        }
        
    def connect(self) -> bool:
        """Подключение к источнику"""
        raise NotImplementedError
    
    def disconnect(self):
        """Отключение от источника"""
        self.running = False
        if self.thread and self.thread.is_alive() and threading.current_thread() is not self.thread:
            self.thread.join(timeout=2.0)
        if self.cap:
            self.cap.release()
        self.cap = None
        self.status = ConnectionStatus.DISCONNECTED
        logger.info(f"Источник {self.config.source_id} отключен")
    
    def start_capture(self):
        """Начало захвата видео"""
        if self.running:
            logger.warning(f"Захват уже запущен для {self.config.source_id}")
            return
        
        if not self.connect():
            logger.error(f"Не удалось подключиться к {self.config.source_id}")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()
        logger.info(f"Захват видео запущен для {self.config.source_id}")
    
    def stop_capture(self):
        """Остановка захвата видео"""
        self.running = False
        self.disconnect()
    
    def _capture_loop(self):
        """Цикл захвата кадров"""
        while self.running:
            try:
                ret, frame = self._read_frame()
                if ret and frame is not None:
                    self._process_frame(frame)
                elif not self.running:
                    break
                else:
                    self._handle_read_error()
                    
            except Exception as e:
                logger.error(f"Ошибка захвата кадра: {e}")
                self.stats['connection_errors'] += 1
                time.sleep(0.1)
    
    def _read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Чтение кадра (должен быть переопределен)"""
        raise NotImplementedError
    
    def _process_frame(self, frame: np.ndarray):
        """Обработка полученного кадра"""
        current_time = time.time()
        
        # Изменение размера если нужно
        if (frame.shape[1], frame.shape[0]) != (self.config.frame_width, self.config.frame_height):
            frame = cv2.resize(frame, (self.config.frame_width, self.config.frame_height))
        
        # Создание метаданных
        metadata = {
            'source_id': self.config.source_id,
            'source_type': self.config.source_type.value,
            'processing_time': current_time - self.last_frame_time if self.last_frame_time > 0 else 0,
            'frame_size': frame.shape,
            'compression': self.config.codec
        }
        
        # Создание FrameData
        frame_data = FrameData(
            frame=frame,
            timestamp=current_time,
            frame_number=self.frame_count,
            source_id=self.config.source_id,
            metadata=metadata
        )
        
        # Добавление в очередь
        try:
            self.frame_queue.put_nowait(frame_data)
            self.stats['frames_received'] += 1
            for callback in self.frame_callbacks:
                try:
                    callback(frame_data)
                except Exception as callback_error:
                    logger.error("Ошибка frame handler для %s: %s", self.config.source_id, callback_error)
        except:
            self.stats['frames_dropped'] += 1
            logger.warning(f"Очередь переполнена, кадр {self.frame_count} отброшен")
        
        self.frame_count += 1
        self.last_frame_time = current_time
        
        # Обновление статистики FPS
        if self.frame_count % 30 == 0:
            self._update_fps_stats()
    
    def _update_fps_stats(self):
        """Обновление статистики FPS"""
        now = time.time()
        elapsed = now - self._fps_calc_time
        frames_delta = self.frame_count - self._fps_calc_frames
        if elapsed > 0 and frames_delta >= 0:
            self.stats['avg_fps'] = frames_delta / elapsed
            self._fps_calc_time = now
            self._fps_calc_frames = self.frame_count
    
    def _handle_read_error(self):
        """Обработка ошибки чтения"""
        self.stats['connection_errors'] += 1
        
        if self.stats['connection_errors'] > self.config.reconnect_attempts:
            logger.error(f"Превышено количество попыток переподключения для {self.config.source_id}")
            self.running = False
        else:
            logger.warning(f"Попытка переподключения {self.stats['connection_errors']} для {self.config.source_id}")
            time.sleep(self.config.reconnect_delay)
            self._reconnect()
    
    def _reconnect(self):
        """Переподключение к источнику"""
        if self.cap:
            try:
                self.cap.release()
            except Exception:
                pass
        self.cap = None
        self.status = ConnectionStatus.RECONNECTING
        time.sleep(1)
        if self.connect():
            self.status = ConnectionStatus.CONNECTED
            logger.info(f"Переподключение к {self.config.source_id} успешно")
        else:
            self.status = ConnectionStatus.ERROR

    def register_frame_callback(self, callback):
        self.frame_callbacks.append(callback)
    
    def get_frame(self, timeout: float = 1.0) -> Optional[FrameData]:
        """Получение кадра из очереди"""
        try:
            return self.frame_queue.get(timeout=timeout)
        except Empty:
            return None
    
    def clear_queue(self):
        """Очистка очереди кадров"""
        while not self.frame_queue.empty():
            try:
                self.frame_queue.get_nowait()
            except Empty:
                break
    
    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики"""
        with self.lock:
            return {
                **self.stats,
                'queue_size': self.frame_queue.qsize(),
                'status': self.status.value,
                'frame_count': self.frame_count,
                'running': self.running
            }

class USBCameraSource(VideoSource):
    """Источник USB камеры"""
    
    def __init__(self, config: VideoSourceConfig):
        super().__init__(config)
        self.camera_index = config.camera_id or 0
    
    def connect(self) -> bool:
        """Подключение к USB камере"""
        try:
            logger.info(f"Подключение к USB камере {self.camera_index}")
            
            self.cap = cv2.VideoCapture(self.camera_index)
            
            if not self.cap.isOpened():
                logger.error(f"Не удалось открыть USB камеру {self.camera_index}")
                return False
            
            # Настройка параметров
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.frame_width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.frame_height)
            self.cap.set(cv2.CAP_PROP_FPS, self.config.fps)
            
            # Попытка установить кодек
            if self.config.codec == 'mjpeg':
                self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            
            self.status = ConnectionStatus.CONNECTED
            logger.info(f"USB камера {self.camera_index} подключена успешно")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка подключения к USB камере: {e}")
            self.status = ConnectionStatus.ERROR
            return False
    
    def _read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Чтение кадра с USB камеры"""
        if self.cap is None or not self.cap.isOpened():
            return False, None
        
        ret, frame = self.cap.read()
        return ret, frame

class RTSPSource(VideoSource):
    """Источник RTSP потока"""
    
    def __init__(self, config: VideoSourceConfig):
        super().__init__(config)
        self.rtsp_url = self._build_rtsp_url()
    
    def _build_rtsp_url(self) -> str:
        """Построение RTSP URL с аутентификацией"""
        parsed = urlparse(self.config.source_uri)
        
        # Если URL уже содержит протокол rtsp://
        if parsed.scheme == 'rtsp':
            return self.config.source_uri
        
        # Добавление аутентификации если указана
        auth_part = ""
        if self.config.rtsp_username and self.config.rtsp_password:
            auth_part = f"{self.config.rtsp_username}:{self.config.rtsp_password}@"
        
        # Построение полного URL
        rtsp_url = f"rtsp://{auth_part}{parsed.netloc or parsed.path}"
        
        # Добавление пути и параметров
        if parsed.path:
            rtsp_url += parsed.path
        if parsed.query:
            rtsp_url += f"?{parsed.query}"
        
        return rtsp_url
    
    def connect(self) -> bool:
        """Подключение к RTSP потоку"""
        try:
            logger.info(f"Подключение к RTSP: {self.rtsp_url}")
            
            # Параметры OpenCV для RTSP
            gst_params = self._build_gstreamer_pipeline()
            
            if self.config.use_gpu and self._check_gpu_support():
                # Использование GPU ускорения
                self.cap = cv2.VideoCapture(gst_params, cv2.CAP_GSTREAMER)
            else:
                # Обычное подключение
                self.cap = cv2.VideoCapture(self.rtsp_url)
            
            if not self.cap.isOpened():
                logger.error(f"Не удалось открыть RTSP поток: {self.rtsp_url}")
                return False
            
            # Установка таймаута
            self.cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, int(self.config.timeout_sec * 1000))
            
            self.status = ConnectionStatus.CONNECTED
            logger.info(f"RTSP поток подключен: {self.rtsp_url}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка подключения к RTSP: {e}")
            self.status = ConnectionStatus.ERROR
            return False
    
    def _build_gstreamer_pipeline(self) -> str:
        """Построение GStreamer пайплайна для лучшей производительности"""
        # Базовый пайплайн для RTSP
        pipeline = (
            f"rtspsrc location={self.rtsp_url} latency=0 "
            f"! rtph264depay "
            f"! h264parse "
            f"! avdec_h264 "
            f"! videoconvert "
            f"! videoscale "
            f"! video/x-raw,width={self.config.frame_width},height={self.config.frame_height} "
            f"! appsink sync=false"
        )
        
        if self.config.use_gpu:
            # Пайплайн с GPU ускорением (для NVIDIA)
            pipeline = (
                f"rtspsrc location={self.rtsp_url} latency=0 "
                f"! rtph264depay "
                f"! h264parse "
                f"! nvh264dec "
                f"! nvvidconv "
                f"! video/x-raw,width={self.config.frame_width},height={self.config.frame_height} "
                f"! appsink sync=false"
            )
        
        return pipeline
    
    def _check_gpu_support(self) -> bool:
        """Проверка поддержки GPU"""
        try:
            # Проверка доступности GStreamer
            cap = cv2.VideoCapture()
            return cap.open(0, cv2.CAP_GSTREAMER)
        except:
            return False
    
    def _read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Чтение кадра из RTSP потока"""
        if self.cap is None or not self.cap.isOpened():
            return False, None
        
        ret, frame = self.cap.read()
        
        # Если не удалось прочитать кадр, попробовать переподключиться
        if not ret:
            logger.warning(f"Потеря соединения с RTSP: {self.rtsp_url}")
            self._reconnect()
        
        return ret, frame

class HTTPSource(VideoSource):
    """Источник HTTP потока (MJPEG, JPEG)"""
    
    def __init__(self, config: VideoSourceConfig):
        super().__init__(config)
        self.session = None
        self.response = None
        self.buffer = b""
        self.boundary = None
    
    def connect(self) -> bool:
        """Подключение к HTTP потоку"""
        try:
            logger.info(f"Подключение к HTTP потоку: {self.config.source_uri}")
            
            # Создание сессии с таймаутом
            self.session = requests.Session()
            self.session.timeout = self.config.timeout_sec
            
            # Добавление аутентификации если указана
            auth = None
            if self.config.http_auth:
                auth = requests.auth.HTTPBasicAuth(*self.config.http_auth)
            
            # Запрос потока
            self.response = self.session.get(
                self.config.source_uri,
                stream=True,
                auth=auth,
                headers={'User-Agent': 'VideoCapture/1.0'}
            )
            
            if self.response.status_code != 200:
                logger.error(f"HTTP ошибка: {self.response.status_code}")
                return False
            
            # Определение типа потока
            content_type = self.response.headers.get('Content-Type', '')
            
            if 'multipart/x-mixed-replace' in content_type:
                # MJPEG поток
                self._parse_boundary(content_type)
                self.status = ConnectionStatus.CONNECTED
                logger.info(f"MJPEG поток подключен: {self.config.source_uri}")
                return True
            elif 'image/jpeg' in content_type:
                # Одиночный JPEG кадр
                self.status = ConnectionStatus.CONNECTED
                logger.info(f"JPEG поток подключен: {self.config.source_uri}")
                return True
            else:
                logger.error(f"Неподдерживаемый Content-Type: {content_type}")
                return False
            
        except Exception as e:
            logger.error(f"Ошибка подключения к HTTP: {e}")
            self.status = ConnectionStatus.ERROR
            return False
    
    def _parse_boundary(self, content_type: str):
        """Парсинг boundary из заголовка Content-Type"""
        if 'boundary=' in content_type:
            self.boundary = content_type.split('boundary=')[1].strip()
        else:
            self.boundary = '--myboundary'
    
    def _read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Чтение кадра из HTTP потока"""
        try:
            if not self.response or not self.response.raw:
                return False, None
            
            if self.boundary:
                # Чтение MJPEG потока
                frame = self._read_mjpeg_frame()
            else:
                # Чтение одиночного JPEG
                frame = self._read_jpeg_frame()
            
            return frame is not None, frame
            
        except Exception as e:
            logger.error(f"Ошибка чтения HTTP кадра: {e}")
            return False, None
    
    def _read_mjpeg_frame(self) -> Optional[np.ndarray]:
        """Чтение кадра из MJPEG потока"""
        try:
            # Чтение до следующего boundary
            while True:
                line = self.response.raw.readline()
                if not line:
                    return None
                
                line = line.strip()
                
                if line.startswith(b'Content-Type: image/jpeg'):
                    # Читаем следующий boundary или начало следующего кадра
                    self.response.raw.readline()  # Пропускаем пустую строку
                    
                    # Читаем размер кадра
                    size_line = self.response.raw.readline()
                    if size_line.startswith(b'Content-Length:'):
                        size = int(size_line.split(b':')[1].strip())
                        
                        # Читаем данные JPEG
                        jpeg_data = self.response.raw.read(size)
                        
                        # Декодируем JPEG в кадр
                        frame = cv2.imdecode(
                            np.frombuffer(jpeg_data, np.uint8),
                            cv2.IMREAD_COLOR
                        )
                        
                        return frame
                
                elif line.startswith(self.boundary.encode()):
                    continue
        
        except Exception as e:
            logger.error(f"Ошибка чтения MJPEG: {e}")
            return None
    
    def _read_jpeg_frame(self) -> Optional[np.ndarray]:
        """Чтение одиночного JPEG кадра"""
        try:
            # Получаем новый кадр
            self.response = self.session.get(
                self.config.source_uri,
                auth=self.config.http_auth if self.config.http_auth else None
            )
            
            if self.response.status_code == 200:
                frame = cv2.imdecode(
                    np.frombuffer(self.response.content, np.uint8),
                    cv2.IMREAD_COLOR
                )
                return frame
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка чтения JPEG: {e}")
            return None
    
    def disconnect(self):
        """Отключение от HTTP потока"""
        super().disconnect()
        if self.response:
            self.response.close()
        if self.session:
            self.session.close()

class ONVIFSource(VideoSource):
    """Источник ONVIF камеры"""
    
    def __init__(self, config: VideoSourceConfig):
        super().__init__(config)
        self.onvif_camera = None
        self.media_service = None
        self.ptz_service = None
        self.profiles = []
        self.rtsp_url = None
        self.rtsp_source = None
    
    def connect(self) -> bool:
        """Подключение к ONVIF камере"""
        try:
            if ONVIFCamera is None:
                logger.error("python-onvif-zeep не установлен, ONVIF недоступен")
                self.status = ConnectionStatus.ERROR
                return False

            logger.info(f"Подключение к ONVIF камере: {self.config.source_uri}")
            
            parsed = urlparse(self.config.source_uri)
            host = parsed.hostname
            port = parsed.port or 80
            username = self.config.rtsp_username
            password = self.config.rtsp_password
            
            # Подключение к ONVIF камере
            self.onvif_camera = ONVIFCamera(
                host, port, username, password,
                wsdl_dir='./wsdl'  # Путь к WSDL файлам
            )
            
            # Создание медиа сервиса
            self.media_service = self.onvif_camera.create_media_service()
            
            # Получение профилей камеры
            self.profiles = self.media_service.GetProfiles()
            
            if not self.profiles:
                logger.error("Не найдены профили ONVIF камеры")
                return False
            
            # Получение RTSP URL из профиля
            profile = self.profiles[0]  # Используем первый профиль
            stream_uri = self.media_service.GetStreamUri({
                'StreamSetup': {
                    'Stream': 'RTP-Unicast',
                    'Transport': {'Protocol': 'RTSP'}
                },
                'ProfileToken': profile.token
            })
            
            self.rtsp_url = stream_uri.Uri
            
            # Создание RTSP источника для захвата видео
            rtsp_config = VideoSourceConfig(
                source_type=VideoSourceType.IP_CAMERA_RTSP,
                source_uri=self.rtsp_url,
                source_id=f"{self.config.source_id}_rtsp",
                rtsp_username=username,
                rtsp_password=password,
                frame_width=self.config.frame_width,
                frame_height=self.config.frame_height,
                fps=self.config.fps
            )
            
            # Создание RTSP источника
            self.rtsp_source = RTSPSource(rtsp_config)
            
            # Подключение RTSP
            if self.rtsp_source.connect():
                self.status = ConnectionStatus.CONNECTED
                logger.info(f"ONVIF камера подключена: {self.config.source_uri}")
                return True
            else:
                logger.error("Не удалось подключиться к RTSP потоку ONVIF камеры")
                return False
            
        except Exception as e:
            logger.error(f"Ошибка подключения к ONVIF: {e}")
            self.status = ConnectionStatus.ERROR
            return False
    
    def _read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Чтение кадра через RTSP источник"""
        if not self.rtsp_source:
            return False, None
        
        return self.rtsp_source._read_frame()
    
    def ptz_move(self, pan: float, tilt: float, zoom: float):
        """Управление PTZ камерой"""
        try:
            if not self.ptz_service:
                self.ptz_service = self.onvif_camera.create_ptz_service()
            
            velocity = {
                'PanTilt': {
                    'x': pan,
                    'y': tilt
                },
                'Zoom': {
                    'x': zoom
                }
            }
            
            self.ptz_service.ContinuousMove({
                'ProfileToken': self.profiles[0].token,
                'Velocity': velocity
            })
            
        except Exception as e:
            logger.error(f"Ошибка PTZ управления: {e}")
    
    def get_camera_info(self) -> Dict[str, Any]:
        """Получение информации о камере"""
        try:
            device_service = self.onvif_camera.create_devicemgmt_service()
            info = device_service.GetDeviceInformation()
            
            return {
                'manufacturer': info.Manufacturer,
                'model': info.Model,
                'firmware_version': info.FirmwareVersion,
                'serial_number': info.SerialNumber,
                'hardware_id': info.HardwareId
            }
        except:
            return {}
    
    def disconnect(self):
        """Отключение от ONVIF камеры"""
        super().disconnect()
        if self.rtsp_source:
            self.rtsp_source.disconnect()

class WebcamAPISource(VideoSource):
    """Источник веб-камер через публичные API"""
    
    def __init__(self, config: VideoSourceConfig):
        super().__init__(config)
        self.api_urls = {
            'insecam': 'http://www.insecam.org/en/json/',
            'webcam_taxi': 'https://api.webcamtaxi.com/',
            'openipc': 'http://openipc.org/api/v1/cameras'
        }
        self.current_camera_url = None
    
    def connect(self) -> bool:
        """Подключение к веб-камере через API"""
        try:
            # Определение типа API
            if 'insecam' in self.config.source_uri.lower():
                return self._connect_insecam()
            elif 'webcamtaxi' in self.config.source_uri.lower():
                return self._connect_webcam_taxi()
            else:
                # Прямой URL к камере
                return self._connect_direct()
                
        except Exception as e:
            logger.error(f"Ошибка подключения к API камере: {e}")
            self.status = ConnectionStatus.ERROR
            return False
    
    def _connect_insecam(self) -> bool:
        """Подключение к Insecam API"""
        try:
            # Получение списка камер
            response = requests.get(self.api_urls['insecam'])
            cameras = response.json()['cameras']
            
            # Поиск нужной камеры по ID или URL
            camera = None
            for cam in cameras:
                if (self.config.source_id in cam.get('id', '') or 
                    self.config.source_uri in cam.get('direct_url', '')):
                    camera = cam
                    break
            
            if not camera:
                logger.error(f"Камера не найдена в Insecam: {self.config.source_id}")
                return False
            
            self.current_camera_url = camera['direct_url']
            
            # Создание HTTP источника
            http_config = VideoSourceConfig(
                source_type=VideoSourceType.IP_CAMERA_HTTP,
                source_uri=self.current_camera_url,
                source_id=f"{self.config.source_id}_http",
                frame_width=self.config.frame_width,
                frame_height=self.config.frame_height,
                fps=self.config.fps
            )
            
            self.http_source = HTTPSource(http_config)
            
            if self.http_source.connect():
                self.status = ConnectionStatus.CONNECTED
                logger.info(f"Insecam камера подключена: {self.current_camera_url}")
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"Ошибка Insecam API: {e}")
            return False
    
    def _connect_webcam_taxi(self) -> bool:
        """Подключение к WebcamTaxi API"""
        try:
            # Получение информации о камере
            camera_id = self.config.source_uri.split('/')[-1]
            api_url = f"{self.api_urls['webcam_taxi']}cameras/{camera_id}"
            
            response = requests.get(api_url)
            camera_data = response.json()
            
            self.current_camera_url = camera_data.get('hls_url') or camera_data.get('mjpg_url')
            
            if not self.current_camera_url:
                logger.error("URL камеры не найден")
                return False
            
            # Определение типа потока
            if 'm3u8' in self.current_camera_url:
                source_type = VideoSourceType.HLS_STREAM
            else:
                source_type = VideoSourceType.MJPEG_STREAM
            
            # Создание соответствующего источника
            stream_config = VideoSourceConfig(
                source_type=source_type,
                source_uri=self.current_camera_url,
                source_id=f"{self.config.source_id}_stream",
                frame_width=self.config.frame_width,
                frame_height=self.config.frame_height,
                fps=self.config.fps
            )
            
            if source_type == VideoSourceType.HLS_STREAM:
                self.stream_source = HLSSource(stream_config)
            else:
                self.stream_source = HTTPSource(stream_config)
            
            if self.stream_source.connect():
                self.status = ConnectionStatus.CONNECTED
                logger.info(f"WebcamTaxi камера подключена: {self.current_camera_url}")
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"Ошибка WebcamTaxi API: {e}")
            return False
    
    def _connect_direct(self) -> bool:
        """Прямое подключение к URL камеры"""
        try:
            # Проверка типа URL
            parsed = urlparse(self.config.source_uri)
            
            if parsed.scheme == 'rtsp':
                # RTSP камера
                rtsp_config = VideoSourceConfig(
                    source_type=VideoSourceType.IP_CAMERA_RTSP,
                    source_uri=self.config.source_uri,
                    source_id=self.config.source_id,
                    frame_width=self.config.frame_width,
                    frame_height=self.config.frame_height,
                    fps=self.config.fps
                )
                self.stream_source = RTSPSource(rtsp_config)
                
            elif 'm3u8' in parsed.path:
                # HLS поток
                hls_config = VideoSourceConfig(
                    source_type=VideoSourceType.HLS_STREAM,
                    source_uri=self.config.source_uri,
                    source_id=self.config.source_id,
                    frame_width=self.config.frame_width,
                    frame_height=self.config.frame_height,
                    fps=self.config.fps
                )
                self.stream_source = HLSSource(hls_config)
                
            else:
                # HTTP/MJPEG поток
                http_config = VideoSourceConfig(
                    source_type=VideoSourceType.IP_CAMERA_HTTP,
                    source_uri=self.config.source_uri,
                    source_id=self.config.source_id,
                    frame_width=self.config.frame_width,
                    frame_height=self.config.frame_height,
                    fps=self.config.fps
                )
                self.stream_source = HTTPSource(http_config)
            
            if self.stream_source.connect():
                self.status = ConnectionStatus.CONNECTED
                logger.info(f"Камера подключена напрямую: {self.config.source_uri}")
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"Ошибка прямого подключения: {e}")
            return False
    
    def _read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Чтение кадра через вложенный источник"""
        if not hasattr(self, 'stream_source') or not self.stream_source:
            return False, None
        
        return self.stream_source._read_frame()
    
    def disconnect(self):
        """Отключение от API камеры"""
        super().disconnect()
        if hasattr(self, 'stream_source') and self.stream_source:
            self.stream_source.disconnect()

class HLSSource(VideoSource):
    """Источник HLS потока"""
    
    def __init__(self, config: VideoSourceConfig):
        super().__init__(config)
        self.process = None
        self.pipe_path = None
    
    def connect(self) -> bool:
        """Подключение к HLS потоку"""
        try:
            logger.info(f"Подключение к HLS: {self.config.source_uri}")
            
            # Используем ffmpeg для чтения HLS
            self.pipe_path = f'/tmp/hls_pipe_{self.config.source_id}'
            
            # Создание named pipe
            import os
            if os.path.exists(self.pipe_path):
                os.remove(self.pipe_path)
            os.mkfifo(self.pipe_path)
            
            # Команда ffmpeg для чтения HLS
            ffmpeg_cmd = [
                'ffmpeg',
                '-i', self.config.source_uri,
                '-loglevel', 'quiet',
                '-an',  # без аудио
                '-f', 'image2pipe',
                '-pix_fmt', 'bgr24',
                '-vcodec', 'rawvideo',
                '-'
            ]
            
            # Запуск ffmpeg в фоне
            self.process = subprocess.Popen(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=10**8
            )
            
            self.status = ConnectionStatus.CONNECTED
            logger.info(f"HLS поток подключен: {self.config.source_uri}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка подключения к HLS: {e}")
            self.status = ConnectionStatus.ERROR
            return False
    
    def _read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Чтение кадра из HLS потока"""
        try:
            if not self.process or self.process.poll() is not None:
                return False, None
            
            # Чтение raw видео данных
            frame_size = self.config.frame_width * self.config.frame_height * 3
            raw_frame = self.process.stdout.read(frame_size)
            
            if len(raw_frame) != frame_size:
                logger.warning("Неполный кадр из HLS")
                return False, None
            
            # Преобразование в numpy array
            frame = np.frombuffer(raw_frame, np.uint8)
            frame = frame.reshape((self.config.frame_height, self.config.frame_width, 3))
            
            return True, frame
            
        except Exception as e:
            logger.error(f"Ошибка чтения HLS кадра: {e}")
            return False, None
    
    def disconnect(self):
        """Отключение от HLS потока"""
        super().disconnect()
        if self.process:
            self.process.terminate()
            self.process.wait()
        
        # Удаление named pipe
        import os
        if self.pipe_path and os.path.exists(self.pipe_path):
            os.remove(self.pipe_path)

class VideoSourceFactory:
    """Фабрика источников видео"""
    
    @staticmethod
    def create_source(config: VideoSourceConfig) -> Optional[VideoSource]:
        """Создание источника видео по конфигурации"""
        source_map = {
            VideoSourceType.USB_CAMERA: USBCameraSource,
            VideoSourceType.IP_CAMERA_RTSP: RTSPSource,
            VideoSourceType.IP_CAMERA_HTTP: HTTPSource,
            VideoSourceType.IP_CAMERA_ONVIF: ONVIFSource,
            VideoSourceType.WEB_CAMERA: USBCameraSource,
            VideoSourceType.VIDEO_FILE: VideoSource,  # Реализовать отдельно
            VideoSourceType.MJPEG_STREAM: HTTPSource,
            VideoSourceType.HLS_STREAM: HLSSource,
            VideoSourceType.WEBCAM_API: WebcamAPISource,
            VideoSourceType.CUSTOM: VideoSource
        }
        
        source_class = source_map.get(config.source_type)
        if not source_class:
            logger.error(f"Неизвестный тип источника: {config.source_type}")
            return None
        
        return source_class(config)
    
    @staticmethod
    def config_from_dict(config_dict: Dict[str, Any]) -> Optional[VideoSourceConfig]:
        """Создание конфигурации источника из словаря"""
        try:
            return VideoSourceConfig(
                source_type=VideoSourceType(config_dict["source_type"]),
                source_uri=config_dict["source_uri"],
                source_id=config_dict["source_id"],
                camera_id=config_dict.get("camera_id"),
                rtsp_username=config_dict.get("rtsp_username"),
                rtsp_password=config_dict.get("rtsp_password"),
                rtsp_channel=config_dict.get("rtsp_channel", 0),
                http_auth=config_dict.get("http_auth"),
                frame_width=config_dict.get("frame_width", 1280),
                frame_height=config_dict.get("frame_height", 720),
                fps=config_dict.get("fps", 25),
                buffer_size=config_dict.get("buffer_size", 100),
                reconnect_attempts=config_dict.get("reconnect_attempts", 3),
                reconnect_delay=config_dict.get("reconnect_delay", 2.0),
                timeout_sec=config_dict.get("timeout_sec", 10.0),
                use_gpu=config_dict.get("use_gpu", False),
                codec=config_dict.get("codec", "h264"),
                protocols=config_dict.get("protocols", ["tcp", "udp", "rtp"]),
                additional_params=config_dict.get("additional_params", {}),
            )
        except Exception as e:
            logger.error(f"Ошибка создания источника из конфигурации: {e}")
            return None

    @staticmethod
    def create_from_dict(config_dict: Dict[str, Any]) -> Optional[VideoSource]:
        """Создание источника из словаря конфигурации"""
        config = VideoSourceFactory.config_from_dict(config_dict)
        if config is None:
            return None
        return VideoSourceFactory.create_source(config)

class MultiSourceManager:
    """Менеджер нескольких источников видео"""
    
    def __init__(self):
        self.sources: Dict[str, VideoSource] = {}
        self.lock = threading.RLock()
        self.running = False
        self.frame_handlers = []
        self.stats_interval = 5.0  # Интервал сбора статистики в секундах
        self.last_stats_time = time.time()
        self._monitor_thread = None
    
    def add_source(self, config: VideoSourceConfig) -> bool:
        """Добавление нового источника"""
        with self.lock:
            if config.source_id in self.sources:
                logger.warning(f"Источник {config.source_id} уже существует")
                return False
            
            source = VideoSourceFactory.create_source(config)
            if not source:
                return False

            source.register_frame_callback(self._dispatch_frame_handlers)
            
            self.sources[config.source_id] = source
            
            if self.running:
                source.start_capture()
            
            logger.info(f"Источник {config.source_id} добавлен")
            return True
    
    def remove_source(self, source_id: str):
        """Удаление источника"""
        with self.lock:
            if source_id in self.sources:
                self.sources[source_id].stop_capture()
                del self.sources[source_id]
                logger.info(f"Источник {source_id} удален")
    
    def start_all(self):
        """Запуск всех источников"""
        with self.lock:
            if self.running:
                return
            self.running = True
            for source_id, source in self.sources.items():
                source.start_capture()
            
            # Запуск мониторинга статистики
            self._monitor_thread = threading.Thread(target=self._monitor_stats, daemon=True)
            self._monitor_thread.start()
            
            logger.info("Все источники запущены")
    
    def stop_all(self):
        """Остановка всех источников"""
        with self.lock:
            self.running = False
            for source_id, source in self.sources.items():
                source.stop_capture()
            
            logger.info("Все источники остановлены")
    
    def get_frame(self, source_id: str, timeout: float = 1.0) -> Optional[FrameData]:
        """Получение кадра от конкретного источника"""
        with self.lock:
            source = self.sources.get(source_id)
            if not source:
                return None
        
        return source.get_frame(timeout)
    
    def get_all_frames(self, timeout: float = 0.1) -> Dict[str, Optional[FrameData]]:
        """Получение последних кадров от всех источников"""
        frames = {}
        with self.lock:
            for source_id, source in self.sources.items():
                frames[source_id] = source.get_frame(timeout)
        return frames
    
    def register_frame_handler(self, handler):
        """Регистрация обработчика кадров"""
        self.frame_handlers.append(handler)

    def _dispatch_frame_handlers(self, frame_data: FrameData):
        for handler in self.frame_handlers:
            try:
                handler(frame_data)
            except Exception as handler_error:
                logger.error("Ошибка обработчика кадров: %s", handler_error)
    
    def _monitor_stats(self):
        """Мониторинг статистики источников"""
        while self.running:
            current_time = time.time()
            if current_time - self.last_stats_time >= self.stats_interval:
                self._log_stats()
                self.last_stats_time = current_time
            
            time.sleep(1)
    
    def _log_stats(self):
        """Логирование статистики"""
        with self.lock:
            total_frames = 0
            total_dropped = 0
            active_sources = 0
            
            for source_id, source in self.sources.items():
                stats = source.get_stats()
                total_frames += stats['frames_received']
                total_dropped += stats['frames_dropped']
                if stats['running']:
                    active_sources += 1
            
            logger.info(
                f"Статистика источников: "
                f"Активных: {active_sources}/{len(self.sources)}, "
                f"Кадров: {total_frames}, "
                f"Потеряно: {total_dropped}"
            )
    
    def get_source_info(self, source_id: str) -> Optional[Dict[str, Any]]:
        """Получение информации об источнике"""
        with self.lock:
            source = self.sources.get(source_id)
            if not source:
                return None
            
            stats = source.get_stats()
            return {
                'source_id': source_id,
                'config': source.config.to_dict(),
                'stats': stats,
                'status': source.status.value
            }
    
    def get_all_source_info(self) -> Dict[str, Dict[str, Any]]:
        """Получение информации обо всех источниках"""
        with self.lock:
            return {
                source_id: {
                    "source_id": source_id,
                    "config": source.config.to_dict(),
                    "stats": source.get_stats(),
                    "status": source.status.value,
                }
                for source_id, source in self.sources.items()
            }

    def has_source(self, source_id: str) -> bool:
        with self.lock:
            return source_id in self.sources

    def start_source(self, source_id: str) -> bool:
        with self.lock:
            source = self.sources.get(source_id)
            if not source:
                return False
            source.start_capture()
            return True
    
    def auto_discover_usb_cameras(self) -> List[Dict[str, Any]]:
        """Автоматическое обнаружение USB камер"""
        discovered = []
        
        # Проверка индексов 0-10
        for i in range(10):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret:
                    discovered.append({
                        'camera_index': i,
                        'type': 'usb_camera',
                        'source_id': f'usb_camera_{i}',
                        'frame_size': frame.shape if frame is not None else None
                    })
                cap.release()
        
        return discovered

# Пример использования
if __name__ == "__main__":
    # Пример конфигурации различных источников
    
    # 1. USB камера
    usb_config = VideoSourceConfig(
        source_type=VideoSourceType.USB_CAMERA,
        source_uri="",  # Для USB не нужен URI
        source_id="usb_camera_0",
        camera_id=0,
        frame_width=1280,
        frame_height=720,
        fps=30
    )
    
    # 2. RTSP камера
    rtsp_config = VideoSourceConfig(
        source_type=VideoSourceType.IP_CAMERA_RTSP,
        source_uri="192.168.1.100:554",
        source_id="rtsp_camera_1",
        rtsp_username="admin",
        rtsp_password="password",
        rtsp_channel=0,
        frame_width=1920,
        frame_height=1080,
        fps=25
    )
    
    # 3. HTTP/MJPEG камера
    http_config = VideoSourceConfig(
        source_type=VideoSourceType.IP_CAMERA_HTTP,
        source_uri="http://192.168.1.101/video.mjpg",
        source_id="http_camera_1",
        http_auth=("admin", "admin"),
        frame_width=1280,
        frame_height=720,
        fps=15
    )
    
    # 4. ONVIF камера
    onvif_config = VideoSourceConfig(
        source_type=VideoSourceType.IP_CAMERA_ONVIF,
        source_uri="http://192.168.1.102:80",
        source_id="onvif_camera_1",
        rtsp_username="admin",
        rtsp_password="password",
        frame_width=1280,
        frame_height=720,
        fps=25
    )
    
    # 5. Веб-камера через API
    api_config = VideoSourceConfig(
        source_type=VideoSourceType.WEBCAM_API,
        source_uri="https://webcamtaxi.com/camera_id",
        source_id="api_camera_1",
        frame_width=1280,
        frame_height=720,
        fps=10
    )
    
    # Создание менеджера источников
    manager = MultiSourceManager()
    
    # Добавление источников
    manager.add_source(usb_config)
    manager.add_source(rtsp_config)
    
    # Запуск всех источников
    manager.start_all()
    
    try:
        # Основной цикл обработки
        while True:
            # Получение кадров от всех источников
            frames = manager.get_all_frames(timeout=0.1)
            
            for source_id, frame_data in frames.items():
                if frame_data:
                    # Обработка кадра
                    frame = frame_data.frame
                    cv2.imshow(f"Source: {source_id}", frame)
            
            # Выход по нажатию 'q'
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            
            # Периодический вывод статистики
            if time.time() - manager.last_stats_time >= 5:
                print("\n" + "="*50)
                print("Статистика источников:")
                for source_id, info in manager.get_all_source_info().items():
                    print(f"{source_id}: {info['stats']}")
                print("="*50)
                
    except KeyboardInterrupt:
        print("\nОстановка по запросу пользователя")
    
    finally:
        # Остановка всех источников
        manager.stop_all()
        cv2.destroyAllWindows()
