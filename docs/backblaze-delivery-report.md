# Entrega: respaldo off-site B2 de MascoMatch

Fecha: 22 de octubre de 2026. Informe preparado al completar la implementación para revisión. Guía del propietario: [backblaze-backup.md](backblaze-backup.md).

Autorización posterior: el propietario solicitó hacer commit y push de la entrega. El estado Git documentado al final corresponde a la captura previa al commit. B2 continúa desactivado hasta completar su configuración y validación reales.

## 1. EXISTING BACKUP AUDIT

Se revisaron el módulo de respaldo completo, Compose de producción, inicialización/aplicación/validación del despliegue, documentación, pruebas de cifrado y recuperación, métricas y reglas Prometheus. Al comenzar, `git status --short` y `git diff --stat` no mostraban cambios; referencia de partida `48ee2f8b63b3a99c61c1c4fbbd1bd4e331177ba3`.

El sistema previo genera un tar de `pg_dump` y fotos referenciadas por la misma snapshot PostgreSQL, con manifiesto SHA-256; lo cifra mediante AES-256-GCM y publica el `.mbak` con renombrado atómico. `verified_archive()` autentica, valida rutas y compara hashes. `restore_backup()` verifica antes de modificar destinos y exige DB sin tablas de aplicación y bucket vacío. Límites existentes: 1 GiB de tar, 20.000 fotos y tmpfs de 2 GiB. La retención local conservaba 14 copias y el loop diario dormía todo el intervalo.

No existían copia externa, reintentos remotos, recibos ni estado B2. El éxito Redis se registraba antes de una verificación local completa y una caída de Redis podía hacer fallar el comando después de crear el archivo. Ahora se registra después de verificar y Redis es best effort. Se mantienen formato, cifrado, snapshot, clave y lógica de recuperación existentes.

## 2. IMPLEMENTED

- Módulo desacoplado `app.ops.offsite`: configuración por archivos, cliente S3, comprobación privada/Object Lock, upload, HEAD, descarga, listado, recibos, reconciliación y retención local segura.
- Estado saneado `app.ops.backup_status`, métricas privadas, resumen administrativo y reglas de alerta independientes.
- Comandos `check-offsite`, `sync-offsite`, `verify-offsite`, `list-offsite`, `restore-offsite`; se preservan `create`, `verify`, `restore`, `serve`.
- Configuración/secretos exclusivos de `backup`, preparación no destructiva de instalaciones existentes y simulacro real opt-in.
- Tests con S3 simulado, recuperación real PostgreSQL/SeaweedFS desde copia simulada, reglas Prometheus probadas y guía operativa.

## 3. ARCHITECTURE

```text
Snapshot PostgreSQL + fotos SeaweedFS
  → create_backup → .mbak AES-256-GCM → verificación local
      ├─ volumen local + recibos persistentes
      └─ copia de los mismos bytes → B2 S3 → HEAD + retención
                                         → descarga/autenticación semanal
```

API/admin/Prometheus leen exclusivamente un resumen saneado en Redis. No reciben cliente, configuración ni secretos B2. B2 no participa en la lectura/escritura operativa de fotos. No se añadieron servicios de cola ni nuevas tablas/migraciones.

## 4. B2 CONFIGURATION

`OFFSITE_BACKUP_ENABLED=false` por defecto. Activarlo exige endpoint HTTPS canónico de Backblaze, región coincidente, bucket privado distinto del operativo y dos archivos de secretos no vacíos. No se hardcodea región ni bucket. `check-offsite` comprueba HEAD del bucket, ACL y configuración de retención. Una configuración inválida falla temprano en el proceso de backup; no afecta la configuración de API/web.

La guía contiene el bloque exacto de `.env.production`, permisos, comandos y creación manual del bucket. No se creó ninguna cuenta, bucket ni clave real en esta entrega.

## 5. OBJECT LOCK DESIGN

Bucket configurado manualmente con Object Lock y default COMPLIANCE de 30 días. Cada subida especifica COMPLIANCE y fecha de retención de 30 días más margen de transferencia; HEAD y `GetObjectRetention` comprueban la versión almacenada. Un bucket público, default diferente o bloqueo inesperado se rechaza con código saneado. El código no cambia la configuración del bucket ni ejecuta pruebas destructivas sobre archivos reales.

