from dataclasses import dataclass, field
from collections.abc import Callable
from typing import Any

@dataclass(frozen=True, slots=True)
class MenuContext:
    auth: Any
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True, slots=True)
class MenuRoute:
    key: str
    handler: Callable[[Any], Any]
    permission: str | None = None
    description: str = ""
