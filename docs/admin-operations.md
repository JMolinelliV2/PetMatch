# Panel privado: operación y moderación

## Funciones

Acceso desde **Mi cuenta → Administración**, reservado a la cuenta confirmada y asignada como administradora. Se mantienen todas las comprobaciones del servidor descritas en [admin-matching.md](admin-matching.md). Ningún permiso depende de ocultar botones en el navegador.

| Sección | Información y controles |
| --- | --- |
| Resumen | Cuentas registradas, actividad por período y últimos 15 minutos, bloqueos, trabajos, correos y contactos. |
| Usuarios | Nombre, contacto, confirmación de correo, registro, última actividad y publicaciones actuales. Bloquear y reactivar con motivo y confirmación. |
| Trabajos | Espera, ejecución, completados, fallidos y reemplazados; modelo, intentos, fechas y código de error. |
| Correos | Un registro por intento real de envío; vistas previas separadas. Cola de solicitudes pendientes y fallidas. |
| Contactos | Nombre y correo declarados, mensaje recibido y estado de reenvío a administración. |
| Publicaciones | Avisos perdidos, avistamientos y encontrados, ID público, autor y estado. Ocultar y restaurar con motivo. |
| Auditoría | Acción, fecha, referencia del objetivo y motivo registrado. |
| Seguimiento de coincidencias | Recomendaciones únicas y respuestas de los dueños, con filtro de fecha y hora. |
| Denuncias y correcciones | Denuncias con período, estado y paginación; se conservan las correcciones de descripción y moderación de reseñas. |

### Fechas, conteos y búsquedas

Los formularios reciben fecha y hora con precisión de minuto en Uruguay (UTC−3). El navegador convierte los extremos a UTC y suma un minuto al final; el servidor usa `desde <= fecha < hasta`. Así incluye el minuto final completo, sin depender de la zona horaria de la computadora. Fechas invertidas y fechas sin zona horaria son rechazadas por la API. Los atajos ofrecen 7, 30 y 90 días o todo el período.

Cada sección explica la fecha aplicada: registro o actividad de usuarios, creación o finalización de trabajos, intento de correo, creación de solicitudes de envío, recepción de contactos, creación de publicaciones, acciones administrativas y generación de recomendaciones. Los listados de operación y denuncias usan 25 registros por página, con límite de API de 100. Los totales de estado respetan período y búsqueda; se calculan antes del filtro de estado. Las categorías de cuentas habilitadas/confirmadas/con actividad se superponen y no deben sumarse como conjuntos disjuntos. Los datos corresponden a registros conservados.

El resumen cuenta los trabajos según su fecha de creación y estado actual; en Trabajos se puede elegir finalización para estudiar cuándo terminaron. La cola global de correos y la actividad de los últimos 15 minutos indican el estado actual de toda la plataforma y lo anuncian expresamente. El resto de métricas respeta el período seleccionado. Buscar usuarios usa nombre/correo; publicaciones, ID, nombre, descripción o autor; trabajos, modelo/código de error; contactos, nombre/correo/mensaje. La búsqueda usa parámetros y escapa comodines SQL.

**Mascotas recuperadas** cuenta avisos de pérdida con estado actual `FOUND`, creados en el período seleccionado. Se muestra junto a Publicaciones por tipo y en Estado de operación. Reconocer a la mascota en una coincidencia no basta: se cuenta cuando el dueño indica que la recuperó o marca su aviso como encontrado. Cada aviso cuenta una vez, aunque tenga varias coincidencias. Este filtro usa la creación del aviso, no la fecha en que se recuperó a la mascota.

Publicaciones por tipo cuenta registros: Avisos de pérdida incluye los recuperados y cerrados; Avistamientos cuenta reportes `USER_SIGHTING`; Reportes de mascotas encontradas cuenta publicaciones `FOUND_ANIMAL` recibidas desde Encontré una mascota. La recuperación de una mascota no crea un reporte de ese último tipo ni incrementa el total de publicaciones.

Las etiquetas tienen una «i» para consultar qué representa cada cifra o estado y cómo se aplica el período. También está disponible en los filtros, detalles de registros y seguimiento de coincidencias. Las ayudas explican la diferencia entre mascotas recuperadas y reportes de encontrados, tareas y publicaciones, envíos e intentos, cuentas habilitadas y actividad reciente. Abrir una ayuda no modifica filtros, estados ni datos.

### Actividad

`User.status = ACTIVE` indica una cuenta habilitada. La actividad se registra cuando una solicitud autenticada termina correctamente, también al iniciar sesión o crear una cuenta. Incluye las consultas automáticas del sitio. No certifica que la persona esté observando la pantalla ni mide duración de sesión.

