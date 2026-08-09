"""The education systems.

Seven systems live here: nursery, primary, secondary, sixth_form and university
are the five mature ones; apprenticeships and fe_college are smaller but are
full members — both are wired into the launcher dispatch table, auth seeding,
the cross-system registry (their own student_journey slot, an entry in
``paths.SYSTEM_DB_PATHS`` and a PhaseAdapter) and both ship API routes.

Each system declares its own key, display name and interfaces in its
``manifest.py``. Do not restate those facts elsewhere — read them from
:mod:`education_system.systems.registry`, which collects every manifest.

The registry is deliberately not re-exported here: importing it loads all seven
system packages, and importing one system should not drag in the other six.
"""
