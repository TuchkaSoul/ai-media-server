import cv2
import collections
import time
from ultralytics import YOLO

# --- Настройки ---
BUFFER_SECONDS = 5
FPS = 30
EVENT_TIMEOUT = 3
TARGET_CLASSES = {"person", "cat", "dog"}  # ловим людей и животных

# --- Инициализация ---
cap = cv2.VideoCapture(0)
buffer = collections.deque(maxlen=BUFFER_SECONDS * FPS)
event_writer = None
last_detection_time = None
event_id = 0

# Загружаем предобученную модель YOLOv8
model = YOLO("yolo11x.pt")   # лёгкая версия для edge-устройств

while True:
    ret, frame = cap.read()
    if not ret:
        break

    frame_resized = cv2.resize(frame, (640, 480))
    buffer.append(frame_resized)

    # --- YOLO детекция ---
    results = model(frame_resized, verbose=False)
    detections = results[0].boxes

    detected = False
    for box in detections:
        cls_id = int(box.cls[0])
        cls_name = model.names[cls_id]
        if cls_name in TARGET_CLASSES:
            detected = True
            # Отрисуем прямоугольник
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            cv2.rectangle(frame_resized, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame_resized, cls_name, (x1, y1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    # --- Начало события ---
    if detected and event_writer is None:
        event_id += 1
        filename = f"event_{event_id}_{int(time.time())}.avi"
        event_writer = cv2.VideoWriter(
            filename, cv2.VideoWriter_fourcc(*'XVID'), FPS, (640, 480)
        )
        print(f"[INFO] Начато событие: {filename}")

        for f in buffer:
            event_writer.write(f)

    # --- Во время события ---
    if event_writer:
        event_writer.write(frame_resized)
        if detected:
            last_detection_time = time.time()

        if last_detection_time and (time.time() - last_detection_time > EVENT_TIMEOUT):
            print("[INFO] Событие завершено")
            event_writer.release()
            event_writer = None
            last_detection_time = None

    # --- Показ ---
    cv2.imshow("YOLO Detection", frame_resized)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
if event_writer:
    event_writer.release()
cv2.destroyAllWindows()
