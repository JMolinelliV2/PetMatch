# Aviso de fotos y recordatorio posterior

## Formulario

Solo en **Perdí una mascota**, el primer intento de avanzar desde Mascota con los datos válidos pero sin foto mantiene el paso y muestra el consejo de agregar una imagen clara. **Agregar una foto** abre el selector existente; **Continuar sin foto** permite seguir. La foto continúa siendo opcional y no se agrega un cuarto paso. Se conservan los campos y el lugar al volver entre etapas.

El aviso recibe foco para lectura con teclado y usa un mensaje informativo. Seleccionar una foto retira el consejo; una imagen inválida sigue usando la validación existente de formato y tamaño. Si la carga falla después de publicar, el reporte queda guardado y se informa cómo agregarla desde Mis avisos.

## Correo a los 30 minutos

`PHOTO_REMINDER_DELAY_MINUTES=30` define la espera desde la creación del aviso. Admite entre 1 y 1440 minutos y se transmite al backend en Compose local y de producción. El recordatorio se guarda en `photo_reminders` dentro de la misma transacción que el aviso; tiene una fila por caso. No depende de la pestaña del usuario y se retoma después de reiniciar la API.

La API consulta los recordatorios vencidos cada 10 segundos. Antes de cada intento revisa:

- Que el aviso siga `ACTIVE` y visible, y que la cuenta siga activa.
- Que no haya fotos asociadas al aviso ni a la mascota. Las fotos de un avistamiento ajeno no sustituyen las de la mascota perdida.
- Que el dueño tenga el correo confirmado y no haya desactivado los correos en Notificaciones.

Si el aviso se cerró, fue encontrado, quedó oculto o ya tiene fotos, el recordatorio se cancela. Si la persona desactivó los correos, queda omitido. Una confirmación pendiente retrasa la próxima consulta cinco minutos. La carga de fotos y el envío comparten el bloqueo del caso para comprobar las fotos confirmadas antes de enviar.

Usa el transporte SMTP existente y el modo `MAIL_DELIVERY_MODE`: `smtp` envía por el proveedor configurado, `preview` genera en Mailpit y `disabled` conserva la programación sin enviar. Un recordatorio aceptado por SMTP queda `SENT` (o `PREVIEWED`), sin nuevos envíos automáticos. Los fallos tienen hasta cinco intentos con espera creciente. SMTP no garantiza entrega exactamente una vez si una conexión se interrumpe después de aceptar el mensaje; el Message-ID se mantiene estable por aviso.

La migración `0015_photo_reminders` crea una tabla vacía: no programa recordatorios para avisos anteriores. Tampoco se envían por borradores, registros de cuenta, avistamientos o mascotas encontradas. El borrado definitivo del aviso elimina su recordatorio mediante la clave foránea.

## Mensaje y destino

El correo tiene texto plano y HTML con la marca, logo incrustado y botón centrado. Explica el beneficio de una foto sin prometer resultados ni porcentajes y recuerda que el aviso permanece publicado sin imagen.

**Agregar una foto** abre `/mis-avisos?foto=<id>#fotos-<id>`. La persona debe ingresar con la cuenta dueña; el formulario de carga se abre dentro de su aviso y se desplaza hasta él. El parámetro solo admite un UUID, no inicia sesión ni autoriza subidas. Si la cuenta no posee el aviso, se informa que no está disponible en esa cuenta. Los logs de entrega no incluyen correos, descripciones ni credenciales.
