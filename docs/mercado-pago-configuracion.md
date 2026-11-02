# Configurar Mercado Pago para MascoMatch

## 1. Crear o elegir la aplicación

1. En Mercado Pago Uruguay, ingresar a **Integraciones** y crear o seleccionar la aplicación de MascoMatch para **Checkout Pro con Orders**. [Instrucciones oficiales](https://www.mercadopago.com.uy/developers/es/docs/checkout-pro-orders/create-application).
2. Verificar que la cuenta receptora corresponda a Uruguay.
3. Seleccionar **Prueba** antes de copiar el **Access Token**. El prefijo `APP_USR` también puede aparecer en claves de prueba: no determina el entorno.
4. Anotar el **ID de aplicación** de esa aplicación; será `MP_APPLICATION_ID`.

No hace falta una Public Key en el frontend para el recorrido implementado: utiliza redirección al checkout alojado. El Access Token y la firma de webhooks son privados. No pegarlos en el chat, el repositorio ni variables `NEXT_PUBLIC_`.

## 2. Tener una URL HTTPS para probar

Mercado Pago debe poder acceder desde Internet al webhook y devolver el navegador al sitio; `localhost` no sirve como callback.

Usar una URL HTTPS de preproducción que llegue a la instancia a probar. También puede utilizarse temporalmente una URL pública HTTPS de desarrollo. En producción será `https://mascomatch.com`, apuntando al servidor.

En los ejemplos se utiliza `https://pruebas.ejemplo.com`: sustituirla por la URL real. **Abrir el sitio e iniciar el aporte desde ese mismo origen**, no desde localhost, para conservar la cookie al regresar. Durante esa prueba, `PUBLIC_SITE_URL`, `WEB_ORIGIN` y `MP_PUBLIC_BASE_URL` deben coincidir con el origen servido.

Si el sitio de pruebas tiene un filtro de acceso, la ruta del webhook debe permitir los POST de Mercado Pago. La propia integración valida su firma.

## 3. Configurar notificaciones de prueba

En la aplicación de Mercado Pago:

1. Abrir **Configuración de Webhooks** y seleccionar **Prueba**.
2. Cargar `https://pruebas.ejemplo.com/api/payments/mercadopago/webhook`, cambiando el dominio.
3. Elegir **Order (Mercado Pago)**, correspondiente a Checkout Pro con Orders.
4. Guardar y copiar la **firma secreta** generada.

La integración usa `/v1/orders`; no corresponde seleccionar únicamente el evento de pagos de una integración antigua de preferencias. Firma y Access Token deben pertenecer al mismo entorno y aplicación. [Documentación de webhooks](https://www.mercadopago.com.uy/developers/es/docs/checkout-pro-orders/notifications).

## 4. Cargar la configuración con aportes desactivados

### Desarrollo local con Docker Compose

Editar el `.env` local, ignorado por Git. No poner datos reales en `.env.example`:

```dotenv
MP_ENABLED=false
MP_ENVIRONMENT=test
MP_ACCESS_TOKEN=TOKEN_PRIVADO_DE_PRUEBA
MP_WEBHOOK_SECRET=FIRMA_PRIVADA_DE_PRUEBA
MP_COLLECTOR_ID=ID_DEL_VENDEDOR_DE_PRUEBA
MP_APPLICATION_ID=ID_DE_LA_APLICACION
MP_PUBLIC_BASE_URL=https://pruebas.ejemplo.com
PUBLIC_SITE_URL=https://pruebas.ejemplo.com
WEB_ORIGIN=https://pruebas.ejemplo.com
```

Desde la carpeta del proyecto:

```powershell
docker compose up -d --no-deps api web
docker compose exec -T api python -m app.ops.payments inspect-account
```

`inspect-account` no crea órdenes ni pagos. Solo consulta la cuenta del Access Token y muestra `collector_id` y `site_id`, sin nombre, correo o credenciales. Copiar `collector_id` a `MP_COLLECTOR_ID`; para Uruguay se espera `MLU`.

Si se desconoce ese ID, se puede dejar `MP_COLLECTOR_ID` vacío mientras `MP_ENABLED=false`. Después de completarlo:

```powershell
docker compose up -d --no-deps api
docker compose exec -T api python -m app.ops.payments check
```

`check` verifica configuración, cuenta uruguaya e ID del vendedor sin crear pagos. El ID de aplicación y la moneda se validan además en cada order.

### Preproducción o producción con secretos

Una instalación nueva ya tiene los dos archivos vacíos preparados por `production_init.py`. Para una instalación existente:

```sh
python3 tools/production_init.py --directory . --prepare-payment-secrets
```

No reemplaza claves existentes. Si se utiliza `SECRETS_DIR`, agregar `--secrets-directory` con esa ruta privada.

Con un editor del servidor, colocar **solo el valor** del Access Token en `.secrets/mp_access_token` y la firma en `.secrets/mp_webhook_secret`. Mantener privada la carpeta `.secrets`; no copiar su contenido al repo. Solo la API recibe estos secretos.

En `.env.production`, completar los valores no secretos:

```dotenv
MP_ENABLED=false
MP_ENVIRONMENT=test
MP_COLLECTOR_ID=ID_DEL_VENDEDOR_DE_PRUEBA
MP_APPLICATION_ID=ID_DE_LA_APLICACION
MP_PUBLIC_BASE_URL=https://pruebas.ejemplo.com
```

Respaldar y desplegar la versión con `0031_donations` según el procedimiento general. `production_apply.py deploy` prepara los archivos vacíos faltantes. Con el alias `dc` del procedimiento de producción:

```sh
dc up -d --no-deps api
dc exec -T api python -m app.ops.payments inspect-account
dc exec -T api python -m app.ops.payments check
```

Si falta el ID del vendedor, se puede consultar con los aportes desactivados, completarlo y recrear la API. No habilitar aportes hasta que `check` sea correcto.

## 5. Habilitar exclusivamente las pruebas

1. Mantener `MP_ENVIRONMENT=test` y las credenciales de prueba.
2. Cambiar `MP_ENABLED=true` y recrear la API.
3. Abrir una ventana de incógnito, sin sesión iniciada en Mercado Pago, e ingresar a `/apoyanos` desde el origen HTTPS configurado. Comprobar el cartel **Modo de prueba: no se realizan aportes con dinero real**.
4. Elegir el importe y continuar a Mercado Pago.
5. Completar el checkout en esa misma ventana con las [tarjetas de prueba oficiales](https://www.mercadopago.com.uy/developers/es/docs/checkout-pro-orders/integration-test/test-purchase-with-card). Mantener la misma ventana conserva la cookie necesaria para consultar el resultado al regresar.

Tomar los datos vigentes de tarjeta, fecha y documento de esa página. La documentación identifica `APRO` como aprobado, `OTHE` como rechazo general y `CONT` como pendiente. No utilizar tarjetas reales en este ensayo.

## 6. Comprobar el circuito completo

Realizar al menos un caso aprobado, uno rechazado y uno pendiente:

1. El checkout muestra el monto, UYU y el receptor esperado.
2. El regreso abre `/apoyanos/resultado` e identifica la operación como prueba.
3. Un aprobado pasa a confirmado después de la consulta del servidor; un pendiente conserva su estado.
4. En Mercado Pago → Webhooks, se observa entrega con HTTP 200.
5. En `/admin` → Aportes → **Pruebas**, se ve la referencia, importe, estado y última sincronización.
6. En **Producción**, el ensayo no aumenta el total real.
7. Reenviar una notificación no crea otro aporte ni suma dos veces.

Para el simulador de webhooks, usar el ID real de una order de prueba creada por esta integración. Un ID inventado no puede confirmar dinero.

Cambiar `status=approved` en la URL no debe confirmar nada. Si la actualización tarda, consultar Mercado Pago y usar **Actualizar estado**; no iniciar un segundo pago solo porque el regreso todavía muestre pendiente.

El comprobante del pago se gestiona en Mercado Pago. MascoMatch muestra la referencia y el resultado confirmado; no emite un recibo fiscal propio ni ejecuta devoluciones desde el panel.

## 7. Pasar a dinero real

Después de completar las pruebas:

1. Completar la habilitación de producción que solicite Mercado Pago para esa cuenta y aplicación.
2. En Webhooks → **Producción**, registrar `https://mascomatch.com/api/payments/mercadopago/webhook` y obtener la firma correspondiente.
3. Reemplazar los dos secretos por los de producción y verificar el ID del vendedor. El vendedor de prueba y el de producción pueden tener distintos IDs.
4. Establecer `MP_ENVIRONMENT=production`, `MP_PUBLIC_BASE_URL=https://mascomatch.com` y comenzar con `MP_ENABLED=false`.
5. Recrear la API y ejecutar `app.ops.payments check`.
6. Confirmar dominio, HTTPS, nombre del receptor y condiciones mostradas por Mercado Pago.
7. Habilitar `MP_ENABLED=true` y recrear la API.
8. Realizar un aporte real controlado y verificar comprobante y estado en MascoMatch. Si se decide devolver esa prueba real, hacerlo desde Mercado Pago y comprobar la actualización.

La persona operadora realiza y confirma cualquier movimiento con dinero real. En producción, web, base, cola y consultas a Mercado Pago corren en el servidor; no es necesario dejar encendida su PC.

## 8. Pausar y diagnosticar

- `MP_ENABLED=false` detiene nuevos aportes, conservando confirmaciones si permanecen las claves y el entorno. No cambiar a claves de prueba con operaciones reales pendientes.
- HTTP 401 en webhook: revisar entorno, firma, URL exacta y reloj del servidor.
- Moneda, importe, vendedor o aplicación incorrectos: nunca se confirma la operación. Revisar el código técnico en administración y la configuración.
- HTTP 503 al abrir checkout: revisar las claves y disponibilidad de Mercado Pago. Reintentar conserva la solicitud mientras no se cambie el monto.
- Modificar `.env` no cambia un contenedor en ejecución: recrear la API después de modificar su configuración.
- Reembolsos y contracargos se consultan en Mercado Pago. El total del panel es bruto, excluye las devoluciones indicadas y no es el saldo del proveedor.

Referencias: [crear order](https://www.mercadopago.com.uy/developers/es/docs/checkout-pro-orders/create-order), [retornos](https://www.mercadopago.com.uy/developers/es/docs/checkout-pro-orders/web-integration/configure-back-urls), [webhooks](https://www.mercadopago.com.uy/developers/es/docs/checkout-pro-orders/notifications).
