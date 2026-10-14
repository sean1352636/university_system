"""Static production-deployment validation for CI and operator preflight.

Two layers:

* :func:`validate` reads the checked-in deployment manifests. It runs anywhere,
  needs no database, and is what CI should gate on.
* :func:`validate_runtime_posture` inspects a live ``auth.db``. Some production
  requirements — MFA enforcement, forced password rotation — are database
  state, not manifest keys, so a manifest check cannot see them. Run it against
  the target environment before go-live with ``--runtime``.

The runtime layer is deliberately opt-in: development databases are expected to
fail it, and that is not a CI failure.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

import yaml

#: Roles that must not be reachable with a single factor in production.
PRIVILEGED_ROLES = ("admin", "superadmin")


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

    # The application config ships ssl_enabled=false and speaks plain HTTP, which
    # is only safe because TLS terminates in front of it. If the ingress stops
    # doing that, the API is served in clear with no other signal.
    ingress = next((item for item in documents if item.get("kind") == "Ingress"), None)
    if ingress is None:
        errors.append("no Ingress: nothing terminates TLS in front of the API")
    else:
        if not ingress.get("spec", {}).get("tls"):
            errors.append("Ingress has no tls block: API would be served over plain HTTP")
        annotations = ingress.get("metadata", {}).get("annotations", {})
        redirect = annotations.get("nginx.ingress.kubernetes.io/ssl-redirect")
        if str(redirect).lower() != "true":
            errors.append("Ingress does not force ssl-redirect")
    return errors


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def validate_runtime_posture(auth_db: Path) -> list[str]:
    """Check the security posture recorded in a live ``auth.db``.

    Never reads or tests a password — only whether policy rows exist and
    whether privileged accounts have ever rotated their seeded credential.
    """
    errors: list[str] = []
    if not auth_db.exists():
        return [f"auth database not found at {auth_db}"]

    conn = sqlite3.connect(f"file:{auth_db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        # MFA enforcement — the mechanism exists and is read at login; an empty
        # policy table means no role, including admin, is ever challenged.
        if _table_exists(conn, "mfa_enforcement_policies"):
            enforced = {
                str(r["role_name"]).lower()
                for r in conn.execute(
                    "SELECT role_name FROM mfa_enforcement_policies "
                    "WHERE mfa_required = 1"
                )
            }
            missing = [r for r in PRIVILEGED_ROLES if r not in enforced]
            if missing:
                errors.append(
                    "MFA is not required for privileged role(s): "
                    + ", ".join(missing)
                )
        else:
            errors.append("mfa_enforcement_policies table is absent")

        # Forced password rotation.
        if _table_exists(conn, "auth_settings"):
            settings = {
                str(r["key"]): str(r["value"]).lower()
                for r in conn.execute("SELECT key, value FROM auth_settings")
            }
            disabled = sorted(
                k for k, v in settings.items()
                if k.startswith("force_password_reset") and v != "true"
            )
            if disabled:
                errors.append(
                    f"forced password reset is disabled for {len(disabled)} "
                    f"scope(s): {', '.join(disabled[:4])}"
                    + (" ..." if len(disabled) > 4 else "")
                )
            # A JWT secret in the database is a development-only fallback: read
            # access to this file would be enough to forge any token.
            if "jwt_secret" in settings:
                errors.append(
                    "auth_settings holds a plaintext jwt_secret row — set "
                    "JWT_SECRET_KEY and delete it"
                )

        # Accounts that have never rotated their seeded password.
        if _table_exists(conn, "users"):
            columns = {r[1] for r in conn.execute("PRAGMA table_info(users)")}
            if "password_changed_at" in columns:
                never = conn.execute(
                    "SELECT COUNT(*) FROM users "
                    "WHERE is_active = 1 AND password_changed_at IS NULL"
                ).fetchone()[0]
                if never:
                    errors.append(
                        f"{never} active account(s) have never changed their "
                        "password — a seeded credential may still be live"
                    )
    finally:
        conn.close()
    return errors


def main() -> int:
    # validate_deployment.py -> tools -> <repo root>
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runtime", action="store_true",
        help="also check the live auth database's security posture",
    )
    parser.add_argument(
        "--auth-db", type=Path, default=None,
        help="path to auth.db (default: this installation's)",
    )
    args = parser.parse_args()

    errors = validate(root)
    if errors:
        print("Deployment validation failed: " + "; ".join(errors))
        return 1
    print("Deployment validation passed")

    if args.runtime:
        auth_db = args.auth_db
        if auth_db is None:
            from education_system.platform.identity.auth.db import AUTH_DB_FILE
            auth_db = Path(str(AUTH_DB_FILE))
        posture = validate_runtime_posture(auth_db)
        if posture:
            print(f"\nRuntime posture check FAILED for {auth_db}:")
            for item in posture:
                print(f"  - {item}")
            print("\nExpected to fail on a development database. These must all "
                  "be resolved before the environment holds real student data.")
            return 1
        print(f"Runtime posture check passed for {auth_db}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
