# IGRIS OS v4.0 - Orden de evolucion

La evolucion se ejecuta por fases. No se distribuye ni se eliminan versiones antiguas hasta que la fase anterior tenga pruebas reproducibles.

## Fase 1 - Conversacion dinamica


Criterio de salida: saludos, preguntas, criticas y conversaciones largas reciben una respuesta dinamica sin timeout ni silencio.

Estado: validada con pruebas focalizadas, medicion real y suite global completa:
466 passed, 13 skipped. La suite global queda aprobada en el estado actual.

Modelo predeterminado: `qwen2.5-coder:7b` por latencia. Puede probarse
`IGRIS_CONVERSATION_MODEL=gemma4:26b` cuando se priorice naturalidad sobre
tiempo de respuesta.

## Fase 2 - Voz fiable

- Texto TTS limpio y fiel al texto visible.
- Transporte UTF-8 robusto.
- Una sola reproduccion activa.
- Voz y cultura espanolas verificadas.
- Pruebas con acentos, signos y textos largos.

Criterio de salida: el audio no mezcla palabras ni pronuncia metadatos tecnicos.

Estado: validada tecnicamente. Transporte UTF-8, limpieza de texto,
serializacion, reemplazo de audio pendiente y ciclo de vida del proceso TTS
comprobados. La confirmacion auditiva queda como prueba manual del usuario.

## Fase 3 - Ingeniero critico

- Analisis de riesgos antes de modificar codigo.
- Evidencia separada de inferencias.
- Cambios en workspace aislado.
- Pruebas y compilacion obligatorias.
- Confirmacion para escritura, ejecucion o acciones destructivas.

Estado: contrato de comportamiento integrado en la respuesta tecnica y
validado. La conexion con cada flujo especializado de modificacion queda
pendiente.

Validacion actual: prompts de generacion, reparacion, sandbox y capacidades
especializadas aprobados.

Primera habilidad de programacion: `ProgrammingPreflight`. Inspecciona un
proyecto en solo lectura, detecta sintaxis invalida, llamadas sensibles,
ausencia de pruebas y limites de inspeccion, y devuelve evidencia estructurada.

Ejecucion controlada: `programming.execute_verified`. Requiere confirmacion,
usa una lista blanca de ejecutables, limita workspace, memoria, procesos y
tiempo, y devuelve codigo de salida, stdout, stderr y estado de sandbox.

Flujo integrado: `EngineeringWorkflow` encadena preflight, bloqueo de riesgos,
confirmacion, allowlist y ejecucion sandboxed en una unica ruta verificable.

Diagnostico publico: `programming.assess` expone hechos verificados, riesgos,
dudas, propuesta y pruebas necesarias sin modificar el proyecto.

Benchmark local: `programming.benchmark` evalua sintaxis, seguridad y ejecucion
sandboxed sin cuentas, cuotas ni servicios externos.

Entrenamiento local inicial: 8/8 casos aprobados. Incluye Python valido,
SyntaxError, `eval` peligroso, cuatro contratos conversacionales y ejecucion
sandboxed. Esta puntuacion valida el sistema de evaluacion, no certifica por si
sola la calidad del modelo.

Propuesta publica: `programming.propose` convierte el diagnostico en un plan
de cambios con archivos afectados, riesgos, pruebas y confirmacion requerida.

Integracion de panel: las carpetas adjuntas pueden solicitar diagnostico o
propuesta desde la UI; el resultado se muestra antes de cualquier confirmacion
y no modifica la fuente original.

La suite global posterior a estas integraciones termina con codigo `0`; el
log de la ejecucion se conserva fuera del repositorio como evidencia temporal.

## Estado de consolidacion

La regresion focalizada y la suite global estan aprobadas. Queda pendiente la
validacion manual prolongada de la GUI, voz y uso real antes de declarar V4
lista para distribucion.

## Fase 4 - Validacion y distribucion

- Suite completa estable.
- Pruebas de latencia y procesos.
- Ejecutable portable reproducible.
- Documentacion de instalacion y rollback.

## Fase 5 - Limpieza historica

Solo despues de validar V4 y crear un inventario de eliminacion. Las fuentes V2, V3, worktrees y archivo permanecen intactas hasta aprobacion explicita.
