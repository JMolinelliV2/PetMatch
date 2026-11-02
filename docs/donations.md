# Aportes voluntarios con Mercado Pago

La integración implementa aportes **puntuales** en UYU mediante **Checkout Pro con Orders API**. Empieza desactivada hasta completar las credenciales y verificar el circuito. Los aportes mensuales no se pueden seleccionar ni crear desde la API.

## Recorrido

1. La persona elige un nivel o un importe entero propio desde $U 1.
2. El servidor valida el importe, registra una intención y crea una order con referencia propia e idempotencia.
3. El navegador abre el checkout de Mercado Pago. MascoMatch no pide tarjetas ni documentos.
4. Mercado Pago devuelve a `/apoyanos/resultado?aporte=…`. Esa URL no confirma ningún pago.
5. Un webhook firmado agrega el ID de la order a una cola duradera. El servidor consulta la order directamente al proveedor y valida importe, UYU, país URY, vendedor, aplicación, referencia y entorno.
6. Solo entonces se confirma el aporte. Se contemplan pendientes, rechazos, cancelaciones, reembolsos, reembolsos parciales y contracargos.

Los niveles siguen en `apps/web/app/apoyanos/support-levels.ts`: Amigo 100, Colaborador 300, Aliado 600 e Impulsor 1.200. El máximo técnico coincide con el entero exacto máximo de JavaScript; no vuelve a imponerse el tope comercial de 100.000. Mercado Pago puede aplicar sus propios límites.

## Seguridad y operación

- Access Token y firma solo en la API; en producción, como secretos. No llegan a Next.js ni a los workers de IA.
- Una intención conserva el mismo `X-Idempotency-Key` en los reintentos. Un timeout no se considera un aporte recibido.
- El checkout solo puede abrir una URL HTTPS de Mercado Pago Uruguay correspondiente a la order creada.
- Se valida HMAC-SHA256 con `data.id` respetando mayúsculas, `x-request-id` y timestamp en segundos o milisegundos, con tolerancia de cinco minutos. El reloj del servidor debe estar sincronizado.
- Se ignoran el estado e importe del cuerpo del webhook y los parámetros de retorno como `status=approved`.
- La cola deduplica por order y entorno, persiste antes de responder y procesa la consulta externa después, con bloqueos y reintentos progresivos. No requiere un proceso en la PC del operador.
- No se aplican actualizaciones anteriores a la última fecha del proveedor registrada. La fecha de confirmación inicial se conserva al repetir eventos.
- Como recuperación, las operaciones pendientes recientes se consultan cada quince minutos y las confirmadas recientes una vez por día. Los webhooks son la vía principal.
- `MP_ENABLED=false` pausa nuevos checkouts; la confirmación de operaciones existentes continúa si se mantienen credenciales, firma y entorno. No cambiar de entorno ni retirar claves con operaciones reales pendientes.
- Hay límites de solicitudes y cuerpo. Los logs utilizan códigos de error sanitizados, sin claves, firmas, payloads ni datos de tarjetas.

La base guarda importe, fechas, identificadores, estado y correlación de la operación. La cookie anónima es HttpOnly, SameSite=Lax, Secure en producción y dura treinta días. La base conserva solo el hash de su clave. Permite consultar los aportes desde el mismo navegador sin cuenta de MascoMatch. No se almacenan datos del pagador, tarjetas ni respuestas completas del proveedor; no hay vínculo directo con la cuenta de MascoMatch.

## Administración

`/admin` → **Aportes** consulta producción o pruebas por separado, con filtros de fecha/hora, estado, paginación, última sincronización y errores de conciliación. El botón flotante conserva filtros y consulta nuevamente los datos locales.

El total confirmado suma importes brutos actualmente confirmados del entorno y período elegidos. Excluye pendientes, reembolsos, reembolsos parciales y contracargos; no representa saldo disponible ni descuenta comisiones. Las pruebas nunca se mezclan con el total real. Para devolver dinero o gestionar controversias se utiliza Mercado Pago; el panel no ejecuta movimientos financieros.

## Configuración pendiente del operador

Seguir [el procedimiento de Mercado Pago](mercado-pago-configuracion.md). Se necesitan Access Token, firma de webhooks, ID de vendedor, ID de aplicación y una URL pública HTTPS. La prueba externa y la habilitación de dinero real requieren esos datos; no se simulan como si estuvieran completas.

La migración `0031_donations` añade `donations` y `donation_sync`, sin modificar avisos, fotos, usuarios ni coincidencias. Los respaldos de la base incluyen estas tablas.

## Verificación

Las pruebas usan una base aislada y un proveedor simulado: idempotencia, timeouts, importes inválidos, privacidad del navegador, firma y timestamps, duplicados, cuerpos falsificados, moneda/vendedor/aplicación incorrectos, importes pagados, devoluciones, fechas fuera de orden, permisos, totales por entorno y pausa de nuevos checkouts sin perder confirmaciones. No crean pagos reales ni usan tarjetas. El ensayo final con Mercado Pago requiere después las credenciales de prueba del operador.

## Referencias oficiales

- [Crear order y obtener checkout_url](https://www.mercadopago.com.uy/developers/es/docs/checkout-pro-orders/create-order).
- [URLs de retorno](https://www.mercadopago.com.uy/developers/es/docs/checkout-pro-orders/web-integration/configure-back-urls).
- [Notificaciones y firma](https://www.mercadopago.com.uy/developers/es/docs/checkout-pro-orders/notifications).
- [Pruebas con tarjetas](https://www.mercadopago.com.uy/developers/es/docs/checkout-pro-orders/integration-test/test-purchase-with-card).
