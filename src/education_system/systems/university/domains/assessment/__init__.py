"""Assessment: evidence and decisions about attainment.

Owns submissions, grading and grade calculation, learning outcomes, competency
assessment, academic progress, assessment boards, external examiners,
mitigating circumstances, and grade analytics and reports.

Assignment *authoring* stays in Academics: this slice consumes an assignment
identifier, never its persistence model. Progression reads approved outcomes
from here through a query port rather than reaching into these tables.
"""
