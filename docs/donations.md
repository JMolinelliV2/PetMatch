# Aportes voluntarios de MascoMatch

## Estado actual

La página pública `/apoyanos` adapta la idea de niveles de apoyo de [PetRadar](https://www.petradar.org/es/apoyanos) a la identidad de MascoMatch. Está disponible sin cuenta desde el botón Apoyanos visible en el encabezado, tanto en escritorio como en móvil, y desde el bloque de apoyo al final de la portada. El botón está fuera de los menús desplegables.

Los niveles se definen en `apps/web/app/apoyanos/support-levels.ts`:

| Nivel | Importe sugerido (UYU) |
| --- | ---: |
| Amigo | 100 |
| Colaborador | 300 |
| Aliado | 600 |
| Impulsor | 1.200 |

Son importes sugeridos en pesos uruguayos, editables en ese archivo. No representan conversiones desde dólares. La interfaz permite elegir aporte puntual o mensual; comienza con puntual. Otro monto admite números enteros desde $U 1, sin un tope comercial, y muestra la ayuda correspondiente si el valor es inválido. El valor debe poder representarse como un entero exacto en JavaScript para evitar redondeos.

La selección, la frecuencia y el monto personalizado viven únicamente en el estado del componente. No hay solicitudes de cobro, almacenamiento de preferencias, datos bancarios ni registro de donantes. El botón de pago está deshabilitado y la página comunica que los aportes estarán disponibles próximamente.

Los niveles explican áreas que el apoyo puede acompañar: alojamiento, fotos, reportes, correos, procesamiento de fotos y descripciones mediante IA, herramientas, respaldos y mantenimiento. Las propuestas de coincidencias requieren revisión humana. No asignan presupuestos, premios ni privilegios de búsqueda. La publicación de avisos y los avistamientos siguen siendo gratuitos.

## Integración pendiente

Antes de habilitar los pagos:

1. Elegir la pasarela y confirmar que admite UYU, el país de la cuenta receptora y los formatos puntual/mensual deseados.
2. Definir importes, condiciones y datos del responsable de recibir los aportes.
3. Crear el cobro en el servidor con validación de moneda, monto y frecuencia. Los importes mostrados por el navegador no deben ser la autoridad del cobro.
4. Confirmar los resultados mediante notificaciones autenticadas de la pasarela, con deduplicación e idempotencia. Un regreso del navegador no confirma el pago.
5. Añadir estados reales de éxito, fallo y cancelación, comprobantes y gestión de aportes mensuales cuando correspondan.
6. Habilitar el botón únicamente cuando el circuito esté completo.

Esta entrega no modifica la API, la base de datos, los reportes, las cuentas ni las notificaciones.
