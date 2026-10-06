"""Тесты импорта и поиска коллег на отдельной тестовой базе PostgreSQL."""

import os
from pathlib import Path

import psycopg2
import pytest

from org_hierarchy.cli import main
from org_hierarchy.colleagues import UnitLookupError, find_colleagues
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
SPB = 'Офис в Санкт-Петербурге'
MOSCOW = 'Офис в Москве'
MOSCOW_EMPLOYEES = [
    'Винтиков', 'Шпунтиков', 'Белова', 'Крылова',
    'Петрова', 'Иванова', 'Морозов',
]


@pytest.fixture(scope='module')
def conn():
    """Подключиться к тестовой базе и загрузить в неё данные из задания."""
    try:
        connection = connect(TEST_DSN)
    except psycopg2.OperationalError:
        pytest.skip('Тестовая база недоступна, запустите docker compose up -d')
    # CLI сам открывает соединение по DATABASE_URL - направляем его туда же.
    old_dsn = os.environ.get('DATABASE_URL')
    os.environ['DATABASE_URL'] = TEST_DSN
    import_records(connection, load_records(DATA_PATH))
    yield connection
    connection.close()
    if old_dsn is None:
        del os.environ['DATABASE_URL']
    else:
        os.environ['DATABASE_URL'] = old_dsn


def test_example_from_task(conn):
    """Пример из задания: id=3 даёт сотрудников офиса Санкт-Петербурга."""
    assert find_colleagues(conn, 3) == (SPB, ['Иванов', 'Сидоров', 'Петров'])


@pytest.mark.parametrize('employee_id', [9, 13, 17, 20])
def test_nested_departments(conn, employee_id):
    """Сотрудники вложенных отделов находят весь московский офис."""
    assert find_colleagues(conn, employee_id) == (MOSCOW, MOSCOW_EMPLOYEES)


@pytest.mark.parametrize('unit_id', [1, 2, 12, 999])
def test_not_an_employee(conn, unit_id):
    """Офис, отдел или несуществующий id дают ошибку поиска."""
    with pytest.raises(UnitLookupError):
        find_colleagues(conn, unit_id)


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


def test_cli_find(conn, capsys):
    """Команда find печатает офис и сотрудников."""
    assert main(['find', '3']) == 0
    output = capsys.readouterr().out
    assert SPB in output
    assert 'Сидоров' in output


def test_cli_find_error(conn, capsys):
    """Команда find для отдела завершается с кодом 1."""
    assert main(['find', '2']) == 1
    assert 'не найден' in capsys.readouterr().err
