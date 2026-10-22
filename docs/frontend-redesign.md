# Rediseño de MascoMatch

Las cuatro referencias visuales se adaptan al flujo existente. Se conserva la marca MascoMatch, los tres pasos de los formularios generales y el avistamiento breve desde una ficha. Se mantienen las rutas, los campos, las validaciones y los contratos de la API.

## Layout Structure

Términos usa un contenedor centrado de 920 px, con cabecera, resumen, índice desplegable y artículo de lectura continua. El artículo tiene 40 px laterales en escritorio y 20 px en móvil; el índice abierto usa dos columnas y pasa a una a 640 px o menos.

El pie compartido usa un contenedor de 1280 px con 24 px laterales. En escritorio distribuye marca, Explorar, Ayudar a encontrar, Legales y Comunidad en cinco columnas flexibles; a 1100 px o menos pasa a dos y Comunidad ocupa ambas. A 640 px o menos, marca, Legales y comunidad ocupan ambas columnas y los dos grupos de enlaces generales quedan lado a lado.

La bandeja de notificaciones suma un grupo flexible de tres filtros, Sin leer, Todas y Archivadas. La barra de cantidades reúne las acciones de lectura y actualización, con salto de línea en pantallas estrechas.

Las fotos ampliadas usan una ventana de hasta 1180 × 900 px, limitada al ancho y alto disponibles con 16 px de margen. La cabecera, el lienzo flexible y el pie ocupan tres filas; la imagen se ajusta completa al lienzo y las acciones siguen visibles en móvil.

Contacto reutiliza el contenedor centrado de 640 px de las páginas de cuenta, sin exigir una sesión. La tarjeta ocupa todo el ancho interior y se ajusta al padding lateral existente en móvil.

Mis avisos usa un contenedor centrado de hasta 640 px al consultar la sesión y mostrar el ingreso sin cuenta, igual que la página Ingresar. El título, la introducción, el formulario y los errores comparten el ancho disponible. Al mostrar una sesión iniciada, el contenedor pasa a 1280 px para los resúmenes y avisos. En móvil conserva el padding lateral de 20 px.

La espera al ingresar y consultar la sesión usa una tarjeta centrada de hasta 640 px, con altura mínima de 280 px. La carga inicial de Mis avisos ocupa el ancho disponible y agrega una vista provisional de dos bloques de resumen y una tarjeta, limitada a 760 px. En móvil el contenido se ajusta al ancho y la miniatura provisional baja de 80 a 56 px.

Contenedor de 1280 px con márgenes automáticos y 24 px laterales. Portada con texto y foto en dos columnas. Formularios con una columna principal flexible y ayuda lateral de 320 px; bajo 950 px pasan a una columna. Desde 360 px los controles se apilan, el stepper muestra la etapa activa y las fotos se pueden recorrer horizontalmente.

Cómo funciona ocupa una sección abierta con cabecera centrada y cuatro filas ilustradas, conectadas por una línea curva y círculos numerados. Ilustración y texto alternan de lado en una grilla `1fr / 144 px / 1fr`, limitada a 1140 px. Bajo 1000 px la columna central baja a 112 px. A 760 px o menos, los números quedan en una columna lateral de 52 px y las escenas y textos se apilan en otra flexible. Todos los pasos permanecen visibles. El recorrido se detalla en `home-how-it-works.md`.

Apoyanos utiliza el contenedor de 1280 px y una introducción centrada de hasta 780 px. Los cuatro niveles ocupan cuatro columnas, dos a 950 px o menos y una a 640 px o menos. El monto personalizado, el resumen y las acciones se apilan en móvil. El destino de los aportes usa tres columnas en escritorio y una en móvil.

Las reseñas de portada usan el mismo contenedor, tres columnas en escritorio, dos bajo 950 px y una bajo 640 px. Sin reseñas visibles el componente devuelve `null`, por lo que no agrega espacio ni encabezado vacío.

El mapa de animales perdidos ocupa todo el ancho del bloque de avisos, con lienzo de 420 px en escritorio y 360 px en móvil. El encabezado y el acceso al mapa completo se apilan bajo 640 px. La miniatura del pin tiene 240 px de ancho y altura limitada con desplazamiento interno cuando hace falta.

Debajo del mapa completo, la lista desplegable presenta tarjetas en dos columnas y pasa a una columna bajo 950 px. Cada tarjeta divide miniatura cuadrada y contenido; la foto mide 112 px, reducidos a 88 px bajo 640 px. La zona y la fecha pueden ocupar varias líneas sin desbordar.

Los detalles de avistamientos y encontrados usan una tarjeta de 240 px dentro del mapa. Su altura visible se limita al alto del mapa y permite desplazamiento para la descripción completa. Los reportes que comparten una zona se eligen desde un selector en la misma tarjeta.

## Section Order

Términos presenta regreso al inicio, título e introducción, fecha de última actualización, resumen de participación responsable, índice cerrado inicialmente y trece secciones de condiciones. El pie compartido sigue al contenido.

El layout raíz coloca un único pie después del contenido principal de cada página. Presenta logo y propósito, navegación pública, Legales y contacto/apoyo; una línea inferior muestra el año y la marca. El inicio elimina su antiguo pie interno para evitar duplicarlo.

Notificaciones muestra cuenta y acceso a preferencias, filtros, explicación de lectura y archivo, contador y acciones, confirmaciones, tarjetas y paginación. Un detalle abierto desde una alerta conserva su regreso a la bandeja y omite los filtros de listado.

La ventana de fotos presenta título y cierre, imagen, y posición con controles de anterior y siguiente cuando hay varias. Se abre sobre el contexto actual sin sustituir la ficha ni la tarjeta del mapa.

