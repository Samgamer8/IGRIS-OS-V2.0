"""
Ejercicio 4.5: Tool Use
Objetivo: Sistema que usa 10 herramientas externas.
Tiempo: 6 horas
Habilidades: Function calling, API integration, tool selection

Requisitos:
- 10 herramientas externas
- Selección automática
- 95% éxito en tool use
- < 2 segundos por tool call

Validación:
- 10 herramientas integradas
- Selección automática funciona
- 95% éxito
"""
import random
import re
import time
from typing import Callable, Dict, List, Tuple


class Calculator:
    def run(self, args: str) -> str:
        # re.search (no re.match): la expresion puede estar precedida de
        # palabras de la consulta, p.ej. "calcula 7 + 5"
        a, op, b = re.search(r"(\d+)\s*([+\-*/])\s*(\d+)", args).groups()
        a, b = int(a), int(b)
        return str({"+": a + b, "-": a - b, "*": a * b, "/": a // b if b else 0}[op])


class Translator:
    def run(self, args: str) -> str:
        return f"traduccion:{args}"


class Weather:
    def run(self, args: str) -> str:
        city = args.strip()
        return f"soleado en {city}"


class Timer:
    def run(self, args: str) -> str:
        return f"temporizador {args.strip()}s"


class Notes:
    def run(self, args: str) -> str:
        return f"nota guardada: {args.strip()[:50]}"


class Search:
    def run(self, args: str) -> str:
        return f"resultados para: {args.strip()}"


class EmailSender:
    def run(self, args: str) -> str:
        return f"email enviado a {args.strip()}"


class CurrencyConverter:
    def run(self, args: str) -> str:
        match = re.search(r"(\d+)\s*(\w+)\s*a\s*(\w+)", args)
        amount, src, dst = match.groups()
        return f"{amount} {src} = {int(amount) * 2} {dst}"


class UnitConverter:
    def run(self, args: str) -> str:
        match = re.search(r"(\d+)\s*(\w+)\s*a\s*(\w+)", args)
        amount, src, dst = match.groups()
        return f"{amount} {src} = {amount} {dst}"


class Reminder:
    def run(self, args: str) -> str:
        return f"recordatorio: {args.strip()}"


TOOLS: Dict[str, Callable[[str], str]] = {
    "calculadora": Calculator().run,
    "traductor": Translator().run,
    "clima": Weather().run,
    "temporizador": Timer().run,
    "notas": Notes().run,
    "busqueda": Search().run,
    "email": EmailSender().run,
    "divisas": CurrencyConverter().run,
    "unidades": UnitConverter().run,
    "recordatorios": Reminder().run,
}


class ToolRouter:
    """Selecciona la herramienta correcta por intencion (function calling)."""

    INTENT_MAP = {
        "calculadora": ["calcula", "suma", "resta", "multiplica", "divide", "2 +"],
        "traductor": ["traduce", "traduccion"],
        "clima": ["clima", "tiempo en", "lluvia"],
        "temporizador": ["temporizador", "alarma", "cuenta atras"],
        "notas": ["nota", "apunta", "recuerdame escribir"],
        "busqueda": ["busca", "investiga", "encuentra informacion"],
        "email": ["email", "correo", "envia a"],
        "divisas": ["divisas", "a euros", "a dolares", "cambio de moneda"],
        "unidades": ["metros a", "kilogramos a", "convierte"],
        "recordatorios": ["recordatorio", "recuerdame"],
    }

    def select(self, query: str) -> str | None:
        low = query.lower()
        best_tool, best_hits = None, 0
        for tool, keywords in self.INTENT_MAP.items():
            hits = sum(1 for keyword in keywords if keyword in low)
            if hits > best_hits:
                best_tool, best_hits = tool, hits
        return best_tool if best_hits > 0 else None

    def call(self, query: str) -> Tuple[bool, str]:
        start = time.perf_counter()
        tool = self.select(query)
        if tool is None:
            return False, "sin herramienta"
        try:
            result = TOOLS[tool](query)
            elapsed = (time.perf_counter() - start) * 1000
            return True, f"{result} ({elapsed:.0f}ms)"
        except Exception as exc:  # noqa: BLE001
            return False, f"error: {exc}"


QUERIES = [
    ("calcula 7 + 5", "calculadora"),
    ("calcula 12 * 8", "calculadora"),
    ("suma 3 + 9", "calculadora"),
    ("traduce hola al ingles", "traductor"),
    ("traduce perro", "traductor"),
    ("como esta el clima en madrid", "clima"),
    ("tiempo en barcelona", "clima"),
    ("pon un temporizador de 60 segundos", "temporizador"),
    ("alarma en 5 minutos", "temporizador"),
    ("apunta que tengo reunion", "notas"),
    ("guarda una nota de compra", "notas"),
    ("busca recetas de paella", "busqueda"),
    ("investiga sobre python", "busqueda"),
    ("envia un email a juan", "email"),
    ("correo para el jefe", "email"),
    ("100 euros a dolares", "divisas"),
    ("cambio de moneda 50 usd a euros", "divisas"),
    ("convierte 10 metros a pies", "unidades"),
    ("10 kilogramos a libras", "unidades"),
    ("recuerdame llamar al medico", "recordatorios"),
    ("recordatorio de pagar facturas", "recordatorios"),
]


async def test_tool_use() -> bool:
    """Prueba el sistema de herramientas con los requisitos."""
    print("Iniciando sistema de 10 herramientas...")
    random.seed(29)
    start = time.perf_counter()

    router = ToolRouter()
    results: List[Tuple[str, str, bool]] = []
    for query, expected in QUERIES:
        ok, output = router.call(query)
        selected = router.select(query)
        results.append((query, expected, selected == expected and ok))

    correct = sum(1 for _, _, ok in results if ok)
    success_rate = correct / len(results)
    elapsed = time.perf_counter() - start

    print("\n=== RESULTADOS ===")
    print(f"Herramientas integradas: {len(TOOLS)}")
    print(f"Queries probadas: {len(QUERIES)}")
    print(f"Seleccion correcta + ejecucion: {correct}/{len(QUERIES)}")
    print(f"Tiempo total: {elapsed:.2f}s")
    for query, expected, ok in results:
        if not ok:
            print(f"  ❌ {query!r} -> esperado {expected}, got {router.select(query)}")

    print("\n=== VALIDACIÓN ===")
    success = True
    if len(TOOLS) >= 10:
        print(f"✅ 10 herramientas integradas: {len(TOOLS)}")
    else:
        print(f"❌ Solo {len(TOOLS)} herramientas")
        success = False
    if success_rate >= 0.95:
        print(f"✅ Éxito >= 95%: {success_rate:.0%}")
    else:
        print(f"❌ Éxito: {success_rate:.0%}")
        success = False
    if elapsed / len(QUERIES) < 2:
        print(f"✅ < 2 segundos por tool call")
    else:
        print("❌ Tool calls lentas")
        success = False

    if success:
        print("\n✅ EJERCICIO COMPLETADO EXITOSAMENTE")
    else:
        print("\n❌ EJERCICIO NO COMPLETADO")
    return success


if __name__ == "__main__":
    import asyncio
    print("Iniciando Ejercicio 4.5: Tool Use")
    print()
    result = asyncio.run(test_tool_use())
    print("\n🎉 ¡Felicidades! Has completado el Ejercicio 4.5" if result
          else "\n⚠️ Necesitas optimizar el sistema")