El bloqueo protege versiones. Se conservan VersionId en recibos y listados para recuperar una versión verificada aunque aparezcan versiones posteriores. La prueba real opt-in consulta la retención y conserva su archivo sintético protegido.

## 6. RETENTION DESIGN

Captura cada 21.600 s, configurable; 14 archivos locales, también configurable. Con B2 activo no se podan copias sin recibo válido y confirmación remota; las caídas o discrepancias mantienen los archivos. Antes de podar se compara también el SHA del cifrado local con la versión remota. Las copias ajenas al patrón propio no se borran.

B2: COMPLIANCE 30 días, lifecycle sobre `backups/` que oculta tras 31 días y elimina versiones un día después; cancela multipart inconcluso tras un día. La guía explica por qué hacen falta ambas edades con nombres únicos. No hay borrado remoto genérico ni limpieza remota dependiente del daemon.

## 7. SECURITY / CREDENTIALS

Clave dedicada limitada al bucket/prefijo, ocho capacidades enumeradas en la guía, sin administración de buckets, borrado de archivos, bypass ni gestión de claves. No se usa la master key. No se llama a `ListBuckets`; `listAllBucketNames` no se solicita por defecto y su compatibilidad debe comprobarse en el alta real.

Únicamente `backup` monta `b2_key_id` y `b2_application_key`. Secretos en archivos individuales; directorio host privado y permisos coherentes con el patrón existente de Docker secrets. No hay claves en ejemplos, código ni nuevos archivos rastreados. La clave AES independiente debe guardarse fuera del VPS. Las credenciales del simulacro real también se montan solo en `backup`.

Endpoint/bucket son configuración del servidor; no hay parámetros HTTP de destino, URLs arbitrarias, redirecciones ni claves remotas libres. Se validan ruta/prefijo/fecha/UUID y se rechazan traversal, URLs, barras invertidas y fechas inválidas. Logs/estado usan únicamente los siete códigos previstos; no imprimen excepciones SDK, URLs DB ni claves. Métricas exigen token privado; operaciones administrativas exigen la cuenta autorizada.

## 8. BACKUP FLOW

Crear local → autenticar/hash → registrar éxito local → verificar otra vez antes del envío → calcular SHA-256 cifrado → comprobar que el nombre no exista → `upload_file` → HEAD tamaño/hash/versionado → consultar COMPLIANCE → recibo atómico → estado/métricas → retención local condicionada.

Transferencia multipart desde 32 MiB, dos conexiones de transferencia, lectura por bloques y archivos temporales privados. Los nombres son `backups/YYYY/MM/DD/<nombre-original>.mbak`. Nunca se usa `latest.mbak` como única copia. Una versión existente/oculta no se sobrescribe. Un bloqueo de volumen excluye escritores concurrentes; un comando manual ocupado termina con código 2 sin pisar el estado del daemon.

## 9. RETRY FLOW

Cada 900 s se inspeccionan archivos propios y recibos, se contrasta cada versión confirmada con B2 y se reintentan hasta 16 pendientes, de más reciente a más antiguo. El estado persiste en sidecars y `.offsite-state.json`; los recibos son pistas, B2 es la autoridad final. Un recibo ausente/dañado se reconcilia comprobando tamaño/hash del archivo original. Una pérdida del estado global reconstruye la captura reciente desde recibos verificados.

Una caída remota mantiene el archivo local y no frena el siguiente ciclo de capturas. El despliegue previo a migraciones usa `create --local-only`: verifica local sin esperar a B2 ni podar pendientes. El daemon sube después esa misma copia. Esto evita que una caída externa impida volver a iniciar API/web durante un despliegue.

## 10. VERIFICATION

No se confía en un 2xx de subida ni en ETag. Se conserva SHA-256 de los bytes cifrados en metadata y recibo y se compara con HEAD, tamaño y VersionId. La comprobación frecuente es de metadata; no certifica por sí sola el contenido descargado. Verificación profunda semanal: descargar un respaldo reciente, comprobar SHA-256 y ejecutar AES-GCM, rutas y hashes del manifiesto.

`verify-offsite --deep` hace lo mismo manualmente. Descarga acotada por tamaño, streaming, plazo y timeouts SDK; se limpia staging al fallar. No se elimina un archivo preexistente si falla la apertura del destino. Las pruebas incluyen ciphertext manipulado incluso con metadata SHA recalculada: AES sigue rechazándolo.