La revisión de cada aviso reúne **Enviados desde este aviso** y **Posibles coincidencias de otros reportes**. Los primeros permanecen disponibles aunque la comparación automática esté pendiente o sea incompatible. Sus tarjetas muestran miniatura, fecha y hora, zona, descripción, motivos, lugar privado y acciones de revisión.

Contacto presenta regreso al inicio, título e introducción, formulario y dirección de correo alternativa. Los campos aparecen en el orden nombre, correo, tipo de consulta y mensaje; siguen una explicación de privacidad y Enviar mensaje. Al recibir la solicitud, la confirmación reemplaza el formulario y permite escribir otra.

Mi cuenta reúne contacto, notificaciones por correo y eliminación de cuenta, en ese orden. Notificaciones mantiene la bandeja de alertas y enlaza a la configuración en Mi cuenta. La sección de preferencias tiene título, casilla, explicación, feedback de guardado y enlace para consultar las alertas.

Portada: navegación, presentación y acciones para los tres tipos de reporte, Cómo funciona, avisos activos reales, acceso al mapa, bloque de apoyo y pie con navegación, contacto y términos. Cómo funciona explica publicación y confirmación de correo, aportes de la comunidad, revisión de posibles coincidencias y cierre después del reencuentro en cuatro pasos. Formularios: título, tres etapas, campos del paso actual, validación, acciones y ayuda. Mis avisos: sesión, dos cantidades derivadas de los datos, casos con controles, reportes enviados y acceso a notificaciones.

Apoyanos: regreso al inicio, presentación, aviso de disponibilidad próxima, frecuencia del aporte, niveles, monto personalizado, resumen, destino de los aportes, preguntas frecuentes y acción para explorar animales perdidos.

La portada incorpora las reseñas después de los avisos y el acceso al mapa, antes de Apoyanos. En Mis avisos y Notificaciones, la invitación aparece después de guardar el cierre o la recuperación del animal y se mantiene separada del estado de la búsqueda.

El antiguo enlace al mapa se reemplaza por el mapa incrustado después de las tarjetas de avisos activos. Muestra únicamente animales perdidos con ubicación; el enlace **Abrir mapa completo** mantiene el acceso a avistamientos, encontrados y filtros de la página `/mapa`.

## Navigation

Términos y condiciones se enlaza dentro de la sección Legales del pie compartido, con título propio y navegación asociada mediante `aria-labelledby`. Reutiliza los estilos de los otros grupos y el área de interacción de 44 px. Registro, revisión de los formularios y avistamiento breve muestran enlaces informativos que abren otra pestaña y anuncian ese comportamiento a lectores de pantalla. El índice nativo permite saltar a los encabezados con anclas; no se cambia la navegación ni la validación de los formularios.

El pie enlaza las rutas existentes de animales perdidos, mapa, Cómo funciona, los tres tipos de reporte, Contacto y Apoyanos. Los grupos públicos usan landmarks `nav` con encabezados asociados; no se agregan accesos permanentes a Mis avisos o Notificaciones. Los enlaces admiten teclado, muestran el foco existente y tienen al menos 44 px de altura.

La bandeja inicia en Sin leer. Abrir alerta lleva al detalle y guarda la lectura; marcar una como leída la retira de esa vista. Todas conserva las alertas sin archivar. Archivar la mueve a Archivadas, donde Restaurar la devuelve a Todas. Los filtros indican selección con `aria-pressed` y las acciones muestran el resultado después del éxito del servidor. Se bloquean durante el guardado para evitar operaciones simultáneas.

La foto principal abre la ventana con clic, toque o Enter. Las miniaturas con un enlace o acción previa conservan ese destino y agregan un control independiente para ampliar. Cerrar, Escape o pulsar fuera regresa al control de apertura. Las flechas del teclado recorren la galería; Escape dentro de la ventana conserva los detalles del mapa. El diálogo nativo mantiene el foco dentro mientras está abierto.

Contacto y sugerencias está disponible en Explorar, el menú móvil y el pie compartido de todas las páginas. La página conserva el regreso al inicio y el enlace directo a info@mascomatch.com.

El enlace de configuración de la bandeja y de los correos abre `/mi-cuenta#notificaciones`. La sección se lleva a la vista después de cargar la sesión, incluso al entrar sin una sesión iniciada y luego ingresar desde esa página.

Logo a la izquierda; Inicio, Perdí una mascota, Vi una mascota y Mis avisos en el centro; botón Apoyanos, notificaciones y cuenta a la derecha. Mis avisos y Notificaciones se muestran con sesión iniciada. Explorar conserva Animales perdidos, Mapa, Encontré una mascota y el enlace a `#como-funciona`. Apoyanos tiene un botón propio con corazón, borde y fondo coral suave; está fuera de los desplegables y disponible sin sesión. La ruta activa usa subrayado coral y `aria-current`. Bajo 1100 px la navegación se reúne en un menú nativo para dejar lugar a los accesos visibles. Bajo 640 px Apoyanos ocupa una segunda fila del encabezado, sin esconderse dentro del menú.

La reseña se escribe dentro de Mis avisos o de la pantalla de la notificación de recuperación, sin cambiar de página. El autor vuelve a ella desde Mis avisos para retirarla; administración agrega la categoría Reseñas a los registros existentes.

Explorar y el menú móvil se cierran al pulsar fuera del desplegable, con mouse, toque o lápiz, y al presionar Escape. Si el foco estaba dentro, Escape lo devuelve al botón que abre el menú. Las pulsaciones dentro conservan el menú abierto, salvo al seleccionar un enlace o volver a pulsar el botón de apertura.

