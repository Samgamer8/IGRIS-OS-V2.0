# Privacidad y tratamiento local de datos

IGRIS OS está diseñado como aplicación local-first. Conversaciones, memoria,
auditoría y artefactos de trabajo se almacenan en el equipo del usuario.

No se garantiza tratamiento exclusivamente local cuando el usuario configura
un proveedor externo opcional. En ese caso, las entradas enviadas quedan
sujetas a las condiciones y políticas de dicho proveedor.

Antes de soporte técnico o distribución:

- elimina o excluye `runtime/`;
- no adjuntes bases de datos, historiales, claves ni `.env`;
- revisa los proyectos generados por si contienen datos personales;
- informa al usuario de cualquier proveedor externo habilitado.

IGRIS no debe utilizarse para procesar datos regulados sin una evaluación legal
y de seguridad específica del vendedor y del entorno de despliegue.
