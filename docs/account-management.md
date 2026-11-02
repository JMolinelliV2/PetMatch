# Gestión de cuenta

`/mi-cuenta` permite editar nombre, teléfono opcional y correo, cambiar la contraseña y configurar las notificaciones. El acceso Mi cuenta del encabezado lleva a esta página; Mis avisos conserva sus publicaciones, edición, coincidencias y cierre.

## Cambio de contraseña

La sección **Cambiar contraseña** pide la contraseña actual, una nueva de entre 12 y 128 caracteres y su confirmación. Ambas nuevas contraseñas deben coincidir y ser diferentes de la actual. El formulario muestra errores sin perder los datos y, al guardar, vacía los campos y abre el modal de confirmación utilizado en Mi cuenta.

`POST /api/account-settings?action=password` envía únicamente la solicitud permitida a `POST /auth/change-password`, con cookie HttpOnly, control de origen y cuerpo limitado. La API exige una sesión activa, bloquea la cuenta y verifica la contraseña actual con el límite de intentos existente. Guarda el hash, revoca todas las demás sesiones e invalida los enlaces pendientes de recuperación, conservando la sesión que hizo el cambio. El inicio de sesión toma el mismo bloqueo para impedir que un ingreso concurrente con la contraseña anterior sobreviva al cambio. No confirma el correo ni modifica el contacto, las preferencias o el estado de verificación. No requiere migraciones ni un servicio de correo disponible.

## Notificaciones

Debajo del contacto, la sección Notificaciones permite activar o desactivar alertas y recordatorios por correo. El cambio se guarda al marcar o desmarcar la casilla, mediante la ruta existente `PATCH /api/session`; se muestra el resultado y la casilla conserva el último valor confirmado hasta guardar o volver a cargar los datos. Las alertas dentro de la web y los correos solicitados de confirmación o recuperación siguen disponibles.

La bandeja `/notificaciones` contiene las alertas y un enlace a `/mi-cuenta#notificaciones`. Los correos de alertas y recordatorios también llevan a esa sección para cambiar la preferencia.

## Cambio de contacto

Nombre y teléfono se guardan inmediatamente. Cambiar el correo requiere la contraseña actual y genera un enlace de un solo uso, válido durante 24 horas, enviado a la nueva dirección. Hasta confirmarlo, el correo actual sigue siendo la dirección de ingreso y de las alertas. La dirección pendiente no reserva una cuenta: su disponibilidad se vuelve a comprobar mediante la restricción única de la base al confirmar.

Al guardar los datos de contacto, una respuesta exitosa abre el modal **Cambios guardados**. Si hay un cambio de correo pendiente, aclara que falta confirmar la nueva dirección. Se cierra con Entendido, el botón de cerrar, Escape o al pulsar el fondo; luego queda el mensaje junto al formulario. Los errores se muestran en el formulario y no abren el modal de éxito.

El usuario puede reenviar o cancelar el cambio desde Mi cuenta. Se aplican los límites existentes de enlaces (un minuto entre solicitudes y tres por hora por cuenta) y de intentos de contraseña. Confirmar el cambio invalida los enlaces de acceso pendientes y todas las sesiones anteriores; hay que ingresar con el nuevo correo y la contraseña habitual. Los enlaces de cambio están asociados a su destinatario para evitar que un enlace anterior confirme otra dirección.

## Eliminación

La sección desplegable exige la contraseña y escribir ELIMINAR. `DELETE /auth/me` elimina físicamente el usuario, sus mascotas, todos sus avisos perdidos, reseñas, coincidencias, notificaciones, sesiones y enlaces de acceso. Los avistamientos y reportes de encontrados permanecen con `author_id=NULL` y `share_contact=false`, junto con sus fotos y análisis. Las observaciones asociadas a un aviso eliminado se desvinculan y quedan pendientes de comparación con otros casos.

Las fotos de mascotas y avisos eliminados desaparecen de la API en la misma transacción. Sus objetos privados quedan en `photo_deletions`, una cola persistida que el proceso de la API revisa cada diez segundos. Si el almacenamiento falla, reintenta con espera creciente hasta una hora; no abandona el borrado. Un rollback de la cuenta no elimina objetos del almacenamiento. Los respaldos históricos conservan su propia retención y no se modifican en este flujo.

La migración `0016_account_management` añade el correo pendiente, el destinatario de los enlaces y la cola de borrado. Las acciones de moderación conservan su historial con actor nulo cuando se elimina esa cuenta. El downgrade requiere que no haya actores ya eliminados; no reconstruye cuentas borradas.

Las mutaciones de mascotas, casos, observaciones y fotos bloquean primero la cuenta con `FOR NO KEY UPDATE`, para serializar la eliminación sin bloquear las referencias de avistamientos anónimos. La eliminación bloquea después las mascotas y los casos antes de retirar sus datos. Los avistamientos breves sin cuenta siguen admitidos.

El navegador utiliza un proxy con cookie HttpOnly, validación del origen, rutas permitidas y límite del cuerpo. La contraseña no se devuelve, persiste ni registra en estas rutas.

## Revisión de esta entrega

Se revisan tipos y sintaxis, el inicio de los servicios y las páginas en lectura. No se eliminan cuentas reales, cambian contactos, envían solicitudes de correo ni publican reportes para revisar esta implementación. No se ejecutan pruebas automatizadas en esta entrega.

El cambio de contraseña se comprobó con cuentas temporales dentro de una transacción descartada: contraseña actual incorrecta, confirmación distinta, reutilización de la anterior, límites de longitud, sesiones vencidas o ajenas, nueva clave válida, cierre de las demás sesiones y cancelación de la recuperación anterior. Se verificó el ingreso con la nueva contraseña y el rechazo de la anterior, sin modificar la verificación de correo. El proxy rechazó solicitudes sin sesión, desde otro origen y con un cuerpo excesivo. La revisión visual utilizó el componente real en una vista temporal de desarrollo, retirada al terminar, en escritorio y celulares de 320 y 390 px.
