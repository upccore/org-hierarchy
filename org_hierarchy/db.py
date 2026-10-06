"""Подключение к базе данных и создание схемы."""

import os
from pathlib import Path

import psycopg2

# Значения поля type
OFFICE = 1
DEPARTMENT = 2
EMPLOYEE = 3

DEFAULT_DSN = 'postgresql://postgres:postgres@localhost:5432/org_hierarchy'
SCHEMA_PATH = Path(__file__).resolve().parent.parent / 'sql' / 'schema.sql'


def get_dsn():
    """Вернуть строку подключения из DATABASE_URL или значение по умолчанию."""
    return os.environ.get('DATABASE_URL', DEFAULT_DSN)


def connect(dsn=None):
    """Открыть соединение с PostgreSQL."""
    return psycopg2.connect(dsn or get_dsn())


def create_schema(conn):
    """Создать таблицу org_unit и индекс, если их ещё нет."""
    with conn.cursor() as cur:
        cur.execute(SCHEMA_PATH.read_text(encoding='utf-8'))
