# Edición de avistamientos y mascotas encontradas

Los avisos de pérdida también muestran **Editar mi aviso** en su ficha pública
y en la miniatura del mapa cuando la sesión corresponde al dueño. La comprobación
usa el acceso privado a `lost-cases/{id}`, sin comparar nombres públicos. El enlace
abre `/mis-avisos?editar={id}#editar-{id}` y expande el formulario de ese aviso
después de cargar los datos de la cuenta. Otra cuenta no puede activar esa edición.

El autor autenticado de un reporte puede editarlo desde **Mis avisos** o desde
**Editar mi avistamiento** en el detalle del mapa. Los reportes de mascotas
encontrados ofrecen **Editar mi reporte**. El resultado de un avistamiento
vinculado también muestra el acceso si se envió con la cuenta actual.

La pantalla está en `/mis-avisos/avistamientos/{id}/editar`. Permite actualizar
fecha y hora, descripción, ubicación, autorización para compartir contacto y,
en los reportes generales, características de la mascota. Las fotos y la miniatura
se gestionan en un bloque independiente con el límite existente de cinco fotos.
En avistamientos vinculados se conserva el formulario breve y el vínculo original.

## Acceso y datos privados

- `GET /api/v1/observations/{id}/edit` exige una sesión activa y que `author_id`
  coincida con la cuenta autenticada. Devuelve exclusivamente los datos de edición.
- La ubicación precisa se obtiene por este acceso privado; el lector público
  existente conserva sus coordenadas aproximadas. Abrir o guardar una descripción
  no desplaza el punto previamente guardado.
- `PATCH /api/v1/observations/{id}` exige además un correo confirmado y verifica
  otra vez la autoría dentro de la transacción. La interfaz usa el proxy de cuenta,
  que verifica el origen de las escrituras.
- Otras cuentas y reportes anónimos reciben 404 en los accesos privados. Iniciar
  sesión después de enviar un reporte anónimo no atribuye su autoría a esa cuenta.
- El formulario no modifica la visibilidad de moderación, el tipo del reporte,
  su autor ni el aviso vinculado. Los reportes históricos fuera del alcance de
  perros y gatos no ofrecen edición.

Guardar los cambios conserva el mecanismo existente de reanálisis y revisión de
coincidencias. La API rechaza descripciones vacías, fechas futuras y ubicaciones
incompletas. No se necesitan migraciones ni nuevas variables de entorno.
