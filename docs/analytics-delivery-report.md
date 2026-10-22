# Entrega de analytics y preparación del lanzamiento

Requerimiento: `Requerimiento Mascomatch 21102026.txt`. Entrega local del 21 de octubre de 2026. **Sin commit, push, PR, tags, merge ni publicación en Internet.** Este informe describe la implementación y sus comprobaciones; no representa tráfico real de producción ni una medición de eficacia del modelo.

## 1. BASELINE AUDIT

Se inspeccionaron User, UserActivity/last_active_at, OperationalTracking, middleware de actividad/observabilidad, Redis, administración, Match/MatchFeedbackEvent, tracking de recomendaciones/respuestas, búsquedas, observaciones, mascotas, fotos, AnalysisJob, Embedding/FeatureSet, notificaciones, recuperación, Compose, Prometheus y donaciones.

Se reutilizan esas fuentes: UserActivity para actividad; Match para la primera recomendación de cada pareja; MatchFeedbackEvent para las respuestas; AnalysisJob y Prometheus para operación. No se duplica su telemetría en eventos genéricos.

Baseline Git: `ebef1c49f1e2d9dfca1b6a28a63e2f4bfa85cf67`, rama `main`. Había 60 archivos tracked modificados y 35 archivos fuente sin seguimiento. Se guardaron estado, diff y copia de esos 95 archivos en `real-data/analytics-baseline-20261021/`, excluido de Git. Se preservaron cambios ajenos al experimento, especialmente la estructura y alineación local del footer y la corrección operativa de reencolado de imágenes.

Antes de implementar: backend **239 passed, 6 skipped**; frontend **37 passed**, build correcto. El baseline incluía tests exclusivos del experimento retirado; los tests del producto completo se conservaron. La suite final no es una comparación numérica directa con la cantidad del experimento.

## 2. PRELAUNCH CHECK

Se retiraron flag/configuración activa, rutas, gates de acceso, formularios, mails/tareas, demo, lista de espera, experimento de precios/intención de pago, modelos de runtime y documentación específica. La aplicación vuelve al producto completo y la configuración local vuelve a habilitar IA/embeddings instalados.

**Excepción histórica explícita:** se conserva `0023_prelaunch.py`, ya aplicada en la base local. Eliminarla o cambiar su revisión rompería la cadena Alembic de esas bases. 0024 depende de esa revisión; sus tablas antiguas quedan inactivas, sin rutas ni procesos. Las pruebas de actualización referencian esa revisión para comprobar compatibilidad. No se destruyen sus datos. Los permisos previos de evaluación interna de fotos se conservan y se respetan en el exportador.

La búsqueda final de referencias activas no encontró dependencias de ese modo en frontend/backend/configuración productiva. Las referencias restantes son la migración histórica, su enlace y pruebas/documentación de compatibilidad.

## 3. DONATION COPY CHANGES

Se actualizaron inicio/Cómo funciona, `/apoyanos`, niveles y documentación. El servicio se presenta gratuito para buscar y reportar; donar es una colaboración voluntaria para mejorarlo. Se explicita que no da prioridad, altera matching, desbloquea funciones ni condiciona el servicio.

El nivel **Patrocinador** se renombró **Aliado**. Se conserva el estado funcional previo de los aportes: no se agregó pasarela ni cobro. No se creó sistema de patrocinadores, campañas, anuncios, packs, cuotas ni portal comercial.

## 4. IMPLEMENTED

- Identidad propia de visitante, sesiones, navegaciones reales, retorno y enlace futuro con cuentas.
- Hitos de adquisición y uso verificados por el servidor, deduplicados y resistentes a reintentos.
- Visibilidad real de coincidencias, referencias firmadas, posición observada y contexto histórico.
- Recuperación centralizada con atribución opcional en todas las rutas existentes.
- Cinco secciones de analytics privadas en el admin, filtros, series, ayudas y CSV agregado.
- Geografía contextual gruesa, retenciones, agregados diarios y reintentos seguros.
- Métricas de recursos y alertas reutilizando Redis/Prometheus.
- Privacidad, migraciones aditivas, pruebas y guías de operación.

Contrato completo: [analytics.md](analytics.md). Diseño del panel: [analytics-design.md](analytics-design.md).

## 5. DATA MODEL

| Adición | Finalidad |
|---|---|
| AnalyticsTracking | Inicio real de medición por instalación |
| AnalyticsVisitor / AnalyticsSession | Identidad seudónima, sesiones y retorno |
| ProductEvent | Hechos acotados con fecha, categoría, actor y zona; sin contenido libre |
| ProductMilestone | Clave durable que impide duplicar hitos después de expirar eventos |
| ProductDaily | Contadores diarios por dimensiones necesarias, con suma atómica |
| MatchExposure | Deduplicación sesión/coincidencia/contexto y presentación observada |
| RecoveryOutcome | Primer reencuentro registrado del aviso y atribución estructurada |

