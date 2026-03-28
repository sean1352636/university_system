# Backward-compatibility shim — redirects to finance.core.finance_db_operations
import sys as _sys
from education_system.university_system.modules.domain.finance.core import finance_db_operations as _real
_sys.modules[__name__] = _real
