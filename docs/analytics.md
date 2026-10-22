# Medición de producto, coincidencias e impacto

Contrato de métricas de MascoMatch, 21 de octubre de 2026. El servicio se publica como producto completo y gratuito para buscar y reportar mascotas. Los aportes son voluntarios. No se implementan anuncios, campañas, cobros ni cuentas comerciales.

## Fuentes de verdad

| Área | Fuente | Criterio |
|---|---|---|
| Visitas y recorrido | `ProductEvent`, `ProductDaily` | Eventos explícitos del navegador y hechos verificados por la API |
| Actividad autenticada | `UserActivity`, `users.last_active_at` | Se reutiliza el registro existente, sin una segunda definición de usuario activo |
| Recomendaciones | `Match.recommended_at/source/score/snapshot` | Primera recomendación de una pareja única aviso/avistamiento |
| Respuestas | `MatchFeedbackEvent` | Historial existente; última respuesta para contar resultados actuales |
| Recuperación | `RecoveryOutcome` | Una atribución estructurada por búsqueda; no se reconstruye historia desconocida |
| Rendimiento | `AnalysisJob.metrics`, fechas del trabajo, Prometheus y Docker | Sin copiar tiempos, CPU o memoria a eventos de producto |

Las visitas y vistas **no se derivan de solicitudes HTTP**, logs, notificaciones enviadas ni trabajos terminados.

## Visitantes y sesiones

- `mm_visitor`: valor aleatorio de 256 bits, generado por el servidor. Cookie propia HttpOnly, SameSite Lax y Secure en producción. Duración renovable de 180 días, configurable.
- La base conserva un HMAC del valor; no conserva el valor original del visitante. No se deriva de IP, user-agent, correo ni huellas del dispositivo.
- `mm_visit`: identificador de sesión firmado. El servidor termina una sesión después de 30 minutos sin actividad registrada. La cookie puede persistir más tiempo: su presencia no prolonga una sesión vencida.
- Una nueva sesión mantiene el visitante, siempre que siga disponible su cookie. Borrar cookies, cambiar de navegador o dispositivo puede producir otro visitante.
- Visitante que volvió: ya existía antes del comienzo de la nueva sesión. No equivale a una cohorte de retención ni a una persona verificada.
- Al autenticarse se vinculan los **eventos futuros** con la cuenta. No se reescriben eventos anónimos ni se fusionan navegadores.
- El secreto HMAC deriva del secreto privado del servicio. Rotarlo cambia los identificadores seudónimos de visitas futuras; los hitos autoritativos tienen claves SHA-256 estables y conservan su deduplicación.

No hay referrers, UTM, fingerprinting ni geolocalización por IP. El user-agent solo permite descartar bots evidentes y no se guarda en analytics. Las limitaciones de seguridad por IP existentes permanecen separadas.

## Catálogo y responsables de los eventos

| Evento | Emisor y deduplicación |
|---|---|
| `page_view` | Navegador, página visible y navegación real de Next. UUID de navegación y sesión; se conserva durante el replay de StrictMode |
| `landing_view` | Navegador, categoría HOME. Misma navegación, evento separado |
| `registration_started` | Navegador al interactuar con el registro; en el registro integrado al aviso, al enviarlo. Una vez por sesión |
| `account_created` | API tras crear la cuenta, dentro de la misma transacción. Una vez por cuenta |
| `email_verified` | API al consumir un token válido de confirmación o recuperación. Una vez por cuenta; cambiar correo no duplica el hito |
| `pet_created` | API dentro de la transacción de creación. Una vez por mascota |
| `first_photo_uploaded` | API al alcanzar 1 foto de la mascota/avisos con una carga de archivo validada |
| `three_photos_uploaded` | API al pasar de 2 a 3 fotos |
| `five_photos_uploaded` | API al pasar de 4 a 5 fotos |
| `lost_case_created` | API al crear la búsqueda. Una vez por búsqueda |
| `sighting_created` | API al crear un avistamiento o reporte de encontrado, incluido el formulario anónimo vinculado |
| `sighting_anonymous/authenticated`, `sighting_linked/general` | Segmentos mínimos del hecho de publicación, sin contenido del reporte |
| `sighting_with_photo` | Primer aporte con foto validada. Una vez por reporte |
| `match_shown` | Navegador: componente parcialmente visible en una pestaña visible; requiere referencia firmada del servidor |
| `match_viewed` | Navegador: al menos 50% visible durante un segundo continuo. Reinicia el temporizador al ocultarse o perder el umbral |
| `recovery` | Servicio centralizado de recuperación; misma transacción del outcome |
| `session_started`, `returning_session` | Servidor, al resolver la identidad de una visita válida |

