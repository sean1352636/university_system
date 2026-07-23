from education_system.post_18.university_system.modules.services.cli import medical_accommodation_cli as m
from education_system.post_18.university_system.modules.services.cli import carrental_cli as c
from education_system.post_18.university_system.modules.services.cli import equipment_rental_cli as e
import education_system.post_18.university_system.infrastructure.database.db as db


def test_probe():
    print("SERVICE_AVAILABLE", m.SERVICE_AVAILABLE)
    print("TEMPLATES_TABLE", getattr(m, "TEMPLATES_TABLE", "MISSING"))
    print("carrental get_user", c.get_user)
    print("equip get_user", e.get_user)
    print("DEFAULT_DB_PATH", db.DEFAULT_DB_PATH)
    assert True
