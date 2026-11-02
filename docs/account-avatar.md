# Foto de perfil

Mi cuenta permite elegir una imagen JPG, PNG o WebP de hasta 10 MB, moverla dentro del círculo, ajustar el zoom, guardar, reemplazar o quitar la foto. También incluye **Ajustar foto** para modificar el encuadre de la imagen guardada. Guardar y quitar muestran la confirmación habitual del sitio. Sin imagen se muestran las iniciales. El mismo componente circular se usa en el botón, el desplegable de cuenta y las reseñas de la portada; la sesión y las reseñas se actualizan al terminar el cambio.

La gestión de la foto está reservada al titular autenticado. Su foto actual también se muestra junto a las reseñas públicas con nombre o apodo, conservando la elección de publicar como Anónimo sin foto. No aparece en los avisos ni en sus datos públicos de autoría. No se crea un registro `Photo`, ni se programan trabajos de IA, embeddings o coincidencias. La carga requiere una cuenta activa con correo confirmado; la gestión y eliminación requieren la sesión del titular.

## Persistencia

La migración `0030_account_avatars`, posterior a `0029_description_format`, agrega dos campos opcionales a `users`: clave privada del objeto y versión UUID. Las cuentas existentes conservan las iniciales. `UserRead` expone únicamente la versión, nunca la clave de almacenamiento.

La API valida el tipo real, hasta 24 megapíxeles y el tamaño del archivo. Aplica la orientación EXIF, recorta al centro, genera un JPEG de 512 × 512 y elimina metadatos. Se almacena en `user_avatar/{user_id}/{uuid}.jpg` dentro del bucket privado. La web sirve la imagen por `/api/account-avatar`, mediante la sesión HttpOnly y respuestas privadas sin caché. No utiliza enlaces públicos ni firmados al almacenamiento.

El editor web valida el archivo elegido y sus dimensiones, muestra el área circular y calcula un recorte cuadrado con la misma posición y escala. Permite arrastrar con mouse o un dedo, usar las flechas del teclado, zoom de 100 a 300 % y **Restablecer ajuste**. Los límites impiden dejar huecos fuera de la imagen. Al guardar exporta exactamente ese encuadre a JPEG de 512 × 512 y lo envía a la API existente; la API limpia y almacena el cuadrado recibido sin cambiar su composición. Cancelar descarta los cambios locales.

**Ajustar foto** consulta la imagen privada actual y abre el mismo editor, sin volver a pedir un archivo. El ajuste trabaja sobre la imagen guardada: para recuperar partes descartadas en un recorte anterior se debe volver a elegir el archivo original. No se conservan originales adicionales ni se cambia el modelo de almacenamiento.

`GET`, `POST` y `DELETE /api/v1/auth/avatar` operan siempre sobre la cuenta autenticada, sin aceptar IDs de otros usuarios. La escritura usa el bloqueo de cuenta existente, controles de mismo origen en la web, lectura acotada del cuerpo y admisión de cargas. La versión cambia después de cada carga para renovar la imagen del menú.

`GET /api/v1/public/reviews/{review_id}/avatar`, a través de `/api/reviews/{review_id}/avatar` en la web, sirve el JPEG sin sesión únicamente si esa reseña sigue siendo pública, no es anónima y su autor conserva foto, cuenta activa y correo confirmado. Comparte los filtros de la lista de reseñas: aviso retirado y visible, perro o gato. No publica IDs de cuenta ni claves de almacenamiento. Las respuestas no se almacenan en caché; cambiar o quitar la imagen afecta las siguientes consultas de las reseñas existentes.

Reemplazar, quitar o eliminar la cuenta encola la imagen anterior en `PhotoDeletion`. El servicio de limpieza existente realiza la eliminación física. Los respaldos incluyen los objetos de avatar dentro del mismo manifiesto cifrado de imágenes; las versiones y respaldos conservan la política existente de retención.

## Presentación

La tarjeta mantiene el ancho y los estilos de Mi cuenta. En escritorio utiliza avatar de 112 px y controles al lado; en pantallas de hasta 640 px centra la foto y apila el contenido. Los botones permiten salto de línea, conservan áreas táctiles de al menos 44 px y las imágenes siempre se recortan dentro del círculo. No se modifica el guardado de datos de contacto ni las preferencias de notificaciones.

## Verificación local

Se comprobaron carga, reemplazo, versión nueva, lectura privada, eliminación y limpieza al borrar una cuenta, usando datos temporales en una transacción revertida. Se eliminaron los tres objetos de almacenamiento de la comprobación. Se verificó JPEG cuadrado sin EXIF, rechazo de archivos inválidos o demasiado grandes, correo sin confirmar, ausencia de claves privadas en la respuesta y de trabajos de IA nuevos.

La revisión visual usó el componente real en una página temporal de desarrollo, sin iniciar sesión ni modificar una cuenta real. Se revisaron anchos de 320, 390, 768 y 1280 px, sin desbordamientos, y los avatares circulares de 112, 40 y 30 px con una imagen ilustrativa. La página temporal se retiró al terminar.

El editor de encuadre se comprobó con arrastre real, flechas, zoom, restablecimiento y exportación a un JPEG de 512 × 512 en el navegador. Se verificaron los límites de recorte de imágenes horizontales, verticales y cuadradas, con varias posiciones y ampliaciones, y el diseño de 320 a 1280 px. La vista temporal utilizó una foto ya publicada sin guardar cambios en la cuenta, y se retiró después de la revisión.
