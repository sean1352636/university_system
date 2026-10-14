"""Request validation.

Merged surface over the three validators that existed side by side:

    delivery/api/validators.py            field helpers
    delivery/api/request_validator.py     request body/schema checks
    delivery/api/university/validators.py the large university rule set
                                          (53 importers)

Names are resolved in that order, with the university module last so its
richer rules win where they overlap — it is the one with real callers.
A physical merge of the 633-line university module is deliberately not
attempted here; this gives one import site first, so the duplication can
be removed against a passing test suite rather than blind.
"""

from education_system.platform.delivery.api.validators import (  # noqa: F401
    __dict__ as _field_ns,
)
from education_system.platform.delivery.api.request_validator import (  # noqa: F401
    __dict__ as _request_ns,
)
from education_system.platform.delivery.api.university.validators import (  # noqa: F401
    __dict__ as _university_ns,
)

for _ns in (_field_ns, _request_ns, _university_ns):
    globals().update({k: v for k, v in _ns.items() if not k.startswith("__")})
del _ns
