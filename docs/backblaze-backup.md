# Respaldos externos en Backblaze B2

Guía operativa · 22 de octubre de 2026. La integración está desactivada por defecto. B2 recibe únicamente archivos `.mbak` ya cifrados; las fotos de uso cotidiano siguen en SeaweedFS.

## 1. Preparar la cuenta y el bucket

1. Crear una cuenta **Backblaze B2 Cloud Storage**, proteger su acceso y entrar en **Buckets → Create a Bucket**.
2. Crear un bucket exclusivo de respaldos, **privado**. No usar el bucket operativo de fotos. Elegir su región y copiar el nombre, la región y el endpoint S3 exactos que muestra Backblaze.
3. Habilitar **Object Lock** y configurar retención predeterminada **COMPLIANCE, 30 días**. Esta decisión requiere revisión del propietario: habilitar Object Lock tiene efectos permanentes; un período COMPLIANCE vigente no se puede acortar para borrar anticipadamente los datos. El software consulta esta configuración y no la modifica. [Object Lock de Backblaze](https://www.backblaze.com/docs/cloud-storage-enable-object-lock-with-the-s3-compatible-api).
4. Configurar el lifecycle descrito en la sección siguiente antes de activar las subidas.
5. Para el simulacro con datos sintéticos, crear **otro** bucket cuyo nombre empiece por `mascomatch-drill-`, con su propia clave restringida. No reutilizar el de producción en la validación opt-in.

El endpoint debe tener la forma `https://s3.REGION.backblazeb2.com`, con la misma región configurada. No se aceptan hosts arbitrarios, HTTP, credenciales en la URL, rutas ni parámetros. Endpoint y bucket provienen de la configuración privada del servidor; no hay un endpoint HTTP que permita elegir destinos de respaldo.

## 2. Retención y lifecycle

Configurar una regla sobre `backups/` con estos valores de Backblaze:

```json
[
  {
    "fileNamePrefix": "backups/",
    "daysFromUploadingToHiding": 31,
    "daysFromHidingToDeleting": 1,
    "daysFromStartingToCancelingUnfinishedLargeFiles": 1
  }
]
```

La regla oculta cada archivo a partir del día 31 y permite eliminar sus versiones tras un día adicional; el procesamiento no es instantáneo. Es necesario incluir la edad desde la subida: con nombres únicos, limitar solamente las versiones anteriores no elimina la última versión de cada nombre. Un bloqueo vigente impide su eliminación. Configurar estos campos desde las reglas personalizadas del panel o con la herramienta administrativa de Backblaze, y comprobar los valores guardados. MascoMatch no administra lifecycle ni borra objetos remotos. [Semántica de lifecycle](https://www.backblaze.com/docs/en/cloud-storage-lifecycle-rules).

Cada subida solicita COMPLIANCE por 30 días **más un margen de transferencia**: timeout configurado + 180 segundos. Así una subida prolongada sigue protegida al terminar. La consulta posterior exige al menos 30 días desde `LastModified`, con tolerancia de reloj de 60 segundos. Mantener sincronizado el reloj del servidor. Si se cambia el período, también se debe ampliar el lifecycle y comprobar el nuevo diseño; no reducirlo por debajo del bloqueo.

La retención local es independiente: **14 copias completas**, unas 3,5 jornadas a intervalos de seis horas. Con B2 activo, las copias sin confirmación remota se conservan aunque superen ese límite. Durante una caída prolongada pueden llenar el disco; revisar las alertas y ampliar espacio. Nunca eliminar pendientes para silenciar la alarma.

## 3. Application Key dedicada

Crear una clave restringida al bucket seleccionado y, preferentemente, al prefijo `backups/`. Usar capacidades explícitas:

| Capacidad | Operaciones utilizadas |
| --- | --- |
| `listBuckets` | HEAD del bucket concreto |
| `readBuckets` | Consultar ACL privada |
| `listFiles` | Listar versiones bajo el prefijo |
| `readFiles` | HEAD y descarga de versiones |
| `writeFiles` | Subida normal/multipart y cancelación de multipart fallido |
| `readBucketRetentions` | Consultar Object Lock del bucket |
| `readFileRetentions` | Comprobar el bloqueo de cada versión |
| `writeFileRetentions` | Solicitar retención explícita al subir |

No conceder `deleteFiles`, `writeBuckets`, `deleteBuckets`, `writeBucketRetentions`, `bypassGovernance`, permisos de legal hold ni gestión de claves. La integración no llama a `ListBuckets`: no solicita `listAllBucketNames` por defecto. Backblaze lo documenta para compatibilidad de herramientas que enumeran buckets; si un cliente administrativo distinto lo necesita, revisar ese permiso por separado y comprobar la clave mínima con `check-offsite` y el simulacro real. [Capacidades S3](https://www.backblaze.com/docs/cloud-storage-s3-compatible-app-keys), [alcance de las claves](https://www.backblaze.com/docs/cloud-storage-application-key-capabilities).

Si el panel no permite seleccionar exactamente esas capacidades, el propietario puede usar el CLI oficial B2 v4 desde su entorno administrativo seguro:

```sh
b2 key create --bucket NOMBRE_DEL_BUCKET --name-prefix backups/ mascomatch-backup \
  listBuckets,readBuckets,listFiles,readFiles,writeFiles,readBucketRetentions,readFileRetentions,writeFileRetentions
```

El CLI de administración se usa solo para el alta manual; **no se instala un SDK Native ni una credencial administradora en MascoMatch**. El comando muestra el identificador y la application key: guardarlos inmediatamente en el gestor de secretos del propietario, sin grabar la terminal ni copiar su salida a tickets, Git o chats. La application key se muestra una sola vez al crearla. [Comando oficial `key create`](https://b2-command-line-tool.readthedocs.io/en/v4.6.0/subcommands/key_create.html).

## 4. Instalar la configuración en el VPS

Ejecutar desde la carpeta del repositorio en Linux. En una instalación nueva, `python3 tools/production_init.py` genera toda la configuración privada. Para añadir archivos vacíos a una instalación existente sin reemplazar ninguna clave:

```sh
python3 tools/production_init.py --prepare-b2-secrets
```

Si se usa un directorio privado diferente, agregar `--secrets-directory /RUTA/PRIVADA/.secrets`. `production_apply.py deploy` también prepara automáticamente los archivos que falten antes de validar Compose.

Editar en el servidor, con un editor seguro, estos dos archivos individuales:

- `.secrets/b2_key_id`: identificador de la Application Key dedicada.
- `.secrets/b2_application_key`: application key completa, sin comillas.

Los archivos se crean vacíos y nunca se sobrescriben automáticamente. Cambiar temporalmente su permiso a `0600` para editarlos; dejar el directorio privado en `0700` y los archivos individuales en `0444`, siguiendo el patrón del repositorio para montajes de secretos de Docker en servicios sin root. El directorio privado no se monta en los contenedores. Proteger también el usuario administrador del host y la cuenta de Docker. No pasar claves por argumentos ni guardarlas como valores de `.env.production`.

Agregar o ajustar estos valores **no secretos** en `.env.production`:

```dotenv
OFFSITE_BACKUP_ENABLED=true
B2_ENDPOINT=https://s3.REGION.backblazeb2.com
B2_REGION=REGION
B2_BUCKET=NOMBRE_DEL_BUCKET
B2_OBJECT_LOCK_ENABLED=true
B2_OBJECT_LOCK_DAYS=30
B2_OPERATION_TIMEOUT_SECONDS=900
BACKUP_INTERVAL_SECONDS=21600
BACKUP_LOCAL_KEEP=14
OFFSITE_RETRY_INTERVAL_SECONDS=900
OFFSITE_DEEP_VERIFY_INTERVAL_SECONDS=604800
```

Reemplazar `REGION` y `NOMBRE_DEL_BUCKET` por los datos reales, sin cambiar el formato del endpoint. Las rutas `B2_KEY_ID_FILE` y `B2_APPLICATION_KEY_FILE` ya están fijadas en Compose a `/run/secrets/b2_key_id` y `/run/secrets/b2_application_key`. Solo el servicio `backup` recibe configuración y archivos B2; API, web, workers, DB, Redis y fotos no los reciben. La clave AES `backup_key` es independiente: conservar una copia segura **fuera del VPS**, o no será posible recuperar los archivos aunque B2 esté intacto.

Configurar `OFFSITE_BACKUP_ENABLED=false` permite seguir usando respaldos locales sin cuenta B2. Si se activa y falta configuración, el proceso de backup falla con un código saneado. Una caída de B2 no cambia la disponibilidad de la web/API. El despliegue crea su copia local previa con `--local-only`, sin esperar a B2 ni podar copias; el servicio automático las envía después.

## 5. Comandos de producción

Definir esta función de comodidad en una terminal del VPS, dentro del repositorio:

```sh
dc() { docker compose -p mascomatch --env-file .env.production -f compose.production.yml "$@"; }
```

Primero construir la imagen y validar la configuración, sin subir datos:

```sh
dc config --quiet
dc build backup
dc run --rm --no-deps backup python -m app.ops.backup check-offsite
```

El último comando comprueba acceso, privacidad y COMPLIANCE de 30 días. Luego crear una copia manual, comprobar su presencia en el panel de Backblaze y verificarla:

```sh
dc run --rm --no-deps backup python -m app.ops.backup create /backups
dc run --rm --no-deps backup python -m app.ops.backup list-offsite --retention --limit 20
dc run --rm --no-deps backup python -m app.ops.backup verify-offsite --deep
dc up -d --no-deps backup
```

`run` usa la configuración nueva; para un proceso ya activo, `up` recrea el contenedor cuando cambia su configuración. Si ya está corriendo un respaldo, el bloqueo compartido impide ejecutar otro escritor simultáneo: esperar a que termine. Los nombres remotos siguen `backups/YYYY/MM/DD/<nombre-original>.mbak`. Guardar el `key` y `version_id` de un respaldo comprobado en el registro privado del simulacro.

Comandos adicionales, sin recrear el respaldo:

```sh
dc exec -T backup python -m app.ops.backup sync-offsite
dc exec -T backup python -m app.ops.backup verify-offsite OBJETO --version-id VERSION
dc exec -T backup python -m app.ops.backup verify-offsite OBJETO --version-id VERSION --deep
dc exec -T backup python -m app.ops.backup verify /backups/ARCHIVO.mbak
```

Sustituir `OBJETO`, `VERSION` y `ARCHIVO` por referencias reales devueltas por el listado. Sin objeto explícito, se selecciona la versión actual con la fecha de captura más reciente; las versiones ocultas siguen apareciendo en el listado y pueden recuperarse explícitamente con su VersionId. `--retention` agrega una consulta por versión. No existe un comando de borrado remoto.

## 6. Qué se comprueba y cómo se reintenta

1. Crear el `.mbak` local con la lógica existente: snapshot de PostgreSQL, fotos referenciadas y manifiesto; AES-256-GCM antes de salir del VPS.
2. Autenticar y comprobar los hashes localmente. Solo entonces registrar éxito local.
3. Calcular SHA-256 del **archivo cifrado** y subir exactamente esos bytes con `upload_file`. Multipart automático desde 32 MiB; dos transferencias simultáneas, sin cargar todo en memoria.
4. HEAD posterior: tamaño, metadata `mascomatch-sha256`, VersionId y retención. **ETag no se usa como SHA-256**. Esta comprobación valida metadata y tamaño; no equivale a descargar el contenido completo.
5. Guardar recibo local atómico `.mbak.offsite.json`, ligado al destino, hash y versión. En cada reconciliación se vuelve a consultar B2: un recibo solo es una pista. Una descarga profunda semanal autentica un respaldo reciente y revisa su manifiesto completo.
6. Reintentar pendientes cada 15 minutos, hasta 16 archivos por pasada, empezando por los más recientes. Los archivos pendientes sobreviven reinicios. Una pérdida del recibo se resuelve consultando el objeto existente, sin sobrescribirlo.

Las conexiones tienen timeout de 10 s, lecturas de 60 s y hasta tres intentos del SDK. Cada transferencia aplica un plazo de 900 s comprobado entre bloques; una solicitud ya bloqueada puede tardar su timeout y reintentos antes de terminar. No es un kill de proceso a los 900 s exactos. Los listados también están limitados a 100 páginas/10.000 versiones. Las próximas capturas se programan desde el comienzo del ciclo; los fallos locales se reintentan a intervalos de 15 minutos.

Un nombre existente con tamaño/hash diferentes, o una versión oculta del mismo nombre, se rechaza. El daemon y los comandos manuales comparten un bloqueo de archivo en el volumen. No se promete exclusión atómica entre dos VPS independientes con volúmenes distintos: operar **un solo escritor**. Object Lock protege versiones; unas credenciales de escritura comprometidas podrían crear otras versiones, por lo que es importante guardar referencias verificadas de VersionId.

## 7. Operación, métricas y alertas

El resumen de `/admin` muestra última copia local, última confirmación B2, fecha de captura recuperable, pendientes, verificación profunda e inventario aproximado. No depende del filtro de fechas; el botón flotante existente vuelve a consultar este estado. Ninguna respuesta incluye credenciales ni detalles de conexión.

El estado persistente vive en el volumen local; Redis solo publica una vista saneada para administración y Prometheus. Una caída de Redis no invalida una copia ya creada. No confundir **última subida** con **última captura**: enviar hoy un archivo antiguo no satisface el objetivo de recuperación actual.

Métricas privadas añadidas:

```text
mascomatch_offsite_backup_enabled
mascomatch_offsite_backup_last_success_unixtime
mascomatch_offsite_backup_last_attempt_unixtime
mascomatch_offsite_backup_pending_count
mascomatch_offsite_backup_failures_total
mascomatch_offsite_backup_consecutive_failures
mascomatch_offsite_backup_last_size_bytes
mascomatch_offsite_backup_last_duration_seconds
mascomatch_offsite_backup_latest_capture_unixtime
mascomatch_offsite_backup_last_deep_verify_unixtime
mascomatch_offsite_backup_objects
mascomatch_offsite_backup_stored_bytes
mascomatch_offsite_backup_inventory_unixtime
mascomatch_offsite_backup_inventory_truncated
mascomatch_backup_interval_seconds
mascomatch_backup_heartbeat_unixtime
mascomatch_backup_free_bytes
mascomatch_backup_status_known
```

Se conserva `mascomatch_backup_last_success_unixtime`. Las alertas distinguen copia local atrasada, captura remota atrasada (8 h por defecto), fallos consecutivos B2, falta de señal del proceso, menos de 1 GiB libre y verificación profunda atrasada. El margen se adapta al intervalo configurado para copias locales/remotas. La verificación profunda tiene alerta a los ocho días; si se amplía su intervalo, ajustar también esa regla.

Estas son reglas de **Prometheus**, no un servicio de envío de alertas ya conectado. El propietario debe enlazarlas a un receptor externo y verificar la recepción; el repositorio no configura una cuenta de Alertmanager ni un monitor externo del host. Una caída de todo el VPS también apaga su Prometheus. Consultar el estado desde fuera y realizar simulacros periódicos es parte de la operación.

Errores admitidos en registros/estado: `LOCAL_BACKUP_FAILED`, `LOCAL_VERIFY_FAILED`, `OFFSITE_UPLOAD_FAILED`, `OFFSITE_VERIFY_FAILED`, `OFFSITE_AUTH_FAILED`, `OFFSITE_CONFIGURATION_ERROR`, `OFFSITE_RETENTION_ERROR`. Nunca se copia el mensaje crudo del SDK, URLs DB ni claves a los logs.

## 8. Simulacro real opt-in en un entorno desechable

La validación ordinaria no se conecta a B2:

```sh
python3 tools/production_validate.py --keep
```

Primero ejecutarla para preparar `real-data/production-preview/.secrets`. Después colocar allí los dos secretos **del bucket de prueba**. Crear un archivo privado, por ejemplo `real-data/b2-drill.env`, con solo `B2_ENDPOINT`, `B2_REGION`, `B2_BUCKET` y opcionalmente `B2_OBJECT_LOCK_ENABLED=true`, `B2_OBJECT_LOCK_DAYS=30`; usar el endpoint y el bucket reales de prueba. No incluir claves en ese archivo.

```sh
python3 tools/production_validate.py --with-b2 --b2-env-file real-data/b2-drill.env
```

Se usa el proyecto fijo `mascomatch-prod-smoke`, sin puertos públicos: datos sintéticos, correo restringido a Mailpit, DB y fotos temporales. La prueba crea el `.mbak`, sube a B2, comprueba HEAD y Object Lock, descarga/autentica, restaura en otra DB y bucket vacíos, compara filas y hashes de fotos y rechaza restaurar sobre una base con datos. Solo el contenedor `backup` recibe los secretos B2.

El test imprime `B2_DRILL_ARCHIVE_RETAINED` con objeto, versión y vencimiento antes de restaurar. Esa copia sintética **queda protegida en el bucket de prueba**, visible para el propietario; lifecycle la elimina posteriormente. No intenta violar COMPLIANCE ni deja un archivo oculto sin referencia. El entorno Docker se elimina al terminar, salvo `--keep`. No se borra el archivo remoto. CI normal omite esta prueba; `RUN_B2_INTEGRATION=1` exige además las protecciones del stack y bucket de prueba.

## 9. Recuperación manual desde B2 ante pérdida del servidor

Usar otro VPS o un entorno Linux aislado, con un proyecto Docker diferente y almacenamiento vacío. Mantener detenidas API/workers. Inicializar secretos nuevos, guardar allí la **clave AES original** y una clave B2 restringida con acceso al respaldo. Configurar el mismo endpoint/región/bucket. No ejecutar migraciones sobre la DB de recuperación antes de restaurar: debe estar vacía.

En ese entorno, dentro del repositorio:

```sh
dr() { docker compose -p mascomatch-recovery --env-file .env.production -f compose.production.yml "$@"; }
dr build backup db photos-init migrate
dr up -d --wait db redis photos
dr run --rm --no-deps photos-init
dr run --rm --no-deps backup python -m app.ops.backup list-offsite --retention --limit 20
```

Copiar de forma privada la URL del propietario de la **nueva DB vacía** a `.secrets/restore_database_url` (puede provenir de su `migrator_database_url`, sin imprimirla). Mantenerla protegida. Usar su ruta absoluta en el montaje:

```sh
dr run --rm --no-deps \
  -v /RUTA/PRIVADA/.secrets/restore_database_url:/run/secrets/restore_database_url:ro \
  backup python -m app.ops.backup restore-offsite OBJETO --version-id VERSION \
  --target-database-file /run/secrets/restore_database_url
```

La configuración S3 de ese contenedor debe apuntar al **nuevo** SeaweedFS y bucket vacío de recuperación, nunca a las fotos de producción. El comando descarga temporalmente el cifrado, comprueba SHA/AES/manifiesto y llama al `restore_backup()` existente. Este rechaza DB con tablas o bucket con objetos; no se introduce otra lógica de restauración. Luego aplicar permisos/migraciones con `dr run --rm --no-deps migrate` y comprobar usuarios, avisos, fotos y acceso antes de habilitar tráfico. No destruir el entorno anterior hasta verificar la recuperación.

Para un simulacro periódico, preferir el comando opt-in de la sección 8: crea y destruye solo los destinos desechables. Anotar duración de descarga, restore PostgreSQL, fotos y comprobaciones, fecha de captura y VersionId. Repetir después de cambios de tamaño, infraestructura o formato de respaldo.

## 10. Capacidad, RPO, RTO y límites

- **RPO objetivo aproximado ≤6 h**, según intervalo de captura; no es una garantía absoluta. Duración del respaldo/subida, caída de B2, cola pendiente o fallos locales pueden ampliarlo. La métrica de captura remota y las alertas permiten detectarlo.
- **RTO aún no medido en el servidor real**. Recuperación manual, dependiente de tamaño, ancho de banda, provisión del VPS, restore PostgreSQL y subida de fotos.
- Cada copia es completa: cuatro al día ×30 días ≈120 archivos; con margen de lifecycle de unos 32 días, alrededor de 128 archivos más retrasos/versiones. Multiplicar por el tamaño cifrado medio y agregar tráfico/solicitudes para estimar costos con las tarifas vigentes del proveedor. No hay consultas de billing ni promesa de gasto fijo.
- El inventario cuenta versiones incluidas las ocultas y puede quedar parcial al alcanzar 10.000; se indica su antigüedad y truncamiento. Los valores no son una factura ni incluyen multipart sin finalizar.
- Se mantiene el límite existente de **1 GiB de tar descifrado**, 20.000 fotos y tmpfs de 2 GiB. Las descargas cifradas temporales usan disco en el volumen de respaldos; el descifrado/verificación usa `/tmp`. Reservar capacidad y ampliar/probar estos límites antes de superarlos.
- Se reutiliza boto3/botocore ya fijado; no hay nuevas dependencias de producción, cola ni base de datos para B2.
- No se implementan réplicas, failover, segundo VPS permanente ni alta disponibilidad. Las copias off-site sirven para recuperación ante desastres.

## 11. Activación y criterio de aprobación

El código y las pruebas simuladas pueden validarse sin cuenta B2. **No declarar el respaldo off-site operativo** hasta completar el setup real, `check-offsite`, subida, verificación profunda, Object Lock observado, restore desechable y recepción de alertas. Conservar la clave AES fuera del host y repetir el simulacro. Consultar los resultados de esta entrega en [el informe](backblaze-delivery-report.md).
