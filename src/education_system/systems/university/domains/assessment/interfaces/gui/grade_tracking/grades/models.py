from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class GradeRow:
    grade_id: int | None
    student_id: str
    assessment_id: str
    percentage: float
    letter_grade: str | None = None

@dataclass(frozen=True, slots=True)
class GradeFilter:
    student_id: str | None = None
    assessment_id: str | None = None

@dataclass(frozen=True, slots=True)
class GradeInput:
    student_id: str
    assessment_id: str
    percentage: float
