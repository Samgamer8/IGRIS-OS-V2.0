# Componentes excluidos de la release comercial

Los siguientes módulos permanecen en el repositorio para investigación, pero
no se importan, registran ni prometen como funciones de la release:

- `igris_os.programming.project_generator`: generador histórico basado en
  marcadores; sustituido en producción por desarrolladores con staging y tests.
- `igris_os.delegation.claude_specialist`: integración declarada pendiente.
- Extras `multiagent`, `providers` y `media` cuando no se instalan explícitamente.

Una capacidad experimental solo puede entrar en una release posterior después
de integrarse en el registro, superar pruebas y actualizar estas notas.
