# Preparación para producción

Actualizado el 1 de noviembre de 2026. Este archivo describe un despliegue Docker en un servidor Linux. No publica automáticamente el dominio ni contrata servicios.

Para una instalación nueva, seguir el [procedimiento detallado paso a paso](puesta-en-produccion-paso-a-paso.md), que distingue PowerShell, terminal del VPS y paneles de los proveedores, e incluye comprobaciones y tareas operativas pendientes.

## Lanzamiento del producto y medición propia — 21 de octubre

El despliegue utiliza el producto completo: registro, búsqueda, reportes, Pet-ReID/OpenCLIP/Gemma locales, alertas y recuperación. No se publican listas de espera ni demostraciones simuladas. Los modelos no se descargan durante solicitudes públicas. Las métricas y sus límites están definidos en [analytics](analytics.md).

Antes de actualizar una base existente, detener API/workers, generar y verificar un respaldo y ejecutar `alembic upgrade head` con la imagen nueva. La revisión actual es `0031_donations`; agrega el registro de aportes puntuales y su cola de confirmación, conserva las tablas operativas, features, vectores e historial, limita nuevas publicaciones a perros/gatos y retira del procesamiento los registros de otras especies. Ver [alcance y migración](dog-cat-scope.md), [fotos y miniaturas](report-photos.md), [descripciones originales](report-descriptions.md) y [foto de perfil](account-avatar.md) y [Mercado Pago](mercado-pago-configuracion.md). La cadena incluye una revisión histórica ya aplicada que se conserva por compatibilidad; no habilita rutas ni un modo de acceso distinto.

El procedimiento de despliegue completo sigue siendo `python3 tools/production_apply.py deploy --with-ai`. La primera instalación de Gemma requiere la aceptación explícita de sus términos por el responsable; una instalación existente puede verificarse sin volver a descargarla. No se contrataron servidores ni se aceptaron términos en nombre del responsable durante este cambio.

Configurar `ANALYTICS_ENABLED`, sus retenciones y los límites `RATE_LIMIT_ANALYTICS` / `RATE_LIMIT_ANALYTICS_DAILY`. La decisión jurídica sobre consentimiento previo de estas cookies debe resolverse para los países atendidos. Si está pendiente, se puede desactivar analytics sin bloquear el producto. No se asume que las cookies estén exentas de consentimiento.

La limpieza de analytics corre cada hora en los procesos de API: reintenta agregados pendientes con bloqueos de fila y expira eventos a los 90 días. Los contadores diarios duran 730 días. Prometheus observa agregados pendientes y memoria; CPU/cola/utilización se consultan según la tabla de operación de la guía. Verificar esas alertas y la restauración de respaldos en el servidor real.

`python3 tools/production_validate.py` prueba un stack desechable sin puertos públicos, con correo restringido a `example.test` en Mailpit y sin inferencia pesada. No se debe reemplazar ese aislamiento por cuentas de prueba en producción. Los tests de inferencia real siguen separados y no representan una evaluación de eficacia con animales diferentes.

La actualización a Pillow 13.0.0 corrige los avisos detectados en la auditoría del procesamiento de imágenes. Se deben reconstruir también los workers y las herramientas operativas, además de API/web.

## Cambios

