"""FE College to Sixth Form change-of-provider workflow.

The workflow lives in the platform's integration layer
(:mod:`education_system.platform.cross_system.sixth_form_transfers`), which
the Sixth Form's incoming queue also uses, so neither college imports the
other. FE's screens keep using this name for it.
"""

from __future__ import annotations

from education_system.platform.cross_system.sixth_form_transfers import (  # noqa: F401
    DESTINATION,
    SOURCE,
    TransferError,
    accept_offer,
    enrol,
    incoming,
    request_transfer,
    review_application,
)

__all__ = ["TransferError", "request_transfer", "review_application",
           "accept_offer", "enrol", "incoming"]
