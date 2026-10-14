"""How much risk an employer poses to the apprenticeships they host.

A provider's apprenticeships mostly fail at the employer: the apprentice
is not released for training, reviews slip, promises are not kept. The
rating gathers the signals the system already holds — attendance,
off-the-job progress, reviews, commitments and the employer's own
satisfaction — and scores each against the thresholds in config. Every
point comes with a reason, so the rating is never a number nobody can
explain.

Missing data scores nothing. An employer with no rated attendance yet is
not penalised for it, and says so in the reasons instead.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from education_system.systems.apprenticeships import config


@dataclass
class EmployerRiskMetrics:
    """The raw figures a rating is worked out from."""

    employer_id: int
    employer_name: str
    employer_status: str = "Active"
    apprentices: int = 0
    active_apprentices: int = 0
    # Pooled across the active apprentices' registers.
    sessions_attended: int = 0
    sessions_countable: int = 0
    otj_on_track: int = 0
    reviews_completed: int = 0
    reviews_overdue: int = 0
    commitments_outstanding: int = 0
    commitments_overdue: int = 0
    highest_escalation: int = 0
    satisfaction: float | None = None
    feedback_count: int = 0

    @property
    def attendance_percent(self) -> float | None:
        """None until enough sessions are marked to mean something."""
        if self.sessions_countable < config.ATTENDANCE_MIN_SESSIONS:
            return None
        return round(self.sessions_attended / self.sessions_countable * 100, 1)

    @property
    def otj_compliance_percent(self) -> float | None:
        """Share of active apprentices on track with off-the-job hours."""
        if self.active_apprentices == 0:
            return None
        return round(self.otj_on_track / self.active_apprentices * 100, 1)


@dataclass
class EmployerRisk:
    """An employer's rating and the reasons behind it."""

    metrics: EmployerRiskMetrics
    level: str
    points: int
    reasons: list[str] = field(default_factory=list)

    @property
    def employer_id(self) -> int:
        return self.metrics.employer_id

    @property
    def employer_name(self) -> str:
        return self.metrics.employer_name

    @property
    def rag(self) -> str:
        return config.EMPLOYER_RISK_RAG.get(self.level, "Green")

    @property
    def sort_key(self) -> tuple[int, int, str]:
        """Highest risk first, then most points, then by name."""
        rank = config.EMPLOYER_RISK_LEVELS.index(self.level)
        return (-rank, -self.points, self.employer_name.casefold())


def assess(metrics: EmployerRiskMetrics) -> EmployerRisk:
    """Score every indicator and turn the total into Low, Medium or High."""
    points = 0
    reasons: list[str] = []

    def flag(score: int, reason: str) -> None:
        nonlocal points
        points += score
        reasons.append(f"{reason} (+{score})")

    attendance = metrics.attendance_percent
    if attendance is not None:
        if attendance < config.ATTENDANCE_CONCERN_PERCENT:
            flag(2, f"Attendance {attendance:.1f}%, below "
                    f"{config.ATTENDANCE_CONCERN_PERCENT:.0f}%")
        elif attendance < config.ATTENDANCE_TARGET_PERCENT:
            flag(1, f"Attendance {attendance:.1f}%, below the "
                    f"{config.ATTENDANCE_TARGET_PERCENT:.0f}% target")

    otj = metrics.otj_compliance_percent
    if otj is not None:
        detail = (f"{metrics.otj_on_track} of {metrics.active_apprentices} active "
                  f"apprentices on track with off-the-job hours ({otj:.0f}%)")
        if otj < config.EMPLOYER_RISK_OTJ_CONCERN_PERCENT:
            flag(2, f"Only {detail}")
        elif otj < config.EMPLOYER_RISK_OTJ_TARGET_PERCENT:
            flag(1, detail)

    if metrics.reviews_overdue >= config.EMPLOYER_RISK_OVERDUE_REVIEWS_CONCERN:
        flag(2, f"{metrics.reviews_overdue} progress reviews overdue")
    elif metrics.reviews_overdue:
        flag(1, f"{metrics.reviews_overdue} progress review"
                f"{'s' if metrics.reviews_overdue != 1 else ''} overdue")

    if metrics.commitments_overdue:
        flag(1, f"{metrics.commitments_overdue} commitment"
                f"{'s' if metrics.commitments_overdue != 1 else ''} overdue")
    if metrics.highest_escalation >= config.EMPLOYER_RISK_ESCALATION_CONCERN_LEVEL:
        label = config.COMMITMENT_ESCALATION_LEVELS.get(
            metrics.highest_escalation, str(metrics.highest_escalation)
        )
        flag(2, f"A commitment is escalated to level {metrics.highest_escalation} ({label})")

    if metrics.satisfaction is not None:
        if metrics.satisfaction < config.EMPLOYER_RISK_SATISFACTION_CONCERN:
            flag(2, f"Satisfaction {metrics.satisfaction:.1f} out of 5")
        elif metrics.satisfaction < config.EMPLOYER_RISK_SATISFACTION_TARGET:
            flag(1, f"Satisfaction {metrics.satisfaction:.1f} out of 5, below "
                    f"{config.EMPLOYER_RISK_SATISFACTION_TARGET:.1f}")

    if points >= config.EMPLOYER_RISK_HIGH_POINTS:
        level = "High"
    elif points >= config.EMPLOYER_RISK_MEDIUM_POINTS:
        level = "Medium"
    else:
        level = "Low"

    if not reasons:
        reasons.append("No risk indicators")
    if metrics.active_apprentices == 0:
        reasons.append("No active apprentices, so off-the-job progress is not assessed")
    elif attendance is None:
        reasons.append("Too few marked sessions to rate attendance yet")
    if metrics.satisfaction is None:
        reasons.append("No satisfaction feedback yet")

    return EmployerRisk(metrics=metrics, level=level, points=points, reasons=reasons)