- Imágenes de API y web con usuario sin privilegios, código dentro de la imagen y dependencias fijadas. La web usa el servidor de producción de Next.js.
- Caddy termina HTTPS y administra sus certificados. Solo publica 80 y 443; PostgreSQL, Redis, fotos, Ollama y workers tienen redes privadas. La web y Caddy se separan de la red de datos.
- PostgreSQL tiene un propietario para migraciones y un usuario de aplicación sin privilegios de superusuario ni creación de tablas o roles.
- Los secretos se montan en los servicios que los necesitan. El worker de visión no recibe claves de firma de sesiones ni SMTP y tiene credenciales de fotos de lectura.
- Sesiones con identificador almacenado, expiración y revocación. Salir invalida el token en el servidor. La web conserva el token únicamente en una cookie HttpOnly, Secure y con prefijo `__Host-` en producción.
- Las sesiones anteriores a esta entrega necesitan un nuevo ingreso una sola vez. Las cuentas, contraseñas y avisos se conservan.
- Contraseñas nuevas de al menos 12 caracteres; PBKDF2 SHA-256 con 600.000 iteraciones. Los hashes anteriores se actualizan al ingresar, manteniendo las contraseñas existentes.
- Confirmación de correo y recuperación mediante enlaces de un solo uso. Los códigos se guardan como hash y cifrados para su envío; vencen a las 24 horas y 30 minutos respectivamente. El registro envía la confirmación en todos los entornos; publicar, editar, subir fotos y solicitar análisis desde una cuenta exige correo confirmado en la API. Restablecer la contraseña revoca las sesiones y confirma el correo. El correo de alertas espera a que el dueño confirme su dirección.
- Límites compartidos en Redis por cuenta o dirección verificada del cliente. Un proxy ajeno no puede suplantar esa dirección. Si Redis falla, el acceso y las escrituras se suspenden temporalmente; las lecturas conservan límites locales.
- Las cargas de fotos tienen un máximo de tres solicitudes simultáneas en la web, con permisos temporales que vencen. Caddy limita el tamaño del cuerpo y su tiempo de lectura. Las escrituras de la API pasan por los proxies de la web.
- Registros de solicitudes con identificador, ruta general, duración y estado; se omiten cuerpos, consultas, direcciones y contactos. Los errores SQL no imprimen parámetros.
- Respaldos cifrados cada seis horas por defecto, conservación local de catorce copias y verificación antes de registrar éxito. Copia off-site opcional en B2, con reintentos, Object Lock y recuperación en destinos vacíos. Ver [configuración B2](backblaze-backup.md).
- Métricas privadas y reglas de Prometheus para disponibilidad, demora de análisis, fallos de correo y respaldos atrasados. Integración continua para pruebas, compilación y auditoría de dependencias de Python y web.

