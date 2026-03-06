CREATE SCHEMA IF NOT EXISTS mediahub;

CREATE TABLE IF NOT EXISTS mediahub.users (
    id BIGSERIAL PRIMARY KEY,
    username VARCHAR(128) NOT NULL UNIQUE,
    email VARCHAR(256) UNIQUE,
    password_hash TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS mediahub.cameras (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    source_uri TEXT NOT NULL,
    source_type VARCHAR(64) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS mediahub.videos (
    id BIGSERIAL PRIMARY KEY,
    camera_id BIGINT REFERENCES mediahub.cameras(id) ON DELETE SET NULL,
    storage_path TEXT NOT NULL,
    duration_seconds NUMERIC(10, 3),
    started_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS mediahub.analysis_tasks (
    id BIGSERIAL PRIMARY KEY,
    video_id BIGINT REFERENCES mediahub.videos(id) ON DELETE CASCADE,
    status VARCHAR(32) NOT NULL DEFAULT 'queued',
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS mediahub.detections (
    id BIGSERIAL PRIMARY KEY,
    task_id BIGINT REFERENCES mediahub.analysis_tasks(id) ON DELETE CASCADE,
    label VARCHAR(128) NOT NULL,
    confidence NUMERIC(6, 5),
    timestamp_seconds NUMERIC(10, 3) NOT NULL,
    bbox JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS mediahub.alerts (
    id BIGSERIAL PRIMARY KEY,
    task_id BIGINT REFERENCES mediahub.analysis_tasks(id) ON DELETE CASCADE,
    level VARCHAR(32) NOT NULL,
    message TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS mediahub.system_logs (
    id BIGSERIAL PRIMARY KEY,
    service_name VARCHAR(128) NOT NULL,
    level VARCHAR(16) NOT NULL,
    message TEXT NOT NULL,
    context JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
