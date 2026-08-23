# Inventario de toolchain local

## Disponible en V4

- Python 3.14.7
- Ollama local
- Modelos locales detectados: qwen2.5-coder:7b, gemma4:26b y nomic-embed-text
- PyQt6
- pytest
- PyInstaller
- Git
- PowerShell
- SAPI / System.Speech

## Integraciones propias

- `ProgrammingPreflight`: inspeccion estatica de solo lectura.
- `EngineeringAssessor`: hechos, riesgos, dudas y pruebas.
- `ChangeProposalBuilder`: propuesta sin escritura.
- `EngineeringWorkflow`: confirmacion, allowlist, sandbox y evidencia.
- `RepositoryDeveloper`: staging, cambios y rollback.
- `MultiLanguageVerifier`: validacion por lenguaje.

## Reglas

- Ningun modelo cloud es requisito de arranque.
- Ninguna API key se almacena en codigo.
- Ninguna herramienta se ejecuta sin disponibilidad comprobada.
- Ninguna capacidad declara exito sin evidencia.
- Los modelos adicionales se incorporan solo despues de benchmark local.
