from importlib import import_module
from collections.abc import Callable
from .errors import MenuRoutingError

def load_handler(module_path: str, function_name: str) -> Callable:
    try:
        module = import_module(module_path)
        handler = getattr(module, function_name)
    except (ImportError, AttributeError) as exc:
        raise MenuRoutingError(
            f"Unable to load {module_path}.{function_name}"
        ) from exc
    if not callable(handler):
        raise MenuRoutingError(f"{module_path}.{function_name} is not callable")
    return handler
