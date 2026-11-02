# Cómo funciona: recorrido ilustrado

## Layout Structure

El bloque conserva el ancho general de 1280 px del inicio y usa una cabecera centrada de hasta 720 px. El recorrido ocupa hasta 1140 px, con cuatro filas abiertas. Cada fila distribuye ilustración, punto numerado y explicación en tres columnas: `1fr / 144 px / 1fr`, con 20 px entre columnas. Ilustración y texto alternan de lado. La fila mide al menos 380 px y crece según el texto visible.

A 1000 px o menos, el centro baja a 112 px, el espacio entre columnas a 12 px y las ilustraciones a 280 px. A 760 px o menos, una columna lateral de 52 px contiene los números y otra flexible contiene ilustración y texto apilados. El recorrido crece con el contenido y conserva los cuatro pasos visibles.

## Section Order

La sección sigue después de la portada y antes de las mascotas perdidas. Presenta título e introducción, seguidos de cuatro pasos con número, ilustración, título y dos párrafos visibles. Los pasos son: publicar el aviso, sumar un avistamiento, revisar pistas y cerrar la búsqueda tras el reencuentro. Las ilustraciones son conceptuales y no muestran reportes reales.

## Navigation

Se conserva `#como-funciona` para la navegación del encabezado y el footer. Los cuatro pasos forman una lista ordenada, con identificadores estables `#how-notice`, `#how-sighting`, `#how-review` y `#how-reunion`.

Toda la explicación está visible en los párrafos de cada paso. Los números y la línea son decorativos; cada encabezado incluye el número del paso como texto accesible para lectores de pantalla. Se retiraron los desplegables, los enlaces de acción y los pretítulos.

## Typography

Se mantiene Arial. El título principal usa 30–42 px, peso 800 e interlineado 1,18; en móvil, 32 px. La introducción usa 18 px y baja a 16 px en móvil. Los títulos de paso usan 26–34 px, peso 750, interlineado 1,2 y balance de líneas; a 1000 px o menos usan 28 px, y a 760 px o menos, 26 px. Toda la explicación usa 16 px e interlineado 1,75, reducidos a 15 px y 1,7 en móvil. Los números usan 23 px en escritorio, 21 px en tablet y 18 px en móvil.

## Color System

La superficie abierta utiliza el fondo crema del sitio. El texto conserva azul oscuro y gris azulado. Publicación usa coral; comunidad y revisión, azul; reencuentro, verde. Cada paso reutiliza los tokens de acento y fondo suave existentes. La línea base usa `#c7d8e4` y su tramo recorrido usa coral. Los puntos visitados combinan borde, fondo suave y número con el acento de su paso.

La primera ilustración conserva su adaptación coral de ManyPixels. Las otras tres parten de las referencias del usuario y usan coral, azul oscuro, azul y fondos suaves verdes y celestes, manteniendo piel y pelaje en colores naturales. Los estados decorativos del recorrido no representan el estado de una publicación ni una identidad confirmada.

## Spacing and Layout Rhythm

La sección tiene 88 px superiores, 76 px inferiores y 24 px laterales. La cabecera se separa 52 px del recorrido; las filas, 32 px entre sí. La explicación empieza 18 px después del título de cada paso y sus dos párrafos se separan 12 px. En móvil el primer párrafo empieza 14 px después del título.

En tablet el padding superior baja a 64 px. En móvil la sección usa 56 px verticales y 20 px laterales; la cabecera se separa 32 px del recorrido. Las filas tienen 44 px de separación; las dos columnas, 18 px, y la ilustración se separa 18 px del texto.

## Image Treatment

El paso 1 conserva Content Creation, de la colección Playstroke de ManyPixels. Los pasos 2, 3 y 4 usan adaptaciones de las referencias `clue.avif`, `ia busqueda.avif` y `reunion.jpg`, respectivamente. Muestran una mano con lupa y preguntas, un robot revisando información y una persona acariciando a su perro tras el reencuentro. Se adaptaron con la herramienta integrada imagegen, conservando la composición general y usando la paleta del sitio. Su origen, archivos y prompts se documentan en `apps/web/public/images/README.md`.

El primer archivo es SVG con área de dibujo de 500 × 500. Los otros tres son WebP con transparencia, optimizados con calidad 88 y dimensiones de 1536 × 1024, 1685 × 933 y 1222 × 1287. Se sirven desde `public/images` con Next Image y carga diferida. Su ancho máximo visible es 360 px en escritorio, 280 px en tablet y 300 px en móvil. Se conserva un espacio cuadrado con `object-fit: contain` para mostrar sus diferentes proporciones completas. La forma orgánica de CSS acompaña solamente al primer paso; los otros usan el fondo de su propia ilustración. El texto contiguo explica completamente cada paso; las imágenes decorativas tienen `alt` vacío para evitar repetición.

## Cards and Content Blocks

Las cuatro escenas se presentan sobre el fondo abierto de la página. Un camino curvo conecta círculos numerados de 72 px; en tablet son de 64 px y en móvil, 48 px. El paso actual agrega un halo de 8 px. Cada ilustración tiene un pequeño sello circular con un icono del sistema existente. El contenido de cada paso reúne la explicación y sus aclaraciones en un único bloque de dos párrafos con la misma tipografía.

El camino usa un SVG construido a partir de la posición real de los números. Se recalcula cuando cambia el ancho, las fuentes o el alto de una fila. Si JavaScript o alguna API de observación no está disponible, todo el contenido sigue visible; una línea vertical sirve de base antes de calcular la curva.

## Buttons and CTAs

Se retiraron los CTA de los pasos y el enlace “Seguí el recorrido” de la cabecera. El bloque es informativo: explica cuenta y correo confirmado, fotos opcionales, avistamientos sin cuenta desde un aviso, reportes generales, recepción de pistas, revisión humana y cierre tras recuperar a la mascota. Toda esa información se puede leer directamente.

## Overall Design Feel

La sección utiliza una composición editorial con aire, escenas elegidas a partir de las referencias del usuario, texto alternado y un camino numerado. La primera imagen se conserva y las otras tres siguen los motivos solicitados. El tono es cálido y lúdico, con títulos directos e información funcional accesible.

El camino se colorea con el avance por la página. IntersectionObserver activa una entrada suave de 600 ms para el texto, una única vez por escena. El contenido permanece visible antes de esa animación. Las ilustraciones y sus sellos permanecen estáticos al desplazarse y al pasar el puntero. La preferencia de movimiento reducido elimina la animación del texto y las transiciones de los círculos numerados.

## Implementación y alcance

`HomeHowItWorks` y su CSS conservan su ubicación independiente de la página principal. El recorrido usa APIs nativas, sin nuevas dependencias. Su estado controla únicamente la decoración del camino. El texto mantiene la publicación con correo confirmado, el avistamiento breve sin cuenta, la recepción de pistas vinculadas, la revisión humana de coincidencias y el cierre del aviso tras recuperar a la mascota.

El primer paso aclara que publicar un aviso es gratis y que MascoMatch se financia con donaciones, integrado en la explicación existente.

TypeScript terminó sin errores. No se añadieron ni ejecutaron pruebas automatizadas para esta modificación.