La flecha de Explorar reutiliza el chevron SVG de 16 px, centrado con el texto mediante flex. Apunta abajo al estar cerrado y arriba al estar abierto, siguiendo directamente el atributo nativo `open`, también al cerrar con Escape o pulsar fuera. La rotación dura 180 ms y se desactiva con la preferencia de movimiento reducido.

Los círculos de animales perdidos abren una miniatura al pasar el mouse, tanto en portada como en `/mapa`. El cierre se demora 450 ms al salir para permitir mover el puntero hasta la tarjeta y usar **Ver aviso**. Pulsar el círculo, Enter o Espacio mantiene la tarjeta abierta; en táctil se abre con un toque. El foco tiene contorno azul y el estado se informa con `aria-expanded`. La miniatura muestra foto, nombre, rasgos, localidad y fecha. Las fichas abiertas en portada usan `origen=inicio` y vuelven a `/#mapa-perdidos`; las abiertas desde `/mapa` conservan su regreso a `/mapa`.

La lista conserva `details` y `summary` nativos. La miniatura, el nombre y **Ver aviso** de un animal perdido llevan a su ficha con `origen=mapa`. Las capas, los filtros y el límite de 100 reportes siguen usando los mismos puntos del mapa.

En avistamientos y encontrados, la foto y **Ver detalles en el mapa** centran el punto y abren el reporte elegido. Los puntos tienen un área de interacción de 44 px y admiten Enter y Espacio. Escape cierra la tarjeta y devuelve el foco. Un aviso relacionado solo enlaza si está activo y visible, conserva `origen=mapa` y aclara que no confirma la identidad.

Al avanzar desde Mascota sin foto en un aviso de pérdida se presenta una ayuda dentro del mismo paso, con foco, fondo azul suave, icono de cámara y acciones Agregar una foto / Continuar sin foto. Mantiene los tres pasos y la publicación opcional sin imagen. El bloque usa padding de 20 px, título de 18 px y texto de 14 px. El recordatorio por correo reutiliza el logo y el botón centrado de los mensajes transaccionales; su enlace abre la carga de fotos del aviso propio en Mis avisos.

## Typography

Términos usa el título general de página, subtítulos de 21 px —20 en móvil— y texto de 15 px con interlineado 1,8. La fecha y los enlaces del índice usan 13 px. Los párrafos y los enlaces largos permiten salto de línea.

El pie mantiene Arial: marca de 25 px y peso 800, encabezados de 15 px y peso 700, enlaces y descripciones de 14 px, gratuidad de 13 px e información de la franja inferior de 12 px. Las descripciones usan interlineado 1,7 y los enlaces permiten saltos de línea.

El estado de lectura de cada alerta usa texto de 12 px y fecha de Uruguay. Los filtros usan 14 px y peso 600. Los mensajes de guardado se anuncian como estados accesibles.

El título de la ventana de fotos usa Arial de 18 px y peso 700; el contador del pie, 14 px, y los mensajes de carga o error, 15 px. Los títulos largos permiten saltos de línea.

Los estados de carga usan título de 20–24 px, peso 700 y explicación de 15 px con interlineado 1,6. El mensaje distingue preparar la cuenta, abrir los avisos y consultar las publicaciones; los lectores de pantalla reciben un estado cortés y atómico.

Se conserva Arial, la fuente existente, sin añadir descargas externas. Títulos de página de 32–46 px y peso 800; portada de hasta 58 px; secciones de 22–26 px; tarjetas de 18–22 px; texto de 14–16 px y ayudas de 12–13 px. El contenido largo permite salto de línea.

El título de Cómo funciona usa 30–42 px y la introducción 18 px. Los títulos de paso usan 26–34 px y cada paso tiene dos párrafos de 16 px que reúnen toda su explicación. En móvil el título principal usa 32 px, los títulos de paso 26 px, la introducción 16 px y el texto 15 px. Los números usan 23 px en escritorio, 21 px en tablet y 18 px en móvil.

Apoyanos mantiene los títulos generales, encabezados de sección de 24–28 px y niveles de 21 px. Los importes usan 30 px y peso 800, con frecuencia de 13 px. Las descripciones usan 15 px y los detalles de destino 13 px.

Las reseñas usan texto principal de 15 px con interlineado 1,7, nombre público de 14 px y fecha de 12 px. El formulario tiene título de 18 px y campos de 14–16 px. Los comentarios completos conservan saltos de línea y permiten cortar palabras largas para evitar desbordamientos.

## Color System

El artículo de condiciones usa blanco, bordes suaves y los textos existentes en azul oscuro y gris azulado. El resumen tiene fondo azul claro y escudo azul; los enlaces subrayados usan el azul de acciones y coral al pasar el puntero.

El pie tiene fondo azul grisáceo claro `#f2f6fa`, texto azul oscuro de la marca y descripciones con el token secundario existente. El logo y el apoyo conservan el coral; Contacto utiliza el azul de los enlaces. Bordes suaves separan el pie y su franja inferior.

Los filtros de notificaciones seleccionados usan borde y texto azul con fondo azul suave. Sin leer conserva borde y fondo azul; Leída y Archivada tienen texto secundario, separado de la etiqueta del resultado de comparación.

La ventana de fotos conserva cabecera y pie blancos con texto navy. El lienzo usa navy oscuro `#102536` y el fondo exterior navy al 78%, para separar la foto de la página. Los controles tienen borde visible y foco azul.

Variables semánticas en `globals.css` y colores equivalentes en el tema Tailwind. Fondo cálido, superficies blancas y texto navy. Coral para acciones principales; azul para información, ubicación y foco; verde para encontrado o compatibilidad alta; amarillo para revisión y advertencias. El coral se oscurece respecto de la referencia para mejorar el contraste del texto blanco. Los estados también llevan texto y no dependen solo del color.