Se añaden primeras fechas/ranks/snapshot de vista a Match, snapshot de contexto a MatchFeedbackEvent y zona gruesa a LostCase/Observation. Las tablas existentes, vectores, features y respuestas no se reemplazan.

## 6. EVENT DEFINITIONS

Navegador: `page_view`, `landing_view`, `registration_started`, `match_shown`, `match_viewed`. El servidor valida categorías y referencias; no acepta estados autoritativos enviados por el cliente.

Servidor: `account_created`, `email_verified`, `pet_created`, hitos de 1/3/5 fotos, `lost_case_created`, `sighting_created` y sus segmentos mínimos, primer avistamiento con foto, `recovery`, inicio de sesión y retorno. Los hechos de negocio se guardan dentro de la transacción real: si esta revierte, sus hechos también.

Recomendación y respuesta mantienen sus fuentes existentes; no se crean entidades duplicadas de generación/feedback. Ver el catálogo y fórmulas en [analytics.md](analytics.md).

## 7. VISITOR / SESSION DESIGN

Cookie visitante aleatoria de 256 bits, propia, HttpOnly, SameSite Lax, Secure en producción y 180 días renovables. La base conserva HMAC, no el valor crudo. Sesión UUID firmada, finalizada tras 30 minutos de inactividad. Sus tiempos son configurables centralmente.

Retorno significa visitante previamente observado al empezar una sesión nueva. Login enlaza hechos futuros, mantiene el visitante y no fusiona dispositivos ni reescribe historia. No se usa IP ni fingerprinting para identidad. Un navegador no equivale a un ser humano verificado. Rotar el secreto HMAC cambia visitantes futuros; los hitos autoritativos tienen claves estables independientes de esa rotación.

## 8. FUNNEL DESIGN

Inicio → interacción con registro → cuenta → correo confirmado → mascota → 1/3/5 fotos. Los primeros pasos cuentan navegadores distintos; los hitos posteriores, usuarios distintos. Crear varias mascotas no multiplica personas, aunque sí el total de mascotas.

Se muestran cantidad, conversión desde el paso previo y desde inicio. Denominador cero se muestra ausente. Es un funnel de volúmenes del período, **no una cohorte cerrada**: visitas/cargas en otros períodos pueden producir conversiones superiores al 100%. Esto se informa en el panel.

Los umbrales de fotos se cuentan al cruzar 0→1, 2→3 y 4→5 con archivos validados. La serialización por mascota y claves únicas cubre concurrencia/reintentos. No se inventan hitos de fotos antiguas ni se duplican al borrar y volver a cargar.

## 9. MATCHING ANALYTICS

Se distinguen recomendada, mostrada, vista y respondida. Vista exige ≥50% visible durante ≥1 segundo continuo y pestaña visible. Deduplicación mínima por sesión, match y contexto. El servidor firma propietario/match/contexto/rank/score con vencimiento; no cuenta solo por devolver una lista o notificación.

Primera posición vista y mejor posición quedan conservadas. Top 1/3/5 usa confirmadas con rank observado en lista, no una notificación aislada como supuesto Top 1. Se etiqueta **Posición de las coincidencias confirmadas**, sin llamarlo Recall@K poblacional.

Tasa positiva = confirmadas / (confirmadas + falsas). Se muestran también revisión, falsas, dudosas y pendientes con denominadores explicados. No se llama accuracy general. El detalle reutilizado permite revisar falsos positivos, componentes de score, cobertura, distancia, versiones y fechas.

## 10. EXISTING MATCH FEEDBACK REUSED

Se conservan controles y nombres internos: CONFIRMED_RELEVANT = dudosa, FALSE_MATCH = falsa, RESOLVED = confirmada; recuperada sigue siendo una decisión separada. Se conserva el historial, incluyendo cambios de opinión. Repetir la misma respuesta no crea otra entrada ni cambia su primera fecha innecesariamente.

El snapshot de contexto acompaña la respuesta. Solo el dueño autorizado puede dar feedback. Los totales actuales usan la última respuesta; no suman cada cambio de opinión como otra coincidencia.

## 11. RECOVERY ATTRIBUTION

Las tres rutas existentes pasan por el mismo servicio de transición: edición directa, edición conjunta del dashboard y feedback de coincidencias. Pregunta **¿Cómo lograste encontrarla?**, con nueve razones: coincidencia, avistamiento de MascoMatch, redes, WhatsApp, veterinaria/refugio, calle/carteles, volvió sola, otra y prefiero no responder.

No se exige texto ni responder para cerrar. Se asocia automáticamente el match/reporte correspondiente cuando procede y se rechazan referencias de otro aviso. Estado, outcome, notificaciones y desactivación de candidatos se mantienen consistentes. Retries no duplican reencuentros.

Un FOUND histórico sin outcome queda desconocido. Un aviso reabierto conserva su primer outcome: no se presenta como otro reencuentro independiente del mismo aviso.

