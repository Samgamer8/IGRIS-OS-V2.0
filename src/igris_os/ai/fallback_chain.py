"""Cadena de modelos con failover para IGRIS OS (codigo propio).

Adapta una idea observada en agentes frontier (free-claude-code): resolver una
peticion a una lista ORDENADA de modelos (principal + reservas) y, si el
candidato actual falla ANTES de producir respuesta, saltar en silencio al
siguiente sin perder el turno del usuario.

Regla de "committed": un candidato solo se da por bueno cuando devuelve texto
no vacio (``reply.ok and reply.text``). Si falla o viene vacio, se considera
que no comprometio la respuesta y se prueba el siguiente. Esto evita convertir
un fallo de backend en un falso positivo para el usuario.

No copia codigo del proyecto observado: implementa el patron con la interfaz
propia de IGRIS (``FrontierGateway.generate`` -> ``ModelReply``).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, Sequence

from .ollama import ModelReply


class _Generator(Protocol):
    """Cualquier cliente con el mismo contrato que FrontierGateway.generate."""

    def generate(self, prompt: str, model: str, **kwargs: Any) -> ModelReply:
        ...


@dataclass(frozen=True, slots=True)
class FallbackAttempt:
    """Traza de un candidato probado dentro de la cadena."""

    model: str
    ok: bool
    produced_text: bool = False
    error: str = ""


@dataclass(slots=True)
class FallbackResult:
    """Resultado de recorrer la cadena de modelos.

    ``reply`` es la respuesta del candidato que comprometio el turno, o el
    ultimo fallo si ninguno lo hizo. ``attempts`` deja constancia honesta de
    todo lo que se probo.
    """

    reply: ModelReply
    attempts: tuple[FallbackAttempt, ...] = ()
    committed_index: int = -1

    @property
    def ok(self) -> bool:
        return self.reply.ok

    @property
    def committed_model(self) -> str:
        return self.reply.model if self.committed_index >= 0 else ""

    @property
    def used_fallback(self) -> bool:
        """True si el turno lo resolvio un modelo distinto del principal."""
        return self.committed_index > 0


class FallbackChain:
    """Recorre una lista ordenada de modelos hasta que uno responde.

    Uso::

        chain = FallbackChain(gateway, models=[principal, reserva1, reserva2])
        result = chain.run("tu prompt", model=principal)
        if result.used_fallback:
            print("salto a", result.committed_model)
    """

    def __init__(self, generator: _Generator, *,
                 models: Sequence[str],
                 generate_kwargs: dict[str, Any] | None = None) -> None:
        if not models:
            raise ValueError("La cadena necesita al menos un modelo")
        # Conserva el orden, elimina duplicados y vacios.
        self.models: tuple[str, ...] = tuple(
            dict.fromkeys(m for m in models if str(m).strip()))
        if not self.models:
            raise ValueError("La cadena necesita al menos un modelo valido")
        self._generator = generator
        self._generate_kwargs = dict(generate_kwargs or {})

    def run(self, prompt: str, *, model: str | None = None,
            extra_kwargs: dict[str, Any] | None = None) -> FallbackResult:
        candidates = self._ordered_candidates(model)
        attempts: list[FallbackAttempt] = []
        last: ModelReply | None = None
        for index, candidate in enumerate(candidates):
            kwargs = dict(self._generate_kwargs)
            if extra_kwargs:
                kwargs.update(extra_kwargs)
            reply = self._generator.generate(prompt, candidate, **kwargs)
            last = reply
            produced = bool(reply.ok and str(reply.text).strip())
            attempts.append(FallbackAttempt(
                model=candidate, ok=bool(reply.ok),
                produced_text=produced, error=reply.error))
            if produced:
                return FallbackResult(
                    reply=reply, attempts=tuple(attempts), committed_index=index)
        # Ninguno comprometio: devolvemos el ultimo fallo con la traza completa.
        assert last is not None  # candidates nunca esta vacio
        return FallbackResult(
            reply=last, attempts=tuple(attempts), committed_index=-1)

    def _ordered_candidates(self, model: str | None) -> tuple[str, ...]:
        """Pone ``model`` primero si se indica; si no, el principal de la lista."""
        if not model or model not in self.models:
            return self.models
        rest = tuple(m for m in self.models if m != model)
        return (model,) + rest