El nivel elegido lleva borde coral de 2 px, fondo coral suave, check y texto Elegido. El resumen usa fondo azul suave. El botón de pagos pendientes es gris y está deshabilitado; no se presenta como una operación en curso.

Las estrellas y la puntuación seleccionada usan coral, con texto accesible que informa de 1 a 5 estrellas. La invitación a reseñar usa fondo azul suave, separado de los mensajes de cierre ya guardado.

## Spacing and Layout Rhythm

La página legal separa resumen, índice y artículo con 24–28 px. El artículo tiene 36 px superiores/inferiores y separa las secciones por 28 px y una línea suave. En móvil usa 24 px interiores verticales y 20 px laterales.

El pie tiene 48 px de espacio superior, columnas separadas por 28 px y 36 px antes de la línea inferior. En tablet los gaps son 28 px verticales y 40 px horizontales. En móvil usa 32 px arriba, 20 px laterales, gaps de 24 × 16 px y 28 px antes de la franja inferior.

Los filtros de la bandeja usan objetivos de 44 px, padding de 10 × 16 px y separación de 8 px. Las acciones de la barra se separan 16 px y permiten salto de línea. El estado de lectura se separa 12 px del contenido de la alerta.

La ventana de fotos usa 12 × 16 px en cabecera, 10 × 16 px en pie y 20 px entre sus controles. El cierre y las flechas miden 44 px. Las miniaturas tienen un indicador o botón de ampliar de 44 px, separado 6 px de los bordes.

Separaciones de 8, 12, 16, 20, 24, 28 y 32 px. Tarjetas con 24–28 px de padding en escritorio y 16–20 px en móvil. Campos de al menos 48 px y acciones táctiles de al menos 44 px. Ayudas y revisión conservan una jerarquía separada de los campos.

Cómo funciona tiene 88 px de separación superior y 76 px inferior en escritorio. La cabecera se separa 52 px del recorrido y sus cuatro filas, de al menos 380 px, tienen 32 px entre sí. En tablet el padding superior baja a 64 px. En móvil se usan 56 px verticales y 20 px laterales, 44 px entre pasos y 18 px entre ilustración y texto. Los párrafos de cada paso se separan 12 px y el alto aumenta con el contenido visible.

Los niveles de apoyo usan gaps de 20 px y padding de 24 px; el resumen, 24–28 px. La sección de destino empieza 64 px después del selector, reducidos a 48 px en móvil. El bloque de apoyo en portada usa padding de 28 px y una separación inferior de 40 px.

La grilla de reseñas usa gaps de 20 px y tarjetas con padding de 24 px, reducido a 20 px en móvil. La invitación tiene margen superior de 24 px y padding de 20 px. Puntuaciones y acciones conservan objetivos táctiles de 48 px.

## Image Treatment

Términos reutiliza el escudo y el chevron SVG existentes, sin imágenes adicionales ni nuevas descargas.

El pie reutiliza la huella SVG de la marca dentro de un bloque coral de 40 px y los iconos de corazón y flecha existentes. Su franja inferior muestra el año y la marca; el acceso a los términos pertenece a Legales. La portada utiliza una imagen generada y no incorpora un crédito de fotografía externa.

Las imágenes ampliadas usan `object-fit: contain`, sin recortes ni deformaciones, y se descargan al seleccionarlas. Las versiones de hasta 2048 px mantienen la resolución original disponible y eliminan metadatos; las miniaturas y el análisis siguen usando 1024 px. Las galerías consultan imágenes que pertenecen al reporte y mantienen las comprobaciones públicas o privadas de acceso.

La espera reutiliza la huella SVG de 30 px dentro de un círculo coral suave de 76 px. Un aro de 3 px rota cada 1,2 segundos y permanece quieto con movimiento reducido. No requiere descargar imágenes. Las formas provisionales se ocultan a los lectores de pantalla y no representan cantidades ni publicaciones reales.

La portada utiliza `dog-hero-generated.jpg`, una imagen ilustrativa original de un golden retriever generada con imagegen y optimizada a JPEG de 1536 × 1024 px y aproximadamente 180 KB. La composición centrada mantiene visibles la cabeza y las orejas con los recortes existentes en escritorio y móvil. El origen y el prompt se documentan en `apps/web/public/images/README.md`. Los avisos muestran únicamente fotos reales de la API, con un estado de ausencia cuando no hay foto. Miniaturas cuadradas y fotos de detalle de 4:3. El cargador compartido conserva una foto opcional para reportes generales y hasta cuatro para avistamientos vinculados, con JPEG, PNG y WebP de hasta 10 MB. Incluye selección, arrastre, miniaturas, eliminación y errores; no agrega campos al payload.

Apoyanos reutiliza los iconos SVG de corazón, huella, coincidencias y cuidado del proyecto. No añade imágenes remotas ni fotografías de supuestos reencuentros.

Las reseñas usan el corazón existente y estrellas de texto; no añaden avatares, fotografías ni imágenes del aviso. El nombre público elegido se muestra independientemente de la identidad privada de la cuenta.

Los marcadores de animales perdidos son círculos de 56 px con foto real recortada mediante `object-fit: cover`, borde blanco de 3 px y anillo coral. Sin foto o ante error se reutiliza la huella de marca. La API informa la presencia de foto en la misma consulta de puntos; el navegador carga la imagen desde el endpoint público que elimina metadatos. No se exponen claves de almacenamiento ni coordenadas precisas.

