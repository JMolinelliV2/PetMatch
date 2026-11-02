# Identificación de avisos y reportes

Cada aviso de pérdida, avistamiento y reporte de mascota encontrada tiene un código público permanente, por ejemplo **MM-000123**. Los tres tipos comparten la misma numeración. El código identifica la publicación, no a la mascota ni a la persona.

El código aparece en el catálogo, las fichas, las miniaturas y listas del mapa, Mis avisos, coincidencias y notificaciones. Al publicar se muestra en la confirmación, incluso para los avistamientos breves sin cuenta. La ficha y el panel propio permiten copiarlo. En Mascotas perdidas se puede buscar un aviso activo por su código completo, sin distinguir mayúsculas de minúsculas.

## Persistencia

- `public_number` se asigna una sola vez al insertar la publicación. No es un campo editable de la API.
- `public_id` presenta ese número con el prefijo `MM-` y al menos seis dígitos. La numeración puede superar los seis dígitos.
- Editar, cerrar, marcar como encontrado o reabrir conserva el código.
- Borrar un aviso o una cuenta conserva el número emitido en `publication_numbers`, sin datos personales. No se asigna de nuevo.
- La base asigna los números mediante autoincremento, dentro de la transacción de publicación. Las solicitudes concurrentes reciben números distintos. Los errores o las eliminaciones pueden dejar saltos; el último número no representa la cantidad de avisos.
- Los UUID internos y las rutas actuales siguen identificando las mismas publicaciones. El código público no concede acceso a datos privados y las búsquedas públicas mantienen los filtros de actividad y moderación.

## Instalaciones existentes

La migración `0019_publication_numbers`, posterior a `0018_notification_archive`, crea el registro de números y asigna códigos a los avisos y observaciones existentes, ordenados por fecha de creación con desempate determinista. Agrega restricciones de presencia, unicidad por tabla y referencia al registro de números. Se aplica con las demás migraciones al iniciar la API.

La interfaz acepta respuestas de una versión anterior de la API durante una actualización y, si falta el código público, muestra el UUID completo. No recorta UUIDs para simular un código único.
