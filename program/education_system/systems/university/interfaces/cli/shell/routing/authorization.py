from .errors import RouteAuthorizationError
from .models import MenuRoute

def authorize(route: MenuRoute, auth) -> None:
    if route.permission is None:
        return
    checker = getattr(auth, "has_permission", None)
    if not callable(checker) or not checker(route.permission):
        raise RouteAuthorizationError(route.permission)
