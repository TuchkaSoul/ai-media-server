-- 1. ENUM TYPES

CREATE TYPE detection_type_enum AS ENUM ('object', 'action', 'face', 'anomaly');

CREATE TYPE alert_severity_enum AS ENUM ('low', 'medium', 'high', 'critical');

CREATE TYPE alert_status_enum AS ENUM ('new', 'acknowledged', 'resolved');

CREATE TYPE analysis_status_enum AS ENUM ('pending', 'running', 'completed', 'failed');

CREATE TYPE user_role_enum AS ENUM ('admin', 'operator', 'viewer');

CREATE TYPE video_status_enum AS ENUM ('recording', 'processed', 'archived', 'failed');

CREATE TYPE segment_type_enum AS ENUM ('keyframe', 'event', 'important', 'normal');

-- 2. HELPER FUNCTIONS & TRIGGERS

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE OR REPLACE FUNCTION create_monthly_partition(
    parent_table TEXT,
    start_date DATE
)
RETURNS VOID AS $$
DECLARE
    end_date DATE := (start_date + INTERVAL '1 month')::DATE;
    partition_name TEXT := parent_table || '_' || to_char(start_date, 'YYYY_MM');
BEGIN
    EXECUTE format(
        '
CREATE TABLE IF NOT EXISTS %I PARTITION OF %I
         FOR VALUES FROM (%L) TO (%L);',
        partition_name, parent_table, start_date, end_date
    );
END;
$$ LANGUAGE plpgsql;
CREATE OR REPLACE FUNCTION drop_old_partitions(
    parent_table TEXT,
    retention_months INTEGER
)
RETURNS VOID AS $$
DECLARE
    cutoff DATE := date_trunc('month', NOW()) - (retention_months || ' months')::INTERVAL;
    r RECORD;
BEGIN
    FOR r IN
        SELECT inhrelid::regclass AS partition_name
        FROM pg_inherits
        WHERE inhparent = parent_table::regclass
    LOOP
        IF r.partition_name::TEXT ~ '\d{4}_\d{2}$' THEN
            IF to_date(
                substring(r.partition_name::TEXT from '\d{4}_\d{2}$'),
                'YYYY_MM'
            ) < cutoff THEN
                EXECUTE format('DROP TABLE IF EXISTS %I;', r.partition_name);
            END IF;
        END IF;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- 3. CORE TABLES

CREATE TABLE cameras (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    location VARCHAR(500),
    owner VARCHAR(255),
    stream_url TEXT NOT NULL,
    resolution VARCHAR(50) DEFAULT '720p',
    fps INTEGER DEFAULT 15,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TRIGGER trg_cameras_updated
BEFORE UPDATE ON cameras
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();
CREATE TABLE models (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    version VARCHAR(100) NOT NULL,
    UNIQUE(name, version)
);

CREATE TABLE storage_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    codec VARCHAR(50) NOT NULL,
    bitrate_kbps INTEGER NOT NULL,
    resolution VARCHAR(50),
    fps INTEGER,
    retention_days INTEGER,
    archive_after_days INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. VIDEO DATA (Partitioned)

CREATE TABLE videos (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    camera_id UUID NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
    model_profile_id UUID REFERENCES storage_profiles(id) ON DELETE SET NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    file_path TEXT NOT NULL,
    file_size_mb DECIMAL(100,2),
    status video_status_enum DEFAULT 'recording',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    duration_sec INTEGER GENERATED ALWAYS AS (
        EXTRACT(EPOCH FROM (end_time - start_time))::INTEGER
    ) STORED,
    PRIMARY KEY (id, start_time)
) PARTITION BY RANGE (start_time);
CREATE INDEX idx_videos_camera ON videos(camera_id);

CREATE INDEX idx_videos_profile ON videos(model_profile_id);

CREATE INDEX idx_videos_start_time ON videos(start_time);
CREATE TABLE video_segments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id UUID NOT NULL,
    video_start_time TIMESTAMP NOT NULL,
    start_sec DECIMAL(10,3) NOT NULL,
    end_sec DECIMAL(10,3) NOT NULL,
    segment_type segment_type_enum DEFAULT 'normal',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT valid_segment_time CHECK (end_sec > start_sec),
    CONSTRAINT fk_segments_video
        FOREIGN KEY (video_id, video_start_time)
        REFERENCES videos(id, start_time)
        ON DELETE CASCADE
);
CREATE INDEX idx_segments_video ON video_segments(video_id, video_start_time);

