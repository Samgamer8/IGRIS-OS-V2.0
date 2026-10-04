# Perfil local profesional

## Combinacion adoptada

- Python conserva la coordinacion, permisos, herramientas y flujo de misiones.
- llama.cpp ejecuta el modelo de texto mediante C/C++ y CUDA, sin exigir Ollama.
- PyQt conserva la interfaz. No se agrega un navegador ni XAMPP.
- La memoria persistente existente conserva SQLite. No se agrega otro servidor SQL.
- Los especialistas comparten el cliente y el modelo local; no requieren LiteLLM.
- La voz conserva Chatterbox, el modelo de Espana y la referencia aprobada.
- No se instalan Aider ni LangGraph como dependencias obligatorias.

## Repositorios consultados

| Proyecto | Licencia del software | Decision |
| --- | --- | --- |
| [llama.cpp](https://github.com/ggml-org/llama.cpp) | MIT | Motor nativo instalado y comparado |
| [Aider](https://github.com/Aider-AI/aider) | Apache-2.0 | Referencia de flujo Git/pruebas; no se duplica el agente existente |
| [LangGraph](https://github.com/langchain-ai/langgraph) | MIT | Posible extension futura; no necesaria para esta optimizacion |

Se utiliza la compilacion oficial b11381 de llama.cpp para Windows/CUDA 13.4.
Los dos archivos ZIP se verificaron contra sus SHA256 publicados por GitHub y
se eliminaron al terminar la extraccion. Los binarios quedan en
`runtime/tools/llamacpp/b11381`. No se descargaron nuevos pesos de texto: se reutiliza
el GGUF Qwen2.5-Coder 7B Q4_K_M existente en la carpeta de modelos de Ollama.
Su ubicacion no exige que Ollama se ejecute, pero el archivo debe conservarse.

## Limites y configuracion

`runtime/settings.json` activa el perfil mediante `preferred_backend: openai`,
`exclusive_backend: true`, `native_executable` y `native_model_path`.
Aqui **openai significa protocolo compatible local**, no un servicio cloud de pago.

El servidor escucha solo en loopback, sin interfaz web y con origen CORS restringido.
Usa una ranura, contexto de 4096 tokens, cache KV q8_0, Flash Attention y hasta ocho
hilos CPU. Tras 180 segundos de inactividad se configura su suspension nativa.
No se espero ese intervalo durante las pruebas: no se atribuye un ahorro de reposo
medido a esta opcion. IGRIS termina los procesos que ha arrancado al cerrar la ventana;
no termina servidores externos que encuentre ya activos.

El modo exclusivo evita consultar/cargar otros motores para tareas sencillas.
Los modelos cloud se excluyen de los especialistas y los proveedores de pago se
bloquean tanto en seleccion como en ejecucion, incluido el fallback.
Las respuestas de texto tienen limites de salida; los contratos JSON se transmiten
al motor compatible. Las pruebas de disponibilidad se solapan en el modo multimotor.

El contexto de 4096 tokens es un limite del perfil, no capacidad para leer un
repositorio completo. Los encargos grandes necesitan seleccion de archivos y
trabajo por etapas. Una generacion demasiado grande o incompatible debe fallar con
evidencia, no presentarse como una entrega terminada.

## Mediciones de este equipo

Prueba corta, tres rondas, mismo GGUF y limite de 256 tokens. Los tiempos calientes
de las rondas 2 y 3 fueron:

| Configuracion | Tiempo caliente | GPU total observada |
| --- | --- | --- |
| Ollama, contexto 4096 | 1,1715 / 1,1619 s | 6049 MiB |
| llama.cpp, contexto 4096, KV q8_0 | 1,1806 / 1,1740 s | 5949 MiB |

La velocidad caliente es practicamente equivalente; no hay evidencia de una gran
aceleracion. La reduccion observada de unos 100 MiB incluye el sistema y no es una
medicion aislada del proceso. No comparar la primera ronda como arranque frio:
el servidor nativo ya habia cargado el modelo antes de esa ronda.

Arranque gestionado mas dos solicitudes: 10,65 s. Codigo generado por el motor
nativo: funcion validada con casos independientes en sandbox. Aceptacion local: 10/10.
Texto y voz de Espana cargados juntos: 7756 MiB de GPU total; primera sintesis, 25,64 s.
Esto deja poco margen en una GPU de 8 GB. No ejecutar a la vez grandes cargas 3D.
El audio corregido se transcribio localmente y contenia el texto solicitado.

Se detecto una salida de voz demasiado corta. Ahora se aplica una comprobacion
heuristica de duracion y hasta tres intentos reproducibles (semillas 42, 43, 44).
La heuristica no prueba fidelidad palabra por palabra; la transcripcion se uso solo
durante la validacion y no se agrega al consumo normal de IGRIS.

## Evidencia y vuelta atras

- `runtime/benchmarks/engine_comparison.json`: tiempos y respuestas de ambos motores.
- `runtime/benchmarks/managed_native.json`: arranque, JSON y especialista local.
- `runtime/benchmarks/generated_native.json`: ejecucion del codigo generado.
- `runtime/benchmarks/local_acceptance.json`: evaluacion local existente.
- `runtime/benchmarks/combined_voice.json`: convivencia de texto y voz.
- `runtime/logs/native_inference.log`: diagnostico del servidor gestionado.
- `runtime/settings_before_native_default.json`: valores previos, al no existir ajustes guardados.

Para volver al modo anterior, restaurar esos ajustes y reiniciar IGRIS. No se han
borrado modelos, proyectos, misiones, datos de usuario ni la referencia de voz.
La comparacion es una prueba acotada de este equipo, no demuestra ser el mejor
asistente ni sustituye la evaluacion de proyectos reales grandes.