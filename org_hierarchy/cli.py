"""Консольный интерфейс: команды import и find."""

import argparse
import sys

import psycopg2

from org_hierarchy.colleagues import UnitLookupError, find_colleagues
from org_hierarchy.db import connect
from org_hierarchy.importer import (
    ImportDataError,
    import_records,
    load_records,
)


def build_parser():
    """Создать парсер аргументов командной строки."""
    parser = argparse.ArgumentParser(
        prog='app.py',
        description='Оргструктура компании: импорт и поиск коллег по офису.',
    )
    subparsers = parser.add_subparsers(dest='command', required=True)

    import_parser = subparsers.add_parser(
        'import', help='загрузить данные из JSON-файла в базу',
    )
    import_parser.add_argument('path', help='путь к JSON-файлу')

    find_parser = subparsers.add_parser(
        'find', help='вывести всех сотрудников офиса по id сотрудника',
    )
    find_parser.add_argument('employee_id', type=int, help='id сотрудника')
    return parser


def run_import(path):
    """Выполнить команду import и вывести количество записей."""
    records = load_records(path)
    conn = connect()
    try:
        count = import_records(conn, records)
    finally:
        conn.close()
    print(f'Импортировано записей: {count}')


def run_find(employee_id):
    """Выполнить команду find и вывести офис и список сотрудников."""
    conn = connect()
    try:
        office_name, employees = find_colleagues(conn, employee_id)
    finally:
        conn.close()
    print(f'Офис: {office_name}')
    print('Сотрудники:')
    for name in employees:
        print(f'  {name}')


def main(argv=None):
    """Точка входа: разобрать аргументы и выполнить команду."""
    args = build_parser().parse_args(argv)
    try:
        if args.command == 'import':
            run_import(args.path)
        else:
            run_find(args.employee_id)
    except (ImportDataError, UnitLookupError) as error:
        print(f'Ошибка: {error}', file=sys.stderr)
        return 1
    except (OSError, ValueError) as error:
        print(f'Ошибка чтения файла: {error}', file=sys.stderr)
        return 1
    except psycopg2.Error as error:
        print(f'Ошибка базы данных: {error}', file=sys.stderr)
        return 3
    return 0
