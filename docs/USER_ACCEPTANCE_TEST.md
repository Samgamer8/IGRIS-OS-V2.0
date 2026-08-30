# Prueba de aceptación de IGRIS OS 4.0 RC1

Registra cada resultado como `OK`, `FALLO` o `NO PROBADO` y copia cualquier
mensaje visible. No introduzcas claves ni datos personales durante esta prueba.

## 1. Inicio y cierre

1. Abre `IGRIS OS v4.0.exe`.
2. Confirma que aparece una sola ventana y que responde al moverla.
3. Abre ajustes y vuelve al panel.
4. Cierra IGRIS y confirma que no queda audio reproduciéndose.

## 2. Conversación local

1. Escribe: `Hola IGRIS, dime qué modelo local estás usando.`
2. Confirma que aparece una respuesta o un error accionable, nunca silencio.
3. Escribe una segunda pregunta relacionada y comprueba continuidad.

## 3. Voz

1. Activa la voz y reproduce una respuesta con acentos y números.
2. Comprueba que no pronuncia metadatos, Markdown ni rutas internas.
3. Interrumpe la reproducción con una respuesta nueva.

## 4. Proyecto seguro

1. Solicita una aplicación Python pequeña con criterios verificables.
2. Comprueba que IGRIS muestra plan, staging y resultado de pruebas.
3. Rechaza una autorización y confirma que no aparece una entrega.
4. Repite, autoriza la entrega y confirma que incluye pruebas y evidencia.
5. Intenta entregar otra vez en la misma carpeta: debe negarse a sobrescribir.

## 5. Persistencia y recuperación

1. Cierra y abre IGRIS.
2. Comprueba que la configuración esperada persiste.
3. Verifica que una misión incompleta no se presenta como completada.

## Informe mínimo

- Windows y versión:
- Modelo Ollama:
- Voz seleccionada:
- Pasos con fallo:
- Texto exacto del error:
- Captura o vídeo:
- ¿Quedaron procesos tras cerrar?:
