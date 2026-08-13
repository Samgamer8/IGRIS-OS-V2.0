# Seguridad

- Las capacidades destructivas estan bloqueadas.
- Toda escritura declarada requiere confirmacion explicita.
- Cada mision trabaja dentro de su propio directorio bajo `runtime/missions`.
- Las rutas se validan por pertenencia real, no por coincidencia textual.
- La auditoria no debe almacenar secretos ni contenido privado completo.
- Este nucleo no ejecuta comandos arbitrarios. Esa capacidad se incorporara solo
  con aislamiento del sistema operativo y pruebas adversariales.

