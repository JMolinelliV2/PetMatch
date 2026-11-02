# Alcance: perros y gatos

Desde el 31 de octubre de 2026, las nuevas mascotas, búsquedas, avistamientos y reportes de mascotas encontradas admiten únicamente `dog` y `cat`.

## Publicación y comparación

- Los formularios de publicación y edición y el filtro del mapa ofrecen perro/gato. Se debe elegir una de las dos especies. Se conserva «No lo sé» para atributos como sexo, color y tamaño.
- Las entradas de la API usan el mismo tipo restringido. Se rechazan otras especies, `unknown`, valores vacíos y `null` explícito en una modificación de especie.
- Los modelos y los disparadores de base de datos protegen también las escrituras que no pasan por formularios. No se puede crear ni reactivar una búsqueda de otra especie.
- El catálogo, las fichas, las fotografías públicas, los reportes públicos, el mapa, las recomendaciones y las notificaciones excluyen los registros fuera del alcance.
- El matching general compara perro con perro y gato con gato. Los avistamientos breves heredan la especie del aviso seleccionado y solo pueden enviarse desde avisos admitidos.
- Pet-ReID sigue siendo el modelo visual predeterminado. OpenCLIP es una alternativa explícita para perros y gatos al deshabilitar Pet-ReID; no habilita nuevas especies.
- Gemma utiliza `text_feature_extractor_v4_dog_cat` y `vision_feature_extractor_v3_dog_cat`. `unsupported` es una señal interna de evidencia sobre otra especie: no es una opción publicable. `unknown`, `uncertain` y `not_visible` expresan incertidumbre del análisis. Una señal clara de especie no admitida impide recomendar la coincidencia.
- La planificación, el backfill, el despacho y la ejecución verifican el alcance vigente. El correo vuelve a comprobarlo antes de enviar alertas o recordatorios de fotos.

## Datos anteriores

No se borran ni se convierten los registros de otras especies: conservan especie, ID, estado original, fotos e historial. Sus dueños pueden consultarlos y cerrar sus avisos; administración conserva acceso al historial y la moderación. No aparecen públicamente ni admiten reactivación, fotos nuevas o análisis nuevos. «Mis avisos» y administración los identifican como fuera del alcance.

La migración `0027_dog_cat_scope`:

1. Marca `STALE` los trabajos pendientes o en ejecución de registros fuera del alcance y revoca sus ejecuciones anteriores.
2. Deja inactivo su matching, desactiva sus coincidencias y notificaciones y cancela correos y recordatorios pendientes.
3. Instala restricciones para nuevas especies y para la creación/reactivación de búsquedas. Permite cambios ajenos a la especie sobre registros históricos, como cerrar un aviso.

Los análisis completados se conservan como evidencia histórica. Los resultados de prompts anteriores no se reutilizan como características vigentes. Los vectores de perros/gatos conservan su espacio compatible. Las estadísticas históricas siguen conservando la historia; los contadores de búsquedas activas excluyen otras especies.

## Aplicación en otro entorno

1. Guardar un respaldo verificable de PostgreSQL.
2. Detener API y todos los workers para evitar ejecuciones con código anterior.
3. Instalar el código y ejecutar `alembic upgrade head` con la configuración del entorno.
4. Iniciar API y workers con la misma versión del código. No se necesitan modelos nuevos ni claves de servicios.
5. Comprobar que la versión incluya `0027_dog_cat_scope` o una migración posterior, la salud de los servicios y que el catálogo y mapa solo devuelvan `dog`/`cat`. Comprobar que no queden trabajos activos, coincidencias activas o correos pendientes para otras especies.

Si se desea renovar los atributos de los reportes admitidos ya existentes, `python -m app.analysis.backfill` programa extracción con los prompts actuales de forma idempotente y con prioridad baja. Es una operación de mantenimiento opcional que consume CPU; no se ejecuta automáticamente por esta migración.

El downgrade retira los disparadores. No reactiva trabajos ni correos antiguos automáticamente. Restaurar un respaldo requiere un procedimiento independiente y no debe utilizarse para volver a enviar alertas obsoletas.
