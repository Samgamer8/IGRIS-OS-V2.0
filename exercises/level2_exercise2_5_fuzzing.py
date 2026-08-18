"""
Ejercicio 2.5: Generación de 1000 Casos de Prueba con Fuzzing
Objetivo: Sistema que genera 1000 casos de prueba con fuzzing.
Tiempo: 4 horas
Habilidades: Fuzzing, property-based testing, test generation

Requisitos:
- Genera 1000 casos de prueba
- Property-based testing
- Detecta edge cases
- Ejecuta en < 5 minutos
- 95% coverage

Validación:
- 1000 casos generados
- Coverage > 95%
- Ejecución < 5 minutos
"""
import dis
import inspect
import math
import random
import string
import sys
import time
from typing import Any, Callable, Dict, List, Tuple


# ============================================
# FUNCIONES OBJETIVO (se prueban con fuzzing)
# ============================================

def divide(a: float, b: float) -> float:
    """Divide a entre b."""
    if b == 0:
        raise ZeroDivisionError("division by zero")
    return a / b


def parse_int(s: str) -> int | None:
    """Convierte un string a entero, o None si no es convertible."""
    s = s.strip()
    if not s:
        return None
    if len(s) > 12:
        return None
    try:
        return int(s)
    except ValueError:
        return None


def is_palindrome(s: str) -> bool:
    """True si el string es palíndromo (ignorando mayúsculas y no alfanuméricos)."""
    cleaned = "".join(c.lower() for c in s if c.isalnum())
    if not cleaned:
        return False
    return cleaned == cleaned[::-1]


def sort_list(items: list) -> list:
    """Devuelve una copia ordenada de la lista."""
    return sorted(items)


def validate_email(email: str) -> bool:
    """Validación básica de email."""
    if not email or len(email) > 254:
        return False
    if " " in email:
        return False
    if email.count("@") != 1:
        return False
    local, domain = email.split("@")
    if not local or not domain:
        return False
    if "." not in domain:
        return False
    if domain.startswith(".") or domain.endswith("."):
        return False
    return True


# ============================================
# PROPERTIES (invariantes que deben cumplirse)
# ============================================

def prop_divide_roundtrip(a: float, b: float) -> bool:
    """a/b * b == a para valores finitos con b != 0."""
    if not (math.isfinite(a) and math.isfinite(b)) or b == 0:
        return True  # fuera del dominio de esta propiedad
    return math.isclose(divide(a, b) * b, a, rel_tol=1e-9)


def prop_divide_zero(a: float, b: float) -> bool:
    """b == 0 debe lanzar ZeroDivisionError."""
    if b != 0:
        return True  # no aplica
    try:
        divide(a, b)
        return False
    except ZeroDivisionError:
        return True


def prop_parse_int_roundtrip(n: int) -> bool:
    """int -> str -> int devuelve el mismo número."""
    return parse_int(str(n)) == n


def prop_parse_int_consistency(s: str) -> bool:
    """Si parse_int devuelve int, coincide con el string limpio y es corto."""
    result = parse_int(s)
    if result is None:
        return True
    return str(result) == s.strip() and len(s.strip()) <= 12


def prop_palindrome_symmetry(s: str) -> bool:
    """s es palíndromo si y solo si s[::-1] lo es."""
    return is_palindrome(s) == is_palindrome(s[::-1])


def prop_palindrome_concat(s: str) -> bool:
    """s + s[::-1] siempre es palíndromo (o no tiene caracteres alfanuméricos)."""
    if not any(c.isalnum() for c in s):
        return True
    return is_palindrome(s + s[::-1])


def prop_sort_ordered_permutation(items: list) -> bool:
    """Resultado ordenado, misma longitud y es permutación del original."""
    result = sort_list(items)
    return (len(result) == len(items)
            and all(result[i] <= result[i + 1] for i in range(len(result) - 1))
            and sorted(result) == sorted(items))


def prop_sort_idempotent(items: list) -> bool:
    """Ordenar dos veces da lo mismo que ordenar una vez."""
    return sort_list(sort_list(items)) == sort_list(items)


def prop_email_wellformed(e: str) -> bool:
    """Si validate_email acepta, el email está bien formado."""
    if not validate_email(e):
        return True
    if e.count("@") != 1 or " " in e:
        return False
    domain = e.split("@")[1]
    return (bool(domain) and "." in domain
            and not domain.startswith(".") and not domain.endswith("."))


