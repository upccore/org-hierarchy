"""Загрузка оргструктуры из JSON-файла в таблицу org_unit."""

import json

from psycopg2.extras import execute_values

from org_hierarchy.db import DEPARTMENT, EMPLOYEE, OFFICE, create_schema

# Какого типа может быть родитель у узла каждого типа.
# Офис всегда корень, отдел лежит в офисе или в другом отделе,
# сотрудник - только в отделе.
ALLOWED_PARENTS = {
    OFFICE: set(),
    DEPARTMENT: {OFFICE, DEPARTMENT},
    EMPLOYEE: {DEPARTMENT},
}


class ImportDataError(Exception):
    """Ошибка в содержимом импортируемого файла."""


def _get_field(record, name):
    """Получить поле записи без учёта регистра ключа."""
    values = [value for key, value in record.items()
              if key.lower() == name.lower()]
    if not values:
        raise ImportDataError(f'В записи {record} нет поля {name!r}')
    if len(values) > 1:
        raise ImportDataError(f'В записи {record} поле {name!r} повторяется')
    return values[0]


def _is_int(value):
    """Проверить, что значение - целое число (bool не считается)."""
    return isinstance(value, int) and not isinstance(value, bool)


def parse_record(record):
    """Преобразовать запись JSON в кортеж (id, parent_id, name, type)."""
    if not isinstance(record, dict):
        raise ImportDataError(f'Ожидался объект, получено: {record!r}')
    unit_id = _get_field(record, 'id')
    parent_id = _get_field(record, 'parentid')
    name = _get_field(record, 'name')
    unit_type = _get_field(record, 'type')
    if not _is_int(unit_id):
        raise ImportDataError(f'Некорректный id: {unit_id!r}')
    if parent_id is not None and not _is_int(parent_id):
        raise ImportDataError(f'Некорректный ParentId у id={unit_id}')
    if not isinstance(name, str) or not name.strip():
        raise ImportDataError(f'Пустое имя у id={unit_id}')
    if not _is_int(unit_type) or unit_type not in ALLOWED_PARENTS:
        raise ImportDataError(f'Неизвестный Type={unit_type!r} у id={unit_id}')
    return unit_id, parent_id, name.strip(), unit_type


def check_tree(records):
    """Проверить ссылки на родителей, вложенность типов и отсутствие циклов."""
    types = {unit_id: unit_type for unit_id, _, _, unit_type in records}
    parents = {unit_id: parent_id for unit_id, parent_id, _, _ in records}

    for unit_id, parent_id, _, unit_type in records:
        if parent_id is None:
            if unit_type != OFFICE:
                raise ImportDataError(f'У id={unit_id} нет родителя, '
                                      f'но это не офис')
            continue
        if parent_id not in types:
            raise ImportDataError(f'У id={unit_id} указан несуществующий '
                                  f'ParentId={parent_id}')
        if types[parent_id] not in ALLOWED_PARENTS[unit_type]:
            raise ImportDataError(f'id={unit_id} (Type={unit_type}) не может '
                                  f'находиться внутри id={parent_id} '
                                  f'(Type={types[parent_id]})')

    for unit_id in parents:
        seen = set()
        node = unit_id
        while node is not None:
            if node in seen:
                raise ImportDataError(f'Цикл в иерархии через id={node}')
            seen.add(node)
            node = parents[node]


def load_records(path):
    """Прочитать JSON-файл и вернуть список проверенных записей."""
    with open(path, encoding='utf-8') as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise ImportDataError('Корнем JSON должен быть массив')
    if not data:
        raise ImportDataError('Файл не содержит ни одной записи')
    records = [parse_record(item) for item in data]
    ids = [record[0] for record in records]
    if len(ids) != len(set(ids)):
        raise ImportDataError('В файле есть повторяющиеся id')
    check_tree(records)
    return records


def import_records(conn, records):
    """Заменить содержимое org_unit переданными записями в одной транзакции."""
    with conn:
        create_schema(conn)
        with conn.cursor() as cur:
            cur.execute('TRUNCATE org_unit')
            execute_values(
                cur,
                'INSERT INTO org_unit (id, parent_id, name, type) VALUES %s',
                records,
            )
    return len(records)