## 12. AI VERSIONING

Se reutilizan recommendation_snapshot, EmbeddingSpec, AnalysisJob y Embedding. Las nuevas recomendaciones conservan proveedor visual realmente utilizado, modelo/revisión/espacio, dimensión, preparación, versión de scoring y umbrales relevantes; se conserva el contexto de Gemma/prompt y revisión cuando fue informada por el proveedor. El runtime de procesamiento de imágenes también queda identificado.

El admin segmenta Pet-ReID/OpenCLIP, modelo/revisión y origen GENERAL/LINKED. Un dato histórico desconocido permanece desconocido. No se modificaron pesos, umbrales, ranking, modelos, scoring geográfico/temporal ni se incorporó MegaDescriptor.

## 13. AI / OPERATIONAL METRICS

Estados y fechas existentes de AnalysisJob permiten volumen, cola, procesamiento, total, throughput, errores y reintentos. Las mediciones existentes aportan inferencia visual/Gemma, carga, CPU y arranque frío. Falta de medición se conserva como desconocida; cold start usa solo trabajos que la informaron.

Las distribuciones muestran n, p50 y p95 solo con ≥20 valores. Se acotan a los 10.000 registros más recientes; los totales SQL no se limitan a esa muestra. El throughput usa finalizaciones en el período; estados/latencias, creación de trabajos.