## 11. RESTORE FLOW

`restore-offsite OBJETO --version-id VERSION --target-database-file ARCHIVO_PRIVADO`: comprobar configuración/bloqueo → descargar versión fijada → verificar SHA/AES/manifiesto → reutilizar `restore_backup()` en DB nueva y fotos vacías. Se autentica antes de modificar destinos; se rechaza restaurar sobre datos existentes. No se duplicó el motor de restore.

La guía incluye comandos para un proyecto separado `mascomatch-recovery` y para el simulacro totalmente desechable. No se restauró sobre desarrollo ni producción, solo sobre destinos sintéticos temporales.

## 12. MONITORING

Se conserva la métrica local existente y se añaden éxito/intento remoto, pendientes, contador de fallos, fallos consecutivos, tamaño/duración, captura recuperable, verificación profunda, inventario/tamaño aproximado y estado de truncamiento. Hay heartbeat, espacio libre e intervalo configurado.

El resumen `/admin` muestra las fechas local/remota por separado, pendientes, inventario y verificación profunda, con ayudas informativas y el botón flotante de recarga existente. No aplica el filtro de fechas al estado operativo actual. La antigüedad se evalúa por **captura**, no por subir hoy una copia antigua. Inventario limitado a 10.000 versiones/100 páginas; cuenta versiones ocultas y no equivale a billing.

## 13. ALERTS

Se mantienen alertas generales y se añaden/diferencian: respaldo local vencido, captura B2 vencida (8 h por defecto), tres fallos consecutivos, heartbeat ausente, poco espacio y verificación profunda atrasada. El umbral de captura/local se adapta al intervalo +2 h, con mínimo 8 h. Prometheus valida 14 reglas totales.

Cuatro escenarios probados con `promtool test rules`: B2 desactivado sin alertas off-site; subida reciente de captura vieja dispara alerta; fallos consecutivos disparan warning; respaldo local atrasado alerta aunque B2 esté desactivado.

Falta conectar y probar un receptor real de alertas y supervisión externa al VPS. Las reglas locales de Prometheus por sí solas no envían correo ni detectan desde fuera la pérdida total de ese host.

## 14. TESTS

Resultados locales finales, 22 de octubre de 2026. Las pruebas normales no llaman a B2 ni requieren credenciales reales.

| Validación ejecutada | Resultado |
| --- | --- |
| Backend completo, IA/correo externo desactivados | **313 passed, 9 skipped**, 42,47 s |
| Frontend `node --experimental-strip-types --test tests/*.test.mjs` | **35 passed**, 0 fallos |
| TypeScript `tsc --noEmit --incremental false` | Correcto |
| `tools/production_validate.py --keep`, ejecución final | Correcto: build de imágenes, web de producción y recorrido BFF completo |
| Recuperación PostgreSQL/fotos local + remota simulada | **2 passed**, 2,28 s; hashes correctos y destinos no vacíos rechazados |
| Copia real del stack sintético con B2 inválido y `--local-only` | Correcta, salida 0; no conexión B2 |
| Compose producción, todos los perfiles, B2 desactivado | Correcto |
| Compose + overlay opt-in, B2 activado con destino ficticio; solo configuración | Correcto; no servicios iniciados ni subida |
| `promtool check rules` | **14 reglas válidas** |
| `promtool test rules` | **4 escenarios correctos** |
| `pip-audit` sobre lock API, contenedor sin secretos | Sin vulnerabilidades conocidas |
| `pip-audit` sobre dependencias instaladas del worker CPU | Sin vulnerabilidades conocidas; versiones CPU normalizadas para consultar PyPI, igual que CI |
| `npm audit --omit=dev --audit-level=high` | **0 vulnerabilidades** |
| `git diff --check` | Correcto |
| Búsqueda de prefijos de claves reales en los archivos de la entrega | Sin coincidencias |

Las nueve omisiones corresponden a integración B2 real (1), PostgreSQL analytics/migraciones opt-in (2), inferencia/matching local opt-in (4) y las dos recuperaciones de producción que se ejecutaron aparte y pasaron. No se entrenaron ni descargaron modelos para esta mejora. La verificación inicial y la repetición final de producción pasaron; una repetición intermedia se interrumpió por el salto de reloj explicado en limitaciones.

