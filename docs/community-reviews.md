# Reseñas de la comunidad

## Solicitud y publicación

- Después de **Cerrar aviso** o **Marcar como encontrado** en Mis avisos, el estado se guarda y se muestra una invitación independiente y opcional a escribir una reseña.
- Después de **Ya la recuperé** desde una notificación, se conserva la invitación fuera de la alerta que acaba de retirarse. Confirmar **Es mi mascota, sigo buscándola** no solicita reseña y mantiene la búsqueda activa.
- Los avisos propios en estado `FOUND`, `CLOSED` o `CANCELLED` muestran la invitación al volver a Mis avisos. Si ya hay una reseña, se muestra su estado y la opción de retirarla.
- **Ahora no** permite omitir la invitación y **Cancelar** permite salir del formulario sin afectar el aviso. Escribir una reseña no cambia el estado ni el matching.

El formulario pide de 1 a 5 estrellas, un comentario de 20 a 800 caracteres y autorización explícita para mostrar la reseña en la portada. El nombre público es opcional, admite un apodo y no se rellena desde la identidad de la cuenta: vacío significa **Anónimo**. Las reseñas con nombre muestran la foto de perfil actual cuando existe; las anónimas no muestran la foto. El formulario informa esta diferencia. No se publican correo, IDs de cuenta/aviso, contacto, fotos de mascotas ni ubicación.

Solo el dueño del aviso, con cuenta activa y correo confirmado, puede publicar. El servidor comprueba la titularidad y que el aviso esté cerrado o la mascota encontrada; no confía en el estado enviado por la web. El formulario conserva el texto al confirmar el correo en otra pestaña. La unicidad por aviso y el bloqueo de escritura evitan reseñas duplicadas por doble envío; también se aplican los límites generales de publicación.

## Portada

`HomeReviews` consulta la lista pública y no renderiza encabezado, espacio ni mensaje vacío cuando no hay reseñas. La sección se ubica después de los avisos activos y antes del bloque Apoyanos. Utiliza un panel azul suave con título centrado y tarjetas blancas, comillas coral y las estrellas reales. Las tarjetas muestran el comentario completo en cursiva, una foto circular de 52 px o las iniciales del nombre público, el nombre elegido y el mes/año. Conserva el ancho del inicio, con dos columnas en escritorio y una en celular; una única reseña queda centrada y limitada a 560 px.

Se consultan hasta seis reseñas recientes, sin filtrar por puntuación ni inventar testimonios, estrellas, nombres o resultados de búsqueda. Se muestran primero dos; **Ver más reseñas** permite desplegar las restantes en el mismo lugar y **Ver menos reseñas** vuelve a la vista inicial. El botón solo aparece cuando hay más de dos y comunica su estado mediante `aria-expanded`. Las tarjetas ocultas también se retiran de la navegación accesible con `hidden`; el comentario no se recorta. La función de presentación `ReviewsSection` reutiliza este mismo diseño sin cambiar el envío, la moderación ni la autorización de las fotos.

Se incluyen solo reseñas visibles de cuentas activas con correo confirmado y avisos retirados que no estén ocultos por moderación. Reabrir una búsqueda retira temporalmente su reseña de la lista pública; cerrarla de nuevo permite mostrar la misma reseña, sin crear otra. La consulta evita caché; la portada actualiza al cargar y recuperar el foco. Un fallo de carga también oculta la sección.

## Retirada y administración

**Retirar mi reseña de la portada** cambia su visibilidad a `WITHDRAWN`; conserva un registro privado y no vuelve a pedirla ni permite restaurarla desde administración. Las reseñas se consultan en `/admin` → Registros de la plataforma → Reseñas, donde se pueden ocultar/restaurar las demás. Las acciones administrativas se auditan. El bloqueo de la cuenta o la eliminación definitiva del aviso también retiran su reseña pública; el borrado del aviso elimina la reseña mediante su clave foránea.

## Rutas

| Método | Ruta de API | Acceso |
| --- | --- | --- |
| GET | `/api/v1/public/reviews?limit=6` | Público; máximo 12 |
| GET | `/api/v1/public/reviews/{review_id}/avatar` | Público; solo reseña visible, no anónima y autor habilitado con foto |
| GET | `/api/v1/reviews/lost-cases/{case_id}` | Dueño; elegibilidad y reseña propia |
| POST | `/api/v1/reviews/lost-cases/{case_id}` | Dueño con correo confirmado; una por aviso |
| DELETE | `/api/v1/reviews/lost-cases/{case_id}` | Dueño; retirada de portada |
| GET | `/api/v1/admin/records/reviews` | Administrador |
| PATCH | `/api/v1/admin/reviews/{review_id}` | Administrador; ocultar/restaurar |

La web usa el proxy `/api/reviews`, la cookie de sesión existente, validación de origen en escrituras y cuerpos acotados. La lista pública incluye `avatar_version` únicamente para las reseñas que pueden mostrar foto; la imagen se consulta por ID de reseña, sin exponer el ID de cuenta ni la clave privada. Cambiar la foto renueva la versión y quitarla restaura las iniciales. La imagen comparte las reglas de visibilidad de la lista y responde sin caché. El texto se renderiza como contenido de React, sin interpretar HTML. La migración `0014_case_reviews` agrega una tabla y no genera reseñas ni altera los avisos anteriores. El inicio de la API aplica la migración.

## Verificación de fotos de perfil

Se comprobaron las fotos públicas de reseñas con nombre, la ausencia de identificadores privados, el cambio de versión y la vuelta a iniciales al quitar la foto. Reseñas anónimas, ocultas o retiradas, autores bloqueados o sin correo confirmado y avisos reabiertos u ocultos no permiten consultar la imagen. La comprobación utilizó registros temporales en una transacción revertida y eliminó su imagen del almacenamiento; no se modificaron reseñas o cuentas reales. Se revisó la tarjeta existente en la portada en escritorio y a 320 px, sin desbordamientos.

El nuevo diseño se revisó con la reseña real y su foto en la portada, y con una vista temporal de desarrollo para cero, una, tres y seis tarjetas. Se comprobó el despliegue y la contracción, el comentario completo de 700 caracteres, las puntuaciones de 1 a 5 y la ausencia total de la sección sin datos. Escritorio, tablet de 768 px y celular de 320 px conservaron su ancho sin desplazamiento horizontal. Los datos de esa vista fueron únicamente ejemplos de presentación; no se publicaron reseñas ni se modificaron usuarios. La vista temporal se retiró al finalizar. Se verificaron TypeScript, sintaxis CSS y espacios del cambio.
