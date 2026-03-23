FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app:/app/services

COPY services/video_stream/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY common /app/common
COPY services/video_stream /app/services/video_stream

EXPOSE 8080

CMD ["uvicorn", "services.video_stream.api:app", "--host", "0.0.0.0", "--port", "8080"]
