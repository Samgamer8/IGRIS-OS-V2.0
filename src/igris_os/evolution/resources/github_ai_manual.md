# Guia oficial de GitHub sobre IA/Copilot (resumen de referencia)

Fuentes: docs.github.com/en/copilot/get-started/best-practices y
docs.github.com/en/copilot/concepts/prompting/prompt-engineering
(descargadas el 2026-10-04 para uso como contexto de debate offline).

## Buenas practicas para usar un asistente de IA de codigo

- Entiende sus puntos fuertes (tests, codigo repetitivo, depuracion de
  sintaxis, explicar/comentar codigo, expresiones regulares) y sus limites
  (no sustituye el criterio del desarrollador; siempre hay que revisar).
- Elige la herramienta correcta: sugerencias en linea para completar
  mientras escribes; chat para tareas grandes, iterar, y "roles" (pedirle
  que actue como un perfil concreto, p. ej. "Senior C++ Developer centrado
  en calidad y legibilidad").
- Verifica siempre el resultado: entiende el codigo antes de aceptarlo,
  revisalo por seguridad/legibilidad/mantenibilidad, y apoyate en tests y
  linters automaticos como capa adicional de control.
- Dale contexto util: archivos relevantes abiertos, elimina del historial
  lo que ya no aporte, se especifico con simbolos/archivos concretos.

## Ingenieria de prompts

- Empieza general, luego especifica: describe el objetivo amplio primero y
  anade requisitos concretos despues.
- Da ejemplos: datos de entrada, salidas esperadas, o tests unitarios como
  especificacion antes de pedir la implementacion.
- Divide tareas complejas en tareas simples encadenadas en vez de un unico
  prompt monolitico.
- Evita ambiguedad: nunca "esto/eso" sin que quede claro a que te refieres;
  nombra funciones/variables/archivos explicitamente.
- Indica el codigo relevante (abre/cierra archivos, referencia simbolos).
- Experimenta e itera: si la respuesta no sirve, reformula en vez de
  insistir con el mismo prompt.
- Manten el historial relevante: nueva conversacion por tarea nueva; borra
  lo que ya no ayude.
- Sigue buenas practicas de codigo tu mismo (nombres descriptivos, estilo
  consistente, modularidad, tests) porque la calidad de lo que ya existe
  condiciona la calidad de lo que el asistente sugiere.