Los hitos persisten únicamente si la transacción del producto termina correctamente. Una falla de medición no impide la operación principal. El registro y su agregado secundario utilizan savepoints separados: si falla el agregado, el hecho permanece pendiente para el reintento.

No se cuentan como recomendaciones los recálculos. Tampoco se registran respuestas de matching en un sistema paralelo: se usa el historial existente.

### Fotos y concurrencia

Se cuentan fotos de la mascota y de sus avisos. Se serializan las cargas por mascota, con orden de bloqueos mascota → avisos, y una clave durable por mascota/umbral. Borrar fotos y volver a cargarlas no duplica hitos. La API histórica que solo declara metadatos no dispara un hito de carga validada.

No se inventa el primer día de una foto antigua. Por ejemplo, dos fotos anteriores al seguimiento más una nueva producen el hito de tres fotos, sin inventar un nuevo hito de primera foto. Los contadores de fotos actuales sí pueden mostrar el inventario histórico existente.

## Definiciones estables del funnel

| Métrica | Definición |
|---|---|
| Visitantes únicos | Navegadores seudónimos distintos con `page_view` dentro del período |
| Sesiones | Sesiones iniciadas dentro del período |
| Vistas | Navegaciones `page_view` deduplicadas; no solicitudes de API |
| Visitantes que volvieron | Visitantes distintos con una nueva sesión clasificada como retorno |
| Comenzaron registro | Visitantes distintos con `registration_started` |
| Cuentas creadas/verificadas | Usuarios distintos con el hito autoritativo correspondiente |
| Usuarios que crearon mascota | Usuarios distintos, aunque crearan varias mascotas |
| Mascotas creadas | Número de hechos `pet_created`; puede superar el número de personas |
| Usuarios con 1/3/5 fotos nuevas | Usuarios distintos que alcanzaron el umbral durante el seguimiento |

Conversión desde el paso anterior = personas del paso / personas del anterior. Acumulada = personas del paso / visitantes del inicio. Un denominador cero se muestra como ausente, nunca como 0% de éxito.

Es un **funnel de volúmenes en el período**, no una cohorte cerrada. Un usuario puede visitar antes, registrarse desde otra ruta o cargar fotos en otro mes. Las conversiones pueden superar 100% si se interpretan ventanas independientes como cohortes; el panel explica este límite. No se implementan retención por cohortes, churn ni atribución por fuente.

## Usuarios activos

- DAU: usuarios distintos en `UserActivity` desde las 00:00 de hoy en America/Montevideo.
- WAU: usuarios distintos con actividad en los últimos siete días.
- MAU: usuarios distintos con actividad en los últimos treinta días.

Son ventanas actuales, independientes del filtro de fecha de creación de publicaciones. La actividad puede incluir polling automático autenticado; **no significa atención continua a la pantalla**.

## Coincidencias: generar, mostrar, ver y revisar

La pareja `LostCase + Observation` sigue siendo única. `record_recommendation` conserva la primera fecha, origen, puntaje y snapshot, aunque luego cambie el puntaje actual.

La API firma una referencia con coincidencia, dueño, contexto, posición, puntaje de presentación y momento de emisión. Dura dos horas. Consultar la API no cuenta como mostrar ni ver. Los reportes vinculados que todavía no son recomendaciones automáticas no reciben esta referencia.

`MatchExposure` deduplica por sesión/coincidencia/contexto. Otra coincidencia o sesión puede sumar una vista; repetir scroll no la duplica. Una notificación y una lista son contextos distintos. El navegador aporta la señal de visibilidad: es un proxy de exposición, no una prueba antifraude de atención humana.

La posición se toma del orden que **ya utilizaba la lista del aviso**, incluyendo su agrupación de reportes vinculados. No se modifica ese orden para mejorar indicadores. Se conserva la posición al ver por primera vez, incluso si la tarjeta antes se mostró en otra posición. La mejor posición vista puede mejorar después.

