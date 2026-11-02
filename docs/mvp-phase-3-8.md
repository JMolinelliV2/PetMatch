# MVP: embeddings, matching, alertas, mapa, feedback y moderación

Este documento conserva la entrega funcional original. Las sesiones, el correo confirmado, los límites compartidos y el despliegue actual se describen en [la preparación para producción](production.md). El sistema visual vigente y las alertas se detallan en [IA productiva](ai-production.md); los resultados históricos de este archivo no son los de la versión actual.

Entrega del 8 de octubre de 2026. El dominio `mascomatch.com` fue adquirido por el usuario; DNS, correo externo, despliegue y refuerzo de producción se configuran después del plan funcional.

## Funciones

- Los avistamientos generales y mascotas encontradas buscan automáticamente avisos activos compatibles, aunque no tengan foto. También se reconsideran al publicar o editar un aviso y al completar el procesamiento de evidencia.
- Las características declaradas de especie, sexo, color y tamaño se conservan. El texto original no se sustituye por la salida de IA.
- Las fotos generan vectores visuales locales; se combinan con características, ubicación y fecha. Los resultados tienen motivos legibles y una puntuación de compatibilidad que **no es una probabilidad de identidad**.
- La pantalla de confirmación de un avistamiento muestra candidatos ordenados. Los avistamientos enviados desde un aviso siguen utilizando su formulario breve.
- El dueño recibe alertas privadas y puede responder «podría ser», «no es» o «confirmado». El feedback se conserva al recalcular y evita nuevas alertas para coincidencias descartadas. Confirmar una coincidencia no cierra automáticamente el aviso.
- La revisión distingue **Es mi mascota, sigo buscándola** de **Ya la recuperé**. La primera confirma el avistamiento y conserva la búsqueda activa. La segunda guarda la coincidencia y cambia el aviso a `FOUND` en una transacción, desactiva sus coincidencias y notificaciones y cancela los correos pendientes. Está disponible en Notificaciones y Mis avisos; el estado se actualiza al guardar. Confirmaciones anteriores conservan su significado de identidad, sin marcar recuperaciones que el dueño no indicó.
- **Mis avisos** permite consultar publicaciones, editar datos de la mascota, descripción, fecha y ubicación, agregar fotos, ver coincidencias, cerrar/reabrir una búsqueda y marcar a la mascota como encontrada.
- **Mapa** separa perdidos, avistamientos y encontrados. Filtra especie, fecha, distancia a una referencia del dispositivo y reportes con coincidencias. Las coordenadas públicas se redondean; hay alternativa en una lista.
- **Denunciar publicación** registra motivos y detalles. Administradores pueden revisar la evidencia, ocultar/restaurar publicaciones, descartar denuncias, bloquear/reactivar cuentas, consultar registros y fallos de IA y corregir descripciones. Las correcciones conservan la descripción anterior en auditoría privada.
- El correo agrupa los reportes pendientes de un mismo dueño y aviso. La espera inicial predeterminada es 15 segundos, más el intervalo de despacho, para agrupar avisos próximos en el tiempo. Las alertas internas se crean inmediatamente al completar la comparación.
- Los reportes generales pueden compartir el correo del autor **solo con consentimiento explícito**, únicamente en alertas privadas de los dueños relevantes. Por defecto está desactivado. No se agrega contacto público ni al input de IA.

## Modelo visual local

La versión actual usa Pet-ReID 512D para perros/gatos y OpenCLIP `ViT-B-32/openai` 512D como alternativa explícita para perros/gatos si se deshabilita Pet-ReID. No admite otras especies. Vectores normalizados, CPU y dos hilos por defecto. No utiliza claves, API pagas ni inferencia remota. El worker visual tiene una imagen separada para que la API no cargue PyTorch.

Los pesos se descargan explícitamente desde revisiones fijadas y se verifican por SHA-256. OpenCLIP se instala directamente en Safetensors y Pet-ReID/detector en ONNX, sin pickle ni conversión de código remoto. El volumen `vision_models` conserva aproximadamente 1 GB de pesos visuales. Ver [modelos y licencias](third-party-models.md).

