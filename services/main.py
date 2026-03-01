import cv2
import numpy as np
import torch
import torchaudio
from pathlib import Path
import json
import time
import logging
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple
from queue import Queue
from threading import Thread, Lock
import warnings
warnings.filterwarnings('ignore')

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class Config:
    """Конфигурация системы"""
    # Видео параметры
    input_resolution: Tuple[int, int] = (1280, 720)  # HD
    processing_fps: int = 15
    output_fps: int = 10
    
    # Пороги детекции
    motion_threshold: float = 0.1
    importance_threshold: float = 0.3
    scene_change_threshold: float = 0.4
    
    # Сжатие
    base_skip_frames: int = 5  # Пропуск кадров в спокойных сценах
    critical_skip_frames: int = 1  # Пропуск в важных сценах
    
    # Модели
    use_yolo: bool = True
    yolo_confidence: float = 0.5
    use_action_detection: bool = True
    
    # Профиль сжатия
    compression_profile: str = "balanced"  # balanced, maximum_compression, maximum_quality
    
    # Хранение
    save_metadata: bool = True
    save_keyframes: bool = True
    save_compressed_video: bool = True

class YOLODetector:
    """Детектор объектов на основе YOLO"""
    def __init__(self, model_type='yolov8n'):
        try:
            from ultralytics import YOLO
            self.model = YOLO(f'{model_type}.pt')
            self.class_names = self.model.names
            logger.info(f"YOLO модель загружена: {model_type}")
        except ImportError:
            logger.warning("Ultralytics не установлен. Используем простой детектор.")
            self.model = None
    
    def detect(self, frame):
        """Детекция объектов в кадре"""
        if self.model is None:
            # Простой детектор для тестирования
            return self._simple_detection(frame)
        
        results = self.model(frame, verbose=False)
        detections = []
        
        for result in results:
            boxes = result.boxes
            if boxes is not None:
                for box in boxes:
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    conf = box.conf[0].cpu().numpy()
                    cls_id = int(box.cls[0].cpu().numpy())
                    
                    detections.append({
                        'bbox': [float(x1), float(y1), float(x2), float(y2)],
                        'confidence': float(conf),
                        'class_id': cls_id,
                        'class_name': self.class_names[cls_id],
                        'importance': self._calculate_importance(cls_id, conf)
                    })
        
        return detections
    
    def _calculate_importance(self, class_id, confidence):
        """Расчет важности объекта"""
        class_name = self.class_names.get(class_id, '')
        
        # Важные классы
        critical_classes = ['person', 'dog', 'cat', 'bird', 'horse', 'bear']
        vehicle_classes = ['car', 'truck', 'bus', 'motorcycle', 'bicycle']
        
        if class_name in critical_classes:
            return 0.8 + confidence * 0.2
        elif class_name in vehicle_classes:
            return 0.5 + confidence * 0.3
        else:
            return 0.3 + confidence * 0.2
    
    def _simple_detection(self, frame):
        """Простой детектор для тестирования"""
        # Контуры движения
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (21, 21), 0)
        
        if not hasattr(self, 'prev_gray'):
            self.prev_gray = blurred
            return []
        
        frame_diff = cv2.absdiff(self.prev_gray, blurred)
        _, thresh = cv2.threshold(frame_diff, 25, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        detections = []
        for contour in contours:
            if cv2.contourArea(contour) > 500:
                x, y, w, h = cv2.boundingRect(contour)
                detections.append({
                    'bbox': [float(x), float(y), float(x+w), float(y+h)],
                    'confidence': 0.7,
                    'class_id': 0,
                    'class_name': 'motion',
                    'importance': 0.6
                })
        
        self.prev_gray = blurred
        return detections

class ActionDetector:
    """Детектор действий"""
    def __init__(self):
        self.history = []
        self.max_history = 10
        
    def detect(self, frame, detections):
        """Детекция действий на основе последовательности кадров"""
        actions = []
        
        for det in detections:
            if det['class_name'] == 'person':
                action = self._detect_person_action(det, frame)
                if action:
                    actions.append({
                        'object_id': det.get('id', 0),
                        'action': action,
                        'confidence': 0.7,
                        'bbox': det['bbox']
                    })
        
        return actions
    
    def _detect_person_action(self, detection, frame):
        """Детекция действий человека"""
        x1, y1, x2, y2 = map(int, detection['bbox'])
        h = y2 - y1
        w = x2 - x1
        
        # Простая эвристика для падения
        if h > 0 and w > 0:
            aspect_ratio = h / w
            # Если человек "растянулся" по горизонтали - возможно упал
            if aspect_ratio < 0.5:
                return "lying_down"
            elif aspect_ratio > 2.5:
                return "standing"
        
        # Анализ движения
        if hasattr(self, 'prev_bbox'):
            prev_area = (self.prev_bbox[2] - self.prev_bbox[0]) * (self.prev_bbox[3] - self.prev_bbox[1])
            curr_area = (x2 - x1) * (y2 - y1)
            
            if curr_area > prev_area * 1.5:
                return "approaching"
            elif curr_area < prev_area * 0.5:
                return "moving_away"
        
        self.prev_bbox = detection['bbox']
        return None

class AudioAnalyzer:
    """Анализатор аудио"""
    def __init__(self, sample_rate=16000):
        self.sample_rate = sample_rate
        self.history = []
        
    def analyze(self, audio_data):
        """Анализ аудио на наличие криков"""
        if audio_data is None or len(audio_data) == 0:
            return {'scream_detected': False, 'confidence': 0.0}
        
        # Простая энергетическая детекция
        energy = np.mean(np.abs(audio_data))
        
        # Детекция резких звуков
        if energy > 0.1:  # Порог
            return {'scream_detected': True, 'confidence': min(1.0, energy * 2)}
        
        return {'scream_detected': False, 'confidence': 0.0}

class VideoStreamProcessor:
    """Обработчик видеопотока"""
    def __init__(self, config: Config):
        self.config = config
        self.object_detector = YOLODetector()
        self.action_detector = ActionDetector()
        self.audio_analyzer = AudioAnalyzer()
        self.frame_buffer = []
        self.stats = {
            'frames_processed': 0,
            'important_events': 0,
            'compression_ratio': 1.0
        }
        
    def process_frame(self, frame, audio_chunk=None):
        """Обработка одного кадра"""
        self.stats['frames_processed'] += 1
        
        # Детекция объектов
        detections = self.object_detector.detect(frame)
        
        # Детекция действий
        actions = self.action_detector.detect(frame, detections)
        
        # Анализ аудио
        audio_analysis = self.audio_analyzer.analyze(audio_chunk)
        
        # Расчет общей важности сцены
        scene_importance = self._calculate_scene_importance(detections, actions, audio_analysis)
        
        # Определение нужно ли сохранять кадр
        save_frame = self._should_save_frame(scene_importance)
        
        # Сбор метаданных
        metadata = {
            'timestamp': time.time(),
            'frame_index': self.stats['frames_processed'],
            'scene_importance': scene_importance,
            'detections': detections,
            'actions': actions,
            'audio_analysis': audio_analysis,
            'save_frame': save_frame
        }
        
        return metadata, save_frame
    
    def _calculate_scene_importance(self, detections, actions, audio_analysis):
        """Расчет важности сцены"""
        importance = 0.0
        
        # Важность от объектов
        for det in detections:
            importance += det.get('importance', 0.0)
        
        # Важность от действий
        for action in actions:
            if action['action'] in ['lying_down', 'approaching']:
                importance += 0.5
        
        # Важность от аудио
        if audio_analysis['scream_detected']:
            importance += audio_analysis['confidence'] * 0.8
        
        # Нормализация
        return min(1.0, importance / 3.0)
    
    def _should_save_frame(self, scene_importance):
        """Определение нужно ли сохранять кадр"""
        if scene_importance > self.config.importance_threshold:
            # Важная сцена - сохраняем чаще
            return self.stats['frames_processed'] % self.config.critical_skip_frames == 0
        else:
            # Неважная сцена - сохраняем реже
            return self.stats['frames_processed'] % self.config.base_skip_frames == 0

class MetadataManager:
    """Менеджер метаданных"""
    def __init__(self, output_dir='output'):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.metadata = []
        self.keyframes = []
        
    def add_metadata(self, metadata, frame):
        """Добавление метаданных"""
        self.metadata.append(metadata)
        
        if metadata['save_frame']:
            self.keyframes.append({
                'timestamp': metadata['timestamp'],
                'frame_index': metadata['frame_index'],
                'frame': frame.copy(),
                'detections': metadata['detections'],
                'actions': metadata['actions']
            })
    
    def save_all(self, video_name):
        """Сохранение всех данных"""
        # Сохранение метаданных в JSON
        metadata_path = self.output_dir / f"{video_name}_metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(self.metadata, f, indent=2, default=str, ensure_ascii=False)
        
        # Сохранение ключевых кадров
        keyframes_dir = self.output_dir / f"{video_name}_keyframes"
        keyframes_dir.mkdir(exist_ok=True)
        
        for i, kf in enumerate(self.keyframes):
            frame_path = keyframes_dir / f"keyframe_{i:06d}_{kf['timestamp']:.2f}.jpg"
            cv2.imwrite(str(frame_path), kf['frame'])
        
        logger.info(f"Сохранено {len(self.metadata)} записей метаданных")
        logger.info(f"Сохранено {len(self.keyframes)} ключевых кадров")

class SemanticVideoCompressor:
    """Главный класс системы семантического сжатия"""
    def __init__(self, config: Config):
        self.config = config
        self.processor = VideoStreamProcessor(config)
        self.metadata_manager = MetadataManager()
        self.video_writer = None
        self.is_recording_important = False
        self.important_segment_frames = []
        
    def process_webcam(self, camera_id=0, duration=None):
        """Обработка видео с веб-камеры"""
        cap = cv2.VideoCapture(camera_id)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.input_resolution[0])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.input_resolution[1])
        cap.set(cv2.CAP_PROP_FPS, self.config.processing_fps)
        
        start_time = time.time()
        frame_count = 0
        
        logger.info(f"Начата обработка видео с камеры {camera_id}")
        
        while True:
            ret, frame = cap.read()
            if not ret:
                logger.error("Не удалось получить кадр с камеры")
                break
            
            # Обработка кадра
            metadata, save_frame = self.processor.process_frame(frame)
            
            # Визуализация
            frame_display = self._visualize_frame(frame, metadata)
            
            # Управление записью
            self._manage_recording(frame, metadata, save_frame)
            
            # Сохранение метаданных
            self.metadata_manager.add_metadata(metadata, frame)
            
            # Отображение
            cv2.imshow('Semantic Video Compressor', frame_display)
            
            frame_count += 1
            
            # Проверка времени
            if duration and (time.time() - start_time) > duration:
                logger.info(f"Достигнута заданная длительность: {duration} сек")
                break
            
            # Выход по нажатию 'q'
            if cv2.waitKey(1) & 0xFF == ord('q'):
                logger.info("Остановка по команде пользователя")
                break
        
        # Завершение
        self._finalize_recording()
        cap.release()
        cv2.destroyAllWindows()
        
        # Сохранение результатов
        self.metadata_manager.save_all(f"webcam_{time.strftime('%Y%m%d_%H%M%S')}")
        
        # Вывод статистики
        self._print_statistics()
    
    def process_video_file(self, video_path):
        """Обработка видеофайла"""
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            logger.error(f"Не удалось открыть видеофайл: {video_path}")
            return
        
        video_name = Path(video_path).stem
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        
        logger.info(f"Начата обработка видео: {video_name}")
        logger.info(f"Всего кадров: {total_frames}, FPS: {fps}")
        
        frame_count = 0
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Пропуск кадров для ускорения обработки
            if frame_count % 2 != 0:  # Обрабатываем каждый второй кадр
                frame_count += 1
                continue
            
            # Изменение размера для обработки
            frame = cv2.resize(frame, self.config.input_resolution)
            
            # Обработка кадра
            metadata, save_frame = self.processor.process_frame(frame)
            
            # Управление записью
            self._manage_recording(frame, metadata, save_frame)
            
            # Сохранение метаданных
            self.metadata_manager.add_metadata(metadata, frame)
            
            frame_count += 1
            
            if frame_count % 100 == 0:
                logger.info(f"Обработано {frame_count}/{total_frames} кадров")
        
        # Завершение
        self._finalize_recording()
        cap.release()
        
        # Сохранение результатов
        self.metadata_manager.save_all(video_name)
        
        # Вывод статистики
        self._print_statistics()
    
    def _manage_recording(self, frame, metadata, save_frame):
        """Управление записью видео"""
        scene_importance = metadata['scene_importance']
        
        if scene_importance > self.config.importance_threshold:
            # Важное событие - начинаем/продолжаем запись
            if not self.is_recording_important:
                self._start_important_recording()
            
            self.important_segment_frames.append(frame)
            self.is_recording_important = True
        
        elif self.is_recording_important:
            # Завершаем запись важного сегмента
            self._save_important_segment()
            self.is_recording_important = False
    
    def _start_important_recording(self):
        """Начало записи важного сегмента"""
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        self.important_segment_file = f"important_segment_{timestamp}.mp4"
        
        # Инициализация VideoWriter для важного сегмента
        frame_height, frame_width = self.config.input_resolution[1], self.config.input_resolution[0]
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        self.segment_writer = cv2.VideoWriter(
            str(Path('output') / self.important_segment_file),
            fourcc,
            self.config.output_fps,
            (frame_width, frame_height)
        )
        
        logger.info(f"Начата запись важного сегмента: {self.important_segment_file}")
    
    def _save_important_segment(self):
        """Сохранение важного сегмента"""
        if hasattr(self, 'segment_writer') and self.segment_writer is not None:
            for frame in self.important_segment_frames:
                self.segment_writer.write(frame)
            
            self.segment_writer.release()
            logger.info(f"Сохранен важный сегмент: {self.important_segment_file}")
            
            # Очистка буфера
            self.important_segment_frames.clear()
    
    def _finalize_recording(self):
        """Завершение всех записей"""
        if self.is_recording_important:
            self._save_important_segment()
    
    def _visualize_frame(self, frame, metadata):
        """Визуализация информации на кадре"""
        frame_display = frame.copy()
        
        # Отображение детекций
        for det in metadata['detections']:
            x1, y1, x2, y2 = map(int, det['bbox'])
            cv2.rectangle(frame_display, (x1, y1), (x2, y2), (0, 255, 0), 2)
            
            label = f"{det['class_name']}: {det['confidence']:.2f}"
            cv2.putText(frame_display, label, (x1, y1-10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        # Отображение важности
        importance = metadata['scene_importance']
        color = (0, 0, 255) if importance > 0.5 else (0, 255, 255) if importance > 0.3 else (0, 255, 0)
        cv2.putText(frame_display, f"Importance: {importance:.2f}", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
        
        # Отображение действий
        if metadata['actions']:
            action_text = ", ".join([a['action'] for a in metadata['actions']])
            cv2.putText(frame_display, f"Actions: {action_text}", (10, 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        # Статус записи
        if self.is_recording_important:
            cv2.putText(frame_display, "RECORDING IMPORTANT", (10, 90),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        return frame_display
    
    def _print_statistics(self):
        """Вывод статистики обработки"""
        stats = self.processor.stats
        total_frames = stats['frames_processed']
        important_frames = self.metadata_manager.keyframes
        
        if total_frames > 0:
            compression_ratio = total_frames / max(1, len(important_frames))
            
            logger.info("=" * 50)
            logger.info("СТАТИСТИКА ОБРАБОТКИ")
            logger.info(f"Всего обработано кадров: {total_frames}")
            logger.info(f"Сохранено ключевых кадров: {len(important_frames)}")
            logger.info(f"Коэффициент сжатия: {compression_ratio:.2f}:1")
            logger.info(f"Важных событий: {stats['important_events']}")
            logger.info("=" * 50)

class MultiCameraManager:
    """Менеджер нескольких камер"""
    def __init__(self, config: Config):
        self.config = config
        self.cameras = {}
        self.lock = Lock()
    
    def add_camera(self, camera_id, source):
        """Добавление камеры"""
        compressor = SemanticVideoCompressor(self.config)
        self.cameras[camera_id] = {
            'compressor': compressor,
            'source': source,
            'thread': None,
            'active': False
        }
    
    def start_all(self):
        """Запуск всех камер"""
        for cam_id, cam_info in self.cameras.items():
            thread = Thread(target=self._process_camera, args=(cam_id,))
            cam_info['thread'] = thread
            cam_info['active'] = True
            thread.start()
            logger.info(f"Запущена камера {cam_id}")
    
    def _process_camera(self, camera_id):
        """Обработка одной камеры в отдельном потоке"""
        cam_info = self.cameras[camera_id]
        compressor = cam_info['compressor']
        source = cam_info['source']
        
        if isinstance(source, int) or source.startswith('rtsp://') or source.startswith('http://'):
            compressor.process_webcam(source, duration=None)
        else:
            compressor.process_video_file(source)
    
    def stop_all(self):
        """Остановка всех камер"""
        for cam_id, cam_info in self.cameras.items():
            cam_info['active'] = False
            if cam_info['thread']:
                cam_info['thread'].join()
        logger.info("Все камеры остановлены")

# Пример использования
if __name__ == "__main__":
    # Конфигурация
    config = Config(
        input_resolution=(1280, 720),
        processing_fps=15,
        compression_profile="balanced",
        use_yolo=True
    )
    
    # Создание компрессора
    compressor = SemanticVideoCompressor(config)
    
    # Выбор режима работы
    print("Выберите режим работы:")
    print("1. Веб-камера")
    print("2. Видеофайл")
    print("3. Несколько камер")
    
    choice = input("Введите номер: ")
    
    if choice == "1":
        # Обработка веб-камеры
        camera_id = int(input("Номер камеры (0 для встроенной): ") or "0")
        duration = int(input("Длительность в секундах (0 для бесконечной): ") or "0")
        compressor.process_webcam(camera_id, duration if duration > 0 else None)
    
    elif choice == "2":
        # Обработка видеофайла
        video_path = input("Путь к видеофайлу: ")
        compressor.process_video_file(video_path)
    
    elif choice == "3":
        # Многокамерный режим
        manager = MultiCameraManager(config)
        
        # Добавление камер (пример)
        manager.add_camera("cam1", 0)  # Веб-камера 0
        manager.add_camera("cam2", "test_video.mp4")  # Видеофайл
        
        try:
            manager.start_all()
            input("Нажмите Enter для остановки всех камер...")
        finally:
            manager.stop_all()
    
    else:
        print("Неверный выбор")