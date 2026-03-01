import cv2
import numpy as np
import datetime

# Захват с камеры
cap = cv2.VideoCapture(0)

# Кодек и инициализация записи
fourcc = cv2.VideoWriter_fourcc(*'XVID')
out = None

# Параметры

# Чувствительность системы движения
threshold = 50       # чувствительность
min_area = 500       # минимальный размер "события"

save_seconds = 3     # сколько секунд сохранять после события
frame_buffer = []    # буфер для хранения последних кадров
event_active = False
event_timer = 0

while True:
    ret, frame = cap.read()
    if not ret:
        break

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (21, 21), 0)

    # Первичный кадр для сравнения
    if len(frame_buffer) == 0:
        frame_buffer.append(gray)
        continue

    # Разница между текущим и предыдущим кадром
    delta = cv2.absdiff(frame_buffer[-1], gray)
    thresh = cv2.threshold(delta, threshold, 255, cv2.THRESH_BINARY)[1]
    thresh = cv2.dilate(thresh, None, iterations=2)
    contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    motion_detected = False
    for c in contours:
        if cv2.contourArea(c) > min_area:
            motion_detected = True
            break

    if motion_detected:
        if not event_active:
            print("Событие началось!")
            event_active = True
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            out = cv2.VideoWriter(f"event_{timestamp}.avi", fourcc, 20.0, (frame.shape[1], frame.shape[0]))
        event_timer = save_seconds * 30  # сбрасываем таймер, если движение есть
    else:
        if event_active:
            event_timer -= 1
            if event_timer <= 0:
                print("Событие закончилось.")
                event_active = False
                out.release()
                out = None

    # Обновляем буфер
    frame_buffer = [gray]

    # Отображение
    cv2.imshow("Camera", frame)
    # cv2.imshow("Thresh", thresh)
    # cv2.imshow("Delta", delta)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
if out:
    out.release()
cv2.destroyAllWindows()
## ffmpeg