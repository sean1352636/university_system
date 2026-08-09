"""Read-only credential-verification microservice.

This process deliberately exposes no issuance or revocation operations. The
registrar API owns writes; this service can therefore be scaled and exposed to
external verification networks with a much smaller permission surface.
"""

from __future__ import annotations

import os

from flask import Flask, jsonify

from education_system.systems.university.domain.finance.blockchain.services import (
    CredentialConfigurationError,
    verify_credential,
)


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/health/live")
    def live():
        return jsonify({"status": "ok", "service": "credential-verifier"})

    @app.get("/v1/credentials/<string:credential_hash>")
    def verify(credential_hash: str):
        try:
            result = verify_credential(
                credential_hash=credential_hash,
                verification_method="external_network",
                initialize_schema=False,
            )
        except CredentialConfigurationError:
            return jsonify({"valid": False, "reason": "service_unavailable"}), 503
        status = 200 if result.get("valid") else 404 if result.get("reason") == "not_found" else 409
        # The public contract returns signed claims and status, never internal
        # relational rows containing implementation metadata.
        credential = result.pop("credential", None) or {}
        result["credential"] = {
            "credential_type": credential.get("credential_type"),
            "credential_name": credential.get("credential_name"),
            "issue_date": credential.get("issue_date"),
            "blockchain_hash": credential.get("blockchain_hash"),
        }
        return jsonify(result), status

    return app


def main() -> None:
    create_app().run(
        host=os.getenv("VERIFIER_HOST", "0.0.0.0"),
        port=int(os.getenv("VERIFIER_PORT", "5010")),
    )


if __name__ == "__main__":
    main()
