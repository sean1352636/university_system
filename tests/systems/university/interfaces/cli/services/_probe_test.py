from education_system.systems.university.interfaces.cli.shell.services import medical_accommodation_cli as m
from education_system.systems.university.interfaces.cli.shell.services import carrental_cli as c
from education_system.systems.university.interfaces.cli.shell.services import equipment_rental_cli as e
import education_system.systems.university.infrastructure.database.db as db


def test_probe():
    print("SERVICE_AVAILABLE", m.SERVICE_AVAILABLE)
    print("TEMPLATES_TABLE", getattr(m, "TEMPLATES_TABLE", "MISSING"))
    print("carrental get_user", c.get_user)
    print("equip get_user", e.get_user)
    print("DEFAULT_DB_PATH", db.DEFAULT_DB_PATH)
    assert True
