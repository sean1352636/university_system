"""Progression: completion and movement beyond study.

Owns degree audit and graduation eligibility, credentials, portfolios,
placements, apprenticeships, the employer portal and employability outcomes.

Reads approved assessment outcomes through a query port rather than Assessment's
tables, and publishes completion and credential events for Learners and external
integrations.

Degree-audit *orchestration* still sits in Academics; the document moves it here
once that boundary is explicit, which needs Academics migrated first.
"""
