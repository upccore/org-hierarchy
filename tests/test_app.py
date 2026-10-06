"""Тесты импорта и поиска коллег на отдельной тестовой базе PostgreSQL."""

import os
from pathlib import Path

import psycopg2
import pytest

from org_hierarchy.db import connect
from org_hierarchy.importer import (
    ImportDataError,
    check_tree,
    import_records,
    load_records,
    parse_record,
)

DATA_PATH = Path(__file__).resolve().parent.parent / 'data.json'
TEST_DSN = os.environ.get(
    'TEST_DATABASE_URL',
    'postgresql://postgres:postgres@localhost:5432/org_hierarchy_test',
)


@pytest.fixture(scope='module')
def conn():
    """Подключиться к тестовой базе и загрузить в неё данные из задания."""
    try:
        connection = connect(TEST_DSN)
    except psycopg2.OperationalError:
        pytest.skip('Тестовая база недоступна, запустите docker compose up -d')
    import_records(connection, load_records(DATA_PATH))
    yield connection
    connection.close()


def test_reimport_is_idempotent(conn):
    """Повторный импорт не создаёт дубликатов."""
    import_records(conn, load_records(DATA_PATH))
    with conn.cursor() as cur:
        cur.execute('SELECT count(*) FROM org_unit')
        assert cur.fetchone()[0] == 19


def test_parse_record_accepts_any_key_case():
    """Ключи JSON читаются без учёта регистра."""
    record = {'Id': 1, 'parentId': None, 'NAME': ' Офис ', 'type': 1}
    assert parse_record(record) == (1, None, 'Офис', 1)


@pytest.mark.parametrize('record', [
    {'id': 1, 'ParentId': None, 'Name': 'X', 'Type': 5},
    {'id': 1, 'ParentId': None, 'Name': 'X', 'Type': True},
    {'id': True, 'ParentId': None, 'Name': 'X', 'Type': 1},
    {'id': 1, 'Id': 2, 'ParentId': None, 'Name': 'X', 'Type': 1},
])
def test_parse_record_rejects_bad_values(record):
    """Неизвестный Type, bool вместо числа и дубли ключей отклоняются."""
    with pytest.raises(ImportDataError):
        parse_record(record)


@pytest.mark.parametrize('records', [
    [(1, None, 'Офис', 1), (2, 99, 'Отдел', 2)],
    [(1, None, 'Отдел', 2)],
    [(1, None, 'Офис', 1), (2, 1, 'Иванов', 3)],
    [(1, None, 'Офис', 1), (2, 3, 'Отдел А', 2), (3, 2, 'Отдел Б', 2)],
])
def test_check_tree_rejects_bad_structure(records):
    """Нет родителя, корень не офис, сотрудник вне отдела, цикл."""
    with pytest.raises(ImportDataError):
        check_tree(records)


def test_load_records_rejects_empty_file(tmp_path):
    """Пустой массив не загружается, чтобы случайно не стереть данные."""
    path = tmp_path / 'empty.json'
    path.write_text('[]', encoding='utf-8')
    with pytest.raises(ImportDataError):
        load_records(path)
