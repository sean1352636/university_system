from education_system.paths import PLATFORM_AUTH_DB, SYSTEM_DB_PATHS
from education_system.paths import PLATFORM_AUTH_DB_FILE, VAR_DIR


def test_cross_system_registry_uses_runtime_var_databases():
    # Anchor on VAR_DIR, not PROGRAM_ROOT: the latter is the deprecated alias
    # for src/, so it stopped naming the runtime tree when var/ moved to the
    # repository root. A wrong anchor does not error, it just compares unequal.
    assert PLATFORM_AUTH_DB == PLATFORM_AUTH_DB_FILE
    assert SYSTEM_DB_PATHS == {
        "nursery": VAR_DIR / "data/nursery/nursery.db",
        "primary": VAR_DIR / "data/primary/primary.db",
        "secondary": VAR_DIR / "data/secondary/secondary.db",
        "sixth_form": VAR_DIR / "data/sixth_form/sixthform.db",
        "fe_college": VAR_DIR / "data/fe_college/fe_college.db",
        "apprenticeships": VAR_DIR / "data/apprenticeships/apprenticeships.db",
        "university": VAR_DIR / "data/university/db_files/student_records.db",
    }
