# ai-media-server
# Информационной системы обработки и хранения потока видеоданных

---

# 1. Архитектурная модель системы

## Тип архитектуры

Микросервисная, событийно-ориентированная (event-driven), с асинхронной обработкой.

## Основные компоненты

1. API-шлюз (FastAPI)
2. Сервис видеозахвата
3. Сервис анализа (GPU worker)
4. Сервис хранения
5. Сервис семантического поиска
6. Очередь задач
7. Реляционная БД
8. Векторная БД
9. Объектное хранилище видео
10. Клиент

---

# 2. Технологический стек (финализированный)

## Backend API

* Язык: Python 3.11+
* Фреймворк: FastAPI
* Авторизация: JWT (OAuth2 Password Flow)
* Валидация: Pydantic v2
* ASGI сервер: Uvicorn / Gunicorn

## Асинхронные задачи

* Celery
* Redis (broker + result backend)

## Работа с БД

* PostgreSQL 15+
* SQLAlchemy 2.0 (ORM)
* Alembic (миграции)

## Векторный поиск

* Qdrant
* Метрика расстояния: Cosine
* Размерность: 512 (CLIP)

## Анализ видео

* OpenCV
* PyTorch
* YOLOv8 (детекция объектов)
* CLIP (семантические эмбеддинги)
* ViT / action model (действия)
* CUDA (при наличии GPU)

## Хранение видео

* Локальная файловая система (MVP)
* Структура: /storage/camera_id/YYYY/MM/DD/

## Логирование и мониторинг

* Loki
* Promtail
* Grafana
* Структурированное логирование (JSON)

## Контейнеризация

* Docker
* Docker Compose

---

# 3. Логическая схема модулей

```
Camera/RTSP
      ↓
Video Capture Service
      ↓
Frame Queue (Redis)
      ↓
Analysis Worker (GPU)
      ↓
 ┌──────────────┬───────────────┐
 │ PostgreSQL   │   Qdrant      │
 │ метаданные   │   эмбеддинги  │
 └──────────────┴───────────────┘
      ↓
Video Storage (disk)
      ↓
FastAPI
      ↓
Client (React / PyQt)
```

---

# 4. Подробная декомпозиция сервисов

---

## 4.1 API Service (FastAPI)

### Назначение:

* REST API
* Авторизация
* Управление камерами
* Поиск
* Получение архива
* Повторная обработка

### Основные эндпоинты:

```
POST   /auth/login
GET    /cameras
POST   /cameras
POST   /analysis/reprocess/{video_id}
GET    /events
GET    /events/{id}
POST   /search/semantic
GET    /video/stream/{camera_id}
```

---

## 4.2 Video Capture Service

### Назначение:

* Подключение к RTSP
* Захват кадров
* Нормализация FPS
* Отправка задач в очередь

### Технологии:

* OpenCV
* asyncio
* Redis

### Поведение:

* Каждый поток — отдельная асинхронная задача
* Буферизация кадров
* Ограничение до 8 камер

---

## 4.3 Analysis Worker (GPU Service)

### Назначение:

Полный семантический анализ кадров.

### Pipeline анализа:

1. Детекция объектов (YOLO)
2. Трекинг (ByteTrack / DeepSort — опционально)
3. Классификация сцены
4. Детекция действий
5. Вычисление важности сцены
6. Генерация CLIP эмбеддинга
7. Формирование события
8. Сохранение результатов

### Выходные данные:

* JSON метаданные
* embedding (512 float)
* bounding boxes
* labels
* scene_importance

---

## 4.4 Сервис хранения (Storage Layer)

### Физическая организация:

```
/storage/
    camera_1/
        2026/
            03/
                01/
                    segment_0001.mp4
                    segment_0002.mp4
```

### Тип записи:

* Сегментами по 1–5 минут
* H264/H265
* Индексация по timestamp

---

## 4.5 PostgreSQL — модель данных

### Основные сущности:

#### Camera

* id
* name
* location
* status
* rtsp_url
* created_at

#### VideoSegment

* id
* camera_id
* file_path
* start_time
* end_time
* checksum

#### FrameMetadata

* id
* segment_id
* timestamp
* scene_importance
* has_event

#### Detection

* id
* frame_id
* class_name
* confidence
* bbox
* track_id

#### Event

* id
* camera_id
* timestamp
* type
* importance_score
* embedding_id (Qdrant reference)

---

## 4.6 Qdrant — векторная модель

Collection: video_events
Размерность: 512
Distance: COSINE

Payload:

```
{
  "event_id": UUID,
  "camera_id": int,
  "timestamp": datetime,
  "event_type": str,
  "importance": float
}
```

---

# 5. Механизм повторной обработки (ключевая часть ВКР)

1. Загружается новая версия модели
2. Выбирается временной диапазон
3. Сегменты отправляются в Celery очередь
4. Пересчитываются эмбеддинги
5. Qdrant обновляется
6. Старые версии маркируются как obsolete

Это демонстрирует масштабируемость и эволюционность системы.

---

# 6. Сценарии потоков данных

## 6.1 Реальное время

Камера → Захват → Очередь → Анализ → БД → WebSocket клиент

## 6.2 Семантический поиск

Запрос текста → CLIP encode(text) → Qdrant search → Event list → UI

---

# 7. Требования к производительности

* До 8 потоков 720p
* 10–15 FPS обработка
* GPU ускорение
* Очередь задач не более 1000 сообщений
* Latency события < 2 секунд

---

# 8. Развертывание (Docker Compose)

Сервисы:

* api
* worker
* redis
* postgres
* qdrant
* loki
* grafana

---

# 9. Версионирование моделей

Структура:

```
models/
   yolo_x.pt
   clip_x.pt
   action_x.pt
```

В БД хранится:

* model_version
* applied_at

---

# 10. Безопасность

* JWT access + refresh
* Ролевой доступ (admin/operator/viewer)
* Хэширование паролей (bcrypt)
* Ограничение потоков

---

# 11. Текущий E2E pipeline

Основной backend: `services/api`

Legacy-слой: `services/orm_api.py` заморожен и не должен использоваться как точка входа.

Рабочий сценарий MVP:

1. `POST /cameras` регистрирует USB/web/IP-камеру или web URL.
2. `POST /cameras/{id}/start` подключает источник через `services/video_stream`.
3. API открывает активный `VideoSegment` и пишет метаданные кадров в PostgreSQL и `storage/videos/.../frames.jsonl`.
4. `GET /cameras/{id}/snapshot` отдает живой кадр.
5. `POST /frames/{frame_id}/analysis` принимает детекции/события от будущего analyzer/worker.

Ядро текущей схемы:

* `Camera`
* `VideoSegment`
* `FrameMetadata`
* `Detection`
* `Event`
