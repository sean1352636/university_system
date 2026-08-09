from education_system.systems.university.domains.pastoral.domain.student_life.student_union.events.application.ports import AcademicCalendarManager

class AcademicCalendarGateway:
    def __init__(self):
        self.manager = AcademicCalendarManager() if AcademicCalendarManager else None
