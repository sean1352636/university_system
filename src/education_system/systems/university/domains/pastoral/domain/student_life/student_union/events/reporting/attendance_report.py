def attendance_rate(*, attended: int, registered: int) -> float:
    return 0.0 if registered <= 0 else attended * 100.0 / registered
