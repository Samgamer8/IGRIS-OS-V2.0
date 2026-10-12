# IGRIS OS

**Orquestador local con permisos y entregas ejecutables verificables.**

IGRIS OS es un sistema operativo de agente IA *local-first* para Windows. No es un
chat: es un orquestador que **resuelve misiones completas**, respeta un **control
de permisos** explícito y **entrega trabajo verificable** (código que compila,
tests que pasan) en lugar de promesas sin ejecutar.

> **Filosofía:** demostrar una capacidad concreta y comprobable, no simular un
> agente general. Cada entrega viene con su evidencia (build, tests, hash).

---

## Por qué IGRIS OS

| | IGRIS OS | Chatbots generales (ChatGPT, Claude…) |
|---|---|---|
| **Ejecución** | Ejecuta y **verifica** lo que entrega | Sugieren código sin ejecutarlo |
| **Datos** | *Local-first*: tus archivos y proyectos no salen de tu PC salvo que elijas un proveedor remoto | Todo pasa por la nube |
| **Permisos** | Control explícito (READ_ONLY / WRITE / EXECUTE) con *gate* de consentimiento | Sin control fino por acción |
| **Multi-proveedor** | Local (Ollama) + remotos OpenAI-compatible, con **cadena de fallback** y recuperación de stream | Un solo proveedor |
| **Verificabilidad** | 250 tests, hash SHA-256 por entrega | Opaco |

---

## Características principales

- **66 capabilities registradas** organizadas por dominio (sistema, archivos,
  programación, git, red, voz, *reverse engineering*, productividad…).
- **Entrega verificable:** el kernel ejecuta, compila y prueba; adjunta evidencia.
- **Control de permisos + consentimiento:** IGRIS **pregunta antes** de tocar algo
  sensible; la duda tiene prioridad sobre un "no" ambiguo.
- **Multi-proveedor con fallback:** cadena ordenada de modelos; si uno falla, otro
  continúa la respuesta (recuperación a mitad de stream).
- **Reverse engineering (ética y legal):** analiza binarios/paquetes de software
  propio o autorizado y propone capacidades **propias** inspiradas en lo observado.
- **Memoria persistente:** historial y hechos a largo plazo entre sesiones, 100% local.
- **Panel de control nativo** (PyQt6) con diagnóstico completo del PC y de IGRIS.

---

## Requisitos

- **Windows 10/11** (usa Job Objects nativos para el sandbox).
- **Python 3.11+**.
- Opcional: **GPU** y [Ollama](https://ollama.com) para inferencia local.
- Dependencias: `requests`, `psutil`, `PyQt6` (las tres se instalan solas).

---

## Instalación

```powershell
git clone https://github.com/Samgamer8/IGRIS-OS-V2.0.git
cd IGRIS-OS-V2.0
python -m venv .venv
.\.venv\Scripts\activate
pip install -e .
```

O ejecuta directamente `INSTALAR_IGRIS_OS.cmd` / `launch_igris.cmd`.

---

## Uso

**Panel de control** (interfaz gráfica):
```powershell
igris panel
```

**Línea de comandos** — comandos reales, por ejemplo:
```powershell
igris health              # Diagnóstico completo del sistema y de IGRIS
igris capabilities        # Lista las 66 capacidades y su nivel de riesgo
igris providers           # Proveedores de IA disponibles
igris work "…" --approve-execution   # Resolver una misión de programación verificada
igris verify              # Verificar una entrega previa
```
Para la lista completa: `igris --help`.

---

## Arquitectura (a vista de pájaro)

```
igris_os/
├── application/   # Asistente, orquestador, misiones, gate de consentimiento
├── ai/            # Multi-proveedor, cadena de fallback, router de modelos
├── capabilities/  # 66 capacidades por dominio (cableadas en bootstrap)
├── files/         # Análisis de artefactos, repositorios, blueprint, staging
├── memory/        # Memoria persistente (historial + hechos a largo plazo)
├── ui/            # Panel de control nativo (PyQt6)
└── domain/        # Modelos y contratos del kernel
```

---

## Estado y calidad

- **Versión:** 5.1.0a8 (Beta).
- **262 módulos** de Python, **36 suites de test**, **250 tests** en verde.
- Cobertura de seguridad: sandbox con Job Object, validación de rutas, *gate* de
  consentimiento y permisos por capacidad.

---

## Licencia

**Propietaria — Todos los derechos reservados.** Uso personal, educativo o de
evaluación interna. Cualquier uso comercial requiere licencia por escrito del autor.

Consulta [LICENSE](LICENSE) para los términos completos.

---

## Autor

**Samuel (Samgamer8)** — [GitHub](https://github.com/Samgamer8/IGRIS-OS-V2.0)
