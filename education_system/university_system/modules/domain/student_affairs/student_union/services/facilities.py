from __future__ import annotations

from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.university_system.modules.domain.student_affairs.student_union.services import union_context as ctx
from education_system.university_system.core.i18n import get_text as _

def view_facilities():
    """View available facilities"""

    if not ctx.auth or not ctx.auth.current_user:
        print(_("errors.login_required"))
        return

    if not ctx.auth.check_permission('view_facilities'):
        print(_("errors.permission_denied"))
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Fetch all available facilities
        cursor.execute('''
        SELECT facility_id, facility_name, location, capacity, description, equipment, booking_fee
        FROM union_facilities
        WHERE status = 'available'
        ORDER BY facility_name
        ''')

        facilities = cursor.fetchall()

        if not facilities:
            print(_("student_union.facilities.no_facilities_found"))
            conn.close()
            return

        print(f"\n{_('student_union.facilities.available_facilities')}:")
        print("=" * 20)

        for facility in facilities:
            print(f"\n{_('common.id')}: {facility[0]}")
            print(f"{_('common.name')}: {facility[1]}")
            print(f"{_('student_union.facilities.location')}: {facility[2]}")
            print(f"{_('student_union.facilities.capacity')}: {facility[3]} {_('student_union.facilities.people')}")
            print(f"{_('common.description')}: {facility[4]}")
            print(f"{_('student_union.facilities.equipment')}: {facility[5]}")
            print(f"{_('student_union.facilities.booking_fee')}: £{facility[6]:.2f}")
            print("-" * 40)

        conn.close()
    except sqlite3.Error as e:
        print(_("common.database_error", error=str(e)))