Cobertura añadida: configuración apagada/activa/incompleta, archivos de secretos, TLS/host/región/bucket, claves seguras, privacidad, retención, transferencia exacta, metadata/tamaño erróneos, no sobrescritura, versión oculta, recibos perdidos/dañados, reinicio, destino cambiado, reintentos, conservación local, fallo SDK saneado, autenticación de descargas, bloqueo de escritor, API/admin sin cliente B2 y aislamiento de secretos Compose. Se prueba también que un fallo de Redis no invalide el backup local y que una verificación fallida no registre éxito.

La integración B2 real es opt-in y **no fue ejecutada**: no hay bucket ni credenciales reales configurados. No se afirma una ejecución de CI remota: solo sus pasos locales y la configuración del workflow, sin commit/push.

## 15. PRODUCTION COMMANDS

Desde el repositorio Linux del VPS:

```sh
python3 tools/production_init.py --prepare-b2-secrets
dc() { docker compose -p mascomatch --env-file .env.production -f compose.production.yml "$@"; }
dc config --quiet
dc build backup
dc run --rm --no-deps backup python -m app.ops.backup check-offsite
dc run --rm --no-deps backup python -m app.ops.backup create /backups
dc run --rm --no-deps backup python -m app.ops.backup list-offsite --retention --limit 20
dc run --rm --no-deps backup python -m app.ops.backup verify-offsite --deep
dc up -d --no-deps backup
```

Primero completar bucket, configuración y secretos de la guía. No introducir claves en estos comandos ni en `.env.production`. Un escritor ocupado devuelve 2: esperar y repetir; fallos reales devuelven 1.

## 16. RESTORE DRILL

```sh
python3 tools/production_validate.py --keep
# Colocar claves exclusivas del bucket de prueba en real-data/production-preview/.secrets/.
# Crear real-data/b2-drill.env con solo endpoint, región y bucket mascomatch-drill-*.
python3 tools/production_validate.py --with-b2 --b2-env-file real-data/b2-drill.env
```

La prueba explícita crea/sube/HEAD/consulta bloqueo/descarga/autentica/restaura y compara filas y fotos, con SMTP en Mailpit y sin puertos públicos. La copia cifrada de prueba permanece protegida en B2 y se imprime su referencia para seguimiento hasta que lifecycle la expire. Los destinos DB/fotos temporales se destruyen; `--keep` conserva el stack para inspección. La prueba normal hace ambas recuperaciones, local y remota simulada, sin servicios cloud.

## 17. RPO / RTO NOTES

RPO objetivo aproximado ≤6 h según captura. No es garantía: duración de procesos, colas, red y caídas pueden ampliarlo. Se supervisa la fecha de captura recuperable. RTO no comprometido hasta medirlo en la infraestructura del propietario: provisión, tamaño, descarga, PostgreSQL, fotos y validaciones. Registrar tiempos en cada simulacro.

## 18. KNOWN LIMITATIONS

- Falta validar conectividad, permisos mínimos, comportamiento Object Lock/lifecycle y recuperación **en Backblaze real**.
- Un único escritor y volumen de backup. No hay precondición S3 atómica entre dos VPS independientes; no desplegar dos escritores contra el mismo espacio de nombres.
- Copias completas cada 6 h: ≈120 archivos por 30 días, alrededor de 128 con lifecycle de 32 días, más retrasos/versiones. Presupuestar almacenamiento, tráfico y solicitudes. Inventario aproximado, sin API de billing.
- Pendientes preservados pueden llenar el volumen durante una caída prolongada; vigilar y ampliar capacidad. Límite de archivo/fotos/tmpfs existente conservado.
- Plazos de transferencia se comprueban entre bloques; una solicitud en curso puede consumir sus timeouts/reintentos. No se promete terminación exacta a los 900 s.
- La comprobación frecuente es HEAD/metadata; la profunda semanal sí descarga/autentica. No se descargan todas las copias en cada ciclo.
- Es necesaria sincronización de reloj. Durante una repetición del smoke se observó una sesión sintética vencida después de un salto del reloj local; se conservó la seguridad de sesiones y el recorrido posterior pasó.
- El stack desechable usado con `--keep` queda disponible para inspección, separado del desarrollo y sin puertos publicados.
- No se implementan HA, réplicas, failover, balanceador ni segundo servidor permanente.

## 19. OWNER ACTIONS REQUIRED