CPU/RAM de API/workers salen de cgroup v2 y heartbeat; utilización del worker se muestrea cada cinco segundos. Otros servicios se consultan con Docker. Prometheus conserva series/alertas sin copiar infraestructura a PostgreSQL. Se validaron nueve reglas, incluyendo agregados pendientes y memoria. Ver las consultas en [analytics.md](analytics.md#operación-y-despliegue).

## 14. COMMUNITY METRICS

Volumen y evolución de avistamientos/encontrados; con/sin foto; anónimos/autenticados; vinculados/generales; con recomendaciones, confirmaciones y recuperación atribuida. Se conserva el avistamiento breve sin cuenta. Las tablas operativas muestran el estado de registros existentes; las series de publicación conservan los hechos nuevos.

Eliminar una cuenta puede dejar su avistamiento sin autor: su clasificación operativa actual no reconstruye la autoría del día de publicación. Las eliminaciones también pueden reducir totales actuales.

## 15. POTENTIAL COMMERCIAL INVENTORY

HOME y LOST_CASE: vistas reales. MATCHES: `match_viewed`, no candidatos generados. RECOVERY: experiencia de recuperación/reseña visible, no mero cambio de estado. Se muestran eventos, sesiones, visitantes, series día/semana/mes, vistas por aviso y zona.

País/departamento/localidad proceden del contexto geocodificado del reporte. Sin contexto se conserva desconocido. No se usa IP ni se agregan coordenadas exactas a analytics. Filtros permiten consultar zona; tablas acotadas a 200 agrupaciones y 100 avisos. Activas por zona expresa el estado actual de búsquedas creadas en el período, no una reconstrucción de actividad pasada.

Son oportunidades potenciales para estudiar; no impresiones publicitarias servidas/vendidas, promesas de alcance ni ventas proyectadas. No se implementó publicidad.

## 16. ADMIN DASHBOARD

Cinco secciones: Crecimiento, Uso, Matching e IA, Impacto, Inventario potencial. Se mantienen estilo, ancho completo, navegación y permisos del panel existente. Matching separa calidad/utilidad, rendimiento y detalle mediante pestañas. Se conservan usuarios, moderación, trabajos, correos y contactos.

Períodos 7/30/90 días, todo y personalizado, agrupación diaria/semanal/mensual, filtros pertinentes y ayudas. CSV privado agregado con protección de fórmulas. No exporta eventos crudos ni contactos.

La caché productiva se verifica después de autorización: máximo cinco claves de 512 KB y 60 segundos en Redis existente, con fingerprint de filtros. No hay caché HTTP pública. Se informa la demora en pantalla; un fallo de Redis no impide calcular el panel. Matching/Impacto no recorren eventos de páginas.

## 17. PRIVACY

`/privacidad` documenta identificadores propios, visitas/sesiones/uso/matching/rendimiento, retenciones y geografía contextual. Sin referrers, fuentes/UTM, fingerprinting, IP geolocation, SaaS analítico, venta ni entrega de datos personales a futuros patrocinadores.

Analytics genérico no contiene correos, teléfonos, nombres, descripciones, microchips, coordenadas, fotos, embeddings, prompts, contraseñas ni tokens. Las cookies necesarias para autenticar el producto siguen su finalidad separada.

No existía mecanismo previo de consentimiento con el que integrar estas cookies. No se presume una exención legal: la decisión aplicable queda al responsable. `ANALYTICS_ENABLED=false` detiene medición de producto sin bloquear su uso.

## 18. MIGRATIONS

- 0023: revisión histórica local conservada por compatibilidad, sin runtime activo.
- 0024_product_analytics: tablas, campos, índices y fecha de inicio de seguimiento.
- 0025_analytics_case_context: referencia de aviso en hechos/agregados e índices.
- 0026_analytics_rollup_queue: marca de agregado/reintento seguro; filas ya contadas no se vuelven a sumar.

Las nuevas migraciones son aditivas y rechazan downgrade destructivo automático. Se probaron instalaciones nuevas, actualizaciones desde 0021/0022/0023 y repetición de upgrade; conservaron vectores, FeatureSets, snapshots, feedback, actividad e inicio de OperationalTracking.

La base local quedó en `0026_analytics_rollup`. Al iniciar Docker, el arranque automático aplicó 0024 antes de poder generar el checkpoint previsto. Se informa expresamente: `mascomatch-analytics-0024-checkpoint.dump` es posterior a 0024, no un supuesto respaldo previo. También existe el respaldo anterior de 0022 y se generó `mascomatch-before-analytics-0026.dump` antes de 0026. No hubo pérdida ni migraciones destructivas. Antes de actualizar el servidor real: detener servicios, respaldar, verificar y migrar según [production.md](production.md).

## 19. TEST RESULTS

| Comprobación ejecutada | Resultado |
|---|---|
| Backend completo sin inferencia pesada | **259 passed, 7 skipped** |
| Frontend | **35 passed**, sin fallos |
| PostgreSQL real: migraciones, concurrencia, limpieza/eliminación y consultas de las cinco secciones con tres agrupaciones y dos precisiones | **2 passed** |
| Build de frontend en imagen de producción | Correcto, compilación y tipos |
| Flujo completo aislado de producción | Correcto: registro, verificación por correo local, rechazo sin confirmar, publicación/foto, CSRF, logout, cookies analytics, exclusión sintética, avistamiento anónimo notificado, recuperación atribuida |
| Restauración cifrada a destinos vacíos | **1 passed**; datos/hashes preservados, rechazo de destino ocupado |
| API dependency audit | Sin vulnerabilidades conocidas en la ejecución |
| Worker CPU dependency audit | Sin vulnerabilidades conocidas en la ejecución |
| Web production dependency audit | **0 vulnerabilities** |
| Prometheus | **9 reglas válidas** |
| Integración con modelos locales reales | Correcta técnicamente; sin mails externos ni nuevas descargas |

Las siete omisiones de la suite normal corresponden a integraciones que exigen activación/servicios explícitos, no fallos ocultos. PostgreSQL y producción se ejecutaron por separado. El smoke de IA real usó base desechable, modelos ya instalados y fixtures existentes: perros/gatos Pet-ReID, conejo/desconocido OpenCLIP, features texto/imagen Gemma, Redis/PG/storage e idempotencia. Su `effective_identity_accuracy` es **null**; fotos repetidas no son ground truth de identidad. Pico observado del worker de visión: 1.732.932 KiB (~1,65 GiB), sin extrapolarlo al VPS.

La auditoría inicial detectó avisos en Pillow 12.3.0. Se actualizó API/worker a 13.0.0, se reconstruyeron imágenes y se repitieron auditorías/pipeline. [Notas oficiales de Pillow 13](https://pillow.readthedocs.io/en/stable/releasenotes/13.0.0.html).

La comprobación adicional de consultas en PostgreSQL encontró un defecto de agrupación de expresiones JSON en el desglose de versiones, que SQLite no detectaba. Se reutilizan las mismas expresiones en SELECT/GROUP BY y se añadió cobertura del dialecto real. La corrección no cambia scoring ni datos históricos.

Evidencia local ignorada: `analytics-release-api-final.txt`, `analytics-release-web-final.txt`, `analytics-release-postgres-final.txt`, `analytics-release-production-final.txt`, `analytics-real-ai-smoke.txt`, `analytics-final-api-secure.txt`, `analytics-worker-audit.txt`, `analytics-prometheus-check.txt`, dentro de `real-data/`.

## 20. CI RESULTS

El workflow conserva backend, frontend/build/audit, worker/audit y validación Compose. Las nuevas pruebas ligeras entran en pytest/npm test normales; el job PostgreSQL incluye la prueba de concurrencia/analytics sin modelos.

Los equivalentes locales ejecutados pasaron. **No se ejecutó un pipeline remoto de GitHub para estos cambios**, porque no se hizo commit ni push. No se afirma un estado remoto verde de una revisión inexistente.

## 21. DEPLOY NOTES

No se contrató VPS ni se publicó mascomatch.com. La PC actual solo ejecuta desarrollo y validaciones locales. El diseño de producción conserva todos los servicios, almacenamiento y modelos en un servidor externo.

La guía de producción y sus scripts incluyen migraciones, seeds/roles, modelos instalados, backups/restauración, readiness y observabilidad. El validador usa stack desechable sin puertos públicos y Mailpit restringido a `example.test`; no envía estas pruebas a Brevo ni a usuarios. No se imprimieron ni incorporaron claves SMTP/API al código.

Reconstruir API, web, workers y herramientas por el cambio de Pillow. Aplicar migraciones con servicios detenidos y respaldos verificados. Los nuevos datos son aditivos: para rollback de código conservar el esquema; no ejecutar downgrade destructivo. Para restauración completa seguir la guía con destinos vacíos.

No deben desplegarse los contenidos actuales de `main` remoto suponiendo que incluyen este trabajo pendiente de revisión.

## 22. ANALYTICS START DATE

Base local: **21/10/2026 22:05:47.184816 UTC**, equivalente a **21/10/2026 19:05:47 Uruguay**. El admin muestra esta fecha. Cada base de producción recibe su propia fecha al instalar el seguimiento.

Visitas, sesiones, vistas y ranks no se reconstruyen retroactivamente. Los datos operativos anteriores calculables se presentan como historia existente, sin atribución/fecha desconocida inventada.

## 23. KNOWN LIMITATIONS

- Navegador ≠ persona; borrar cookies/dispositivos/bots no evidentes pueden alterar visitantes. Bloqueadores, red o eventos tardíos pueden reducir vistas medidas.
- Se filtran bots/prefetch/solicitudes sintéticas evidentes; no hay antifraude avanzado. Una referencia firmada acota manipulación, sin probar atención humana.
- Funnel de volúmenes, sin cohortes ni atribución por fuente. Login solo enlaza eventos futuros.
- Feedback voluntario tiene sesgo de participación; confirmación entre decididas y Top-K observado no son accuracy/recall poblacional. Aún faltan datos reales para concluir eficacia.
- Duraciones se limitan a 10.000 muestras y p95 exige veinte. No se midió capacidad del VPS ni carga masiva de usuarios concurrentes.
- Raw: 90 días. Agregados: 730 días. Fuera de raw, filtros tienen precisión diaria declarada; las tablas pueden estar incompletas si hay reintentos de rollup pendientes.
- Los agregados conservan dimensiones seudónimas para calcular únicos; no son una tabla estadística irreversible. Aplican acceso y retención.
- Caché hasta 60 segundos. El primer cálculo de una ventana reciente aún recorre sus eventos filtrados: medir consultas con tráfico real antes de ampliar el sistema.
- Zona desconocida para datos antiguos/inicio sin contexto; límites de 200 grupos/100 avisos por consulta y filtros para explorar zonas.
- Estado activo es actual, no inventario retrospectivo. Eliminaciones pueden reducir registros/atribuciones y cambiar segmentación de autoría actual.
- Un recovery outcome por aviso, conservado al reabrir; no representa múltiples episodios del mismo aviso.
- Métricas operativas históricas pueden carecer de revisión/arranque frío. No se rellenan con la versión actual.
- No se hizo una revisión visual manual final con sesión del dueño en el navegador integrado; hubo bloqueo de lectura de su pestaña de error. Compilación, componentes y flujos HTTP fueron verificados.
- Una comprobación adicional final de disponibilidad no llegó a ejecutarse: venció el plazo de revisión automática de permisos para los comandos de Docker. No fue un fallo del producto ni una conclusión de inseguridad. El validador completo anterior sí terminó con API/web saludables, flujo aprobado y restauración verificada.
- Los respaldos/configuración/modelos y logs generados en `real-data/` son locales y están ignorados. Un respaldo en el mismo servidor no cubre su pérdida.

## 24. GO / NO-GO FOR PRODUCTION

**GO técnico para revisar y preparar un piloto controlado:** flujos del producto y pruebas locales verificadas, medición propia implementada, migraciones probadas y restauración validada.

**NO-GO para afirmar que ya está publicado, que la IA tiene eficacia validada, o que el VPS está listo:** no hay despliegue público ni medición real de capacidad/efectividad. La publicación requiere las acciones reales siguientes y repetir readiness/backups/SMTP en el servidor elegido. No se plantea un bloqueo de desarrollo por falta de un dataset de entrenamiento.

## 25. OWNER ACTIONS REQUIRED

1. Revisar estos cambios y el panel local. Aprobar expresamente cualquier commit/push/publicación posterior; esta entrega permanece sin commitear.
2. Elegir/contratar el VPS y habilitar acceso de despliegue; decidir si se migra la base local existente o se inicia una base productiva vacía. Mantener separados datos de prueba y datos reales.
3. Resolver la política de consentimiento de cookies para los países atendidos; hasta entonces puede desactivarse analytics sin desactivar el producto. No se necesita compartir contraseñas aquí.
4. En el despliegue: DNS de mascomatch.com, secretos del servidor y uso de Brevo ya configurado, origen HTTPS y remitente correctos; comprobar un correo real. No hace falta volver a pegar claves al chat.
5. Confirmar el proveedor/límite de búsqueda de direcciones para el piloto; el servicio público actual no ofrece una capacidad ilimitada garantizada. Este cambio no contrata Geoapify ni Google Maps.
6. Autorizar/aceptar términos de modelos en una primera instalación cuando corresponda, elegir destino externo de backups y receptor de alertas operativas, y conservar la clave de restauración fuera del servidor.

Los puntos de implementación descritos arriba están resueltos localmente. Los datos de los primeros meses permitirán evaluar calidad y costes sin inventar resultados ni instalar patrocinadores anticipadamente.

<!-- GIT_REVIEW_APPENDIX -->

## Anexo de revisión: archivos y estado Git

Captura de cierre local; HEAD permanece `ebef1c49f1e2d9dfca1b6a28a63e2f4bfa85cf67`. Los siguientes comandos son de lectura; no se cambió el índice ni se creó ningún commit.

### Archivos tracked con diferencias de contenido

```text
.env.example
.github/workflows/ci.yml
README.md
apps/api/app/account_management.py
apps/api/app/analysis/providers.py
apps/api/app/analysis/worker.py
apps/api/app/core/config.py
apps/api/app/core/rate_limit.py
apps/api/app/main.py
apps/api/app/matching/engine.py
apps/api/app/matching/export_labels.py
apps/api/app/matching/linked.py
apps/api/app/matching/tracking.py
apps/api/app/models.py
apps/api/app/ops/release_check.py
apps/api/app/photo_reminders.py
apps/api/app/routers/admin_matching.py
apps/api/app/routers/auth.py
apps/api/app/routers/dashboard.py
apps/api/app/routers/linked_sightings.py
apps/api/app/routers/lost_cases.py
apps/api/app/routers/matches.py
apps/api/app/routers/notifications.py
apps/api/app/routers/observations.py
apps/api/app/routers/operations.py
apps/api/app/routers/pets.py
apps/api/app/routers/photos.py
apps/api/app/schemas.py
apps/api/requirements-vision.lock
apps/api/requirements.lock
apps/api/requirements.txt
apps/api/tests/conftest.py
apps/api/tests/test_production_integration.py
apps/api/tests/test_visual_migrations_integration.py
apps/web/app/admin/admin-workspace.tsx
apps/web/app/admin/administration.tsx
apps/web/app/admin/matching-dashboard.tsx
apps/web/app/api/admin/[...path]/route.ts
apps/web/app/apoyanos/page.tsx
apps/web/app/apoyanos/support-levels.ts
apps/web/app/apoyanos/support-options.tsx
apps/web/app/crear-cuenta/registration-form.tsx
apps/web/app/globals.css
apps/web/app/home-how-it-works.tsx
apps/web/app/layout.tsx
apps/web/app/linked-sighting-form.tsx
apps/web/app/location-picker.tsx
apps/web/app/match-feedback.tsx
apps/web/app/mis-avisos/candidate-report.tsx
apps/web/app/mis-avisos/my-reports.tsx
apps/web/app/notificaciones/notifications-inbox.tsx
apps/web/app/page.tsx
apps/web/app/report-form.tsx
apps/web/app/review-request.tsx
apps/web/app/site-footer.tsx
apps/web/lib/places.ts
apps/web/lib/server-api.ts
apps/web/tsconfig.json
compose.production.yml
docker-compose.yml
docs/donations.md
docs/frontend-redesign.md
docs/production.md
infrastructure/production/alerts.yml
tools/production_apply.py
tools/production_init.py
tools/production_smoke.mjs
tools/production_validate.py
```

### Archivos nuevos sin seguimiento

```text
apps/api/app/matching/visibility.py
apps/api/app/ops/resources.py
apps/api/app/product_analytics.py
apps/api/app/recovery.py
apps/api/app/routers/admin_analytics.py
apps/api/app/routers/analytics.py
apps/api/migrations/versions/0023_prelaunch.py
apps/api/migrations/versions/0024_product_analytics.py
apps/api/migrations/versions/0025_analytics_case_context.py
apps/api/migrations/versions/0026_analytics_rollup_queue.py
apps/api/tests/test_analytics_postgres.py
apps/api/tests/test_product_analytics.py
apps/web/app/admin/analytics-dashboard.tsx
apps/web/app/admin/analytics.css
apps/web/app/api/analytics/route.ts
apps/web/app/privacidad/page.tsx
apps/web/app/product-tracking.tsx
apps/web/app/recovery-experience.tsx
apps/web/app/recovery-question.tsx
apps/web/lib/product-analytics.ts
apps/web/tests/product-analytics.test.mjs
docs/analytics-delivery-report.md
docs/analytics-design.md
docs/analytics.md
```

### Generated files y artefactos locales

No forman parte del diff ni se deben incorporar secretos o datos de prueba al repositorio:

- `real-data/analytics-baseline-20261021/`: estado inicial, patch, ZIP de fuentes y respaldo privado de configuración, todos ignorados.
- `real-data/mascomatch-analytics-0024-checkpoint.dump` y `real-data/mascomatch-before-analytics-0026.dump`: checkpoints locales. El respaldo anterior a la fase permanece separado.
- `real-data/analytics-*.txt`: ejecuciones de pruebas, auditorías, compilación, migraciones, Prometheus y smoke de IA.
- `real-data/production-preview/`: configuración/secrets sintéticos y artefactos del entorno desechable de validación. No contiene la configuración de despliegue público.
- `.next/`, archivos de tipos/caché generados por Next, cachés de Python y dependencias: regenerados por las herramientas; no son nuevas fuentes del producto.
- Imágenes/contenedores/volúmenes de Docker del desarrollo y del preview desechable quedan locales para inspección. No se podaron imágenes ni se borraron volúmenes de usuarios.
- Helpers de auditoría/snapshot de `real-data/`: ignorados. No ejecutar otra vez los helpers de retiro de la capa anterior sobre las nuevas modificaciones.

Riesgos que requieren atención: migraciones y despliegue con respaldo previo; conservar 0023 histórica; supervisar retención/reintentos y espacio; medir carga del servidor; política de cookies; datos reales de feedback antes de afirmar eficacia. Las limitaciones y acciones concretas están en las secciones 23–25.

### git status --short

```text
 M .env.example
 M .github/workflows/ci.yml
 M README.md
 M apps/api/app/account_management.py
 M apps/api/app/analysis/providers.py
 M apps/api/app/analysis/worker.py
 M apps/api/app/core/config.py
 M apps/api/app/core/rate_limit.py
 M apps/api/app/main.py
 M apps/api/app/matching/engine.py
 M apps/api/app/matching/export_labels.py
 M apps/api/app/matching/linked.py
 M apps/api/app/matching/tracking.py
 M apps/api/app/models.py
 M apps/api/app/ops/release_check.py
 M apps/api/app/photo_reminders.py
 M apps/api/app/routers/admin_matching.py
 M apps/api/app/routers/auth.py
 M apps/api/app/routers/dashboard.py
 M apps/api/app/routers/linked_sightings.py
 M apps/api/app/routers/lost_cases.py
 M apps/api/app/routers/matches.py
 M apps/api/app/routers/notifications.py
 M apps/api/app/routers/observations.py
 M apps/api/app/routers/operations.py
 M apps/api/app/routers/pets.py
 M apps/api/app/routers/photos.py
 M apps/api/app/schemas.py
 M apps/api/requirements-vision.lock
 M apps/api/requirements.lock
 M apps/api/requirements.txt
 M apps/api/tests/conftest.py
 M apps/api/tests/test_production_integration.py
 M apps/api/tests/test_visual_migrations_integration.py
 M apps/web/app/account-session.tsx
 M apps/web/app/admin/admin-workspace.tsx
 M apps/web/app/admin/administration.tsx
 M apps/web/app/admin/matching-dashboard.tsx
 M apps/web/app/api/admin/[...path]/route.ts
 M apps/web/app/apoyanos/page.tsx
 M apps/web/app/apoyanos/support-levels.ts
 M apps/web/app/apoyanos/support-options.tsx
 M apps/web/app/crear-cuenta/registration-form.tsx
 M apps/web/app/globals.css
 M apps/web/app/home-how-it-works.tsx
 M apps/web/app/layout.tsx
 M apps/web/app/linked-sighting-form.tsx
 M apps/web/app/location-picker.tsx
 M apps/web/app/login/login-form.tsx
 M apps/web/app/match-feedback.tsx
 M apps/web/app/mis-avisos/candidate-report.tsx
 M apps/web/app/mis-avisos/my-reports.tsx
 M apps/web/app/notificaciones/notifications-inbox.tsx
 M apps/web/app/page.tsx
 M apps/web/app/report-form.tsx
 M apps/web/app/review-request.tsx
 M apps/web/app/site-footer.tsx
 M apps/web/lib/places.ts
 M apps/web/lib/server-api.ts
 M apps/web/tsconfig.json
 M compose.production.yml
 M docker-compose.yml
 M docs/donations.md
 M docs/frontend-redesign.md
 M docs/production.md
 M infrastructure/production/alerts.yml
 M tools/production_apply.py
 M tools/production_init.py
 M tools/production_smoke.mjs
 M tools/production_validate.py
?? apps/api/app/matching/visibility.py
?? apps/api/app/ops/resources.py
?? apps/api/app/product_analytics.py
?? apps/api/app/recovery.py
?? apps/api/app/routers/admin_analytics.py
?? apps/api/app/routers/analytics.py
?? apps/api/migrations/versions/0023_prelaunch.py
?? apps/api/migrations/versions/0024_product_analytics.py
?? apps/api/migrations/versions/0025_analytics_case_context.py
?? apps/api/migrations/versions/0026_analytics_rollup_queue.py
?? apps/api/tests/test_analytics_postgres.py
?? apps/api/tests/test_product_analytics.py
?? apps/web/app/admin/analytics-dashboard.tsx
?? apps/web/app/admin/analytics.css
?? apps/web/app/api/analytics/
?? apps/web/app/privacidad/
?? apps/web/app/product-tracking.tsx
?? apps/web/app/recovery-experience.tsx
?? apps/web/app/recovery-question.tsx
?? apps/web/lib/product-analytics.ts
?? apps/web/tests/product-analytics.test.mjs
?? docs/analytics-delivery-report.md
?? docs/analytics-design.md
?? docs/analytics.md
```

### git diff --stat

Este comando incluye únicamente archivos tracked. Los nuevos archivos se enumeran por separado arriba; su contenido también debe revisarse antes de agregarlo a Git.

```text
 .env.example                                       |   8 ++
 .github/workflows/ci.yml                           |   2 +-
 README.md                                          |   4 +-
 apps/api/app/account_management.py                 |   6 ++
 apps/api/app/analysis/providers.py                 |   1 +
 apps/api/app/analysis/worker.py                    |   6 +-
 apps/api/app/core/config.py                        |   7 ++
 apps/api/app/core/rate_limit.py                    |   3 +
 apps/api/app/main.py                               |  17 ++++
 apps/api/app/matching/engine.py                    |   2 +-
 apps/api/app/matching/export_labels.py             |   4 +-
 apps/api/app/matching/linked.py                    |   6 +-
 apps/api/app/matching/tracking.py                  |  34 ++++++-
 apps/api/app/models.py                             | 106 ++++++++++++++++++++-
 apps/api/app/ops/release_check.py                  |   6 +-
 apps/api/app/photo_reminders.py                    |   3 +
 apps/api/app/routers/admin_matching.py             |  13 ++-
 apps/api/app/routers/auth.py                       |  10 +-
 apps/api/app/routers/dashboard.py                  |  13 ++-
 apps/api/app/routers/linked_sightings.py           |  14 ++-
 apps/api/app/routers/lost_cases.py                 |  16 +++-
 apps/api/app/routers/matches.py                    |  24 +++--
 apps/api/app/routers/notifications.py              |   9 +-
 apps/api/app/routers/observations.py               |   7 +-
 apps/api/app/routers/operations.py                 |  11 +++
 apps/api/app/routers/pets.py                       |   7 +-
 apps/api/app/routers/photos.py                     |   6 +-
 apps/api/app/schemas.py                            |  41 +++++++-
 apps/api/requirements-vision.lock                  |   2 +-
 apps/api/requirements.lock                         |   2 +-
 apps/api/requirements.txt                          |   2 +-
 apps/api/tests/conftest.py                         |   1 +
 apps/api/tests/test_production_integration.py      |   7 ++
 .../tests/test_visual_migrations_integration.py    |  42 +++++++-
 apps/web/app/admin/admin-workspace.tsx             |   6 +-
 apps/web/app/admin/administration.tsx              |   3 +-
 apps/web/app/admin/matching-dashboard.tsx          |  11 ++-
 apps/web/app/api/admin/[...path]/route.ts          |   4 +-
 apps/web/app/apoyanos/page.tsx                     |   3 +-
 apps/web/app/apoyanos/support-levels.ts            |   2 +-
 apps/web/app/apoyanos/support-options.tsx          |   2 +-
 apps/web/app/crear-cuenta/registration-form.tsx    |   6 +-
 apps/web/app/globals.css                           |  41 +++++---
 apps/web/app/home-how-it-works.tsx                 |   2 +-
 apps/web/app/layout.tsx                            |   3 +-
 apps/web/app/linked-sighting-form.tsx              |   2 +
 apps/web/app/location-picker.tsx                   |   4 +-
 apps/web/app/match-feedback.tsx                    |  16 +++-
 apps/web/app/mis-avisos/candidate-report.tsx       |   6 +-
 apps/web/app/mis-avisos/my-reports.tsx             |   8 +-
 .../web/app/notificaciones/notifications-inbox.tsx |   4 +-
 apps/web/app/page.tsx                              |   2 +-
 apps/web/app/report-form.tsx                       |   4 +
 apps/web/app/review-request.tsx                    |   2 +
 apps/web/app/site-footer.tsx                       |  27 ++++--
 apps/web/lib/places.ts                             |   8 +-
 apps/web/lib/server-api.ts                         |   6 +-
 apps/web/tsconfig.json                             |   1 +
 compose.production.yml                             |   7 ++
 docker-compose.yml                                 |   7 ++
 docs/donations.md                                  |   2 +-
 docs/frontend-redesign.md                          |   2 +-
 docs/production.md                                 |  18 +++-
 infrastructure/production/alerts.yml               |  10 ++
 tools/production_apply.py                          |   4 +-
 tools/production_init.py                           |   7 ++
 tools/production_smoke.mjs                         |  23 ++++-
 tools/production_validate.py                       |   2 +
 68 files changed, 577 insertions(+), 120 deletions(-)
```
