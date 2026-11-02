# MascoMatch

Repositorio: [JMolinelliV2/MascoMatch](https://github.com/JMolinelliV2/MascoMatch).

Para entender el proyecto: [qué hace cada tecnología y cómo funciona un aviso](docs/architecture.md).

Medición propia del producto, coincidencias e impacto: [definiciones de analytics](docs/analytics.md), [diseño del panel](docs/analytics-design.md) e [informe de validación](docs/analytics-delivery-report.md).

Mi cuenta permite [editar contacto, confirmar un nuevo correo y eliminar la cuenta conservando los avistamientos](docs/account-management.md).

Cada publicación tiene un [ID público único y permanente](docs/publication-identifiers.md), visible y copiable, como `MM-000123`.

El [panel privado de administración](docs/admin-matching.md) permite seguir recomendaciones confirmadas, falsas, dudosas y sin respuesta, con acceso reservado a una única cuenta verificada.

La marca también identifica la API, los correos, el paquete web, las sesiones y la cola de IA. Los nombres locales por defecto son `mascomatch` para PostgreSQL y MinIO, `mascomatch-analysis` para la cola y `mascomatch_session` para la cookie de sesión. Al actualizar una instalación con datos, cambiar las variables de Compose no renombra la base ni el usuario de PostgreSQL: hay que migrar sus nombres conservando el volumen, ajustar `.env` y reiniciar los servicios. El cambio de cookie requiere iniciar sesión nuevamente.

Plataforma web y API mobile-first para relacionar mascotas perdidas con observaciones de la comunidad. Incluye publicaciones, extracción de características con IA local, embeddings visuales, ranking de posibles coincidencias, alertas privadas, correo SMTP agrupado, mapa, panel del dueño, feedback y moderación básica. [Estado del MVP, decisiones, pruebas y configuración](docs/mvp-phase-3-8.md).

## Preparación para producción

Ver [despliegue, sesiones, correo, respaldos y monitoreo](docs/production.md). La configuración de servidor es independiente de la instalación local y no publica el dominio automáticamente.

## Requisitos

- Docker Desktop con Docker Compose v2.
- Puertos locales disponibles: 3000, 5432, 6379, 8000, 9000 y 9001.

## Levantar el proyecto

En PowerShell:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Para crear cuentas, configurá SMTP en `.env` para enviar el correo de confirmación. Para usar un buzón local en desarrollo, elegí `MAIL_DELIVERY_MODE=preview`, `SMTP_HOST=mailpit`, `SMTP_PORT=1025` y credenciales SMTP vacías; levantá el proyecto con `docker compose --profile mail-local up --build`. Abrí el enlace de confirmación desde `http://localhost:8025` antes de publicar desde la cuenta. [Configuración del correo](docs/production.md).

El frontend de desarrollo en Docker comprueba cambios de archivos cada segundo para actualizar la vista también en Windows/OneDrive, donde las notificaciones del sistema de archivos pueden no llegar al contenedor. Esta configuración no afecta el servidor de producción.

La primera construcción instala PostGIS y pgvector sobre la imagen oficial `postgres:17-bookworm`, compila MinIO desde su código fuente e instala las dependencias de la aplicación. Puede tardar unos minutos. MinIO usa la versión fija `RELEASE.2025-10-15T17-29-55Z`, sin depender de la imagen retirada de Docker Hub. La API aplica la migración inicial antes de arrancar.

- Web: http://localhost:3000
- API y OpenAPI: http://localhost:8000/api/v1/docs
- Health check: http://localhost:8000/health
- MinIO console: http://localhost:9001
- Redis: localhost:6379
- PostgreSQL: localhost:5432

Para bajar los servicios, conservando datos:

```powershell
docker compose down
```

Para borrar también los volúmenes locales (elimina los datos):

```powershell
docker compose down -v
```

## API inicial

Rutas bajo `/api/v1`:

- `POST /auth/register`, `POST /auth/login`, `GET /auth/me`
- `GET|POST /pets`, `GET|PATCH|DELETE /pets/{id}`
- `GET|POST /lost-cases`, `GET|PATCH|DELETE /lost-cases/{id}`
- `GET|POST /observations`, `GET|PATCH|DELETE /observations/{id}`
- `POST /photos/upload` (valida, limpia EXIF, reduce y almacena una imagen privada; máximo 10 MB)
- `GET|POST /photos`, `GET /photos/{id}/url`, `PATCH|DELETE /photos/{id}`

Las rutas de escritura, las fotos, los análisis y los datos privados de mascotas/casos requieren bearer token. Los avistamientos vinculados a un aviso admiten visitantes. Las observaciones públicas omiten contactos y redondean coordenadas; las precisas se usan internamente para matching y en alertas privadas del dueño. Las fotos se guardan privadas en MinIO. PostGIS y pgvector están habilitados, y hay límites básicos de solicitudes por proceso.

## IA local: Pet-ReID, OpenCLIP y Gemma

MascoMatch admite únicamente perros y gatos, que usan Pet-ReID 512D con detector local. OpenCLIP 512D queda como alternativa explícita para esas mismas especies si se deshabilita Pet-ReID. Gemma 3 4B extrae atributos. El matching combina señales compatibles, características, ubicación y fecha. No usa APIs pagas de IA.

Ver [alcance de perros/gatos y tratamiento de registros históricos](docs/dog-cat-scope.md).

[Arquitectura y operación](docs/ai-production.md) · [Licencias y revisiones](docs/third-party-models.md) · [Informe de entrega y mediciones](docs/ai-delivery-report.md) · [Despliegue](docs/production.md).

En desarrollo, construir el worker e instalar explícitamente los modelos en los volúmenes existentes. El comando Gemma requiere haber leído y aceptado sus términos:

```powershell
docker compose --profile ai-local build worker worker-ai
docker compose --profile ai-local run --rm --no-deps --user 0 worker python -m app.embeddings.setup
docker compose --profile ai-local run --rm --no-deps --user 0 -v buscadormascotas_ollama_models:/ollama worker python -m app.analysis.gemma_setup --accept-gemma-terms
```

El nombre de volumen del último ejemplo corresponde a la carpeta local `buscadorMascotas`; usar el volumen Ollama del proyecto si se cambió el nombre. Después activar `AI_ENABLED=true` y `EMBEDDINGS_ENABLED=true` en `.env`, recrear API/workers y programar faltantes:

```powershell
docker compose --profile ai-local up -d api worker worker-ai web
docker compose --profile ai-local run --rm --no-deps worker python -m app.embeddings.backfill
docker compose --profile ai-local run --rm --no-deps worker-ai python -m app.analysis.backfill
```

Ollama permanece en la red privada y con `OLLAMA_NO_CLOUD=1`. No se descargan pesos durante requests. `AI_ENABLED=false` pausa extracción semántica; `EMBEDDINGS_ENABLED=false` pausa embeddings; `PET_REID_ENABLED=false` conserva OpenCLIP como fallback. La API y publicación no necesitan cargar los modelos.

### Funcionamiento

1. Crear o editar un caso o una observación guarda un trabajo de texto dentro de la misma transacción de base de datos. Cambiar características de una mascota actualiza el análisis de sus casos. Crear una mascota con campos ya estructurados no hace una consulta redundante al modelo.
2. Subir una foto guarda un trabajo de imagen. La request no llama al modelo.
3. Un despachador de la API entrega trabajos pendientes a Redis/RQ. Si Redis falla, el trabajo queda en la base y se retoma después.
4. El worker consulta Ollama, valida el JSON y guarda un `FeatureSet` privado con valor, confianza y origen de cada atributo.
5. Al guardar un reporte, la web consulta el estado y muestra características sugeridas separadas por descripción y foto. La descripción original y los datos declarados se conservan.

Los prompts están versionados. Datos faltantes o ambiguos usan `unknown`, `not_visible` o `uncertain`, con confianza cero. La confianza es una valoración no calibrada del atributo, no una probabilidad de identificar una mascota. El matching posterior revisa esas características junto con las demás señales y aplica los controles de alerta documentados.

Gemma recibe imágenes de hasta 1024 píxeles, sin EXIF, y campos físicos; los modelos de embeddings usan su propio preprocessing. No se agregan nombres, contactos, microchips ni coordenadas a los inputs de IA. Si una persona escribe esos datos dentro de la descripción, forman parte de su texto original; el prompt indica ignorarlos para extraer características físicas. Los resultados y trabajos solamente son accesibles por el dueño del reporte.

Se deduplican trabajos por propietario, evidencia, modelo y versión de prompt. Hay hasta tres intentos por defecto, con espera entre fallos transitorios. Un modelo inexistente falla sin reintentos automáticos. Las ejecuciones interrumpidas se recuperan mediante leases; versiones antiguas de un trabajo no pueden sobrescribir una ejecución nueva. Las descripciones modificadas invalidan resultados anteriores y las eliminaciones borran los análisis relacionados. Los jobs usan serialización JSON, y sus logs incluyen IDs, estado, modelo y latencia, sin cuerpos de texto o imágenes.

### API de análisis

Siempre con `Authorization: Bearer <token>`:

| Método | Ruta | Uso |
| --- | --- | --- |
| GET | `/api/v1/analysis/{owner_type}/{owner_id}` | Estado y características vigentes |
| POST | `/api/v1/analysis/{owner_type}/{owner_id}` | Analizar evidencia existente; reutiliza trabajos ya creados |
| GET | `/api/v1/analysis/jobs/{job_id}` | Consultar un trabajo propio |
| POST | `/api/v1/analysis/jobs/{job_id}/retry` | Reintentar un fallo tras una espera mínima de 60 segundos |

`owner_type`: `pet`, `lost_case` u `observation`. Estados: `PENDING`, `DISPATCHING`, `QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED`, `STALE`. Las respuestas omiten snapshots de entrada y solo incluyen características vigentes. No incluyen embeddings.

### Variables de IA

| Variable | Valor por defecto en Compose | Función |
| --- | --- | --- |
| `AI_ENABLED` | `false` | Activa generación y despacho de análisis |
| `AI_TEXT_MODEL` | `gemma3:4b` | Modelo local para descripciones |
| `AI_VISION_MODEL` | `gemma3:4b` | Modelo local para fotos |
| `OLLAMA_BASE_URL` | `http://ollama:11434` | Servidor local en la red de Docker |
| `REDIS_URL` | `redis://redis:6379/0` | Cola de trabajos |
| `AI_TEXT_REQUEST_TIMEOUT_SECONDS` / `AI_VISION_REQUEST_TIMEOUT_SECONDS` | `120` / `240` | Límites separados de texto e imagen |
| `AI_MAX_ATTEMPTS` | `3` | Máximo de intentos automáticos, entre 1 y 5 |
| `AI_DISPATCH_INTERVAL_SECONDS` | `5` | Intervalo del despachador |

Para ejecutar la API o el worker fuera de Docker, usar `OLLAMA_BASE_URL=http://localhost:11434` y `REDIS_URL=redis://localhost:6379/0`, con Ollama en modo local. Un equipo lento puede requerir aumentar el timeout. Los cambios de variables requieren recrear los servicios con `docker compose --profile ai-local up -d`.

Referencias: [API de Ollama](https://docs.ollama.com/api/chat), [salidas estructuradas](https://ollama.com/blog/structured-outputs), [modo local](https://docs.ollama.com/faq), [modelo](https://ollama.com/library/gemma3:4b), [RQ](https://python-rq.org/docs/).

### Certificados de antivirus o proxy

Si la descarga falla con `x509: certificate signed by unknown authority` y Windows valida la conexión mediante el certificado de un antivirus o proxy, se puede incorporar esa autoridad pública al contenedor. Exportá únicamente el certificado de la autoridad que tu equipo ya confía, en formato PEM, a un archivo `.crt`:

```powershell
docker compose exec ollama mkdir -p /root/.ollama/certificates
docker compose cp ./mi-certificado.crt ollama:/root/.ollama/certificates/network-ca.crt
docker compose restart ollama
```

El directorio se conserva en el volumen de modelos. `SSL_CERT_DIR` agrega esos certificados al directorio del sistema dentro de Ollama; se mantiene la validación HTTPS. Los certificados del equipo no se incluyen en el repositorio. [Configuración de certificados de Go](https://pkg.go.dev/crypto/x509#SystemCertPool).

Los instaladores fijados actuales descargan mediante Python en el worker. Si esa conexión también necesita la autoridad corporativa, montar el certificado público de confianza únicamente durante la instalación:

```powershell
docker compose run --rm --no-deps --user 0 -e SSL_CERT_FILE=/trust/network-ca.crt -v "${PWD}/mi-certificado.crt:/trust/network-ca.crt:ro" worker python -m app.embeddings.setup
```

Aplicar el mismo montaje y variable al comando de `app.analysis.gemma_setup` cuando corresponda. No desactivar la validación TLS ni exportar una clave privada. En un VPS sin esa inspección de tráfico se utiliza el almacén normal de autoridades del contenedor.

## Pruebas de API

Con Python 3.12 o superior:

```powershell
cd apps/api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.lock
pytest
```

Los tests usan SQLite temporal y no requieren Docker ni servicios externos. La fase de extracción tiene pruebas de esquema, permisos, idempotencia, actualización de evidencia, reintentos, recuperación de workers, fallos de Redis, contratos HTTP de Ollama y migraciones desde una base nueva y desde el esquema inicial. Los proveedores de IA y la cola se simulan en estas pruebas; esto no mide la calidad real del modelo ni sustituye una prueba de Docker/PostgreSQL.

La prueba opcional de integración ejecuta un worker RQ real y consulta el modelo local. Usa una base SQLite separada y una cola con nombre único, que elimina al terminar; no modifica los reportes existentes. Requiere el perfil `ai-local`, modelos instalados y la imagen de worker actual:

```powershell
docker compose run --rm --no-deps -e RUN_LOCAL_AI_TESTS=1 -e AI_ENABLED=true -e MAIL_DELIVERY_MODE=disabled worker python -m pytest tests/test_local_ai_integration.py -q
```

Para incluir la fotografía de ejemplo de la portada:

```powershell
docker compose run --rm --no-deps -e RUN_LOCAL_AI_TESTS=1 -e AI_ENABLED=true -e MAIL_DELIVERY_MODE=disabled -e AI_SMOKE_IMAGE_PATH=/fixtures/dog-hero-generated.jpg -v "${PWD}/apps/web/public/images:/fixtures:ro" worker python -m pytest tests/test_local_ai_integration.py -q
```

Estas comprobaciones validan el recorrido y dos ejemplos de extracción; no son una evaluación de precisión del matching.

## Variables de entorno

Copiar `.env.example` a `.env` antes de ejecutar Compose. Cambiar contraseñas y `JWT_SECRET` para entornos compartidos. La configuración de producción, TLS, S3 privado y secretos está en `compose.production.yml` y `docs/production.md`.

## Ubicación en los formularios

**Ver en mapa** despliega un mapa de 300 px dentro del mismo formulario. Permite arrastrar el pin, tocar otro punto o mover el pin con las flechas del teclado. El punto nuevo se guarda inmediatamente y se consulta su dirección; si esa consulta falla, conserva el punto elegido sin usar la dirección ni la precisión GPS anterior. El mapa usa Leaflet 1.9.4 y las teselas HTTPS de OpenStreetMap, sin clave de API. Referencias: [Leaflet](https://leafletjs.com/) y [política de teselas](https://operations.osmfoundation.org/policies/tiles/).

La portada presenta una fotografía y tres acciones: mascota perdida, avistamiento y mascota encontrada. Los formularios se completan en tres etapas: **Mascota**, **Fecha y lugar**, y **Contacto y revisión**. Se valida cada etapa al continuar; el botón Atrás conserva los datos y la foto seleccionada. La última etapa muestra un resumen editable antes de crear la cuenta o ingresar y guardar el reporte. Las fotos son opcionales.

**Crear cuenta** tiene una página independiente en `/crear-cuenta`, accesible desde el encabezado, el menú móvil y los formularios de ingreso. Pide nombre o apodo, correo y contraseña con confirmación, e inicia la sesión al guardar. Envía automáticamente el correo de confirmación: antes de publicar o modificar avisos, subir fotos o solicitar análisis desde la cuenta, hay que confirmar el enlace de un solo uso que vence a las 24 horas. Los formularios de publicación reconocen esa sesión, conservan los datos y la foto mientras se confirma en otra pestaña y permiten cambiar de cuenta. Las cuentas existentes que todavía no confirmaron su correo pueden reenviar el enlace desde su cuenta; sus avisos se conservan y pueden cerrarse o marcarse encontrados.

**Ingresar** abre `/login`, una página independiente que comparte el diseño y la disposición del registro. Pide correo y contraseña, ofrece enlaces para crear una cuenta o recuperar el acceso y, al ingresar correctamente, abre Mis avisos si el correo está confirmado o `/confirmar-correo` si está pendiente. Los enlaces de ingreso desde el registro y la recuperación también llevan a esta página. Cuando ya hay una sesión iniciada, el encabezado muestra **Mi cuenta** y lleva directamente a Mis avisos.

Las opciones **Mis avisos** en la navegación y **Notificaciones** en el encabezado solo aparecen cuando hay una sesión iniciada, tanto en escritorio como en móvil. Se actualizan al ingresar, crear una cuenta o cerrar la sesión.

El primer paso incluye **Sexo**: Macho, Hembra o No lo sé (valor predeterminado). Se guarda como dato declarado en mascotas, avistamientos y mascotas encontradas, aparece en la revisión y, si es conocido, en las tarjetas de mascotas perdidas. La ficha individual muestra también cuando no está indicado. La migración `0004_observation_sex` conserva los avistamientos existentes con valor `unknown`. La IA no infiere el sexo a partir de fotografías.

El lugar se elige buscando una dirección, barrio o punto de referencia, o con el GPS del dispositivo. Los resultados deben seleccionarse para guardar su ubicación; escribir un texto sin elegir un resultado no asigna coordenadas. El GPS se solicita únicamente al tocar el botón y conserva la precisión que informa el dispositivo. Funciona en `localhost` o con HTTPS y requiere permiso del navegador.

La búsqueda usa Photon con datos de OpenStreetMap. `GEOCODER_BASE_URL` permite cambiar el servidor compatible; por defecto se usa `https://photon.komoot.io`, un servicio público de demostración que necesita conexión a Internet y no ofrece disponibilidad garantizada. Para un despliegue público con tráfico, configurar una instancia propia o un proveedor con capacidad contratada. Las direcciones se consultan desde la web a través de `/api/places`; las publicaciones conservan las coordenadas internas y solo agregan la localidad al texto, sin insertar automáticamente la dirección exacta.

Las sugerencias se restringen al país de la persona, determinado con una consulta inversa de la ubicación del dispositivo. Si no hay permiso o no se puede obtener esa referencia, se usa `NEXT_PUBLIC_SEARCH_COUNTRY` (por defecto `UY`, Uruguay), sin presentar ese valor como una ubicación detectada. El botón **Priorizar cerca de mí** solicita el permiso para ordenar las sugerencias sin seleccionar automáticamente el lugar del reporte. Si el navegador ya tiene permiso, se obtiene esa referencia al abrir el formulario. La ubicación elegida para el reporte y la referencia de la persona son independientes.

La consulta al proveedor usa `countrycode` y sesgo geográfico; el servidor vuelve a filtrar por país y ordena coincidencias exactas antes que coincidencias parciales, y dentro de cada grupo por distancia cuando existe una referencia del dispositivo. Los términos genéricos como “plaza” priorizan la cercanía. Se combina una búsqueda cercana con otra dentro del mismo país para recuperar coincidencias exactas lejanas. Nunca se amplía automáticamente la búsqueda a otros países si no hay resultados.

Validar frontend desde `apps/web`: `npm test`, `npm run typecheck` y `npm run build`.

## Diseño del frontend

La portada, los formularios, el catálogo y Mis avisos comparten la paleta de MascoMatch, controles accesibles y componentes de fotos, etapas y compatibilidad. El diseño conserva los tres pasos generales y el avistamiento breve sin cuenta desde una ficha. [Decisiones de diseño y verificación de los flujos](docs/frontend-redesign.md).

## Apoyanos: aportes voluntarios

La página pública `/apoyanos` se abre desde el botón **Apoyanos**, siempre visible en el encabezado, y desde un bloque de la portada. Presenta cuatro niveles de aporte voluntario en pesos uruguayos: Amigo ($U 100), Colaborador ($U 300), Aliado ($U 600) e Impulsor ($U 1.200), con aporte puntual y monto personalizado; los mensuales quedan deshabilitados.

Los aportes puntuales están integrados con Checkout Pro de Mercado Pago mediante Orders API: creación desde el servidor, retorno, confirmación autenticada, cola de reintentos y panel privado de aportes. La integración comienza desactivada hasta configurar credenciales y probar el circuito. Publicar avisos y reportar avistamientos sigue siendo gratuito. [Alcance de los aportes](docs/donations.md) y [configuración paso a paso de Mercado Pago](docs/mercado-pago-configuracion.md).

## Avisos de pérdida sin fotos

Al intentar avanzar desde **Mascota** sin foto, el formulario explica que una imagen clara facilita reconocerla y puede mejorar las posibilidades de encontrarla. Ofrece **Agregar una foto** y permite **Continuar sin foto**; no agrega una etapa ni obliga a subir imágenes.

Al publicar un nuevo aviso sin fotos, se programa un recordatorio por correo para 30 minutos después (`PHOTO_REMINDER_DELAY_MINUTES`). Antes de enviarlo, se comprueba que siga activo, visible y sin fotos del aviso o de la mascota; también se comprueba la cuenta y su preferencia de correo. El mensaje usa logo y botón centrado para abrir la carga de fotos del aviso en Mis avisos. [Programación y alcance](docs/photo-reminders.md).

## Reseñas de la comunidad

Al cerrar un aviso de pérdida o marcar a la mascota como encontrada, se ofrece dejar una reseña opcional. También se solicita después de **Ya la recuperé** desde una notificación. El aviso se actualiza antes de pedirla; no es necesario escribir una reseña para cerrar la búsqueda.

La portada muestra hasta seis reseñas recientes con puntuación, comentario y nombre público elegido, o **Anónimo** si se deja vacío. Cuando no hay reseñas visibles, la sección no se renderiza. Se requiere ser dueño del aviso y tener correo confirmado, se admite una reseña por aviso y se solicita autorización explícita para publicarla. El autor puede retirarla desde Mis avisos; administración permite ocultar o restaurar reseñas que el autor no haya retirado. [Flujo y alcance](docs/community-reviews.md).

## Mascotas publicadas como perdidas

El inicio incluye un mapa interactivo de avisos de pérdida activos con ubicación aproximada, de todas las fechas. Tanto allí como en `/mapa`, las mascotas perdidas aparecen en círculos con su foto real; sin foto o si falla su carga, muestran una huella. Pasar el mouse abre la miniatura con foto, características y **Ver aviso**. Se puede mover el mouse hasta la tarjeta; al salir se cierra, mientras que pulsar o activar el marcador con Enter o Espacio la mantiene abierta. En pantallas táctiles se abre tocando el círculo. Si varios avisos comparten una zona, el círculo muestra una cantidad y la tarjeta permite elegir cuál consultar. Desde esa ficha, **Volver al mapa del inicio** regresa a la sección de la portada. **Abrir mapa completo** conserva las capas y filtros; avistamientos y encontrados mantienen sus puntos de color.

En `/mapa`, **Ver reportes en una lista** muestra tarjetas con miniatura, tipo, mascota, zona y fecha. Los avisos perdidos reutilizan la foto pública y enlazan a su ficha con regreso al mapa. Los reportes sin miniatura pública muestran un ícono; no se consultan fotos privadas de avistamientos ni se amplían sus permisos. La lista sigue las capas y filtros seleccionados, con el límite existente de 100 reportes, y se adapta a una columna en tablet y móvil.

Desde una ficha, **Publicar un avistamiento** abre un formulario vinculado que pide ubicación y fotos opcionales, con hora actual o fecha aproximada. Se puede enviar sin crear una cuenta. El dueño recibe una alerta privada de posible avistamiento, con mapa y fotos, y puede habilitar correo SMTP. La comparación usa características de las fotos, fecha y zona; los reportes sin foto o inconclusos se identifican como por confirmar. [Implementación, pruebas y configuración de Brevo Free](docs/linked-sightings.md).

En **Mascotas perdidas** (`/perdidos`), disponible desde la navegación y la portada, cualquier visitante puede consultar las mascotas de cualquier especie con aviso `ACTIVE`, buscar por nombre, zona o descripción y abrir una ficha individual. Se muestran hasta 24 avisos por página. Las fotos son opcionales; si no hay foto o no se puede cargar, se muestra un marcador de ausencia.

Los avisos incluyen nombre de la mascota, características declaradas, descripción, fecha y localidad. La API pública usa una lista explícita de campos; omite datos de cuenta, microchip y coordenadas exactas. Las fotos siguen en el bucket privado y se sirven mediante una ruta que comprueba que el aviso continúa activo y visible. Al marcarlo `FOUND`, `CLOSED` o `CANCELLED`, eliminarlo u ocultarlo por moderación, deja de estar disponible públicamente. El matching general y las alertas se documentan en la entrega de fases 3–8.

Rutas sin autenticación:

| Método | Ruta | Uso |
| --- | --- | --- |
| GET | `/api/v1/public/lost-animals?q=&limit=24&offset=0` | Listado y búsqueda, máximo 48 por consulta |
| GET | `/api/v1/public/lost-animals/{case_id}` | Ficha de una mascota que sigue perdida |
| GET | `/api/v1/public/lost-animals/{case_id}/photo` | Foto del aviso o de su mascota, limpia y sin metadata EXIF |

La migración `0003_public_lost_dogs` agrega `public_location` a los avisos. La web envía solo la localidad en ese campo; los avisos anteriores usan la línea `Zona:` que ya guardaba el formulario. Las coordenadas internas se conservan para el futuro matching.

Para actualizar servicios existentes:

```powershell
docker compose restart api web
```

El inicio de la API ejecuta `alembic upgrade head`; la web instala las dependencias nuevas. Las pruebas cubren publicación, búsqueda, paginación, campos privados, fotos de la mascota y del aviso, cierre de avisos y migración desde una base nueva o existente.

## Estructura

```text
apps/
  api/       FastAPI, SQLAlchemy, Alembic, análisis local y tests
  web/       Next.js, TypeScript y Tailwind
infrastructure/docker/postgres/  PostGIS + pgvector
docker-compose.yml               PostgreSQL, Redis, MinIO, API, web y perfil ai-local (Ollama/RQ)
```

