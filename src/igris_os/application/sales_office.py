from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True, slots=True)
class SalesQuestion:
    key: str
    prompt: str


@dataclass(frozen=True, slots=True)
class SalesPlan:
    product: str
    audience: str
    channel: str
    price: float
    variable_cost: float
    fixed_cost: float
    acquisition_budget: float
    contribution_margin: float
    break_even_sales: int
    questions: tuple[SalesQuestion, ...] = ()
    actions: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()

    @property
    def ready(self) -> bool:
        return not self.questions


class SalesOffice:
    """Prepara un plan comercial basado en datos, no en promesas de ingresos."""

    _REQUIRED = (
        ("product", "¿Qué producto o servicio se vende?"),
        ("audience", "¿Cuál es el cliente objetivo concreto?"),
        ("channel", "¿Qué canal de captación vas a usar primero?"),
        ("price", "¿Cuál es el precio medio por venta?"),
        ("variable_cost", "¿Cuál es el coste variable por venta?"),
        ("fixed_cost", "¿Cuáles son los costes fijos mensuales?"),
    )

    def build(self, values: Mapping[str, object] | None = None) -> SalesPlan:
        raw = {str(key): str(value).strip()
               for key, value in (values or {}).items() if str(value).strip()}
        questions = tuple(SalesQuestion(key, prompt) for key, prompt in self._REQUIRED
                          if key not in raw)
        product = raw.get("product", "")
        audience = raw.get("audience", "")
        channel = raw.get("channel", "")
        price = self._number(raw.get("price", "0"), "price")
        variable_cost = self._number(raw.get("variable_cost", "0"), "variable_cost")
        fixed_cost = self._number(raw.get("fixed_cost", "0"), "fixed_cost")
        acquisition_budget = self._number(raw.get("acquisition_budget", "0"), "acquisition_budget")
        margin = price - variable_cost
        break_even = 0
        if not questions and margin <= 0:
            questions += (SalesQuestion(
                "price_or_cost", "El margen por venta no es positivo. Revisa precio o coste variable."),)
        elif not questions:
            break_even = int((fixed_cost + acquisition_budget + margin - 1) // margin)
        actions = () if questions else (
            "Definir una oferta con un único resultado medible para el cliente objetivo",
            "Preparar una página o mensaje de venta con la oferta, precio y prueba",
            "Lanzar un experimento en el canal elegido con presupuesto limitado",
            "Registrar contactos, conversiones, coste por adquisición y ventas cada semana",
            "Mantener el canal solo si el margen cubre adquisición y costes fijos",
        )
        assumptions = () if questions else (
            "El punto de equilibrio no es una previsión de ventas; es el mínimo necesario para cubrir costes declarados.",
            "La conversión y el coste de adquisición deben medirse en el canal real antes de escalar inversión.",
        )
        return SalesPlan(product, audience, channel, price, variable_cost,
                         fixed_cost, acquisition_budget, margin, break_even,
                         questions, actions, assumptions)

    @staticmethod
    def _number(value: str, key: str) -> float:
        try:
            number = float(value.replace(",", "."))
        except ValueError as exc:
            raise ValueError("Valor comercial inválido: " + key) from exc
        if number < 0:
            raise ValueError("Valor comercial negativo: " + key)
        return number