Las tarjetas de la lista reutilizan `DogPhoto` para animales perdidos y `ObservationPhoto` para fotos propias de avistamientos y encontrados. Las miniaturas se cargan de forma diferida desde endpoints públicos que procesan las imágenes y eliminan metadatos; no se entregan claves ni URLs firmadas del almacenamiento. Sin foto usan ojo o corazón y **Sin foto**, y ante error **Foto no disponible**. En la tarjeta del mapa la foto mide 144 px de alto y usa `object-fit: contain` para ver el animal completo.

## Cards and Content Blocks

Las condiciones se leen dentro de una única superficie blanca con radio de 16 px. El resumen y el índice usan radio de 14 px. El índice conserva `details`/`summary` y las obligaciones de publicación se muestran como una lista con viñetas.

El pie organiza contenido sobre un fondo continuo, sin tarjetas ni sombras. La descripción de la marca se limita a 30 caracteres de ancho aproximado y crece a 42 en móvil. Los grupos de enlaces son listas semánticas; contacto y apoyo comparten un bloque con encabezado propio.

Cada alerta muestra el estado de lectura antes del resultado de comparación. Marcar o archivar actualiza la lista y el contador, conserva el resultado del servidor frente a consultas anteriores y muestra una confirmación. Cada vista vacía explica dónde consultar las alertas leídas o archivadas.

La ventana de fotos es un diálogo nativo con radio de 16 px y sombra, colocado en un portal fuera del mapa para evitar recortes y herencia de sus estilos. Admite carga, ausencia de imágenes, indisponibilidad y reintento. El desplazamiento de la página se bloquea hasta el cierre.

Los avistamientos recibidos tienen una etiqueta independiente de la comparación: azul para pendiente o revisión manual, amarillo para no compatible y verde para posible coincidencia. Las decisiones del dueño tienen su propia etiqueta. Los resultados pendientes o incompatibles no se presentan con un porcentaje. Cada tarjeta privada utiliza una foto de 112 px y una fila flexible que se apila según el espacio disponible; la ubicación exacta se abre dentro de la misma página.

El formulario de contacto reutiliza la tarjeta blanca, el borde discreto y el radio de 16 px de Ingresar y Mi cuenta. Tiene un mensaje de hasta 4000 caracteres con contador, ayuda debajo del correo y errores junto a los campos o al formulario. Durante el envío bloquea sus controles; al recibir éxito muestra el check verde existente y lleva el foco al título de agradecimiento. No afirma que el correo ya haya llegado a la bandeja.

Guardar el contacto en Mi cuenta abre un `dialog` nativo de hasta 440 px, centrado, con fondo blanco, radio de 20 px, padding de 36 × 28 px y un check verde de 64 px. El título **Cambios guardados** usa 26 px y la descripción 15 px. Un fondo navy con opacidad del 45% separa la confirmación de la página. Solo aparece después de recibir éxito del servidor y aclara la confirmación pendiente de un correo nuevo. El foco pasa a Entendido; el diálogo nativo mantiene el foco dentro y permite Escape. También se puede cerrar con el botón de 44 px o al pulsar fuera. El ancho deja 16 px laterales en móvil y la altura admite desplazamiento en pantallas bajas. Al cerrar, se conserva el resultado junto al formulario.

La tarjeta de carga usa superficie blanca, borde existente, radio de 16 px, padding de 36 × 24 px y mensaje centrado. La huella se separa 24 px del título. Los bloques provisionales son estáticos, de color neutro, con 16 px entre resúmenes y 20 px dentro de la tarjeta. Se retiran cuando llegan los datos o se muestra un error, siguiendo los estados existentes de la sesión y del listado.

Tarjetas blancas, bordes discretos, radios de 12–16 px y sombra mínima. Componentes compartidos para stepper, fotos, iconos, tarjetas de animales y compatibilidad. El panel muestra las cantidades disponibles en sus datos; no se inventan nuevos avistamientos, compartidos, historias o recorridos. La foto de un aviso activo respeta el endpoint público y sus restricciones.

El paso 1 de Cómo funciona conserva la ilustración SVG de publicación de ManyPixels. Los pasos 2, 3 y 4 usan adaptaciones de las referencias del usuario: una mano con lupa y preguntas, un robot analizando información y una persona con su perro tras el reencuentro. Se adaptaron a coral, azul y fondos suaves del sitio y se sirven como WebP con transparencia. Conservan texto alternado, una línea curva y puntos numerados. La línea se colorea con el desplazamiento y el texto tiene una entrada suave; las imágenes y sus sellos permanecen estáticos al desplazarse y pasar el puntero. Cada paso muestra su título y dos párrafos con toda la explicación visible; se retiraron CTA, pretítulos y desplegables. El contenido distingue confirmar un avistamiento de recuperar al animal y explica el envío breve sin cuenta. La preferencia de movimiento reducido elimina las animaciones y transformaciones. El origen, tratamiento y prompts se documentan en `apps/web/public/images/README.md`.

Los niveles de aporte voluntario son etiquetas de radios nativos: toda la tarjeta permite seleccionar, el teclado conserva el comportamiento del grupo y el foco tiene contorno azul. Nombre, importe, frecuencia y descripción tienen jerarquía propia. Las preguntas frecuentes usan `details` y `summary` nativos. No se muestran cantidades de donantes, metas ni testimonios ficticios.

Las tarjetas de reseñas son artículos con puntuación, cita y pie de autor/fecha. El formulario opcional tiene cinco radios nativos, nombre público, comentario, contador y consentimiento sin marcar inicialmente. Solo se muestran testimonios persistidos de dueños de avisos retirados.

