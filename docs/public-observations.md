# Avistamientos en el mapa público

El mapa y su lista muestran fotos de los propios reportes de avistamientos y mascotas encontradas, cuando existen. Sin foto muestran un icono y **Sin foto**; si falla la carga, **Foto no disponible**. Nunca sustituyen una foto faltante con la del aviso perdido relacionado.

## Información visible

La lista incluye especie, sexo, tamaño y color cuando fueron informados, zona aproximada, fecha y hora de Uruguay, un extracto de la descripción y **Ver detalles en el mapa**. La foto también abre esos detalles.

Las miniaturas tienen un botón independiente para ampliar la foto dentro de la página. La imagen de los detalles abre directamente esa ventana, con galería cuando existen varias fotos. El cierre regresa a la tarjeta del mapa; ver `photo-viewer.md` para los controles y permisos.

Los puntos abren una tarjeta con foto, características, zona, fecha y hora, y descripción completa. Un avistamiento enviado desde un aviso puede enlazar a esa publicación si sigue activa y visible. La tarjeta aclara que ese vínculo no confirma la identidad de la mascota; no expone scores ni decisiones privadas de coincidencias.

Los avistamientos y encontrados que comparten coordenadas públicas se agrupan con un contador y un selector. Abrirlos desde la lista selecciona el reporte concreto. El círculo mide 24 px y su área de interacción 44 px; admite clic, toque, Enter y Espacio. Escape cierra los detalles y devuelve el foco al punto. Un grupo mixto muestra coral y verde.

Si la zona coincide con un aviso perdido, el círculo de avistamientos se dibuja a su lado con un desplazamiento visual de 40 px. Las coordenadas siguen siendo las mismas y aproximadas; esto permite seleccionar ambos tipos de reporte. Los círculos con foto de mascotas perdidas, sus miniaturas y enlaces conservan el circuito existente.

## API y fotos

- `/api/v1/public/map` agrega características, extracto y presencia de foto mediante una consulta correlacionada, sin consultar una imagen por cada punto.
- `/api/v1/public/observations/{id}` ofrece una lista explícita de campos públicos, sin autor, correo, teléfono, preferencias de contacto, precisión de GPS, coordenadas exactas ni claves de almacenamiento.
- `/api/v1/public/observations/{id}/photo` devuelve la foto más reciente del reporte desde el almacenamiento privado, limpiada y convertida a JPEG. No entrega enlaces firmados ni hace público el bucket. Su proceso elimina EXIF y otros metadatos.
- `/api/v1/public/observations/{id}/photos` lista identificadores de las fotos propias y `/api/v1/public/observations/{id}/photos/{photo_id}` entrega la imagen ampliada de hasta 2048 px. Ambos vuelven a comprobar la visibilidad del reporte y la pertenencia de la foto.
- Ambos endpoints exigen un reporte visible, de tipo avistamiento o encontrado y con fecha válida para mostrarse. Un reporte oculto, eliminado o ausente devuelve 404. Los resultados usan `no-store`.
- Las miniaturas se cargan de forma diferida. La tarjeta consulta detalles actuales al abrirse y admite ausencia, indisponibilidad, error y reintento.

Los formularios generales y breves informan que las fotos y los detalles del reporte pueden verse en el mapa público. El correo y la ubicación exacta mantienen sus permisos privados; el avistamiento breve sigue pudiendo enviarse sin cuenta y con fotos opcionales.

No se modifica la base de datos ni el envío de alertas para esta función. Las fotos existentes de reportes visibles pasan a estar disponibles como imágenes públicas procesadas para el mapa.

## Revisión

TypeScript y la sintaxis Python terminaron sin errores. La API mostró los dos avisos perdidos y tres avistamientos existentes; dos avistamientos tienen foto propia y uno no. Una imagen respondió con JPEG y el detalle público no incluyó contacto, autor ni coordenadas. La lista cargó las dos miniaturas; el reporte del caniche abrió su foto, rasgos, zona, fecha, hora y descripción. El acceso con teclado al aviso perdido mantuvo `origen=mapa`. Se guardó una captura de los detalles. No se ejecutaron pruebas automatizadas ni se crearon reportes, cargaron fotos, modificaron cuentas o solicitaron correos para la revisión.
