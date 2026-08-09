import re

def validate_password(password: str, *, minimum_length: int = 8) -> tuple[bool, str | None]:
    if len(password) < minimum_length:
        return False, f"password must contain at least {minimum_length} characters"
    if not re.search(r"[A-Z]", password) or not re.search(r"\d", password):
        return False, "password must contain an uppercase letter and a number"
    return True, None
