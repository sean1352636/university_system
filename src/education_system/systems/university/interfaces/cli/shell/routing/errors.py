class MenuRoutingError(RuntimeError):
    """Base error for menu dispatch failures."""

class RouteNotFoundError(MenuRoutingError):
    """Raised when no route exists for a menu option."""

class RouteAuthorizationError(MenuRoutingError):
    """Raised when a user cannot access a route."""
