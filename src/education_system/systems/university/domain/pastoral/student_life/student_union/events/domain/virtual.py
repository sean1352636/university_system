def validate_virtual_event(*, event_type: str, meeting_url: str | None) -> None:
    if event_type.lower() in {"virtual", "hybrid"} and not meeting_url:
        raise ValueError("virtual and hybrid events require a meeting URL")
