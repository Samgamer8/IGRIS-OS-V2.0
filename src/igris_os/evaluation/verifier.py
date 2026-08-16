# -*- coding: utf-8 -*-
"""Verificador independiente: un segundo modelo aprueba o rechaza una entrega.

El mismo modelo que genera algo no debe ser el unico que lo aprueba. Este
modulo consulta un modelo *distinto* del generador, le pide una puntuacion y
un veredicto contra el objetivo y los criterios de aceptacion, y solo aprueba
si la puntuacion supera el umbral.

Si no hay un segundo modelo disponible, marca la revision como omitida (no
bloquea la entrega, pero lo declara).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from igris_os.ai import OllamaClient
from igris_os.utils.json_parser import StrictJSONParser


@dataclass(frozen=True, slots=True)
class Verdict:
    approved: bool
    score: float
    reason: str
    generator_model: str = ""
    verifier_model: str = ""
    skipped: bool = False


VERIFIER_SYSTEM = (
    "Eres un verificador independiente, distinto del generador. Revisa la "
    "entrega contra el objetivo y los criterios de aceptacion. No apruebes si "
    "hay afirmaciones sin evidencia, codigo inseguro, efectos destructivos o "
    "criterios sin cumplir. Responde SOLO JSON con: {\"score\": <0-100>, "
    "\"approved\": <true|false>, \"reason\": \"<motivo breve>\"}."
)


class IndependentVerifier:
    VERIFIER_PREFERENCE = (
        "qwen2.5-coder:14b", "qwen2.5-coder:7b", "llama3.1:8b",
        "llama3.2:latest",
    )

    def __init__(self, client: OllamaClient | None = None,
                 threshold: float = 0.7) -> None:
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("Umbral fuera de rango [0, 1]")
        self.client = client or OllamaClient()
        self.threshold = threshold

    def verify(self, deliverable: str, objective: str,
               acceptance: Sequence[str] = (),
               generator_model: str = "") -> Verdict:
        if not deliverable.strip() or not objective.strip():
            return Verdict(False, 0.0, "Falta entregable u objetivo",
                           generator_model, "")
        verifier_model = self._choose_verifier(generator_model)
        if not verifier_model:
            return Verdict(True, 0.0,
                           "Sin modelo verificador: revision independiente omitida",
                           generator_model, "", True)
        criteria = ("\n".join("- " + item for item in acceptance)
                    if acceptance else "cumplir el objetivo")
        prompt = (
            VERIFIER_SYSTEM + "\nOBJETIVO:\n" + objective +
            "\nCRITERIOS DE ACEPTACION:\n" + criteria +
            "\nENTREGA A REVISAR:\n" + deliverable[:6000])
        reply = self.client.generate(prompt, verifier_model)
        if not reply.ok:
            return Verdict(False, 0.0,
                           "Verificador sin respuesta: " + (reply.error or ""),
                           generator_model, verifier_model)
        try:
            data = StrictJSONParser.extract(reply.text)
            score = float(data.get("score", 0.0))
            explicit = bool(data.get("approved", False))
            reason = str(data.get("reason", "")).strip()
        except (ValueError, TypeError, KeyError) as exc:
            return Verdict(False, 0.0,
                           f"Respuesta del verificador no interpretable: {exc}",
                           generator_model, verifier_model)
        score = max(0.0, min(100.0, score))
        approved = explicit and score >= self.threshold * 100
        return Verdict(approved, score, reason, generator_model,
                       verifier_model)

    def _choose_verifier(self, generator_model: str) -> str:
        installed = self.client.models()
        if generator_model:
            others = [name for name in installed if name != generator_model]
        else:
            others = list(installed)
        for name in self.VERIFIER_PREFERENCE:
            if name in others:
                return name
        if others:
            return others[0]
        return ""
