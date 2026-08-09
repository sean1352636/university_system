from education_system.paths import PLATFORM_AUTH_DB, SYSTEM_DB_PATHS
from education_system.paths import PLATFORM_AUTH_DB_FILE, PROGRAM_ROOT


def test_cross_system_registry_uses_runtime_var_databases():
    assert PLATFORM_AUTH_DB == PLATFORM_AUTH_DB_FILE
    assert SYSTEM_DB_PATHS == {
        "nursery": PROGRAM_ROOT / "var/data/nursery/nursery.db",
        "primary": PROGRAM_ROOT / "var/data/primary/primary.db",
        "secondary": PROGRAM_ROOT / "var/data/secondary/secondary.db",
        "sixth_form": PROGRAM_ROOT / "var/data/sixth_form/sixthform.db",
        "university": PROGRAM_ROOT / "var/data/university/db_files/student_records.db",
    }
