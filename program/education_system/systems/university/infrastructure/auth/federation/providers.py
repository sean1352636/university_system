from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class FederationProvider:
    name: str
    issuer: str
    enabled: bool = True