CREATE INDEX idx_segments_type ON video_segments(segment_type);

-- 5. DETECTIONS & ALERTS (High Volume, Partitioned)

CREATE TABLE detections (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    video_id UUID NOT NULL,
    segment_id UUID,
    detection_type detection_type_enum NOT NULL,
    object_class VARCHAR(255),
    confidence DECIMAL(4,3) CHECK (confidence BETWEEN 0 AND 1),
    bbox_x DECIMAL(6,4) CHECK (bbox_x BETWEEN 0 AND 1),
    bbox_y DECIMAL(6,4) CHECK (bbox_y BETWEEN 0 AND 1),
    bbox_width DECIMAL(6,4) CHECK (bbox_width BETWEEN 0 AND 1),
    bbox_height DECIMAL(6,4) CHECK (bbox_height BETWEEN 0 AND 1),
    event_time TIMESTAMP NOT NULL,
    track_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id, event_time),
    FOREIGN KEY (segment_id)
        REFERENCES video_segments(id)
        ON DELETE SET NULL
) PARTITION BY RANGE (event_time);

CREATE INDEX idx_detections_video ON detections(video_id);

CREATE INDEX idx_detections_event_time ON detections(event_time);

CREATE INDEX idx_detections_track ON detections(track_id);

CREATE INDEX idx_detections_type ON detections(detection_type);
CREATE TABLE alerts (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    video_id UUID NOT NULL,
    detection_id UUID,
    alert_type VARCHAR(100) NOT NULL,
    severity alert_severity_enum DEFAULT 'medium',
    status alert_status_enum DEFAULT 'new',
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);
CREATE INDEX idx_alerts_video ON alerts(video_id);

CREATE INDEX idx_alerts_detection ON alerts(detection_id);

CREATE INDEX idx_alerts_status ON alerts(status);

CREATE INDEX idx_alerts_severity ON alerts(severity);

CREATE INDEX idx_alerts_created_at ON alerts(created_at);

-- 6. анализ и векторное храненение

CREATE TABLE analysis_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id UUID NOT NULL,
    video_start_time TIMESTAMP NOT NULL,
    model_id UUID REFERENCES models(id),
    analysis_type VARCHAR(100) NOT NULL,
    status analysis_status_enum DEFAULT 'pending',
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    parameters JSONB,
    results_summary JSONB,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_analysis_video
        FOREIGN KEY (video_id, video_start_time)
        REFERENCES videos(id, start_time)
        ON DELETE CASCADE
);
CREATE INDEX idx_analysis_video ON analysis_runs(video_id, video_start_time);

CREATE INDEX idx_analysis_model ON analysis_runs(model_id);

CREATE INDEX idx_analysis_status ON analysis_runs(status);
CREATE TABLE embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type VARCHAR(50) NOT NULL,
    entity_id UUID NOT NULL,
    qdrant_collection VARCHAR(100) NOT NULL,
    qdrant_point_id UUID NOT NULL,
    embedding_model VARCHAR(100) NOT NULL,
    embedding_dim INTEGER NOT NULL,
    delete_pending BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(entity_type, entity_id, embedding_model)
);
CREATE INDEX idx_embeddings_entity ON embeddings(entity_type, entity_id);

CREATE INDEX idx_embeddings_collection ON embeddings(qdrant_collection);

-- 7. логирование

CREATE TABLE processing_errors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type VARCHAR(50),
    entity_id UUID,
    error_code VARCHAR(100),
    error_message TEXT,
    trace_id UUID,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_errors_entity ON processing_errors(entity_type, entity_id);

CREATE INDEX idx_errors_time ON processing_errors(created_at);