La representación de una foto entera puede reflejar el fondo, iluminación o pose. No es reconocimiento biométrico de una mascota. [OpenCLIP](https://github.com/mlfoundations/open_clip), [pgvector Python](https://github.com/pgvector/pgvector-python).

### Instalación nueva

```powershell
docker compose --profile ai-local build worker
docker compose --profile ai-local run --rm --no-deps --user 0 worker python -m app.embeddings.setup
```

Después configurar `EMBEDDINGS_ENABLED=true` en `.env`:

```powershell
docker compose --profile ai-local up -d api worker
docker compose run --rm --no-deps worker python -m app.embeddings.backfill
```

El backfill registra las fotos existentes para procesamiento, sin volver a subirlas. Los análisis visuales tienen estado, deduplicación, reintentos y validación de vigencia. Cambiar o eliminar evidencia invalida resultados antiguos. El endpoint privado `/embeddings/{owner_type}/{owner_id}` muestra estado y errores, sin publicar vectores.

## Ranking

Primero se restringen candidatos por especie, estado activo/visible, fecha y área. PostgreSQL utiliza PostGIS; las pruebas SQLite tienen un equivalente de distancia. El radio del aviso es configurable y tiene un límite global de 50 km por defecto, con tolerancia acotada para precisión GPS.

Características: especie 0,15; color principal 0,18; secundarios 0,08; tamaño 0,10; pelaje 0,07; patrón 0,10; rasgos distintivos 0,25; accesorios 0,05; tipo/raza 0,02. Especie o sexo declarados incompatibles descartan el candidato. Se exige información compartida suficiente; una especie aislada no produce un match.

Sin comparación visual: características 0,50 + geografía 0,30 + tiempo 0,20. Con comparación visual: visual 0,45 + características 0,25 + geografía 0,20 + tiempo 0,10. La distancia y el tiempo usan funciones suaves; la compatibilidad temporal mantiene un piso para casos antiguos.

La similitud coseno se transforma con límites configurables, y solo se comparan vectores del mismo modelo, dimensión y versión, con evidencia vigente. pgvector usa distancia coseno y un índice HNSW; los candidatos están restringidos geográfica y temporalmente antes de evaluar. Los umbrales iniciales son 0,55 para mostrar un candidato y 0,82 para una alerta automática. **Son reglas iniciales pendientes de calibración con datos reales.**

## API agregada

| Ruta | Acceso / función |
| --- | --- |
| GET `/matches/observations/{id}` | Autor del reporte; candidatos con información pública de la mascota |
| GET `/matches/lost-cases/{id}` | Dueño del aviso; evidencia y feedback |
| PATCH `/matches/{id}/feedback` | Dueño del aviso; confirmar, descartar o resolver |
| GET / POST `/embeddings/{owner_type}/{id}` | Dueño del reporte; estado / procesamiento |
| GET `/me/dashboard` | Cuenta propia; mascotas, casos y reportes |
| PATCH `/me/cases/{id}` | Cuenta propia; actualización atómica de mascota y aviso |
| GET `/public/map` | Público; coordenadas aproximadas y campos limitados |
| POST `/reports` | Visitante o cuenta; denuncia |
| GET / PATCH `/admin/reports` | Administrador; revisión y acciones |
| GET `/admin/overview` y `/admin/records/{kind}` | Administrador; registros, fallos y auditoría |
| PATCH `/admin/publications/{kind}/{id}` | Administrador; corrección con copia de evidencia previa |
| PATCH `/admin/users/{id}/status` | Administrador; bloquear/reactivar |

La web utiliza proxies con rutas permitidas, comprobación de origen y cargas limitadas; las credenciales permanecen en el servidor. La API verifica autorización aunque se acceda directamente.

## Administrador local

No existe una cuenta ni contraseña administrativa predeterminada. El operador reserva el acceso para una única cuenta mediante un comando privado, incluso antes de que se registre:

```powershell
docker compose exec api python -m app.admin
```

El comando pide el correo por entrada interactiva y no lo agrega al historial de comandos. Si la cuenta aún no existe o no confirmó su correo, se reserva el acceso; se activa al confirmar esa dirección. Luego ingresar en `/admin`, también accesible desde Mi cuenta para la cuenta autorizada. El rol por sí solo no habilita acceso: la API exige la asignación única y el correo confirmado. Una cuenta normal no puede reservar ni transferir la administración mediante el registro o una petición pública. Ver [seguimiento y acceso exclusivo](admin-matching.md).

## Configuración nueva

Ver `.env.example`: `EMBEDDINGS_ENABLED`, `EMBEDDING_CPU_THREADS`, `MATCHING_CANDIDATE_THRESHOLD`, `MATCHING_NOTIFY_THRESHOLD`, `MATCHING_MAX_RADIUS_METERS`, `MATCHING_TEMPORAL_DAYS`, `MATCHING_VISUAL_FLOOR`, `MATCHING_VISUAL_CEILING`, `MAIL_GROUP_SECONDS`, `RATE_LIMIT_ENABLED`, `RATE_LIMIT_AUTH`, `RATE_LIMIT_PUBLISH`, `RATE_LIMIT_READ`.

Hay límites básicos por proceso, cuenta autenticada o dirección de conexión, en ventanas de 60 segundos. No se confía en cabeceras de IP reenviadas. La configuración distribuida y de proxies pertenece a la etapa de producción.

Migraciones `0006` a `0011`: vectores y matches, alertas por pareja aviso/reporte, características declaradas, permisos y moderación, auditoría de correcciones, índice espacial y consentimiento privado de contacto. El inicio aplica `alembic upgrade head`, conservando los datos existentes.

## Pruebas y evaluación

```powershell
docker compose exec -T api python -m pytest -q -p no:cacheprovider
docker compose exec -T api python -m app.matching.evaluate test-data/matching/fixtures.json
docker compose cp ./apps/web/public/images/dog-hero-generated.jpg worker:/tmp/matching-check-dog.jpg
docker compose exec -T -e RUN_MATCHING_INTEGRATION=1 -e AI_SMOKE_IMAGE_PATH=/tmp/matching-check-dog.jpg worker python -m pytest tests/test_matching_integration.py -q -s -p no:cacheprovider
```

La integración crea todas las tablas explícitamente en un esquema PostgreSQL temporal y verifica el aislamiento antes de guardar evidencia. Usa una cola propia, MinIO y CLIP real; elimina solo sus objetos, cola y esquema al terminar. Comprueba pgvector, PostGIS, fotos transformadas del mismo ejemplo y matching sin foto. No envía correo externo ni modifica avisos reales. El coseno de la prueba de foto original/espejada fue 0,9929; esto valida el recorrido técnico, no precisión de identificación.

`test-data/matching/fixtures.json` incluye doce escenarios **sintéticos**, con similitudes visuales simuladas: texto sin foto, señales visuales, animales parecidos, especies distintas, distancia, fecha e información insuficiente. El evaluador informa Precision@1, Precision@5 y Recall@5 sobre consultas con candidatos relevantes conocidos; mide falsos positivos por separado en consultas negativas. Precision@5 usa cinco posiciones, incluyendo posiciones vacías como no relevantes. Esos números no se deben presentar como precisión de CLIP ni del sistema con usuarios reales.

## Comprobación de esta entrega

- API: 131 pruebas aprobadas; tres integraciones opcionales omitidas en la ejecución normal.
- Frontend: 22 pruebas aprobadas, comprobación de tipos y compilación de producción en Docker correctas.
- Integración real de CLIP, Redis, MinIO, PostGIS y pgvector: aprobada con esquema y cola aislados.
- Integración de avistamiento vinculado, Gemma local, fotos privadas y correo SMTP: aprobada; dos alertas del mismo aviso se agruparon en un correo capturado por Mailpit. No se enviaron correos externos.
- Revisión visual con cuentas y publicaciones sintéticas: filtros del mapa, edición de avisos, motivos de coincidencia, respuesta del dueño y ocultación/restauración con auditoría.
- Datos temporales retirados; los dos avisos reales y su foto se conservaron. El SMTP externo permanece desactivado.

## Pendiente después del plan funcional

- Configurar el dominio comprado, DNS, HTTPS y alojamiento permanente.
- Activar el SMTP externo y comprobar entrega con una cuenta/remitente válidos. La instalación mantiene `MAIL_DELIVERY_MODE=disabled`.
- Configurar el administrador real mediante el comando local.
- Evaluar fotos y reportes reales con identidad conocida, ajustar umbrales y medir falsos positivos.
- Revisar secretos, copias de seguridad, recuperación, monitoreo, despliegue, sesiones y límites distribuidos antes de abrirlo al público.
- Push, SMS, WhatsApp, trayectoria y aplicaciones nativas pertenecen a etapas posteriores.
