# Backward-compatibility shim: finance_misc was restructured into finance.core
# This package re-exports submodules so existing imports and test mocks continue to work.

from education_system.university_system.modules.domain.finance.core import (
    aid,
    analytics,
    communications,
    finance_db_operations,
    menu,
    payments,
    students,
)
