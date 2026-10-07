"""Поиск всех сотрудников офиса по идентификатору сотрудника."""

from org_hierarchy.db import DEPARTMENT, EMPLOYEE, OFFICE

# Сначала поднимаемся от сотрудника вверх до офиса, затем спускаемся от
# офиса вниз по всем отделам и забираем сотрудников. Название офиса
# протаскивается по рекурсии, чтобы получить всё одним запросом.
FIND_COLLEAGUES_SQL = """
WITH RECURSIVE ancestors AS (
    SELECT id, parent_id, name, type
    FROM org_unit
    WHERE id = %(employee_id)s AND type = %(employee)s
    UNION
    SELECT u.id, u.parent_id, u.name, u.type
    FROM org_unit u
    JOIN ancestors a ON u.id = a.parent_id
    WHERE a.type <> %(office)s
),
descendants AS (
    SELECT id, name, type, name AS office_name
    FROM ancestors
    WHERE type = %(office)s
    UNION
    SELECT u.id, u.name, u.type, d.office_name
    FROM org_unit u
    JOIN descendants d ON u.parent_id = d.id
)
SELECT office_name, name
FROM descendants
WHERE type = %(employee)s
ORDER BY id
"""


FIND_UNIT_SQL = 'SELECT name, type FROM org_unit WHERE id = %s'

UNIT_TYPE_NAMES = {
    OFFICE: 'офис',
    DEPARTMENT: 'отдел',
}


class UnitLookupError(Exception):
    """Сотрудник с таким id не найден или id принадлежит не сотруднику."""


def describe_missing_employee(conn, employee_id):
    """Объяснить, почему по id не нашёлся сотрудник."""
    with conn.cursor() as cur:
        cur.execute(FIND_UNIT_SQL, (employee_id,))
        unit = cur.fetchone()
    if unit is None:
        return f'запись с id={employee_id} не найдена'
    name, unit_type = unit
    return (f'id={employee_id} - это {UNIT_TYPE_NAMES[unit_type]} '
            f'«{name}», а не сотрудник')


def find_colleagues(conn, employee_id):
    """Вернуть название офиса и список его сотрудников по id сотрудника."""
    params = {
        'employee_id': employee_id,
        'employee': EMPLOYEE,
        'office': OFFICE,
    }
    with conn.cursor() as cur:
        cur.execute(FIND_COLLEAGUES_SQL, params)
        rows = cur.fetchall()
    if not rows:
        raise UnitLookupError(describe_missing_employee(conn, employee_id))
    return rows[0][0], [name for _, name in rows]
