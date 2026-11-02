# Mapa dentro del formulario y perros perdidos

## Mapa de la comunidad: 1 de noviembre de 2026

`/mapa` muestra únicamente las capas Perdidos y Avistamientos. Los reportes de mascotas encontradas no aparecen en los marcadores, el contador ni la lista de esta página. Se conservan los formularios, los reportes existentes y el contrato público de la API.

Ambas capas usan marcadores circulares de 56 px y miniaturas con el mismo estilo. Los avisos de pérdida se identifican en rojo; los avistamientos, en azul, también en la leyenda, las tarjetas y la lista. Los avistamientos sin foto muestran un ojo sobre fondo azul. Se utiliza únicamente el endpoint público de fotos, respetando la miniatura elegida y sin exponer URLs del almacenamiento.

Pasar el mouse abre la tarjeta; tocar el marcador o activarlo con el teclado la mantiene abierta. La tarjeta de avistamiento conserva la ampliación de fotos, ID, autor público, características, ubicación aproximada, fecha y hora de Uruguay, descripción y aviso relacionado. Los avistamientos en una misma ubicación se agrupan y permiten seleccionar el reporte; si coinciden con una mascota perdida, sus marcadores se separan visualmente.

> Documento de una etapa anterior. Ver el [estado actual del MVP](mvp-phase-3-8.md), que incorpora comparación visual local, matching general, mapa y paneles.

Entrega del 7 de octubre de 2026.

## Cambios

- **Ver en mapa** abre una sección de 300 px en el mismo paso del formulario. Cierra con **Ocultar mapa**.
- El pin se puede arrastrar, mover tocando el mapa o ajustar con las flechas del teclado. Funciona con mouse y pantalla táctil.
- El punto nuevo se guarda al moverlo, se consulta una dirección legible y se descartan dirección y precisión GPS anteriores. Las respuestas de consultas anteriores se cancelan para evitar que cambien el punto nuevo.
- **Perros perdidos**, desde la portada y la navegación, muestra avisos activos de perros con foto opcional, nombre, características, descripción, fecha y localidad.
- Permite buscar por nombre, zona o descripción, navegar páginas de 24 avisos y abrir una ficha individual.
- Los avisos anteriores conservan su localidad mediante la línea `Zona:` que ya guardaba el formulario.

## Archivos

- `apps/web/app/location-map.tsx`, `location-picker.tsx`, `layout.tsx`, `globals.css` y `lib/places.ts`: mapa y selección del punto.
- `apps/web/app/perdidos/`, `lib/lost-dogs.ts`, `app/page.tsx` y `app/site-header.tsx`: listado, ficha, fotos y accesos.
- `apps/web/app/report-form.tsx`: localidad estructurada y acceso al listado tras publicar.
- `apps/api/app/routers/public_lost_dogs.py`, `main.py`, `models.py` y `schemas.py`: rutas públicas y campos permitidos.
- `apps/api/migrations/versions/0003_public_lost_dogs.py`: nueva localidad pública; la migración inicial fija el esquema original de `lost_cases` para que una base nueva también migre correctamente.
- `apps/api/tests/test_public_lost_dogs.py`, `test_analysis_migrations.py` y `apps/web/tests/lost-dogs.test.mjs`: cobertura nueva.
- `apps/web/package.json` y `package-lock.json`: Leaflet 1.9.4 y sus tipos. Sin variables de entorno nuevas.

## Datos públicos

La respuesta pública tiene una lista explícita de campos. `publisher_name` contiene solo la primera palabra del nombre o apodo del autor; no publica su identificador, correo ni teléfono. En avistamientos anónimos o con la cuenta eliminada es `null` y la interfaz muestra “Publicado por Anónimo”. Tampoco se incluyen microchip, precisión GPS, coordenadas ni claves de almacenamiento. Las fotos se leen del bucket privado, se limpian y se sirven como JPEG de hasta 1024 px. La foto elegida como miniatura tiene prioridad y se conservan las fotos anteriores del aviso y la mascota.

