FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app

COPY services/worker/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY common /app/common
COPY services/worker/worker /app/worker

CMD ["celery", "-A", "worker.celery_app.celery_app", "worker", "--loglevel=info"]