1. Crear cuenta B2 y bucket privado exclusivo; elegir región y copiar nombre/endpoint exactos.
2. Habilitar Object Lock manualmente; default **COMPLIANCE, 30 días**.
3. Guardar lifecycle `backups/`: ocultar día 31, eliminar un día después y cancelar multipart incompleto tras un día.
4. Crear Application Key dedicada restringida al bucket/prefijo, con las capacidades exactas de la guía. Guardar inmediatamente la application key; no se vuelve a mostrar.
5. Preparar los dos archivos `.secrets/b2_*` en el VPS e introducir los valores con un editor privado. Conservar la clave AES original fuera del servidor.
6. Configurar endpoint/región/bucket, 6 h, 14 copias locales, COMPLIANCE 30 días y activar `OFFSITE_BACKUP_ENABLED=true`.
7. Ejecutar `check-offsite`, respaldo manual, listado y verificación profunda; confirmar versión/fecha de bloqueo en B2.
8. Crear bucket/clave separados `mascomatch-drill-*` y ejecutar el simulacro B2 real de la guía; conservar su resultado y medir tiempos.
9. Conectar un receptor externo de alertas y comprobar recepción ante una condición controlada; revisar capacidad y estado en `/admin`.
10. Iniciar/recrear `backup`, comprobar su siguiente captura automática y programar simulacros periódicos. La autorización posterior de commit y push figura al comienzo del informe.

## 20. GO / NO-GO FOR OFF-SITE BACKUP

**GO para revisión y configuración del propietario. NO-GO para declarar el respaldo off-site operativo** hasta completar alta real, permisos, subida, retención observada, verificación profunda, restore real desechable y alertas recibidas. El respaldo local sigue disponible; la integración B2 está desactivada por defecto y no se subieron datos reales.

El estado Git final y los resultados exactos de validación se añaden a continuación. El diff de Git muestra archivos ya rastreados; los archivos nuevos aparecen como `??` en el status y también forman parte de esta entrega sin staging.

**`git status --short` final:**

```text
 M .github/workflows/ci.yml
 M .gitignore
 M apps/api/app/ops/backup.py
 M apps/api/app/ops/release_check.py
 M apps/api/app/routers/admin_operations.py
 M apps/api/app/routers/operations.py
 M apps/api/tests/test_production_apply.py
 M apps/api/tests/test_production_integration.py
 M apps/web/app/admin/operations-dashboard.tsx
 M apps/web/app/globals.css
 M compose.production.yml
 M docs/production.md
 M infrastructure/production/alerts.yml
 M tools/production_apply.py
 M tools/production_init.py
 M tools/production_validate.py
?? apps/api/app/ops/backup_status.py
?? apps/api/app/ops/offsite.py
?? apps/api/tests/test_b2_integration.py
?? apps/api/tests/test_offsite_backup.py
?? apps/web/app/admin/backup-status.tsx
?? compose.b2-smoke.yml
?? docs/backblaze-backup.md
?? docs/backblaze-delivery-report.md
?? infrastructure/production/backup-alerts.test.yml
```

**`git diff --stat` final:**

```text
 .github/workflows/ci.yml                      |   4 +
 .gitignore                                    |   3 +
 apps/api/app/ops/backup.py                    | 154 ++++++++++++++++++++------
 apps/api/app/ops/release_check.py             |   6 +-
 apps/api/app/routers/admin_operations.py      |   2 +
 apps/api/app/routers/operations.py            |   2 +
 apps/api/tests/test_production_apply.py       |   1 +
 apps/api/tests/test_production_integration.py |  17 ++-
 apps/web/app/admin/operations-dashboard.tsx   |   6 +-
 apps/web/app/globals.css                      |   1 +
 compose.production.yml                        |  18 ++-
 docs/production.md                            |  12 +-
 infrastructure/production/alerts.yml          |  29 ++++-
 tools/production_apply.py                     |   8 +-
 tools/production_init.py                      |  35 +++++-
 tools/production_validate.py                  |  24 +++-
 16 files changed, 268 insertions(+), 54 deletions(-)
```

En esta captura previa al commit hay nueve archivos nuevos enumerados en el status, excluidos del contador por no estar staged. Durante la implementación anterior a la autorización no se modificó HEAD ni el índice Git. Los logs de las comprobaciones están en `real-data/b2-*.txt`, ignorados por Git; contienen resultados locales, no credenciales B2 reales.