El listado, la ficha y la foto verifican que el perro tenga un aviso `ACTIVE`. Cuando cambia a `FOUND`, `CLOSED` o `CANCELLED`, o se elimina, dejan de servirlo. Las respuestas no se almacenan en caché. Los datos ya vistos o guardados por un visitante no pueden revocarse.

## Ejecución

```powershell
docker compose restart api web
```

La API aplica `0003_public_lost_dogs` al iniciar. La web instala la biblioteca nueva. En una instalación desde cero: `docker compose --profile ai-local up --build -d`.

Abrir `http://localhost:3000/perdidos`, o seleccionar una ubicación en un formulario y tocar **Ver en mapa**.

## Comprobaciones

- API en Windows: **60 passed, 1 skipped**. La integración optativa de IA local no se volvió a ejecutar en esta entrega.
- API en el contenedor Python: **60 passed, 1 skipped**.
- Frontend: **12 pruebas aprobadas**, TypeScript sin errores y compilación de producción correcta.
- PostgreSQL real: migración `0003_public_lost_dogs (head)` aplicada y API saludable.
- Navegador: aviso existente de Kobe, foto privada servida, búsqueda por nombre, ficha individual, mapa abierto en el formulario y movimiento del pin con teclado y arrastre.
- Pantalla de celular: listado en una columna y navegación sin desbordamiento.

## Límites

El mapa y la búsqueda de direcciones requieren Internet. Las teselas de OpenStreetMap y el geocodificador público no tienen disponibilidad garantizada. Una búsqueda de dirección que falla no deshace el punto elegido en el mapa.

Esta entrega agrega consulta pública de perros perdidos. El contacto privado entre personas, el panel de administración de avisos, los embeddings, el matching y las alertas siguen pendientes.

Referencias: [Leaflet](https://leafletjs.com/) y [política de teselas de OpenStreetMap](https://operations.osmfoundation.org/policies/tiles/).

## Actualización: campo Sexo

El primer paso de los tres formularios incluye Sexo, con Macho (`male`), Hembra (`female`) y No lo sé (`unknown`, valor predeterminado). Se guarda en la mascota o el avistamiento y aparece en el resumen de revisión. El listado de perros perdidos muestra el sexo conocido entre sus características; la ficha también informa si no está indicado.

La migración `0004_observation_sex` agrega el dato a avistamientos y mascotas encontradas. Los existentes quedan como `unknown`; la mascota ya tenía el campo. La migración inicial mantiene el esquema original de avistamientos para que una base nueva pueda aplicar toda la secuencia. No se agregan variables de entorno ni llamadas de IA.

Archivos: modelos, esquemas, migraciones, ruta pública, formulario compartido, ficha y etiquetas públicas, README y pruebas de sexo/migraciones/listado. Para aplicar: `docker compose restart api web`.

Comprobado: **72 pruebas de API aprobadas y 1 integración opcional omitida**, tanto en Windows como en el contenedor; **13 pruebas de frontend**, TypeScript y compilación de producción correctos. PostgreSQL está en `0004_observation_sex (head)`. En el navegador se verificaron las opciones del formulario y la selección Macho, y el aviso anterior de Kobe muestra Sexo: No indicado.

## Actualización: Mascotas perdidas

La sección pasa a llamarse **Mascotas perdidas** en navegación, portada, títulos, botones, estados del listado y fichas. Actualmente incluye únicamente avisos activos de perros y gatos; los registros históricos de otras especies se conservan en forma privada. Cada tarjeta y ficha informa la especie con una etiqueta en español.

La ruta pública principal es `/api/v1/public/lost-animals`. `/api/v1/public/lost-dogs` se conserva como alias para enlaces y clientes anteriores. La página mantiene `/perdidos`, las fotos privadas y la protección de los datos del dueño. No requiere nueva migración ni variables de entorno.

Comprobado: **83 pruebas de API aprobadas y 1 integración opcional omitida** en Windows y Docker; **14 pruebas de frontend**, TypeScript y compilación correctos. El navegador muestra Mascotas perdidas y los avisos existentes de Pepe (gato) y Kobe (perro).
