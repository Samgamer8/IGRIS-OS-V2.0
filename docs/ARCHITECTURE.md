# Arquitectura canónica de IGRIS OS

Flujo obligatorio:

`petición → contrato → plan → generación aislada → revisión → permiso humano → ejecución confinada → pruebas → evidencia → entrega`

- El kernel coordina; las capacidades no se conceden permisos a sí mismas.
- Los tokens se ligan a ruta y capacidad, caducan y son de un uso.
- La puerta de entrega exige estructura, ejecución, timeout, salida y hashes.
- La generación ocurre fuera del núcleo y solo se promociona tras verificación.

Niveles de evidencia: contrato interno; entrega ejecutada; entrega gráfica con
motor, arranque y captura. V5 alcanza el segundo nivel para una aplicación y un
juego de terminal. Godot 4 no está disponible para validar el tercer nivel.