# (nombre, función de propiedad, generadores de inputs)
PROPERTIES: List[Tuple[str, Callable[..., bool], Tuple[Callable, ...]]] = [
    ("divide: roundtrip a/b*b == a", prop_divide_roundtrip, ("float", "float")),
    ("divide: b==0 lanza ZeroDivisionError", prop_divide_zero, ("float", "float")),
    ("parse_int: roundtrip int->str->int", prop_parse_int_roundtrip, ("small_int",)),
    ("parse_int: consistencia del resultado", prop_parse_int_consistency, ("string",)),
    ("is_palindrome: simetría", prop_palindrome_symmetry, ("string",)),
    ("is_palindrome: s+s[::-1]", prop_palindrome_concat, ("string",)),
    ("sort_list: orden, longitud y permutación", prop_sort_ordered_permutation, ("list",)),
    ("sort_list: idempotencia", prop_sort_idempotent, ("list",)),
    ("validate_email: aceptado => bien formado", prop_email_wellformed, ("string",)),
]


# ============================================
# GENERADORES DE FUZZING
# ============================================

def gen_small_int() -> int:
    """Enteros que caben en 12 caracteres (parse_int los acepta)."""
    choices = [
        lambda: random.randint(-(10 ** 9), 10 ** 9),
        lambda: 0,
        lambda: 1,
        lambda: -1,
        lambda: 2 ** 31 - 1,
        lambda: 10 ** 9,
    ]
    return random.choice(choices)()


def gen_float() -> float:
    """Flotante aleatorio con casos límite."""
    choices = [
        lambda: random.uniform(-1e6, 1e6),
        lambda: 0.0,
        lambda: 1.0,
        lambda: -1.0,
        lambda: float("inf"),
        lambda: float("-inf"),
        lambda: float("nan"),
        lambda: 1e-300,
    ]
    return random.choice(choices)()


def gen_string() -> str:
    """String aleatorio con casos límite."""
    choices = [
        lambda: "".join(random.choices(string.ascii_letters + string.digits, k=random.randint(0, 20))),
        lambda: "",
        lambda: " ",
        lambda: "  123  ",
        lambda: "abc123",
        lambda: "A man a plan a canal Panama",
        lambda: "ñandú-αβγ-你好",
        lambda: "x" * 1000,
        lambda: "a@b.com",
        lambda: "a@b",
        lambda: "a@b@c",
        lambda: "@",
        lambda: "a b@c.d",
        lambda: ".a@b.",
        lambda: "user+tag@sub.domain.es",
    ]
    return random.choice(choices)()


def gen_list() -> list:
    """Lista aleatoria con casos límite."""
    choices = [
        lambda: [random.randint(-100, 100) for _ in range(random.randint(0, 50))],
        lambda: [],
        lambda: [1],
        lambda: [0] * 100,
        lambda: [random.randint(0, 1) for _ in range(10)],
        lambda: list(range(50)),
        lambda: list(range(50, 0, -1)),
        lambda: [5] * 5,
    ]
    return random.choice(choices)()


GENERATORS: Dict[str, Callable[[], Any]] = {
    "small_int": gen_small_int,
    "float": gen_float,
    "string": gen_string,
    "list": gen_list,
}


# Edge cases que el fuzzer DEBE ejercitar (detección de edge cases)
MUST_HIT_EDGES: Dict[str, Any] = {
    "empty_string": "",
    "zero_division": 0.0,
    "empty_list": [],
    "unicode_string": "ñandú-αβγ-你好",
    "long_string": "x" * 1000,
    "negative_number": -1,
    "max_int": 2 ** 31 - 1,
    "whitespace_string": " ",
    "single_element_list": [1],
    "email_without_dot": "a@b",
}


# ============================================
# COBERTURA DE LÍNEA (trace + bytecode, stdlib)
# ============================================

