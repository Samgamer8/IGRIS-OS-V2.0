"""Limites compartidos por formato, compilacion y reparacion: no se multiplican."""
from collections import Counter
import hashlib
import time


class GenerationLimit(ValueError):
    pass


class RepeatedGeneration(ValueError):
    pass


class GenerationBudget:
    def __init__(self, max_calls=32, per_component=4, seconds=1800):
        self.max_calls = max_calls
        self.per_component = per_component
        self.deadline = time.monotonic() + seconds
        self.calls = Counter()
        self.responses = set()
        self.model_calls = Counter()

    def before_call(self, component, model=""):
        if time.monotonic() >= self.deadline:
            raise GenerationLimit("Limite de tiempo alcanzado; avance conservado")
        if sum(self.calls.values()) >= self.max_calls or self.calls[component] >= self.per_component:
            raise GenerationLimit("Limite de llamadas alcanzado para " + component + "; avance conservado")
        if self.model_calls[component, model] >= 2:
            raise RepeatedGeneration("Limite de dos llamadas al mismo modelo para " + component)
        self.calls[component] += 1
        self.model_calls[component, model] += 1

    def observe(self, component, model, text):
        digest = hashlib.sha256(text.strip().encode()).hexdigest()
        key = (component, model, digest)
        if key in self.responses:
            raise RepeatedGeneration("El modelo repitio la misma respuesta para " + component)
        self.responses.add(key)

    def report(self):
        return {"calls": sum(self.calls.values()), "max_calls": self.max_calls,
                "per_component_limit": self.per_component, "component_calls": dict(self.calls)}