Las notificaciones individuales no se presentan como Top 1. Top 1/3/5 utiliza únicamente la primera posición vista dentro de la lista del aviso. Las confirmadas sin rank conocido se muestran aparte. Esto es **posición de confirmaciones recibidas**, no Recall@K de una población con ground truth completo.

| Resultado | Estado existente |
|---|---|
| Confirmada | Última respuesta `RESOLVED`: el dueño reconoció a su mascota, aunque siga buscando |
| Falsa | Última respuesta `FALSE_MATCH` |
| Dudosa | Última respuesta `CONFIRMED_RELEVANT` |
| Pendiente | Sin respuesta de esas categorías |

Tasa de confirmación entre decididas = confirmadas / (confirmadas + falsas). Tasa de falsas entre decididas = falsas / (confirmadas + falsas). Revisión = (confirmadas + falsas + dudosas) / recomendadas. Pendientes y dudosas también se muestran sobre recomendadas. **Ninguna de estas cifras es accuracy general del modelo.**

Los cambios de opinión permanecen en el historial; el resumen usa la última respuesta. Se corrigió la duplicación de auditoría que producía reenviar una recuperación ya guardada.

## Versiones y evaluación

La primera recomendación conserva proveedor visual realmente utilizado, EmbeddingSpec, modelo, revisión, dimensión 512, preparación, prompts de texto/visión, versiones disponibles de los trabajos que aportan evidencia, configuración de umbrales y versión del scoring. Las versiones históricas que no se conocen permanecen desconocidas. Los registros de respuesta conservan el contexto del snapshot y rank existente al responder.

Se pueden separar PET_REID y OPENCLIP, modelo/revisión, GENERAL/LINKED y resultado. El detalle privado muestra componentes de características, visual calibrado, similitud visual cruda, geografía, tiempo, cobertura, distancia, puntaje original y actual, fechas y rank. No se presenta el puntaje como probabilidad de identidad.