Cada reporte de la lista es un artículo dentro de una lista semántica, con borde discreto, radio de 14 px, padding de 16 px y gap de 16 px. En móvil se reducen padding y gap a 12 px. El tipo lleva una etiqueta azul, coral o verde con texto; el título usa 19 px y los datos 13 px. La acción **Ver aviso** conserva un objetivo de al menos 44 px.

Los avistamientos y encontrados añaden características informadas, fecha y hora de Uruguay, y un extracto de hasta 280 caracteres limitado a tres líneas en la lista. La tarjeta del mapa muestra la descripción completa. Los círculos de 24 px conservan coral y verde, con un contador para reportes en la misma zona; un grupo mixto combina ambos colores. Cuando coincide un aviso perdido, el círculo aparece a su lado sin modificar las coordenadas públicas.

## Buttons and CTAs

Los accesos legales son enlaces informativos; no se agregan botones de aceptación ni nuevas barreras a publicar. El índice tiene un control de al menos 48 px y sus enlaces un área mínima de 44 px. Los enlaces de correo y formulario de contacto permiten consultar el documento.

Conocé cómo apoyar usa un botón de 48 px con corazón, fondo blanco y borde coral; al pasar el puntero aparece el fondo coral suave. En móvil ocupa todo el ancho. Contacto y sugerencias es un enlace con flecha azul y área de 44 px. Ambos abren las páginas existentes; el botón no inicia un cobro.

Notificaciones agrega Abrir alerta, Marcar todas como leídas, Archivar notificación y Restaurar notificación. Archivar es reversible desde su vista propia; los reportes y sus controles de revisión se conservan. Los botones usan los estilos existentes y cambian a Guardando durante su operación.

El icono de ampliar reutiliza el sistema SVG existente. En fotos con navegación previa es un botón separado del enlace; en fotos principales es un indicador dentro del botón que ocupa la imagen. Los botones de anterior y siguiente se deshabilitan al llegar a los extremos de la galería, y el contador comunica la posición también a lectores de pantalla.

Acción principal coral, secundaria blanca con borde y terciaria azul con texto. Radios de 10–12 px. En móvil las acciones principales de publicación ocupan el ancho disponible. Todos los controles de cerrar, quitar foto o navegar tienen texto o nombre accesible. Se mantiene el bloqueo de controles durante las operaciones y el feedback de guardado, error y éxito.

Los accesos a animales perdidos y animales encontrados se mantienen en los bloques existentes de la portada y la navegación.

La portada enlaza a **Conocé cómo apoyar**. En Apoyanos, **Donaciones próximamente** está deshabilitado y acompañado por la explicación de disponibilidad. Elegir un nivel no genera un cobro. La acción final **Ver animales perdidos** permite seguir participando sin aportar dinero.

La invitación ofrece **Escribir una reseña** y **Ahora no**. El formulario ofrece **Publicar reseña** y **Cancelar**. El cierre del aviso no depende de estas acciones. Una reseña guardada muestra **Retirar mi reseña de la portada**.

## Overall Design Feel

La página de condiciones prioriza lectura clara y una presentación adecuada para el uso público, sin menciones a un piloto o a una versión preliminar. Explica los comportamientos de MascoMatch y emplea lenguaje formal en tercera persona. Los datos legales pendientes se documentan internamente en `legal-terms.md`.

El pie crea un cierre claro y cercano con más espacio para la marca y las acciones públicas. Mantiene visible la gratuidad de publicar y buscar y ofrece participación mediante reportes, sugerencias y apoyo. Su estructura compartida da continuidad entre páginas sin cambiar formularios o servicios.

Las fotos se amplían dentro de la página y mantienen el contexto del aviso o avistamiento. La ventana se centra en ver el animal completo y conserva el estilo simple de la plataforma. Su implementación y revisión están documentadas en `photo-viewer.md`.

Mi cuenta tiene una página propia de hasta 640 px, con contacto en una tarjeta blanca y eliminación en un desplegable separado. Correo pendiente, confirmación, errores y guardado se explican junto al formulario. Recuperar cuenta reutiliza el ancho, el regreso, el título, los campos y la tarjeta de ingreso y registro; sus resultados y enlaces permanecen dentro de esa tarjeta. El ingreso lleva directamente a Mis avisos o a confirmar el correo, sin la pantalla intermedia de sesión ya iniciada. La portada usa **¿Encontraste una mascota? Reportá un animal encontrado** y Apoyanos explica el procesamiento de IA con revisión humana.

Herramienta clara y cercana, con fotografías como principal elemento emocional. No se agregan ilustraciones decorativas, métricas ficticias ni mensajes de identidad confirmada a partir de una puntuación. La compatibilidad se muestra con contexto y conserva la revisión humana.

La página de apoyo conserva ese estilo simple y presenta la donación como voluntaria. Los importes están identificados como UYU y los niveles no ofrecen prioridad en las búsquedas. El circuito de pagos queda pendiente, documentado en `donations.md`.

Las reseñas describen experiencias de búsqueda, sin asumir que un cierre implica reencuentro ni atribuir una recuperación a MascoMatch. Incluyen puntuaciones de todo el rango y admiten apodos o anonimato.

Los mapas reutilizan Leaflet, las teselas existentes de OpenStreetMap y las coordenadas públicas redondeadas. La portada no pide ubicación del dispositivo para mostrarse. Los avisos perdidos que comparten el mismo punto se agrupan con un contador y un selector, dando preferencia a una foto real para el círculo. Los detalles de la miniatura se consultan al abrirla y usan el componente público del catálogo. La tarjeta de hover se ajusta dentro del mapa sin desplazar el punto bajo el cursor. Avistamientos y encontrados conservan sus colores y las capas siguen controlando qué puntos y avisos aparecen.

