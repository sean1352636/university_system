def matches_identity(expected: dict, supplied: dict, fields: tuple[str, ...]) -> bool:
    return all(expected.get(field) == supplied.get(field) for field in fields)
