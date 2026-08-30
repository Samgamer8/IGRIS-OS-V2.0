# Seguridad de IGRIS OS

- Las acciones destructivas están bloqueadas por defecto.
- Escribir, ejecutar, publicar o actuar externamente requiere permiso.
- Los permisos son firmados, ligados a proyecto/capacidad, caducan y son de un uso.
- El código generado usa Job Objects con límites de memoria, CPU, procesos y tiempo.
- Un Job Object no sustituye una VM frente a código hostil: sin secretos ni red por defecto.
- Ninguna entrega se marca completa sin salida cero y evidencia.
