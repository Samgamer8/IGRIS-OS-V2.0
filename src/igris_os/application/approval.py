# -*- coding: utf-8 -*-
"""Autoridad de aprobacion con tokens firmados (HMAC).

Sustituye el booleano ``confirmed=True`` que cualquier codigo podia pasar para
saltarse la confirmacion humana. Ahora una capacidad que requiere confirmacion
solo se ejecuta si el kernel recibe un token emitido por esta autoridad, que:

- vincula el token a un objetivo y una capacidad concretos (no es generico);
- caduca a los ``ttl_seconds`` (por defecto 300 s);
- se verifica en tiempo constante (``hmac.compare_digest``) contra manipulacion.

La clave es HMAC simetrica por disponibilidad de stdlib; la separacion dura
emisor/verificador (claves asimetricas) queda como endurecimiento futuro.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time


class ApprovalAuthority:
    """Emite y verifica tokens de aprobacion firmados."""

    def __init__(self, secret: bytes | None = None,
                 ttl_seconds: int = 300) -> None:
        self._secret = secret or secrets.token_bytes(32)
        self.ttl_seconds = ttl_seconds

    def issue(self, binding: str, capability: str) -> str:
        """Emite un token vinculado a ``binding`` y ``capability``."""
        expires = int(time.time()) + self.ttl_seconds
        payload = f"{binding}\n{capability}\n{expires}".encode("utf-8")
        signature = hmac.new(self._secret, payload, hashlib.sha256).hexdigest()
        return f"{expires}.{signature}"

    def verify(self, token: str | None, binding: str,
               capability: str) -> bool:
        """Comprueba que el token es valido para este binding y capacidad."""
        if not token:
            return False
        try:
            expires_raw, signature = token.split(".", 1)
            expires = int(expires_raw)
        except (ValueError, AttributeError):
            return False
        if time.time() > expires:
            return False
        payload = f"{binding}\n{capability}\n{expires}".encode("utf-8")
        expected = hmac.new(self._secret, payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected)