`users.last_active_at` guarda el último minuto observado. `user_activity` conserva una fila por cuenta y minuto, sin IP, ubicación, ruta ni contenido; permite contar usuarios distintos que tuvieron actividad dentro del rango aunque hayan vuelto después. Una actualización condicional en la base evita duplicados entre procesos. Se escribe en una tarea posterior al envío de la respuesta, en una transacción independiente y con espera por bloqueo de fila limitada a 250 ms en PostgreSQL; un fallo de telemetría no invalida la autenticación ni los cambios del usuario. El modo de pruebas o una dependencia de base reemplazada desactiva esa escritura externa.

El historial se conserva 90 días; la última actividad de la cuenta persiste mientras exista la cuenta. El borrado de una cuenta elimina sus buckets mediante cascada. No se fabrican registros de actividad anteriores a la actualización.

### Correos y contactos

`email_delivery_log` registra un intento de entrega desde alertas, confirmación, recuperación, cambio de correo, recordatorio de fotos y reenvío de contactos. Cuando varias alertas se agrupan en un solo mensaje, se cuenta un envío y se indica cuántos elementos agrupó. `SENT` significa aceptado por SMTP; no confirma entrega al buzón, lectura, rechazo posterior o spam. `PREVIEWED` nunca se suma a enviados. `FAILED` cuenta intentos fallidos, incluidos los que se enviaron en un reintento posterior.

Se conservan 90 días de estos registros. El registro contiene tipo, estado, fecha, referencias de solicitudes y vínculo opcional a la cuenta. No copia correo destinatario, contenido, HTML, URL de recuperación, token de confirmación, contraseña o credenciales SMTP. Si se elimina la cuenta, el vínculo queda nulo. La interfaz muestra su nombre actual si la cuenta existe, sin presentarlo como una dirección histórica. El historial de intentos comienza con esta actualización: no se reconstruyen cantidades de mensajes antiguos a partir de notificaciones agrupadas ni se inventan fechas de envío.

La cola usa las solicitudes originales y muestra pendientes/fallidas con intentos y próxima disponibilidad. Omite alertas leídas, archivadas o inactivas y tokens consumidos/vencidos. Cuenta solicitudes, no futuros correos. El envío conserva sus reintentos existentes; este panel no ejecuta reenvíos ni nuevas comunicaciones.

Los contactos reenviados conservan la política existente: se eliminan de la base 30 días después de enviarse o previsualizarse. Pendientes y fallidos permanecen disponibles. Sus cifras describen los contactos conservados, no un total histórico perpetuo. La dirección indicada por el visitante no está verificada.

### Bloqueos

Bloquear una cuenta revoca sus sesiones y oculta sus avisos, avistamientos y encontrados. Se solicita nuevamente la comparación de las publicaciones afectadas. La cuenta administradora no puede bloquearse a sí misma; la API comprueba esto. Reactivar permite una nueva sesión, sin revivir las sesiones revocadas ni restaurar automáticamente las publicaciones.

Ocultar una publicación conserva sus datos y excluye su visibilidad pública y comparación. Restaurar verifica que su autor esté habilitado; esta comprobación también se aplica a restauraciones desde denuncias. Los reportes anónimos pueden ocultarse/restaurarse, pero no tienen una cuenta que bloquear. Ocultar/restaurar no cambia el estado de búsqueda activa, recuperada o cerrada.

Las nuevas acciones directas piden motivo y confirmación y registran estado anterior/nuevo y actor en `admin_audit`, en la misma transacción. Las acciones originadas en una denuncia conservan la referencia y motivo de denuncia. Los controles no eliminan cuentas ni publicaciones. No se aplicaron bloqueos reales para preparar o revisar esta ampliación.

### Despliegue

La migración `0021_admin_operations`, posterior a `0020_admin_matching`, agrega `last_active_at`, actividad, historial SMTP, fecha de inicio del seguimiento e índices de trabajos. Se aplicó en la base local. En cualquier despliegue debe ejecutarse `alembic upgrade head` antes de arrancar API/workers con estos modelos. Compose ya realiza migraciones al iniciar la API; para entornos nuevos se mantiene el paso dedicado de migración. Reiniciar los workers carga el código actualizado.

Rutas nuevas: `GET /api/v1/admin/operations`, `GET /api/v1/admin/operations/{users|jobs|mail|mail_queue|contacts|publications|audit}` y `PATCH /api/v1/admin/publications/{lost_case|observation}/{id}/visibility`. Los filtros temporales se agregan a coincidencias y denuncias. Cada ruta comprueba `administrator`; las respuestas de lectura usan `no-store`. El proxy conserva la cookie de sesión, exige mismo origen en escrituras y admite solo rutas, parámetros, UUID y tamaños previstos. Las respuestas permiten únicamente campos seleccionados; no exponen snapshots de entrada, tokens de trabajos ni secretos.

## Diseño del panel

La navegación lateral, los temas claro y oscuro, los gráficos con datos reales, los filtros compartidos y el ancho común de páginas se describen en [dashboard-design.md](dashboard-design.md).
