# IGRIS OS V4.0

IGRIS OS V4.0 es la base limpia y verificable del asistente OODA para Windows 11.
Convierte órdenes en misiones verificables, aplica políticas de riesgo, ejecuta
capacidades aisladas y conserva evidencia de los resultados.

## Estado real

V4.0 es una **migración selectiva en validación**, no un producto autónomo terminado.
La arquitectura canónica está bajo `src/igris_os/` y usa:

- `IgrisDaemon` como orquestador central;
- fachadas separadas para AI, conversación, memoria y voz;
- `AIProcessRunner` para aislar las llamadas LLM en un subprocess;
- panel PyQt6 con galaxia operativa;
- sandbox, política de permisos, workspaces y auditoría;
- router de modelos con Ollama local y proveedores opcionales;
- memoria SQLite verificada y recuperación contextual;
- pruebas unitarias, integración, seguridad y E2E.

La corrección del Paso 0 garantiza que el chat real del panel pasa por:

```text
Panel → IgrisDaemon → ConversationDaemon → AIProcessRunner → AIDaemon → Ollama
```

## Estructura canónica

```text
main.py                  Punto de entrada unificado
src/igris_os/             Código de producción
  ai/                     Router, Ollama y subprocess AI
  application/            Misiones, kernel y conversación
  core/                   Orquestador central
  memory/                 Memoria persistente
  security/               Políticas y sandbox
  ui/                     Panel PyQt6 y galaxia
  voice/                  Voz Windows
  programming/            Capacidades de programación
tests/                   Tests verificables
tools/                   Quality gate, release check y utilidades
docs/                    Arquitectura, migración y validación
assets/                  Recursos del panel
legacy/                  Prototipos y runtime histórico, no ejecutables
```

`legacy/` se conserva para trazabilidad y recuperación. No forma parte del
runtime canónico y no debe importarse desde `src/igris_os`.

La carpeta V4 se construye en paralelo a las versiones anteriores. No se deben
eliminar fuentes históricas hasta completar la auditoría, comparar pruebas y
confirmar la distribución portable.

## Verificación

Desde esta carpeta:

```powershell
python -m pytest
python tools/release_check.py
$env:PYTHONPATH = "src"
python main.py health
$env:QT_QPA_PLATFORM = "offscreen"
$env:IGRIS_TEST_GUI = "1"
python main.py
python tools/quality_gate.py
```

## Limitaciones conocidas

- La calidad depende del modelo instalado y del proveedor seleccionado.
- La conversación human-like no equivale a conciencia ni comprensión humana total.
- La autonomía de programación requiere pruebas, permisos y verificación; no se
  considera segura por el mero hecho de que un modelo genere código.
- El quality gate con cobertura debe seguir validándose específicamente con
  multiprocessing en Windows.

No se deben almacenar claves, `.env`, modelos, builds ni bases de datos en Git.
