# Revision historica V2, V3 e IGRIS_Archivo

Fecha: 2026-08-23

## Decision

V4 continua como unica base activa. No se migro codigo de V2 ni V3 porque sus
componentes unicos no superan la arquitectura y controles actuales.

## V2

- `context/`: prototipo de parser y grafo Python. No exportaba `ContextEngine`
  aunque un test lo importaba. Su resolucion de dependencias era superficial y
  no soportaba el contexto multimodulo actual de V4.
- `agents/`: prototipo de coordinacion. Si el LLM falla, algunos agentes
  construyen una respuesta fallback marcada como exitosa. Ese contrato puede
  ocultar fallos y no se acepta en V4.
- `llm/`: adaptadores antiguos reemplazados por `ai/`, contratos IPC y router
  de V4.
- Copias antiguas de `ai`, `assistant`, `creation`, `developer`, `voice` y UI:
  no se migran.
- `runtime/voice_dataset`: no se migra ni se elimina en esta operacion; queda
  en `IGRIS_Archivo` si requiere conservación futura.

## V3

- Los 9 archivos de codigo distintos y 5 tests distintos eran versiones
  anteriores de componentes ya presentes y validados en V4.
- No se identifico capacidad unica necesaria para V4.

## IGRIS_Archivo

Se conserva intacto por instruccion del usuario. Contiene prototipos, material
visual, respaldos y referencias de agentes que se revisaran en una fase aparte.

## Eliminacion autorizada y ejecutada

Se eliminaron las carpetas completas `IGRIS OS V2.O` y `IGRIS OS V 3.0` despues
de revisar sus fuentes, comparar hashes y registrar esta decision. V2 fue
eliminada completamente. V3 quedo vacia y solo conserva el directorio contenedor
porque un terminal de PowerShell lo mantiene abierto; se puede borrar al cerrar
ese terminal. `IGRIS OS V2.O.worktrees` no se elimino en esta operacion.
