from .models import GradeInput
from .scale import percentage_to_letter

def validate_grade(value: GradeInput) -> GradeInput:
    if not 0 <= value.percentage <= 100:
        raise ValueError("percentage must be between 0 and 100")
    return value

def prepare_grade(value: GradeInput):
    value = validate_grade(value)
    return value, percentage_to_letter(value.percentage)
