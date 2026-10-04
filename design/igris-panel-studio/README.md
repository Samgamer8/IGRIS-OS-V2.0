# Estudio visual del panel IGRIS

Prototipo de diseno separado de la aplicacion. No inicia IA, voz ni misiones, no
escribe preferencias de IGRIS y no modifica el proyecto de ajedrez pausado.

La vista Original dibuja la captura real sin cambios. Propuesta recompone una
imagen del panel utilizando esa captura, el arte original y los ajustes del
editor. La escena central es una imagen estatica, no la animacion en vivo.
Los indicadores y textos del render son muestras, no telemetria actual.

Los controles cambian composicion, separacion, bordes, acento y contraste.
Guardar borrador utiliza solamente localStorage del estudio. Exportar ajustes
crea un JSON con `scope: visual-only`; no es el archivo de configuracion real.
Exportar PNG guarda una imagen de 1440x810 sin el contorno de seleccion.

Los cambios aprobados se trasladaran al panel Qt en una etapa posterior.
Este estudio no promete que cada combinacion sea ya compatible con el layout Qt.

## Ejecucion

Desde esta carpeta:

```text
npm ci
npm run dev -- --host 127.0.0.1 --port 5185 --strictPort
```

Las referencias se copian desde `runtime/ui-review/panel_actual.png` y
`assets/igris_window_art_only_1600.png` del repositorio, sin editar los originales.

## Comprobaciones

```text
npm test
npm run test:ui
npm run build
```

Las pruebas de navegador utilizan Microsoft Edge, verifican la referencia por
pixeles muestreados, exportacion PNG, persistencia del borrador, vista movil y
que el checksum de `runtime/settings.json` no cambie.
Las capturas se generan en `evidence/`.