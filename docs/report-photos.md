# Fotos y miniaturas

Cada aviso de pérdida, avistamiento o reporte de mascota encontrada admite hasta **cinco fotos** JPEG, PNG o WebP, de hasta **10 MiB por foto**. Los avistamientos breves sin cuenta tienen el mismo límite.

## Interfaz

- Se pueden elegir varias imágenes juntas o agregarlas de a una. La selección no se reemplaza al volver a abrir el selector. Una selección que excede el límite se rechaza conservando las imágenes anteriores.
- La primera foto queda propuesta como miniatura. Se puede elegir cualquiera de las otras antes de enviar y quitar imágenes pendientes. Al quitar la elegida, se propone la primera que queda.
- La revisión del formulario muestra la cantidad y la miniatura elegida. La carga del lote es atómica: si falla una imagen, se revierte todo el lote y se informa el problema sin duplicar el reporte ya creado.
- En **Mis avisos → Fotos y miniatura** se pueden ver, ampliar, agregar o quitar fotos y cambiar la principal. Incluye los avistamientos y mascotas encontradas publicados por esa cuenta. La edición requiere la cuenta autora y el correo confirmado, como la carga existente.
- La miniatura se utiliza en fichas, tarjetas, mapa y galerías de notificaciones. El visor ampliado conserva acceso al resto de las fotos. Los avistamientos anónimos eligen su miniatura al enviarse; la ausencia de cuenta no concede permisos posteriores de edición a otras personas.

## API y almacenamiento

- `POST /api/v1/photos/upload-batch`: `owner_type`, `owner_id`, una a cinco partes `files` y `primary_index` opcional (índice desde cero dentro del lote nuevo). Sin índice se conserva la miniatura anterior; en un álbum vacío se elige la primera foto.
- `GET /api/v1/photos/album?owner_type=…&owner_id=…`: fotos ordenadas con la miniatura primero, `primary_photo_id` y `max_photos`. Es privado y requiere propiedad del reporte.
- `PUT /api/v1/photos/cover`: `owner_type`, `owner_id`, `photo_id`. Solo admite una foto del álbum autorizado.
- `GET /api/v1/photos/{id}/image`: imagen privada sin metadatos, protegida por la propiedad de la foto. El navegador accede mediante el intermediario de sesión de Next.js.
- Los endpoints anteriores de carga individual y alta de metadatos se conservan, con el mismo límite acumulado de cinco.

La tabla `photo_covers` de la migración **0028_photo_covers** guarda una elección por publicación. No mueve fotos ni cambia sus identificadores. Las fotos anteriores conservan el orden de respaldo que utilizaban si todavía no se eligió una miniatura. Una miniatura de un aviso puede ser una foto heredada del perfil de su mascota, sin cambiar la elección de otros avisos. Las fotos heredadas cuentan para el límite de cinco del aviso. La carga al perfil también verifica el espacio disponible en sus avisos existentes.

Las comprobaciones de capacidad y la elección de miniatura se serializan mediante bloqueos de la mascota/caso u observación. No se eliminan fotos anteriores para imponer el límite: un álbum histórico más grande debe reducirse antes de admitir imágenes nuevas. Al eliminar una miniatura se retira su referencia y se usa la siguiente foto disponible. Las eliminaciones de objetos se encolan después de retirar la foto de la base de datos, evitando borrar objetos antes de confirmar la operación.

Todas las fotos se analizan con los mecanismos existentes. Elegir otra miniatura no genera análisis ni modifica los pesos del matching.

## Despliegue

Respaldar PostgreSQL y ejecutar `alembic upgrade head` antes de iniciar esta versión. La migración solo agrega la tabla de elecciones y no borra imágenes existentes. Reiniciar API y workers con el mismo código.

Los intermediarios web admiten hasta 52 MiB por lote y el servidor frontal limita el cuerpo a 55 MB, con 120 segundos para recibirlo. La admisión de cargas mantiene su límite de concurrencia y libera el turno al terminar; el resguardo temporal vence a los 240 segundos. No se habilitan pagos ni se modifica la configuración de IA o almacenamiento.
