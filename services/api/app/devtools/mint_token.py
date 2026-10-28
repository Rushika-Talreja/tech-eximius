"""
Local JWT minting helper for Milestone M0.
Works ONLY when APP_ENV=local. Generates an RSA keypair on first use under .local/
and mints RS256 JWTs with matching OIDC settings for test users A and B.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Literal

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwk, jwt

from app.config import get_settings


def _get_local_dir() -> Path:
    """Find repository root .local/ directory."""
    # This file: services/api/app/devtools/mint_token.py -> repo root is parents[3]
    repo_root = Path(__file__).resolve().parents[3]
    local_dir = repo_root / ".local"
    local_dir.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(local_dir, 0o700)
    except OSError:
        pass
    return local_dir


def ensure_dev_keys() -> tuple[str, dict]:
    """
    Ensure RSA keypair and JWKS exist under .local/.
    Returns (private_key_pem_str, jwks_dict).
    """
    settings = get_settings()
    if settings.app_env != "local":
        raise RuntimeError("mint_token and dev keys are only permitted when APP_ENV=local")

    local_dir = _get_local_dir()
    pem_path = local_dir / "dev_rsa_key.pem"
    jwks_path = local_dir / "dev_jwks.json"

    if pem_path.exists() and jwks_path.exists():
        priv_pem = pem_path.read_text()
        jwks = json.loads(jwks_path.read_text())
        return priv_pem, jwks

    # Generate new 2048-bit RSA keypair
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    pub_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    # Build JWKS
    jwk_dict = jwk.construct(pub_pem, algorithm="RS256").to_dict()
    jwk_dict["kid"] = "dev-key-1"
    jwk_dict["use"] = "sig"
    jwk_dict["alg"] = "RS256"
    jwks = {"keys": [jwk_dict]}

    # Write securely
    pem_path.write_text(priv_pem)
    try:
        os.chmod(pem_path, 0o600)
    except OSError:
        pass
    jwks_path.write_text(json.dumps(jwks, indent=2))

    return priv_pem, jwks


def mint_token(user: Literal["a", "b"], ttl: int = 3600) -> str:
    """
    Dev-only helper to mint RS256 token for User A or User B.
    Works only when APP_ENV=local.
    """
    settings = get_settings()
    if settings.app_env != "local":
        raise RuntimeError("mint_token is only permitted when APP_ENV=local")

    priv_pem, _ = ensure_dev_keys()

    identities = {
        "a": {
            "sub": "dev-user-a",
            "email": "user-a@org-a.local",
            "name": "User A",
        },
        "b": {
            "sub": "dev-user-b",
            "email": "user-b@org-b.local",
            "name": "User B",
        },
    }

    if user not in identities:
        raise ValueError(f"Unknown user '{user}'. Allowed: 'a' or 'b'")

    identity = identities[user]
    now = int(time.time())

    claims = {
        "iss": settings.oidc_issuer_url,
        "aud": settings.oidc_audience,
        "sub": identity["sub"],
        "email": identity["email"],
        "name": identity["name"],
        "iat": now,
        "exp": now + ttl,
    }

    token: str = jwt.encode(
        claims,
        priv_pem,
        algorithm="RS256",
        headers={"kid": "dev-key-1"},
    )
    return token


def main() -> None:
    parser = argparse.ArgumentParser(description="Mint local test JWT for user A or B")
    parser.add_argument("--user", choices=["a", "b"], required=True, help="User identifier ('a' or 'b')")
    parser.add_argument("--ttl", type=int, default=3600, help="Token time-to-live in seconds (default 3600)")
    args = parser.parse_args()

    try:
        token = mint_token(args.user, args.ttl)
        # Never print private keys; print only the token
        print(token)
    except Exception as exc:
        sys.stderr.write(f"Error: {exc}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()

