#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import psycopg2
from psycopg2 import sql
import sys

from db import keys


# ===========================
# Настройки подключения
# ===========================
DB_PARAMS = keys.DB_PARAMS

# ===========================
# SQL-команды для создания DATABASE
# ===========================
DATABASE_SQL="""
CREATE DATABASE postgres
    WITH
    OWNER = postgres
    ENCODING = 'UTF8'
    LC_COLLATE = 'Russian_Russia.1251'
    LC_CTYPE = 'Russian_Russia.1251'
    LOCALE_PROVIDER = 'libc'
    TABLESPACE = pg_default
    CONNECTION LIMIT = -1
    IS_TEMPLATE = False;

COMMENT ON DATABASE postgres
    IS 'default administrative connection database';
"""
# ===========================
# SQL-команды для создания таблиц
# ===========================
SCHEMA_SQL = """
CREATE DATABASE IF NOT EXISTS media_storage;
CREATE SCHEMA IF NOT EXISTS media_storage;
"""

TABLES_SQL = """
-- Таблица пользователей
CREATE TABLE IF NOT EXISTS media_storage.users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    last_login TIMESTAMP
);

-- Таблица видеозаписей
CREATE TABLE IF NOT EXISTS media_storage.videos (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES media_storage.users(id) ON DELETE CASCADE,
    filepath TEXT NOT NULL,
    title VARCHAR(255),
    description TEXT,
    duration FLOAT,
    resolution VARCHAR(20),
    uploaded_at TIMESTAMP DEFAULT NOW(),
    source_id INT REFERENCES media_storage.data_sources(id)
);

-- Таблица сцен
CREATE TABLE IF NOT EXISTS media_storage.scenes (
    id SERIAL PRIMARY KEY,
    video_id INT NOT NULL REFERENCES media_storage.videos(id) ON DELETE CASCADE,
    start_time FLOAT NOT NULL,
    end_time FLOAT NOT NULL,
    description TEXT
);

-- Таблицы тегов
CREATE TABLE IF NOT EXISTS media_storage.tags (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS media_storage.video_tags (
    video_id INT REFERENCES media_storage.videos(id) ON DELETE CASCADE,
    tag_id INT REFERENCES media_storage.tags(id) ON DELETE CASCADE,
    PRIMARY KEY(video_id, tag_id)
);

CREATE TABLE IF NOT EXISTS media_storage.scene_tags (
    scene_id INT REFERENCES media_storage.scenes(id) ON DELETE CASCADE,
    tag_id INT REFERENCES media_storage.tags(id) ON DELETE CASCADE,
    PRIMARY KEY(scene_id, tag_id)
);

-- Таблица событий
CREATE TABLE IF NOT EXISTS media_storage.events (
    id SERIAL PRIMARY KEY,
    video_id INT REFERENCES media_storage.videos(id) ON DELETE CASCADE,
    scene_id INT REFERENCES media_storage.scenes(id) ON DELETE CASCADE,
    event_type VARCHAR(100) NOT NULL,
    timestamp TIMESTAMP DEFAULT NOW(),
    details JSONB
);

-- Таблица источников данных
CREATE TABLE IF NOT EXISTS media_storage.data_sources (
    id SERIAL PRIMARY KEY,
    source_type VARCHAR(50) NOT NULL,
    connection_params JSONB,
    description TEXT
);

-- Таблицы для аудита
CREATE TABLE IF NOT EXISTS media_storage.audit_log_header (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT NOW(),
    table_name VARCHAR(100) NOT NULL,
    row_key TEXT,
    user_id INT REFERENCES media_storage.users(id),
    action VARCHAR(10) NOT NULL
);

CREATE TABLE IF NOT EXISTS media_storage.audit_log_detail (
    id SERIAL PRIMARY KEY,
    log_id INT REFERENCES media_storage.audit_log_header(id) ON DELETE CASCADE,
    field_name VARCHAR(100) NOT NULL,
    old_value TEXT,
    new_value TEXT
);

-- Таблица эмбеддингов
CREATE TABLE IF NOT EXISTS media_storage.embeddings (
    id SERIAL PRIMARY KEY,
    video_id INT REFERENCES media_storage.videos(id) ON DELETE CASCADE,
    scene_id INT REFERENCES media_storage.scenes(id) ON DELETE CASCADE,
    vector FLOAT8[],
    model_name VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_videos_user_id ON media_storage.videos(user_id);
CREATE INDEX IF NOT EXISTS idx_scenes_video_id ON media_storage.scenes(video_id);
CREATE INDEX IF NOT EXISTS idx_events_video_id ON media_storage.events(video_id);
CREATE INDEX IF NOT EXISTS idx_events_scene_id ON media_storage.events(scene_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_video_id ON media_storage.embeddings(video_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_scene_id ON media_storage.embeddings(scene_id);
"""

# ===========================
# Функция выполнения SQL
# ===========================
def execute_sql(conn, sql_commands):
    with conn.cursor() as cur:
        cur.execute(sql_commands)
        conn.commit()

# ===========================
# Основной запуск
# ===========================
def main():
    try:
        print("Подключаемся к базе данных...")
        conn = psycopg2.connect(**DB_PARAMS)
        print("Подключение установлено.")
        
        print("Создаем схему media_storage...")
        execute_sql(conn, SCHEMA_SQL)
        print("Схема создана или уже существует.")
        
        print("Создаем таблицы и индексы...")
        execute_sql(conn, TABLES_SQL)
        print("Таблицы и индексы созданы или уже существуют.")
        
        conn.close()
        print("Инициализация базы данных завершена успешно.")
    except Exception as e:
        print("Ошибка при инициализации базы данных:", e)
        sys.exit(1)

if __name__ == "__main__":
    main()
