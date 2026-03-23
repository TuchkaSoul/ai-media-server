FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app:/app/services

COPY services/api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY services/api/app /app/app
COPY services/api/alembic /app/alembic
COPY services/api/alembic.ini /app/alembic.ini
COPY services/video_stream /app/services/video_stream

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
