# -*- coding: utf-8 -*-
"""Aprobaciones firmadas, vinculadas, caducables y de un solo uso."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time


class ApprovalAuthority:
    """Emite, verifica y consume tokens vinculados a una acción concreta."""

    def __init__(self, secret: bytes | None = None,
                 ttl_seconds: int = 300) -> None:
        self._secret = secret or secrets.token_bytes(32)
        self.ttl_seconds = ttl_seconds
        self._consumed: set[str] = set()

    def issue(self, binding: str, capability: str) -> str:
        expires = int(time.time()) + self.ttl_seconds
        nonce = secrets.token_hex(16)
        payload = f"{binding}\n{capability}\n{expires}\n{nonce}".encode("utf-8")
        signature = hmac.new(self._secret, payload, hashlib.sha256).hexdigest()
        return f"{expires}.{nonce}.{signature}"

    def verify(self, token: str | None, binding: str,
               capability: str) -> bool:
        if not token:
            return False
        try:
            expires_raw, nonce, signature = token.split(".", 2)
            expires = int(expires_raw)
        except (ValueError, AttributeError):
            return False
        if time.time() > expires:
            return False
        payload = f"{binding}\n{capability}\n{expires}\n{nonce}".encode("utf-8")
        expected = hmac.new(self._secret, payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected)

    def consume(self, token: str | None, binding: str,
                capability: str) -> bool:
        """Valida y consume una aprobación, impidiendo su reutilización."""
        if not token or token in self._consumed:
            return False
        if not self.verify(token, binding, capability):
            return False
        self._consumed.add(token)
        return True
