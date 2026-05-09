"""Analytics counterpart to ``modules/domain/research/external_quality_assurance``.

Surfaces the OfS / TEF / REF compliance metrics into the institutional
KPI dashboard. The compute logic lives in the source module; this file
exists so the analytics package owns its own entry point and can evolve
independently (e.g. to add trend lines or comparison cohorts).
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def compute_external_qa_kpis() -> list[dict]:
    """Re-export of the source-module compute function. Returns dicts in
    the shape ``KPIManager.record_kpi`` expects."""
    from education_system.university_system.modules.domain.research.external_quality_assurance.services import (
        qa_service as _qa,
    )
    return _qa.compute_external_qa_kpis()


def record_external_qa_kpis() -> int:
    """Recompute and persist all external-QA KPIs into ``kpi_metrics``."""
    from education_system.university_system.modules.domain.research.external_quality_assurance.services import (
        qa_service as _qa,
    )
    return _qa.record_external_qa_kpis()


__all__ = ["compute_external_qa_kpis", "record_external_qa_kpis"]
