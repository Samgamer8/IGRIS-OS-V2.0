# Politica de autonomia de IGRIS OS v4.0

## Objetivo

IGRIS debe funcionar y programar localmente sin cuotas, cuentas, API keys ni
servicios cloud obligatorios. Las integraciones externas pueden existir solo
como adaptadores opcionales y nunca deben bloquear el nucleo local.

## Niveles de dependencia

### Nivel 0 - Codigo propio

Nucleo OODA, contratos, router, memoria, retrieval, auditoria, permisos,
sandbox, staging, verificadores, cola de misiones y coordinacion.

Regla: debe funcionar sin Internet y debe tener pruebas locales.

Implementacion actual: `LocalProgrammingBenchmark` evalua sintaxis, seguridad
y ejecucion sandboxed sin red, cuentas ni cuotas.

Las sesiones de entrenamiento deben conservar evidencia local de cada caso y
solo promocionar estrategias que mejoren las pruebas sin introducir regresiones.

### Nivel 1 - Software libre o local instalable

Python, PyQt6, Ollama, Git, FFmpeg, FFprobe, Godot y otros ejecutables locales.

Regla: detectar disponibilidad, informar limites y degradar con claridad si
falta una herramienta. No descargar ni instalar silenciosamente.

### Nivel 2 - Adaptadores opcionales

Proveedores OpenAI-compatible, Groq, Cerebras, Hugging Face, GitHub y servicios
similares.

Regla: requieren configuracion explicita, no son necesarios para arrancar ni
para programar con el modo local.

### Nivel 3 - Servicios con cuenta o cuota

Cloud, telemetria externa, APIs de pago, SaaS y almacenamiento remoto.

Regla: no entran en el runtime base de V4. Solo se evaluaran para funciones
opcionales y con consentimiento.

## Criterio de autosuficiencia

Una capacidad se considera localmente autosuficiente solo si:

1. funciona sin Internet;
2. no requiere cuenta ni API key;
3. tiene una alternativa local o devuelve una limitacion clara;
4. tiene pruebas reproducibles;
5. registra evidencia de lo que hizo;
6. puede cancelarse o terminar por timeout;
7. no modifica fuera del workspace autorizado.

## Prioridades de desarrollo

1. Mejorar herramientas propias de análisis y edición.
2. Mejorar verificación, rollback y aprendizaje por experiencias.
3. Añadir soporte local para más lenguajes y toolchains.
4. Crear benchmarks de modelos locales.
5. Integrar servicios externos solo como fallback opcional.

## Decisión

No se instalarán ni incorporarán automáticamente los recursos de un catálogo
externo. Se estudiarán sus ideas y se implementarán versiones propias cuando
aporten valor y puedan mantenerse localmente.