## Preservación de flujos

- Los pasos generales siguen siendo Mascota → Fecha y lugar → Contacto y revisión. Las fotos permanecen en el primer paso y no se agrega una etapa nueva.
- La búsqueda restringida por país, selección del lugar, mapa incrustado, movimiento del pin y precisión siguen utilizando los componentes y lógica existentes.
- El selector visual de sexo mantiene el `select` con nombre `sex` y valores `unknown`, `male` y `female` que utilizan la revisión y los payloads actuales.
- Se mantienen creación/ingreso de cuenta, privacidad del contacto, publicaciones sin foto, aviso cuando falla una foto y procesamiento posterior a publicar.
- El avistamiento vinculado conserva ubicación, hora y fotos opcionales, envío sin cuenta, identificador de solicitud y consulta posterior del estado.
- Mis avisos conserva edición, fotos, coincidencias, feedback, encontrado, cierre y reapertura. El mapa de última ubicación usa los datos privados del caso propio.
- La navegación conserva catálogo, mapa, notificaciones, recuperación, confirmación y administración mediante sus rutas existentes.
- Los avisos abiertos desde los puntos o la lista del mapa incluyen `origen=mapa` y muestran **Volver al mapa**. Los abiertos desde el mapa de portada usan `origen=inicio` y muestran **Volver al mapa del inicio**. Los avisos abiertos desde el catálogo conservan **Volver a animales perdidos**. Solo se admiten estos orígenes conocidos, sin aceptar direcciones de regreso arbitrarias.

## Verificación

Las pruebas de componentes comprueban las tres etapas, el contrato de sexo, las fotos opcionales y el contexto de los scores. La compilación de producción confirma las rutas existentes. La revisión de navegador utiliza una instancia temporal de la API con SQLite, imágenes en memoria, correo e IA desactivados, y cuentas de prueba; no publica reportes de prueba en la base real.

### Resultado de la revisión del 9 de octubre de 2026

- Frontend: 31 pruebas aprobadas, TypeScript sin errores y compilación de la imagen de producción completada con las rutas existentes.
- API: 163 pruebas aprobadas y 4 omitidas en la suite aislada. No hubo cambios en código, modelos ni contratos del backend.
- Pérdida: validación por etapa, selección y eliminación de foto, reselección del mismo archivo, Atrás sin perder datos, sexo en la revisión, ingreso con cuenta existente y publicación con foto.
- Ubicación: sugerencias restringidas a Uruguay, mapa incrustado y movimiento del pin con teclado, conservado al volver entre etapas.
- Avistamiento vinculado: envío sin cuenta ni foto; alerta privada al dueño, mapa de la alerta, marcado como leída y feedback guardado. La opción de indicar una hora aproximada conserva el formulario breve.
- Avistamiento general: publicación sin foto y con ubicación; las coincidencias aparecen después de guardar, con características, fecha y distancia como explicación.
- Encontrado: publicación sin foto ni ubicación, conservando los datos opcionales y el tipo de reporte diferenciado en Mis avisos.
- Mis avisos: edición guardada, cierre, reapertura, marcado como encontrado, nueva reapertura y mapa de última ubicación dentro de la página.
- Catálogo: búsqueda sin resultados y regreso a todos los avisos. Mapa comunitario: puntos reales, colores resueltos desde los tokens y filtro de capas que actualiza la cantidad visible.
- Móvil: navegación y formularios revisados a 360 × 800 px, sin desbordamiento horizontal. Campos y acciones principales de 48 px; pin y controles de zoom de 44 px; mapa de 240 px de altura. Los errores se muestran junto al campo y se relacionan con `aria-describedby` y `aria-invalid`.
- Contraste calculado sobre blanco: acción coral con texto blanco, 4,60:1; texto de ayuda, 4,76:1; borde de controles, 3,04:1. La selección de sexo incluye un check y el estado accesible del control.
- La base local real conserva los mismos registros: 2 avisos, 0 avistamientos, 1 foto y 1 embedding.
- Portada local: avisos reales con y sin foto, revisados en escritorio y móvil. Las fotos compactas quedan dentro de su columna y no se superponen al texto. La instancia temporal de revisión fue retirada al terminar.

La revisión de navegador usó matching por datos declarados. No mide la calidad de identificación por fotos ni confirma entrega de correo real: IA y correo estaban desactivados en esa instancia temporal. El rediseño conserva esos servicios y sus estados de procesamiento.

### Revisión de Apoyanos del 10 de octubre de 2026

TypeScript terminó sin errores y la revisión visual de la página local mostró los cuatro niveles en UYU, la frecuencia, el campo de otro monto, el resumen y el botón de pagos deshabilitado. Se guardó una captura de la página. No se ejecutaron pruebas de flujos ni se enviaron pagos, correos o reportes; esta entrega agrega contenido y selección local al frontend.

### Revisión de reseñas del 10 de octubre de 2026

TypeScript y la sintaxis Python terminaron sin errores. La API inició con la migración `0014_case_reviews` aplicada y la consulta pública devolvió cero reseñas. La portada local se revisó en lectura y se guardó una captura: no muestra la sección de reseñas ni un espacio reservado. No se ejecutaron pruebas automatizadas ni se publicaron reseñas de muestra, se cerraron avisos o se enviaron correos para esta revisión. Los flujos autenticados de escritura quedan implementados sin haber modificado datos de usuarios durante la revisión.

### Revisión de círculos con foto del 10 de octubre de 2026

