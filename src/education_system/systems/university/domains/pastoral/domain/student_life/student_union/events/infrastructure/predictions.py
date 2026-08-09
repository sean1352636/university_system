def popularity_score(*, registrations: int, capacity: int | None) -> float:
    if not capacity:
        return float(registrations)
    return min(100.0, registrations * 100.0 / capacity)
