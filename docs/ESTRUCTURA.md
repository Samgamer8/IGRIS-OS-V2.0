# IGRIS OS V3.0 — estructura canónica

La carpeta `IGRIS OS V 3.0` es la base de trabajo canónica. El runtime ejecutable
usa exclusivamente `src/igris_os`; el material antiguo queda preservado en
`legacy/` y no participa en imports ni en el arranque.

```text
IGRIS OS V 3.0/
├─ main.py                       # entry point unificado
├─ pyproject.toml                # paquete y configuración de pytest
├─ PROJECT_STATE.json            # identidad y comandos verificables
├─ README.md                     # estado real y limitaciones
├─ SECURITY.md                   # reglas de seguridad
├─ assets/                       # recursos del panel
├─ src/igris_os/                 # código canónico
│  ├─ ai/                        # modelos, router y AIProcessRunner
│  ├─ application/               # misiones, kernel y conversación
│  ├─ core/                      # IgrisDaemon, orquestador central
│  ├─ memory/                    # memoria persistente verificada
│  ├─ programming/               # capacidades de programación
│  ├─ security/                  # política y sandbox
│  ├─ ui/                        # panel PyQt6 y galaxia
│  └─ voice/                     # voz Windows
├─ tests/                        # unit, integración, seguridad y E2E
├─ tools/                        # quality gate y release check
├─ docs/                         # arquitectura y continuidad
└─ legacy/                       # histórico preservado, no ejecutable
   ├─ v2_prototype/              # core/brain.py + GUI Tkinter anterior
   └─ runtime_snapshot/          # datos generados históricos, ignorados por Git
```

## Regla de evolución

Todo código nuevo va a `src/igris_os`, con pruebas bajo `tests`. No se añaden
funcionalidades a `legacy/`. Una migración solo se acepta cuando tiene contrato,
prueba de regresión, evidencia de ejecución y revisión del diff.

## Estado de verificación de la base

- Pytest completo: 359 passed, 4 skipped.
- Release check: aprobado.
- Entry point `main.py` en Qt offscreen: aprobado.
- `main.py health`: núcleo operativo.
- Routing conversacional al subprocess AI: comprobado con prueba real.
- Coverage completo: 56%, sobre el umbral mínimo actual del 55%.
