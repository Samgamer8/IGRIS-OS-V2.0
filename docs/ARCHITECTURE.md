# Arquitectura inicial

La interfaz, CLI y futuras integraciones llaman exclusivamente a `IgrisKernel`.
El kernel consulta el registro, aplica la politica, crea el workspace, ejecuta
la capacidad y registra el resultado. Las capacidades no deciden sus propios
permisos.

Los datos de ejecucion viven bajo `runtime/`, fuera del paquete y del control de
versiones. El nucleo no depende de una interfaz grafica ni de un proveedor de IA.

## Subsistemas

- application: kernel, registro y director de misiones.
- security: riesgo, consentimiento y bloqueo destructivo.
- programming: verificacion Python aislada.
- files: inventario, hashes y lectura confinada.
- memory: recuerdos SQLite que no se usan hasta ser verificados.
- ai: Ollama local con fallo controlado.
- tools: descubrimiento de herramientas multimedia y videojuegos.
- evolution: candidatos medidos, nunca auto-promocion de produccion.
- ui: panel militar; muestra planes reales, no porcentajes ficticios.

## Limites actuales

La calidad depende del modelo instalado y de las herramientas externas disponibles.
IGRIS verifica antes de entregar, pero no promete infalibilidad. Las capacidades de
edicion multimedia y motores de juego se habilitan mediante adaptadores confinados.
