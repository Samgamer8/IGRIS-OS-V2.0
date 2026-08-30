# IGRIS OS — Guía de usuario

## Inicio

Ejecuta `IGRIS OS.exe` desde la carpeta de distribución. El primer inicio
puede tardar mientras Windows extrae el ejecutable portable.

## Requisitos

- Windows 11 de 64 bits.
- Ollama local para conversación y generación mediante modelos locales.
- Micrófono y voces SAPI de Windows solo para las funciones de voz.
- Toolchains externos únicamente para proyectos que los necesiten.

## Uso seguro

IGRIS muestra planes y resultados antes de entregar proyectos. Las escrituras,
ejecuciones y entregas sensibles conservan sus puertas de confirmación. Revisa
siempre la carpeta de staging y las pruebas antes de distribuir código generado.

## Datos

Los datos operativos se guardan localmente junto al runtime portable. No copies
la carpeta `runtime` al distribuir una instalación usada. Las claves de
proveedores opcionales no deben guardarse dentro de la carpeta del producto.

## Diagnóstico

Desde una copia con fuentes puede ejecutarse:

```powershell
python main.py health
python tools/quality_gate.py
```

Cada distribución incluye `SHA256SUMS.txt`; compara su valor con el SHA-256 del
ejecutable antes de instalar o vender la copia.

## Recuperación

IGRIS no sobrescribe entregas existentes. Conserva una copia del instalador y
de los proyectos entregados. Para restaurar una instalación limpia, cierra el
programa, respalda `runtime` y vuelve a extraer la distribución original.