class CoverageTracker:
    """Rastrea líneas ejecutadas y calcula cobertura real por instrucción."""

    def __init__(self) -> None:
        self.executed: set[Tuple[str, int]] = set()
        self._target_file = __file__

    def _tracer(self, frame: Any, event: str, arg: Any) -> Any:
        if event == "line" and frame.f_code.co_filename == self._target_file:
            self.executed.add((frame.f_code.co_name, frame.f_lineno))
        return self._tracer

    def start(self) -> None:
        sys.settrace(self._tracer)

    def stop(self) -> None:
        sys.settrace(None)

    @staticmethod
    def docstring_lines(func: Callable) -> set[int]:
        """Líneas de la docstring (texto, nunca generan evento de línea)."""
        try:
            src, start = inspect.getsourcelines(func)
        except (OSError, IOError):
            return set()
        lines: set[int] = set()
        in_doc = False
        for offset, text in enumerate(src[1:], start=start + 1):
            stripped = text.strip()
            if not in_doc:
                if stripped.startswith(("\"\"\"", "'''")):
                    in_doc = True
                else:
                    continue
            lines.add(offset)
            if stripped.endswith(("\"\"\"", "'''")) and len(stripped) >= 6:
                in_doc = False
        return lines

    @classmethod
    def logical_lines(cls, func: Callable) -> set[int]:
        """Líneas con instrucciones reales (def y docstrings no cuentan)."""
        lines: set[int] = set()

        def walk(code: Any) -> None:
            for instr in dis.get_instructions(code):
                if instr.starts_line is not None:
                    lines.add(instr.starts_line)
            for const in code.co_consts:
                if isinstance(const, type(code)):
                    walk(const)

        walk(func.__code__)
        # La línea del 'def' (donde se atribuye el const de la docstring en
        # CPython 3.12) nunca emite evento de línea: excluirla junto con la
        # propia docstring.
        return lines - cls.docstring_lines(func) - {func.__code__.co_firstlineno}

    def coverage_for(self, func: Callable) -> Tuple[int, int]:
        """Devuelve (líneas cubiertas, líneas lógicas totales)."""
        total = self.logical_lines(func)
        covered = {
            line for line in total
            if (func.__name__, line) in self.executed
        }
        return len(covered), len(total)


TARGETS: List[Callable] = [
    divide,
    parse_int,
    is_palindrome,
    sort_list,
    validate_email,
]


# ============================================
# FUZZER PROPERTY-BASED
# ============================================

class PropertyFuzzer:
    """Genera casos, los ejecuta contra propiedades y registra edge cases."""

    def __init__(self, count: int = 1000) -> None:
        self.count = count
        self.cases: List[Tuple[int, tuple]] = []
        self.violations: List[Dict[str, Any]] = []
        self.hit_edges: set[str] = set()
        self.total_checks = 0

    def generate(self) -> None:
        """Genera `count` casos repartidos entre todas las propiedades."""
        for i in range(self.count):
            prop_idx = i % len(PROPERTIES)
            _, _, gen_names = PROPERTIES[prop_idx]
            inputs = tuple(GENERATORS[name]() for name in gen_names)
            self.cases.append((prop_idx, inputs))

    def run(self) -> None:
        """Ejecuta todos los casos y verifica las propiedades."""
        for prop_idx, inputs in self.cases:
            prop_name, prop_fn, _ = PROPERTIES[prop_idx]
            try:
                ok = prop_fn(*inputs)
            except Exception:  # noqa: BLE001 - un fallo inesperado es una violación
                ok = False
            self.total_checks += 1
            if not ok:
                self.violations.append({"property": prop_name, "inputs": inputs})
            self._register_edges(inputs)

    def _register_edges(self, inputs: tuple) -> None:
        """Registra qué edge cases conocidos tocaron los inputs."""
        for name, value in MUST_HIT_EDGES.items():
            if value in inputs:
                self.hit_edges.add(name)

    def edge_cases_detected(self) -> List[str]:
        """Edge cases que el fuzzer NO llegó a ejercitar."""
        return [name for name in MUST_HIT_EDGES if name not in self.hit_edges]


# ============================================
# DEMOSTRACIÓN: el fuzzer TAMBIÉN detecta bugs
# ============================================

def buggy_is_palindrome(s: str) -> bool:
    """Versión con bug: no maneja el caso vacío (devuelve True en vez de False)."""
    cleaned = "".join(c.lower() for c in s if c.isalnum())
    return cleaned == cleaned[::-1]  # "" == "" es True, debería ser False


