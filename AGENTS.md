# Protección del panel de control

`src/igris_os/ui/cinematic.py` y `src/igris_os/ui/panel_presentation.py` son archivos protegidos del panel principal.

- No cambies su estructura, geometría, navegación, controles, estilos, comportamiento ni presentación sin autorización explícita y previa de Samva, como administrador del proyecto.
- La autorización debe nombrar el archivo protegido y el cambio concreto. Una petición de implementar funciones alrededor del panel no autoriza a editar esos archivos.
- Sin esa autorización, implementa funciones nuevas en una ventana o proceso independiente. No insertes widgets, pestañas, overlays ni llamadas nuevas dentro del panel.
- `panel_protection.json` registra las huellas SHA-256 aprobadas. La prueba `tests/test_panel_protection.py` debe pasar. No actualices las huellas sin la misma autorización explícita.
- Después de un cambio aprobado, verifica visualmente el panel en su resolución habitual y comprueba que sus controles no se solapan.
