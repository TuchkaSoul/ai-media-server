CREATE TABLE "cameras" (
  "id" integer PRIMARY KEY,
  "name" varchar,
  "location" varchar,
  "owner" varchar,
  "stream_url" text,
  "resolution" varchar,
  "fps" integer,
  "is_active" boolean,
  "created_at" timestamp
);

CREATE TABLE "events" (
  "id" uuid PRIMARY KEY,
  "video_id" uuid,
  "segment_id" uuid,
  "event_type" varchar,
  "description" text,
  "confidence" numeric,
  "start_sec" integer,
  "end_sec" integer,
  "model_name" varchar,
  "model_version" varchar,
  "created_at" timestamp
);

CREATE TABLE "storage_profiles" (
  "id" uuid PRIMARY KEY,
  "codec" varchar,
  "bitrate_kbps" integer,
  "compression_ratio" numeric,
  "quality_level" varchar,
  "created_at" timestamp
);

CREATE TABLE "tags" (
  "id" uuid PRIMARY KEY,
  "name" varchar,
  "tag_type" varchar,
  "created_at" timestamp
);

CREATE TABLE "entity_tags" (
  "id" uuid PRIMARY KEY,
  "tag_id" uuid,
  "entity_type" varchar,
  "entity_id" uuid,
  "created_at" timestamp
);

CREATE TABLE "videos" (
  "id" uuid PRIMARY KEY,
  "camera_id" integer,
  "storage_profile_id" uuid,
  "start_time" timestamp,
  "end_time" timestamp,
  "duration_sec" integer,
  "file_path" text,
  "file_size_mb" numeric,
  "status" varchar,
  "created_at" timestamp
);

CREATE TABLE "video_segments" (
  "id" uuid PRIMARY KEY,
  "video_id" uuid,
  "start_sec" integer,
  "end_sec" integer,
  "segment_type" varchar,
  "created_at" timestamp
);

CREATE TABLE "analysis_runs" (
  "id" uuid PRIMARY KEY,
  "video_id" uuid,
  "model_name" varchar,
  "model_version" varchar,
  "started_at" timestamp,
  "finished_at" timestamp,
  "status" varchar,
  "created_at" timestamp
);

CREATE TABLE "detected_objects" (
  "id" uuid PRIMARY KEY,
  "analysis_run_id" uuid,
  "segment_id" uuid,
  "object_class" varchar,
  "confidence" numeric,
  "bbox_x" numeric,
  "bbox_y" numeric,
  "bbox_width" numeric,
  "bbox_height" numeric,
  "timestamp_sec" integer,
  "created_at" timestamp
);

CREATE TABLE "embedding_index" (
  "id" uuid PRIMARY KEY,
  "detected_object_id" uuid,
  "qdrant_point_id" uuid,
  "embedding_type" varchar,
  "created_at" timestamp
);

CREATE TABLE "processing_errors" (
  "id" uuid PRIMARY KEY,
  "entity_type" varchar,
  "entity_id" uuid,
  "error_code" varchar,
  "error_message" text,
  "created_at" timestamp
);

CREATE TABLE "stream_sessions" (
  "id" uuid PRIMARY KEY,
  "camera_id" integer,
  "started_at" timestamp,
  "ended_at" timestamp,
  "status" varchar,
  "buffered_sec" integer,
  "created_at" timestamp
);

ALTER TABLE "stream_sessions" ADD FOREIGN KEY ("camera_id") REFERENCES "cameras" ("id");

ALTER TABLE "videos" ADD FOREIGN KEY ("camera_id") REFERENCES "cameras" ("id");

ALTER TABLE "video_segments" ADD FOREIGN KEY ("video_id") REFERENCES "videos" ("id");

ALTER TABLE "analysis_runs" ADD FOREIGN KEY ("video_id") REFERENCES "videos" ("id");

ALTER TABLE "detected_objects" ADD FOREIGN KEY ("analysis_run_id") REFERENCES "analysis_runs" ("id");

ALTER TABLE "detected_objects" ADD FOREIGN KEY ("segment_id") REFERENCES "video_segments" ("id");

ALTER TABLE "embedding_index" ADD FOREIGN KEY ("detected_object_id") REFERENCES "detected_objects" ("id");

ALTER TABLE "storage_profiles" ADD FOREIGN KEY ("id") REFERENCES "videos" ("id");

ALTER TABLE "events" ADD FOREIGN KEY ("video_id") REFERENCES "videos" ("id");

ALTER TABLE "events" ADD FOREIGN KEY ("segment_id") REFERENCES "video_segments" ("video_id");