def demo_bug_detection() -> bool:
    """El fuzzer debe detectar el bug del palíndromo vacío."""
    random.seed(7)
    hits = 0
    for _ in range(500):
        s = gen_string()
        expected = is_palindrome(s)
        got = buggy_is_palindrome(s)
        if expected != got:
            hits += 1
    return hits > 0


# ============================================
# VALIDACIÓN
# ============================================

def test_fuzzing() -> bool:
    """Prueba el sistema de fuzzing con los requisitos."""
    print("Iniciando sistema de fuzzing property-based...")
    random.seed(42)  # corrida reproducible
    start = time.perf_counter()

    # 1. Generar y ejecutar 1000 casos con cobertura activa
    tracker = CoverageTracker()
    fuzzer = PropertyFuzzer(count=1000)
    tracker.start()
    fuzzer.generate()
    fuzzer.run()
    tracker.stop()
    elapsed = time.perf_counter() - start

    # 2. Cobertura por función objetivo
    coverages: Dict[str, Tuple[int, int]] = {}
    for func in TARGETS:
        coverages[func.__name__] = tracker.coverage_for(func)

    print("\n=== RESULTADOS ===")
    print(f"Casos generados: {len(fuzzer.cases)}")
    print(f"Checks de propiedad ejecutados: {fuzzer.total_checks}")
    print(f"Violaciones de propiedad: {len(fuzzer.violations)}")
    print(f"Edge cases ejercitados: {len(fuzzer.hit_edges)}/{len(MUST_HIT_EDGES)}")
    print(f"Tiempo de ejecución: {elapsed:.2f}s")
    print("\nCobertura por función:")
    for name, (covered, total) in coverages.items():
        pct = (covered / total * 100) if total else 0
        print(f"  {name:20s} {covered:3d}/{total:3d} líneas ({pct:.0f}%)")

    # 3. Demostración de detección de bugs
    bug_found = demo_bug_detection()

    # Validación
    print("\n=== VALIDACIÓN ===")
    success = True

    if len(fuzzer.cases) >= 1000:
        print(f"✅ 1000 casos generados: {len(fuzzer.cases)}")
    else:
        print(f"❌ Casos insuficientes: {len(fuzzer.cases)} < 1000")
        success = False

    if len(fuzzer.violations) == 0:
        print("✅ 0 violaciones de propiedad")
    else:
        print(f"❌ Violaciones de propiedad: {len(fuzzer.violations)}")
        for v in fuzzer.violations[:3]:
            print(f"     - {v['property']}: {v['inputs']}")
        success = False

    total_covered = sum(c for c, _ in coverages.values())
    total_logical = sum(t for _, t in coverages.values())
    overall = total_covered / total_logical * 100 if total_logical else 0
    if overall > 95:
        print(f"✅ Coverage > 95%: {overall:.1f}%")
    else:
        print(f"❌ Coverage <= 95%: {overall:.1f}%")
        success = False

    missing_edges = fuzzer.edge_cases_detected()
    if not missing_edges:
        print(f"✅ Todos los edge cases ejercitados ({len(fuzzer.hit_edges)})")
    else:
        print(f"⚠️ Edge cases no ejercitados: {missing_edges}")

    if elapsed < 300:
        print(f"✅ Ejecución < 5 minutos: {elapsed:.2f}s")
    else:
        print(f"❌ Ejecución >= 5 minutos: {elapsed:.2f}s")
        success = False

    if bug_found:
        print("✅ Fuzzer detecta bugs: el bug del palíndromo vacío fue encontrado")
    else:
        print("❌ Fuzzer no detectó el bug plantado")
        success = False

    if success:
        print("\n✅ EJERCICIO COMPLETADO EXITOSAMENTE")
    else:
        print("\n❌ EJERCICIO NO COMPLETADO")

    return success


if __name__ == "__main__":
    print("Iniciando Ejercicio 2.5: Generación de 1000 Casos de Prueba con Fuzzing")
    print("Requisitos: 1000 casos, property-based, edge cases, < 5 min, > 95% coverage")
    print()

    result = test_fuzzing()

    if result:
        print("\n🎉 ¡Felicidades! Has completado el Ejercicio 2.5")
    else:
        print("\n⚠️ Necesitas optimizar el sistema para cumplir los requisitos")
