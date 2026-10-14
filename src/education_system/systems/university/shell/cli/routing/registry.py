from collections.abc import Iterable
from .errors import RouteNotFoundError
from .models import MenuRoute

class RouteRegistry:
    def __init__(self, routes: Iterable[MenuRoute] = ()):
        self._routes = {route.key: route for route in routes}

    def register(self, route: MenuRoute) -> None:
        self._routes[route.key] = route

    def resolve(self, key: str) -> MenuRoute:
        try:
            return self._routes[key]
        except KeyError as exc:
            raise RouteNotFoundError(key) from exc

    def __contains__(self, key: str) -> bool:
        return key in self._routes
