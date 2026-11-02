# Fotos ampliadas

Las fotos de avisos perdidos, avistamientos y mascotas encontradas se pueden abrir en una ventana dentro de la página. También se pueden ampliar desde Mis avisos y las notificaciones. Cuando hay varias imágenes, la ventana permite recorrerlas con Anterior, Siguiente o las flechas del teclado y muestra la posición actual.

## Interacción

- La foto principal del aviso y la foto de los detalles de un avistamiento abren la ventana con un clic, toque o Enter.
- Las miniaturas que ya abrían una ficha o los detalles del mapa conservan esa acción. Tienen un botón independiente de 44 px para ampliar; no hay botones dentro de enlaces u otros botones.
- Cerrar, Escape o pulsar fuera devuelve al contexto anterior. El diálogo nativo mantiene el foco dentro y lo devuelve al control de apertura al cerrar. Mientras está abierto bloquea el desplazamiento de la página.
- La ventana se coloca fuera de las tarjetas y del mapa mediante un portal, por lo que no queda recortada por Leaflet. Escape cierra únicamente la ventana de fotos y conserva la tarjeta del mapa.
- La imagen se ajusta entera, sin recortar ni deformar, al espacio disponible. La cabecera y los controles permanecen visibles. El ancho deja 16 px de margen lateral y la altura usa el tamaño actual de la pantalla.
- La carga, una galería vacía y los errores tienen mensajes propios. Se puede reintentar sin salir del aviso. Solo se descarga la imagen elegida, no todas las fotos grandes al abrir el listado.

## Acceso a las imágenes

- Los avisos usan `GET /api/v1/public/lost-animals/{id}/photos` para los identificadores, ordenados igual que la miniatura, y `GET /api/v1/public/lost-animals/{id}/photos/{photo_id}` para cada imagen. Se incluye la compatibilidad con `/public/lost-dogs`.
- Los avistamientos y encontrados usan `GET /api/v1/public/observations/{id}/photos` y `GET /api/v1/public/observations/{id}/photos/{photo_id}`. Solo se incluyen las fotos propias de esa observación.
- Cada consulta pública vuelve a exigir un aviso activo y visible con dueño activo, o un reporte visible que cumpla los criterios del mapa. Cada foto debe pertenecer al caso, su mascota o la observación correspondiente. No se entregan claves de almacenamiento, datos de contacto ni coordenadas.
- Las fotos de notificaciones usan `GET /api/notifications/{notification_id}/photos/{photo_id}/large`, con el proxy de sesión y las mismas comprobaciones de dueño y pertenencia que la miniatura privada. La galería no convierte una imagen privada en pública ni utiliza URLs firmadas.
- Las versiones ampliadas son JPEG de hasta 2048 px de lado, conservando el límite de tamaño, rotación y limpieza de todos los metadatos. No se aumenta la resolución original. Las miniaturas y el procesamiento de IA siguen limitados a 1024 px.
- Todos los resultados usan `no-store`. Cerrar u ocultar un reporte impide las nuevas consultas públicas a su galería. No hay migración ni cambios de publicaciones, coincidencias o correos.

## Revisión del 10 de octubre de 2026

TypeScript y la sintaxis Python terminaron sin errores. La revisión visual con fotos existentes mostró el aviso de Pablo y la imagen propia del avistamiento del caniche completos dentro de la ventana. Cerrar con Escape devolvió el foco al control de apertura. La lista mantuvo sus enlaces y acciones; abrir y cerrar una foto desde los detalles del mapa conservó la tarjeta y restauró el desplazamiento de la página. Se guardaron capturas de ambos tipos de reporte.

No se agregaron ni ejecutaron pruebas automatizadas, se subieron fotos o se modificaron cuentas o reportes. Los reportes existentes revisados tienen una foto cada uno: la navegación entre varias y la galería privada de notificaciones se revisaron en código, sin crear datos ni iniciar una sesión de usuario para esta entrega.