Los controles siguen las referencias de [sesiones de OWASP](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html), [contraseñas de OWASP](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html), [secretos de Compose](https://docs.docker.com/compose/how-tos/use-secrets/) y [contadores atómicos de Redis](https://redis.io/docs/latest/commands/incr/).

## Fotos

La instalación local conserva MinIO. Su [repositorio está archivado](https://github.com/minio/minio); el despliegue nuevo usa SeaweedFS 4.48 y su [API S3](https://github.com/seaweedfs/seaweedfs/wiki/Amazon-S3-API). Las claves de la aplicación acceden a `pet-photos`; la inicialización usa una clave administrativa separada. El bucket es privado y conserva versiones de los objetos.

Las fotos se recuperan desde el respaldo manteniendo sus claves y las relaciones en PostgreSQL. No hay que reemplazar ni borrar el volumen local para preparar el servidor.

## Preparar el servidor

Objetivo probado: Linux x86_64 / Ubuntu 24.04, Docker Compose 2.24.4 o superior. Punto de partida recomendado: 8 vCPU, 24 GB RAM y 100 GB SSD; 16 GB puede servir para un piloto de baja carga, pero requiere medición del servidor concreto. IA está limitada a 3,5 CPU de Ollama + 2 visual + 0,5 semántico. [Mediciones y límites](ai-delivery-report.md#6-resource-usage).

Todos los servicios de producción, modelos, fotos, colas y base de datos quedan en el VPS. La PC personal no almacena ni ejecuta componentes necesarios para atender usuarios.

En un servidor limpio, ingresar mediante SSH y obtener **la revisión aprobada** del repositorio. La revisión `86f0db3` de `main` incluye la integración B2; se puede utilizar esa revisión o una posterior que haya sido revisada. Las claves y los datos locales no se transfieren al clonar el código.

```sh
sudo apt-get update
sudo apt-get install -y git python3
git clone https://github.com/JMolinelliV2/MascoMatch.git
cd MascoMatch
sudo sh tools/bootstrap_server.sh
python3 tools/production_init.py --domain mascomatch.com
```

`bootstrap_server.sh` instala Docker Engine y Compose desde el [repositorio oficial de Docker](https://docs.docker.com/engine/install/ubuntu/). Ejecutar los comandos Docker posteriores con una cuenta autorizada para usar Docker; si se ingresó como administrador/root, ya lo está. El generador crea `.env.production` y `.secrets/`, excluidos de Git, y se niega a sobrescribir claves existentes. El directorio privado es 0700; solo se montan archivos individuales a cada servicio. Guardar `backup_key` en una ubicación privada separada.

Configurar el SMTP ya contratado/verificado según la sección Brevo antes de la comprobación final. Elegir un servidor Photon propio/contratado compatible mediante `GEOCODER_BASE_URL`, o aceptar explícitamente las limitaciones del endpoint público para un piloto de poco tráfico. Esta mejora no añade un proveedor pago de IA. El buscador público Photon sigue sin SLA; no es una solución garantizada para gran volumen.

DNS en Hostinger: A de `mascomatch.com` a la IPv4 del VPS; `www` CNAME a `mascomatch.com`. No conservar un AAAA que apunte a otro servidor. Mantener los registros MX/DKIM/DMARC de correo. El firewall del proveedor debe admitir 80/TCP, 443/TCP, opcional 443/UDP, y SSH restringido a administración. Caddy obtiene y renueva HTTPS cuando DNS apunta correctamente. No abrir PostgreSQL, Redis, fotos u Ollama.

Después de aceptar los términos de Gemma:

```sh
python3 tools/production_apply.py deploy --with-ai --accept-gemma-terms
python3 tools/production_apply.py smoke
python3 tools/production_apply.py check
```

El despliegue valida Compose, construye imágenes, respalda una instalación existente, detiene API/workers, inicia dependencias privadas, inicializa fotos/versionado, migra y aplica permisos, instala/verifica modelos fijados, recupera trabajos interrumpidos, programa backfill y arranca servicios con healthchecks. En la primera instalación también crea un respaldo antes del chequeo final. Gemma hace prewarm al iniciar su worker. Puede repetirse sin duplicar análisis ni reemplazar datos. Sin `--accept-gemma-terms`, solo reutiliza una instalación Gemma cuyo hash ya coincida.

`check` comprueba DB/Redis/fotos, workers/modelos/Gemma, respaldo registrado y SMTP configurado. Para comprobar una entrega real a una cuenta controlada, ejecutar deliberadamente:

```sh
docker compose -p mascomatch --env-file .env.production -f compose.production.yml exec -T api \
  python -m app.ops.release_check --send-test-email info@mascomatch.com
```

SMTP aceptado no garantiza bandeja de entrada: abrir el mensaje en la cuenta controlada. Luego comprobar desde el dominio público registro → confirmación → publicación, recuperación y una notificación propia. La suite aislada automatiza ese recorrido sin correo externo:

```sh
python3 tools/production_validate.py
```

Crea un proyecto fijo `mascomatch-prod-smoke` separado, sin puertos públicos, SMTP TLS hacia Mailpit y datos sintéticos. Verifica cookie segura, confirmación, foto, CSRF, salida y respaldo/restauración PostgreSQL+S3. Elimina solo los volúmenes de ese proyecto de pruebas al finalizar; `--keep` permite inspeccionarlo.

## Actualización y rollback de IA

```sh
python3 tools/production_apply.py deploy --with-ai
python3 tools/production_apply.py fallback
python3 tools/production_apply.py pause-ai
python3 tools/production_apply.py resume-ai
```

`fallback`: Pet-ReID desactivado y OpenCLIP para nuevas representaciones compatibles. `pause-ai`: pausa Gemma; continúa visual y matching básico. `resume-ai`: reactiva los modelos actuales y agenda faltantes. Las banderas se guardan antes de recrear servicios. Se conservan los embeddings y FeatureSets históricos; evidencia obsoleta no se mezcla con la vigente. Las publicaciones siguen disponibles durante una caída de modelo, aunque la actualización planificada detiene brevemente la API.

La migración 0022 es aditiva y no tiene downgrade destructivo. No ejecutar un checkout antiguo directamente contra el nuevo esquema como supuesto rollback. Para volver exactamente a la versión anterior se utiliza la etiqueta `previo-al-cambio-de-modelo-de-ia` y un respaldo anterior en **destinos nuevos y vacíos**, conservando la instalación actual hasta verificar la recuperación. Para incidencias de modelo usar primero las banderas anteriores.

## Brevo

Para la instalación local, los valores se configuran en `.env` como antes. Para el servidor:

- Completar `SMTP_USERNAME`, `SMTP_FROM`, `SMTP_HOST`, `SMTP_PORT` y `SMTP_TLS_MODE` en `.env.production`.
- Guardar la clave SMTP en `.secrets/smtp_password`, sin incluirla en el repositorio ni pasarla como argumento de comandos.
- Mantener privada la carpeta y permitir la lectura del archivo montado a los contenedores. Recrear la API para aplicar valores o archivos nuevos.
- Cambiar `MAIL_DELIVERY_MODE` a `smtp` cuando el dominio y el remitente estén verificados en Brevo.
- Registrar/ingresar una cuenta, confirmar su correo y comprobar recepción con un avistamiento de prueba.

Los mensajes de confirmación, recuperación y avistamientos utilizan el mismo SMTP. Las preferencias de alertas no desactivan un correo solicitado para recuperar la cuenta. Solicitar recuperación devuelve la misma respuesta exista o no el usuario. Cada cuenta tiene un máximo de tres enlaces nuevos por hora y una separación mínima de un minuto.

El registro crea la cuenta, la sesión y el enlace de confirmación en una misma transacción, sin publicar avisos. Si el correo está desactivado, rechaza el registro antes de crear la cuenta. El enlace abre `/confirmar-correo`, donde el usuario confirma con un botón: abrir la URL por GET no consume el código, para evitar que lo gasten los lectores automáticos del correo. Los enlaces vencidos o usados permiten pedir uno nuevo desde la sesión de la cuenta. Reenviar demasiado pronto devuelve HTTP 429 con `Retry-After`, que la interfaz respeta. Las pantallas abiertas actualizan el estado de confirmación al volver a la pestaña o pulsar **Ya confirmé mi correo**.

El registro tiene un límite adicional de cinco intentos por dirección del cliente por hora (`RATE_LIMIT_REGISTER`), compartido mediante Redis en producción. Los límites de publicaciones y autenticación siguen activos. Los avistamientos breves desde una ficha mantienen el envío sin cuenta, según la decisión del usuario, con los límites de publicación y carga ya existentes. La confirmación reduce el abuso de cuentas sin correo accesible; el flujo anónimo sigue requiriendo moderación. Las cuentas antiguas pendientes pueden leer sus datos, recibir notificaciones internas, eliminar registros propios y cerrar o marcar encontrados sus avisos; no se verifican automáticamente ni se les envían correos masivos.

El correo de recuperación incluye una versión HTML con el logo y los colores de MascoMatch, un botón para elegir una contraseña y el enlace completo como alternativa. El logo viaja incorporado en el mensaje mediante CID, sin depender de una URL pública de imágenes. Se mantiene una versión de texto para lectores que no muestran HTML. Ambas versiones indican el vencimiento de 30 minutos y el uso único del enlace.

El correo de confirmación comparte ese diseño, con el botón **Confirmar mi correo**, el enlace alternativo y el plazo de 24 horas. Ninguna de las dos plantillas depende de imágenes externas.

Cuando `MAIL_DELIVERY_MODE=disabled`, registrar una cuenta, solicitar recuperación o un nuevo correo de confirmación devuelve HTTP 503: no se anuncia un envío que no puede ocurrir. Los enlaces ya emitidos siguen pudiendo consumirse hasta su vencimiento. Para registrar cuentas en desarrollo se necesita SMTP o el modo `preview` con Mailpit. El modo `preview`, exclusivo del desarrollo, indica en el formulario que el enlace está en Mailpit y no en la casilla real.

### Recuperación en desarrollo local

Configurar estas variables en `.env` (archivo privado excluido de Git):

```dotenv
MAIL_DELIVERY_MODE=preview
SMTP_HOST=mailpit
SMTP_PORT=1025
SMTP_TLS_MODE=none
PUBLIC_SITE_URL=http://localhost:3000
```

Aplicar la configuración a la API y levantar el buzón local:

```powershell
docker compose --profile mail-local up -d --no-deps mailpit api
```

Solicitar el enlace en `http://localhost:3000/recuperar` y abrir el correo en `http://localhost:8025`. El envío se procesa cada diez segundos. El enlace de recuperación vence a los treinta minutos y sirve una sola vez. Mailpit captura los correos localmente; para recibirlos en una casilla real hay que configurar SMTP con el servicio externo. Esta configuración local no se utiliza en producción.

```sh
docker compose -p mascomatch --env-file .env.production -f compose.production.yml up -d --force-recreate api
```

En la instalación local, aplicar cambios de `.env` con `docker compose --profile ai-local up -d api worker`; `restart` solo vuelve a iniciar contenedores con sus variables anteriores.

## Respaldos y recuperación

El servicio `backup` arranca con una copia y repite cada 21.600 segundos (seis horas), configurable con `BACKUP_INTERVAL_SECONDS`. Captura una instantánea PostgreSQL con `pg_dump`, guarda las fotos referidas por esa misma instantánea y un manifiesto con hashes. El archivo final usa AES-256-GCM y una clave distinta de las credenciales de la aplicación. Solo registra éxito después de autenticar y verificar el archivo. Las versiones retenidas permiten leer una foto eliminada durante la captura.

```sh
docker compose -p mascomatch --env-file .env.production -f compose.production.yml exec backup python -m app.ops.backup create /backups
docker compose -p mascomatch --env-file .env.production -f compose.production.yml exec backup python -m app.ops.backup verify /backups/ARCHIVO.mbak
```

Esta configuración limita el archivo descifrado a 1 GiB, hasta 20.000 fotos y usa almacenamiento temporal de 2 GiB para recuperar. Antes de superar esa capacidad hay que ampliar y probar el almacenamiento temporal y el presupuesto de respaldo. `BACKUP_LOCAL_KEEP=14` conserva las últimas catorce copias (aproximadamente 3,5 días al intervalo predeterminado). Con B2 activo, conserva además todos los pendientes o no verificables remotamente; vigilar espacio. Un respaldo solo en el mismo servidor no cubre su pérdida.

La [guía B2](backblaze-backup.md) explica el alta manual del bucket privado, retención COMPLIANCE de 30 días, lifecycle posterior, claves exclusivas del servicio `backup`, reintentos y simulacro de restauración. `OFFSITE_BACKUP_ENABLED=false` sigue siendo el valor inicial. B2 no se usa para las fotos operativas. El resumen de administración y las métricas privadas muestran por separado el estado local y off-site. Prometheus incluye reglas de alerta; conectar y probar su receptor externo es una tarea del propietario.

RPO objetivo aproximado: ≤6 h; el intervalo no es una garantía ante fallos o subidas demoradas. RTO sin compromiso hasta medir una recuperación real: depende del tamaño, red, provisión de servidor y restauración PostgreSQL/fotos. No se implementa alta disponibilidad. La validación ordinaria agrega recuperación desde una copia remota simulada; `tools/production_validate.py --with-b2 --b2-env-file ...` habilita deliberadamente el simulacro B2 real con bucket de prueba, nunca en CI normal.

Para recuperar, preparar un entorno aislado con una base PostgreSQL sin tablas de aplicación y un bucket vacío, con la aplicación detenida. Entregar la clave original de respaldo al servicio de recuperación y la URL del destino en un archivo privado. Ejecutar:

```sh
python -m app.ops.backup restore /backups/ARCHIVO.mbak --target-database-file /run/secrets/restore_database_url
```

El comando verifica autenticidad, rutas y hashes antes de modificar destinos. Rechaza una base con tablas de aplicación o un bucket con objetos. Luego ejecutar la aplicación de permisos de `app.ops.database` con el propietario de la base y poner en marcha API, web y workers. Mantener intacta la instalación anterior hasta comprobar usuarios, avisos, fotos y acceso en la recuperada.

## Monitoreo

El formulario público de contacto reutiliza el SMTP configurado y envía a info@mascomatch.com desde una cola privada. Sus métricas de mensajes pendientes y fallidos se incluyen en la supervisión del correo. Los límites por cliente y global, la retención y el reintento manual están descritos en `contact.md`.

```sh
docker compose -p mascomatch --env-file .env.production -f compose.production.yml --profile monitoring up -d prometheus
```

`/internal/metrics` exige el token de monitoreo y no se publica mediante Caddy. `/health/ready` verifica PostgreSQL, Redis y acceso autenticado al bucket. Las métricas contienen cantidades y tiempos, sin contactos ni fotos. Prometheus muestra alertas; queda por configurar un destino de avisos operativos para el operador cuando se elija el servidor. La entrega de un correo no garantiza que el proveedor lo haya colocado en la bandeja de entrada.

## Evaluar coincidencias y operar la IA

Ver [IA local: operación, reglas de alerta, backfill, benchmarks, etiquetas y evaluación](ai-production.md). El informe [de entrega](ai-delivery-report.md) diferencia las pruebas técnicas de la eficacia aún no medida con identidades reales.

La configuración standalone usa volúmenes persistentes, secrets por rol, límites de CPU/memoria, usuarios sin privilegios en API/web/workers, raíces de solo lectura y temporales limitados. No mezclar `compose.production.yml` con el Compose de desarrollo.

## Comprobaciones vigentes

Los comandos y resultados exactos de esta mejora están en [TEST RESULTS](ai-delivery-report.md#2-test-results). Las pruebas normales no descargan modelos. Las integraciones con PostgreSQL, Redis, storage y modelos requieren activación explícita y usan datos aislados. Los benchmarks no constituyen una medición de tráfico del VPS ni de precisión sobre mascotas reales.

## Antes de publicar

Las acciones que necesitan la cuenta, contratación o criterio del titular están detalladas en [OWNER ACTIONS REQUIRED](ai-delivery-report.md#10-owner-actions-required). Los scripts resuelven instalación, migración, modelos, backfill, comprobaciones y rollback; no requieren SQL manual.
