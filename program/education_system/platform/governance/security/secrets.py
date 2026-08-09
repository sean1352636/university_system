"""Platform secret-provider boundary.

Applications request named secrets; they do not construct package-local paths.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from education_system.paths import VAR_DIR


class SecretNotAvailableError(RuntimeError):
    pass


class SecretProvider(Protocol):
    def get_bytes(self, name: str) -> bytes: ...
    def path_for(self, name: str) -> Path: ...


@dataclass(frozen=True, slots=True)
class EnvironmentSecretProvider:
    prefix: str = "EDUCATION_SECRET_"

    def _variable(self, name: str) -> str:
        return self.prefix + name.upper().replace("-", "_").replace(".", "_")

    def get_bytes(self, name: str) -> bytes:
        value = os.getenv(self._variable(name))
        if value is None:
            raise SecretNotAvailableError(f"Secret {name!r} is not configured")
        return value.encode()

    def path_for(self, name: str) -> Path:
        variable = self._variable(name) + "_FILE"
        value = os.getenv(variable)
        if not value:
            raise SecretNotAvailableError(
                f"Secret file reference {variable!r} is not configured"
            )
        return Path(value)


@dataclass(frozen=True, slots=True)
class DevelopmentFileSecretProvider:
    root: Path = VAR_DIR / "secrets"

    def _path(self, name: str) -> Path:
        if not name or any(part in {"", ".", ".."} for part in Path(name).parts):
            raise ValueError("Invalid secret name")
        path = (self.root / name).resolve()
        if self.root.resolve() not in path.parents:
            raise ValueError("Secret path escapes provider root")
        return path

    def get_bytes(self, name: str) -> bytes:
        path = self._path(name)
        try:
            value = path.read_bytes()
        except FileNotFoundError as exc:
            raise SecretNotAvailableError(f"Secret {name!r} is not configured") from exc
        if not value:
            raise SecretNotAvailableError(f"Secret {name!r} is empty")
        return value

    def path_for(self, name: str) -> Path:
        return self._path(name)


def get_secret_provider() -> SecretProvider:
    backend = os.getenv("EDUCATION_SECRET_PROVIDER", "environment").lower()
    if backend == "environment":
        return EnvironmentSecretProvider()
    if backend == "development-file":
        app_env = os.getenv("APP_ENV", "development").lower()
        if app_env not in {"development", "dev", "local", "test"}:
            raise SecretNotAvailableError(
                "Development file secrets are disabled outside development/test"
            )
        root = Path(
            os.getenv("EDUCATION_SECRET_DIR", VAR_DIR / "data" / "university" / "secrets")
        )
        return DevelopmentFileSecretProvider(root)
    raise SecretNotAvailableError(f"Unsupported secret provider {backend!r}")


__all__ = [
    "DevelopmentFileSecretProvider",
    "EnvironmentSecretProvider",
    "SecretNotAvailableError",
    "SecretProvider",
    "get_secret_provider",
]