TypeScript y la sintaxis Python terminaron sin errores. La consulta pública del mapa incluye `photo_url` para los avisos perdidos que tienen foto. Se revisaron la portada y el mapa completo con avisos reales: foto circular, huella para ausencia de foto, miniatura y enlace con el origen correspondiente. La tarjeta se abrió con mouse y con Enter; **Ver aviso** abrió la ficha con **Volver al mapa** apuntando a `/mapa`. Se corrigieron el alcance de Tailwind para incluir las clases del helper compartido, la precedencia de los estilos de imagen frente a Leaflet y el manejo del clic dentro de la tarjeta para conservar la navegación. La captura final muestra el círculo y la tarjeta completa. No se ejecutaron pruebas automatizadas ni se modificaron avisos, fotos o cuentas durante la revisión.

### Revisión de miniaturas en la lista del mapa del 10 de octubre de 2026

TypeScript terminó sin errores. Se abrió la lista desplegable de `/mapa` con los reportes existentes y se guardó una captura: muestra tarjetas con foto pública, ausencia de foto, iconos para avistamientos, tipo, especie, localidad y fecha. Los enlaces de los avisos incluyen `origen=mapa`. No se ejecutaron pruebas automatizadas ni se cambiaron fotos, reportes o permisos de acceso; las fotos privadas de observaciones siguen sin publicarse en esta lista.

### Gestión de cuenta y pedidos retomados del 10 de octubre de 2026

TypeScript y la sintaxis de los archivos Python modificados terminaron sin errores. La API arrancó con `0016_account_management` aplicada. Recuperar, Mi cuenta, Apoyanos e Ingresar respondieron correctamente. La revisión visual confirmó la tarjeta centrada de recuperación, el acceso de invitados a Mi cuenta, la explicación de IA en los aportes y el texto del enlace a Encontré una mascota. Se guardó una captura de recuperación. No se ejecutaron pruebas automatizadas ni se eliminaron cuentas, modificaron contactos o solicitaron correos; los flujos autenticados de cambio de correo y eliminación se revisaron en código, sin modificar cuentas reales.

### Estado de carga del 10 de octubre de 2026

TypeScript terminó sin errores y la web local se actualizó. La lectura de la página Mis avisos mostró **Preparando tu cuenta** y su explicación durante la consulta inicial, seguida del formulario de ingreso de invitados. Los estados de sesión, apertura y listado reutilizan el componente de carga. No se ejecutaron pruebas automatizadas ni se iniciaron sesiones o modificaron cuentas para esta revisión.

### Preferencias en Mi cuenta del 10 de octubre de 2026

TypeScript y la sintaxis de las plantillas de correo terminaron sin errores. La API inició correctamente y Mi cuenta y Notificaciones respondieron en lectura. El control de correo se trasladó a Mi cuenta, reutilizando su persistencia existente, con bloqueo durante el guardado, confirmación y error propios. La bandeja y los correos apuntan a la nueva sección. No se ejecutaron pruebas automatizadas ni se modificaron preferencias reales o enviaron correos durante esta revisión.

### Confirmación al guardar contacto del 10 de octubre de 2026

TypeScript terminó sin errores. El guardado exitoso del contacto abre un diálogo nativo con el resultado y, cuando corresponde, las instrucciones para confirmar el nuevo correo. Se revisaron la llamada posterior al éxito, la descripción accesible, el foco inicial y las formas de cierre en código. No se ejecutaron pruebas automatizadas ni se modificaron datos de cuentas reales para abrir el modal durante esta entrega.

### Ingreso centrado en Mis avisos del 10 de octubre de 2026

TypeScript terminó sin errores. La vista sin sesión mostró el título y el formulario dentro del mismo contenedor centrado de 640 px, con la tarjeta ocupando los 592 px interiores. No hubo desbordamiento horizontal en la vista de escritorio. Se guardó una captura con los campos vacíos; no se iniciaron sesiones, enviaron formularios ni ejecutaron pruebas automatizadas.

### Contacto del 10 de octubre de 2026

TypeScript y la sintaxis Python terminaron sin errores. La API inició con la migración `0017_contact_messages`, el correo SMTP habilitado y cero mensajes de contacto. La revisión visual de la página mostró los campos de nombre, correo, tipo y mensaje dentro de la tarjeta centrada, sin desbordamiento horizontal en escritorio. La navegación incluye el acceso desde Explorar y el pie del inicio. No se ejecutaron pruebas automatizadas ni se enviaron mensajes de contacto de prueba.

### Detalles y fotos de avistamientos del 10 de octubre de 2026

TypeScript y la sintaxis Python terminaron sin errores. La consulta del mapa mostró los dos avisos perdidos y tres avistamientos existentes, dos con foto propia. La foto pública respondió como JPEG y el detalle no incluyó datos de contacto ni coordenadas. La lista mostró ambas miniaturas y el estado sin foto; abrir el reporte del caniche mostró su foto, características, zona, fecha y hora de Uruguay, y descripción. No hubo desbordamiento horizontal en escritorio. No se ejecutaron pruebas automatizadas ni se publicaron reportes o fotos de muestra, se modificaron cuentas o enviaron correos.

### Recepción de reportes vinculados del 10 de octubre de 2026

TypeScript y la sintaxis Python terminaron sin errores. Se recuperó el avistamiento real omitido de Pablo, con una alerta de recepción activa y correo aceptado por SMTP, sin cambiar el resultado incompatible ni marcar al animal como encontrado. Mis avisos y Notificaciones muestran por separado la recepción y el resultado de la comparación. No se agregaron ni ejecutaron pruebas automatizadas; se mantuvieron las comprobaciones existentes actualizando sus expectativas. La revisión de la reparación consultó estados y cantidades sin exponer contacto ni coordenadas.