No cambian modelos, pesos, umbrales ni ranking. Pillow se actualiza a 13.0.0 por los avisos encontrados en la auditoría; se conserva su versión en el snapshot. [Notas oficiales de Pillow 13](https://pillow.readthedocs.io/en/stable/releasenotes/13.0.0.html).

## Recuperación e impacto

`recovery.recover` centraliza todas las rutas de FOUND: edición directa de aviso, edición conjunta desde el dashboard y feedback. Los llamadores bloquean el aviso antes de las coincidencias. Una clave primaria por búsqueda evita outcomes duplicados.

La pregunta admite MASCOMATCH_MATCH, MASCOMATCH_SIGHTING, SOCIAL_MEDIA, WHATSAPP, VET_OR_SHELTER, STREET_OR_POSTERS, RETURNED_ALONE, OTHER y PREFER_NOT_TO_SAY. No se exige texto libre ni respuesta de atribución para cerrar.

Desde una coincidencia se vincula automáticamente el reporte correspondiente si la razón es coincidencia o avistamiento; un match solo se conserva como atribución de match cuando se selecciona esa razón. Se rechazan referencias de otro aviso. Un FOUND anterior permanece sin atribución, sin fabricar una fecha. Reabrir el mismo aviso conserva su primer outcome: no produce otro reencuentro histórico de ese aviso.

Se distinguen recuperaciones registradas, ayuda declarada de MascoMatch, ayuda de match, ayuda de avistamiento, otras vías y falta de respuesta. **“El dueño indicó que MascoMatch ayudó”** expresa atribución declarada, no causalidad demostrada.

## Tiempos y rendimiento

Se muestran tiempos desde creación de búsqueda hasta primera recomendación, primera vista, primera respuesta y recuperación. Cada distribución informa n y mediana/p50; p95 solo aparece con al menos veinte muestras. Las distribuciones se limitan a los 10.000 casos/trabajos más recientes del filtro y se marca cuando hay muestreo. Los totales se calculan por SQL sobre el conjunto completo.

La utilidad incluye búsquedas con/sin recomendaciones, porcentaje con recomendación, promedio y mediana de matches, vistos por búsqueda y porcentajes de primera recomendación antes de 1/6/24 horas o desde 24 horas. Las primeras tres franjas son acumuladas y su denominador son búsquedas con recomendación, indicado en pantalla.

AnalysisJob aporta estados, espera hasta el último intento, procesamiento del último intento, tiempo total y métricas existentes de Gemma/embeddings, CPU, carga y arranques fríos. El porcentaje de arranque frío usa solo trabajos que informaron esa medición. El throughput usa finalizaciones exitosas dentro del período; el resto del panel de trabajos se filtra por su creación. Se puede filtrar proveedor, modelo/revisión y texto/imagen/embedding.

## Comunidad e inventario potencial

Se distinguen reportes con/sin foto, anónimos/autenticados, vinculados/generales, que produjeron recomendaciones, confirmaciones y recuperaciones atribuidas. Las tablas operativas consultan registros existentes y su estado actual; las series nuevas conservan los hechos originales. Una cuenta eliminada deja su avistamiento sin autor, por lo que la segmentación operativa actual puede diferir de la segmentación del momento de publicación.

Las superficies HOME, LOST_CASE, MATCHES y RECOVERY muestran eventos, sesiones y visitantes. MATCHES utiliza `match_viewed`, no recomendaciones generadas. RECOVERY es una experiencia de reseña/reencuentro realmente visible, no el mero cambio de estado. Se muestran vistas de coincidencias por aviso y geografía contextual.

País/departamento/localidad provienen del geocodificador al seleccionar el lugar del reporte. No se copian su dirección ni sus coordenadas. Sin esa información se usa ZZ/unknown, especialmente en avisos anteriores e inicio. El filtro de zona permite reducir tablas limitadas a 200 agrupaciones y 100 avisos. Las búsquedas activas por zona son el estado actual de las creadas en el período; no se inventa actividad histórica.

Estos son **proxies de oportunidades potenciales**, no anuncios servidos, impresiones vendidas, promesas de alcance ni proyecciones de ventas. No se agregan entidades o funcionalidades de patrocinadores.

## Persistencia, seguridad y conservación

- `AnalyticsTracking`: fecha de instalación del seguimiento, visible en todas las secciones. Localmente: 2026-10-21 22:05:47 UTC. Cada base nueva obtiene su propia fecha.
- `AnalyticsVisitor` / `AnalyticsSession`: identidad básica y sesiones; no se almacenan referrers, IP ni user-agent.
- `ProductEvent`: hechos individuales acotados durante 90 días, con categorías y contexto de aviso opcional.
- `ProductMilestone`: claves estables de deduplicación, para no volver a contar un umbral después de expirar los eventos.
- `ProductDaily`: contadores por día/actor/sesión/zona/superficie y contexto de aviso, durante 730 días. Las claves seudónimas permiten contar únicos sin sumar incorrectamente únicos diarios. No contienen el texto de un reporte ni marcas de cada evento individual.
- `MatchExposure`: prueba recibida de presentación/vista por sesión, expira con esta; los primeros tiempos y ranks permanecen en Match.
- `RecoveryOutcome`: primer marcado de recuperación y razón estructurada; conserva su finalidad operativa.

La actualización diaria usa INSERT ON CONFLICT y suma atómica. Si falla, el evento queda pendiente; la limpieza horaria reintenta hasta 500 con bloqueos SKIP LOCKED. Volver a limpiar no duplica lo agrupado. La expiración utiliza transacciones cortas por tabla y bloques de hasta 1.000 filas, con hasta 50 bloques por ejecución. Se respeta el orden de bloqueo de avisos y sus datos relacionados para convivir con la eliminación de cuentas. Los eventos expiran a los 90 días incluso ante un agregado fallido; una alerta permite detectar el problema antes de perder esa ventana de recuperación. Los registros operativos y vectores no se limpian con analytics.

Las consultas por hora usan eventos recientes cuando la ventana está dentro de su retención. El resto utiliza agregados diarios y **muestra su precisión de días completos**, sin fingir precisión horaria anterior. “Todo el período” para visitas cubre el historial agregado conservado, hasta 730 días. Las métricas operativas históricas mantienen su alcance propio.

En producción, los resultados del panel se reutilizan hasta 60 segundos en Redis después de verificar el acceso administrador. Hay como máximo cinco claves, una por sección, con un máximo de 512 KB cada una; cambiar filtros reemplaza el resultado de esa sección. La interfaz informa esa posible demora. Un fallo de caché permite consultar PostgreSQL normalmente. Matching e Impacto consultan sus fuentes operativas sin recorrer eventos de páginas; Uso restringe su serie a publicaciones. No se incorpora infraestructura adicional. El primer cálculo de una ventana reciente aún puede recorrer sus eventos filtrados: si el tráfico supera este diseño inicial, habrá que medir consultas y ampliar los resúmenes, conservando los filtros por hora y los únicos reales.

Todas las secciones administrativas comparten un botón circular flotante de **Recargar datos**, con ícono de recarga y sin texto visible, fijo en la esquina inferior derecha durante el scroll. La recarga conserva filtros, categoría, pestaña, página de resultados e historiales abiertos; vuelve a consultar los bloques de datos de la sección visible, sin recargar la página del navegador. En analytics, `force_refresh=true` omite la lectura de caché y la reemplaza con el cálculo nuevo del mismo filtro, siempre bajo autorización administradora. El ícono gira durante la carga (respeta movimiento reducido), el botón conserva su nombre accesible y evita solicitudes manuales duplicadas mientras hay consultas pendientes.

La API acepta cinco eventos de navegador, categorías enumeradas y UUIDs, con `extra=forbid`, máximo 4 KB, origen permitido, referencias firmadas y permisos del dueño. No acepta user_id, timestamps ni JSON de propiedades arbitrario. La escritura de analytics tiene límite compartido por actor y presupuesto global diario, separado de publicar. Fallar o alcanzar ese límite no impide usar el producto.

No se instala ningún SaaS de seguimiento. El CSV es privado y agregado, omite contactos e identificadores de cuenta y protege celdas que podrían interpretarse como fórmulas. No exporta eventos individuales.

La página `/privacidad` describe estas prácticas. No existe un mecanismo previo de consentimiento de cookies que integrar. La decisión jurídica sobre si se requiere consentimiento previo para los países atendidos corresponde al responsable; no se presume exención. `ANALYTICS_ENABLED=false` permite detener la medición mientras se resuelve.

## Operación y despliegue

| Necesidad | Consulta |
|---|---|
| CPU de API/workers | `rate(mascomatch_container_cpu_seconds_total[5m])`, por service |
| CPU respecto del límite | dividir por `mascomatch_container_cpu_limit_cores` |
| RAM | `mascomatch_container_memory_bytes` y `...memory_limit_bytes` |
| Servicios restantes, incluido Ollama | `docker stats`; no se persiste en PostgreSQL |
| Cola | `mascomatch_analysis_queue{source=...}` y antigüedad por fuente/urgencia |
| Utilización de workers | `avg_over_time(mascomatch_worker_busy[5m])`: muestreo de heartbeat cada cinco segundos, no cronómetro exacto |
| Throughput | `mascomatch_analysis_jobs_last_minute` y finalizaciones por hora del admin |
| Latencia/carga/CPU de tareas | métricas `mascomatch_analysis_*` existentes y tablas de Matching e IA |
| Agregados pendientes | `mascomatch_analytics_rollup_pending`; alerta si no se vacía tras el reintento horario |

Prometheus conserva su almacenamiento y acceso privados existentes. Las lecturas de recursos utilizan cgroup v2 y el heartbeat Redis, sin mounts privilegiados ni nuevos servicios. CPU/RAM no se guardan como eventos de producto. El admin conserva sus pantallas operativas de usuarios, bloqueo, avisos, denuncias, trabajos, correo y contactos.

### Migraciones y rollback

0023 es una revisión histórica ya aplicada del trabajo local retirado. Se mantiene inmutable para que Alembic pueda actualizar esas bases; sus tablas quedan sin rutas, procesos ni modelos de runtime. Sus datos no se destruyen. Se conserva el estado de autorizaciones anteriores en Pet y se respeta al exportar evaluación interna.

0024 agrega analytics, visibilidad y recovery; 0025 agrega contexto por aviso; 0026 separa hechos y reintentos de agregados. Todas son aditivas. Las nuevas revisiones rechazan un downgrade destructivo automático. Un rollback de aplicación debe conservar el esquema añadido; una restauración completa requiere un respaldo verificado y los servicios detenidos.

Ver [despliegue](production.md), [informe de entrega](analytics-delivery-report.md) y [diseño del panel](analytics-design.md). No se hicieron commits, pushes ni modificaciones de ramas remotas.
