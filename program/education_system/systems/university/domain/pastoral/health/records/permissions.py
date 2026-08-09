def can_view_health_record(*, actor_user_id: int, student_id: int, is_health_staff: bool) -> bool:
    return actor_user_id == student_id or is_health_staff
