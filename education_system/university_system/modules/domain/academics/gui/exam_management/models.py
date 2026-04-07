"""Data models for the Exam Scheduling System."""

import json
from dataclasses import dataclass, asdict, field
from typing import List, Optional


@dataclass
class Exam:
    """Represents an exam entry."""
    id: int
    module_code: str  # Changed from course_code
    module_name: str  # Changed from course_name
    date: str
    start_time: str
    end_time: str
    room: str
    instructor_id: Optional[int]  # Now stores instructor ID
    instructor_name: str  # Display name
    students_enrolled: int
    enrolled_student_ids: List[str] = field(default_factory=list)  # List of student IDs

    # Legacy field names for backward compatibility
    @property
    def course_code(self):
        return self.module_code

    @property
    def course_name(self):
        return self.module_name

    @property
    def instructor(self):
        return self.instructor_name

    def to_dict(self):
        d = asdict(self)
        # Store enrolled_student_ids as JSON string for compatibility
        d['enrolled_student_ids'] = json.dumps(d.get('enrolled_student_ids', []))
        return d

    @classmethod
    def from_dict(cls, data: dict):
        """Create Exam from dictionary, handling legacy data."""
        # Handle legacy field names
        if 'course_code' in data and 'module_code' not in data:
            data['module_code'] = data.pop('course_code')
        if 'course_name' in data and 'module_name' not in data:
            data['module_name'] = data.pop('course_name')
        if 'instructor' in data and 'instructor_name' not in data:
            data['instructor_name'] = data.pop('instructor')
        # Handle instructor_id
        if 'instructor_id' not in data:
            data['instructor_id'] = None
        # Handle enrolled_student_ids
        if 'enrolled_student_ids' not in data:
            data['enrolled_student_ids'] = []
        elif isinstance(data['enrolled_student_ids'], str):
            try:
                data['enrolled_student_ids'] = json.loads(data['enrolled_student_ids'])
            except json.JSONDecodeError:
                data['enrolled_student_ids'] = []
        return cls(**data)


@dataclass
class Room:
    """Represents an exam room."""
    id: int
    name: str
    building: str
    capacity: int
    has_computers: bool
    has_projector: bool

    def to_dict(self):
        return asdict(self)
