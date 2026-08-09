from .authorization import authorize
from .models import MenuContext
from .registry import RouteRegistry

def dispatch(option: str, context: MenuContext, registry: RouteRegistry):
    route = registry.resolve(option)
    authorize(route, context.auth)
    return route.handler(context.auth)
