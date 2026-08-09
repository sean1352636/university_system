"""Apprenticeships system.

Work-based learning: an apprentice is employed, trained partly on the job
and partly off it, and finishes with an independently assessed End-Point
Assessment (EPA). That makes it structurally unlike the five school-shaped
systems — there are five parties round every apprentice, not two:

* **admin**              — provider staff who run the programme portfolio,
                           employer contracts, funding and compliance
* **staff**              — tutors / trainers / assessors delivering training
                           and holding a caseload
* **apprentice**         — the learner
* **employer**           — the employing organisation, a signatory to the
                           training plan and a participant in every review
* **end_point_assessor** — the independent EPAO assessor, who must not see
                           the provider's formative judgements

Each role gets its own CLI menu tree and GUI window set under
``interfaces/``; ``config.ROLE_PERMISSIONS`` is the single place that says
who may do what, and both interfaces read it rather than hard-coding
visibility.
"""

SYSTEM_NAME: str = "Apprenticeships System"
SYSTEM_SLUG: str = "apprenticeships"
SYSTEM_KEY: str = "apprenticeships"
VERSION: str = "1.0.0"

__all__ = ["SYSTEM_KEY", "SYSTEM_NAME", "SYSTEM_SLUG", "VERSION"]
