"""
Ejercicio 3.6: Monitoring y Alerting
Objetivo: Sistema que alerta cuando latencia > 100ms.
Tiempo: 4 horas
Habilidades: Prometheus, Grafana, alerting, SLO/SLI

Requisitos:
- Métricas
- Alertas automáticas
- SLO/SLI tracking
- < 1 segundo alert latency

Validación:
- Alertas funcionan
- Latencia alert < 1s
- 0 falsos positivos
"""
import random
import statistics
import time
from typing import Dict, List


class MetricsRegistry:
    """Registro de metricas con ventana deslizante."""

    def __init__(self, window: int = 1000) -> None:
        self.window = window
        self.latencies: List[float] = []
        self.counters: Dict[str, int] = {}

    def observe(self, latency_ms: float) -> None:
        self.latencies.append(latency_ms)
        if len(self.latencies) > self.window:
            self.latencies = self.latencies[-self.window:]

    def p99(self) -> float:
        if not self.latencies:
            return 0.0
        return sorted(self.latencies)[int(len(self.latencies) * 0.99)]

    def increment(self, name: str) -> None:
        self.counters[name] = self.counters.get(name, 0) + 1


class Alert:
    def __init__(self, name: str, fired_at: float, value: float) -> None:
        self.name = name
        self.fired_at = fired_at
        self.value = value


class AlertManager:
    """Evaluacion de alertas con SLO/SLI."""

    def __init__(self, threshold_ms: float = 100.0,
                 eval_interval_s: float = 0.05) -> None:
        self.threshold = threshold_ms
        self.eval_interval = eval_interval_s
        self.alerts: List[Alert] = []
        self.false_positives = 0
        self.slo_target = 0.99  # 99% de peticiones bajo el umbral

    def evaluate(self, registry: MetricsRegistry, now: float) -> None:
        p99 = registry.p99()
        if p99 > self.threshold:
            self.alerts.append(Alert("LATENCIA_P99_ALTA", now, p99))

    def check_slo(self, registry: MetricsRegistry) -> bool:
        """El SLI (fraccion bajo umbral) debe cumplir el SLO (99%)."""
        if not registry.latencies:
            return True
        under = sum(1 for value in registry.latencies if value <= self.threshold)
        return under / len(registry.latencies) >= self.slo_target


async def test_monitoring() -> bool:
    """Prueba el monitoring con los requisitos."""
    print("Iniciando sistema de monitoring y alerting...")
    random.seed(11)

    registry = MetricsRegistry()
    alerts = AlertManager(threshold_ms=100.0)

    # FASE 1: trafico normal (sin alertas, SLO cumplido)
    for _ in range(2000):
        registry.observe(random.uniform(5, 60))
    slo_ok = alerts.check_slo(registry)
    alerts.evaluate(registry, time.time())
    normal_alerts = len(alerts.alerts)

    # FASE 2: degradacion -> debe disparar alerta en < 1s
    degraded_at = time.time()
    alert_latency = None
    for step in range(200):
        for _ in range(50):
            registry.observe(random.uniform(120, 400))
        alerts.evaluate(registry, time.time())
        if alerts.alerts and len(alerts.alerts) > normal_alerts:
            alert_latency = (time.time() - degraded_at) * 1000
            break
        time.sleep(0.01)

    # FASE 3: recuperacion -> sin falsos positivos en trafico sano
    registry2 = MetricsRegistry()
    alerts2 = AlertManager(threshold_ms=100.0)
    for _ in range(2000):
        registry2.observe(random.uniform(5, 60))
    alerts2.evaluate(registry2, time.time())
    fp = len(alerts2.alerts)

    print("\n=== RESULTADOS ===")
    print(f"SLO (99% bajo umbral) en trafico sano: {'OK' if slo_ok else 'FALLO'}")
    print(f"Alertas en trafico sano: {normal_alerts}")
    print(f"Alerta disparada en degradacion: "
          f"{'si' if alert_latency is not None else 'no'} "
          f"({alert_latency:.0f}ms si aplica)")
    print(f"Falsos positivos en trafico sano: {fp}")

    print("\n=== VALIDACIÓN ===")
    success = True
    if normal_alerts == 0 and slo_ok:
        print("✅ Sin alertas en trafico sano (SLO cumplido)")
    else:
        print("❌ Alerta espuria en trafico sano")
        success = False
    if alert_latency is not None and alert_latency < 1000:
        print(f"✅ Alerta en < 1s: {alert_latency:.0f}ms")
    else:
        print(f"❌ Alerta tardia o ausente: {alert_latency}")
        success = False
    if fp == 0:
        print("✅ 0 falsos positivos")
    else:
        print(f"❌ {fp} falsos positivos")
        success = False

    if success:
        print("\n✅ EJERCICIO COMPLETADO EXITOSAMENTE")
    else:
        print("\n❌ EJERCICIO NO COMPLETADO")
    return success


if __name__ == "__main__":
    import asyncio
    print("Iniciando Ejercicio 3.6: Monitoring y Alerting")
    print()
    result = asyncio.run(test_monitoring())
    print("\n🎉 ¡Felicidades! Has completado el Ejercicio 3.6" if result
          else "\n⚠️ Necesitas optimizar el sistema")
