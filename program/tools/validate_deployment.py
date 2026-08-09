"""Static production-deployment validation for CI and operator preflight."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    base = root / "deploy" / "kubernetes" / "base"
    documents = []
    for path in base.glob("*.yaml"):
        documents.extend(item for item in yaml.safe_load_all(path.read_text()) if item)
    kinds = {item.get("kind") for item in documents}
    for required in {"Deployment", "Service", "ConfigMap", "PersistentVolumeClaim"}:
        if required not in kinds:
            errors.append(f"missing Kubernetes {required}")
    deployments = [item for item in documents if item.get("kind") == "Deployment"]
    for deployment in deployments:
        name = deployment["metadata"]["name"]
        containers = deployment["spec"]["template"]["spec"].get("containers", [])
        for container in containers:
            if "livenessProbe" not in container or "readinessProbe" not in container:
                errors.append(f"{name} lacks health probes")
            security = container.get("securityContext", {})
            if security.get("allowPrivilegeEscalation") is not False:
                errors.append(f"{name} permits privilege escalation")
    config = next((item for item in documents if item.get("kind") == "ConfigMap"), {})
    if config.get("data", {}).get("MULTI_TENANT_REQUIRED") != "true":
        errors.append("hosted deployment does not require tenant identity")
    return errors


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    errors = validate(root)
    if errors:
        print("Deployment validation failed: " + "; ".join(errors))
        return 1
    print("Deployment validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
