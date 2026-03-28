# Backward-compatibility shim — re-exports everything from finance.core.payments
# Also imports third-party modules that tests may mock on this module path.
import sys as _sys

from education_system.university_system.modules.domain.finance.core import payments as _real

# Make this shim share the same module object so patches work correctly
_sys.modules[__name__] = _real
