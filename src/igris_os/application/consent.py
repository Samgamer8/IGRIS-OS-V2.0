"""ConsentGate — IGRIS pide permiso antes de un paso de alto calado.

Cuando el asistente identifica que el siguiente paso toca el nucleo del sistema
(cablear un componente, modificar el arranque, cambiar contratos), en vez de
ejecutarlo a ciegas o de solo mencionarlo y esperar que el usuario recuerde,
formula una pregunta explicita y espera una respuesta.

Filosofia:
- La decision de si/no es DETERMINISTA (reglas claras), no la delega en el
  LLM: asi no hay sorpresas ni malas interpretaciones.
- Cada propuesta puede llevar un ``handler`` que solo se ejecuta si el usuario
  acepta. Si no hay handler, el gate simplemente autoriza y otro componente
  actua.
- Todo es local y sin red. Nada se ejecuta sin un "si" explicito.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass(frozen=True, slots=True)
class Proposal:
    """Un siguiente paso de alto calado pendiente de autorizacion."""

    question: str
    summary: str
    risk: str = "high"                 # high | medium | low
    action_id: str = ""
    handler: Optional[Callable[[], Any]] = field(default=None, repr=False)


# Respuestas afirmativas / negativas reconocidas (determinista, sin LLM).
_AFFIRMATIVE = {
    "si", "sí", "sii", "claro", "por supuesto", "adelante", "dale", "hazlo",
    "ok", "vale", "va", "correcto", "afirmativo", "acepto", "quiero", "porfa",
    "por favor", "venga", "genial", "perfecto", "confirmo", "de acuerdo",
}
# Marcadores de duda: tienen PRIORIDAD sobre afirmar/negar. "no estoy seguro"
# o "no se" contienen "no" pero NO son un rechazo a la propuesta.
_DOUBT = {
    "seguro", "segura", "quizas", "quizá", "creo", "tal vez", "talvez",
    "no se", "dud", "pensarlo", "pensar", "despues", "después", "mmmm",
    "bueno", "depende",
}
_NEGATIVE = {
    "no", "nop", "nel", "para", "espera", "mejor no", "ahora no", "luego",
    "cancelar", "cancela", "negar", "rechazo", "todavia no", "todavía no",
    "dejalo", "déjalo", "alto", "basta",
}


class ConsentGate:
    """Motor de propuestas con consentimiento explicito del usuario."""

    def __init__(self) -> None:
        self._pending: Optional[Proposal] = None

    # -- registro / consulta --------------------------------------------
    @property
    def pending(self) -> Optional[Proposal]:
        return self._pending

    def has_pending(self) -> bool:
        return self._pending is not None

    def propose(self, question: str, summary: str, *, risk: str = "high",
                action_id: str = "",
                handler: Optional[Callable[[], Any]] = None) -> str:
        """Registra una propuesta y devuelve el texto de la pregunta al usuario."""
        self._pending = Proposal(
            question=question.strip(), summary=summary.strip(), risk=risk,
            action_id=action_id, handler=handler)
        return self.format_question(self._pending)

    def cancel(self) -> None:
        """Descarta cualquier propuesta pendiente sin ejecutarla."""
        self._pending = None

    # -- respuesta del usuario ------------------------------------------
    def interpret(self, response: str) -> str:
        """Clasifica la respuesta: 'yes' | 'no' | 'unclear'. Determinista."""
        text = str(response or "").strip().lower()
        if not text:
            return "unclear"
        # Coincidencia exacta primero (evita que "no se" cuente como "no").
        if text in _AFFIRMATIVE:
            return "yes"
        if text in _NEGATIVE:
            return "no"
        tokens = {tok.strip("¿?¡!.,;:") for tok in text.split()}
        joined = " " + text + " "
        # La duda tiene PRIORIDAD: "no estoy seguro" contiene "no" pero no es
        # un rechazo. Marcamos multi-palabra por substring y el resto por token.
        doubt = any(m in joined for m in _DOUBT if " " in m)
        doubt = doubt or bool(tokens & {m for m in _DOUBT if " " not in m})
        if doubt:
            return "unclear"
        has_yes = bool(tokens & _AFFIRMATIVE)
        has_no = bool(tokens & _NEGATIVE)
        if has_yes and not has_no:
            return "yes"
        if has_no and not has_yes:
            return "no"
        return "unclear"

    def resolve(self, response: str) -> dict[str, Any]:
        """Procesa la respuesta del usuario frente a la propuesta pendiente.

        Devuelve un dict con ``decision`` ('accepted' | 'rejected' | 'unclear'),
        la propuesta resuelta y, si se acepto y habia handler, su resultado.
        """
        proposal = self._pending
        if proposal is None:
            return {"decision": "unclear", "proposal": None,
                    "reason": "No hay ninguna propuesta pendiente."}
        verdict = self.interpret(response)
        if verdict == "unclear":
            return {"decision": "unclear", "proposal": proposal,
                    "reason": "No entendi si o no. " + self.format_question(proposal)}
        self._pending = None
        if verdict == "no":
            return {"decision": "rejected", "proposal": proposal,
                    "reason": "Entendido, no lo hago. Queda descartado."}
        result = None
        if proposal.handler is not None:
            result = proposal.handler()
        return {"decision": "accepted", "proposal": proposal,
                "reason": "Autorizado. Ejecuto el siguiente paso.",
                "result": result}

    # -- formato ---------------------------------------------------------
    @staticmethod
    def format_question(proposal: Proposal) -> str:
        lines = [proposal.question, ""]
        if proposal.summary:
            lines.append("Que haria exactamente:")
            lines.append(f"  {proposal.summary}")
        lines.append("")
        lines.append("Responde 'si' para que lo haga o 'no' para descartarlo.")
        return "\n".join(lines)
