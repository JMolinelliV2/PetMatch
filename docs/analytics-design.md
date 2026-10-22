# Panel de datos: decisiones de interfaz

## Layout Structure

Se conserva el contenedor de administración a todo el ancho, con su sidebar y área principal. Las tarjetas usan una grilla adaptable con columnas mínimas de 220 px; las tablas tienen desplazamiento horizontal propio. En móvil se apilan controles y tarjetas, sin ensanchar la página.

## Section Order

La navegación incorpora Crecimiento, Uso, Matching e IA, Impacto e Inventario potencial. Cada sección muestra título, período, controles relevantes, inicio del seguimiento, indicadores y detalle. Matching e IA separa Calidad y utilidad, Rendimiento de IA y Revisión de recomendaciones mediante pestañas; no exige recorrer todas esas herramientas en una sola pantalla.

## Navigation

Se reutiliza el sidebar, menú móvil y estado de período existente. Las fechas se conservan al cambiar de sección. Los filtros de proveedor/modelo/origen se aplican también a la lista de recomendaciones; los de trabajos identifican su alcance independiente. Las exportaciones son descargas de agregados del filtro actual.

## Typography

Se hereda la tipografía del sitio. Las cifras tienen mayor tamaño y alineación consistente; las definiciones se muestran con texto secundario y ayudas accesibles. Los snapshots técnicos permanecen dentro de un detalle desplegable y usan formato monoespaciado, con ajuste de líneas.

## Color System

Se mantienen los modos claro y oscuro del panel. Coral, azul, verde agua y violeta distinguen tarjetas sin cambiar el significado de sus estados. Los avisos de datos incompletos utilizan el estilo de advertencia existente. No se usan colores de éxito para afirmar precisión del modelo.

## Spacing and Layout Rhythm

Las tarjetas conservan separaciones de 16 px. Los bloques analíticos tienen 24 px de margen y relleno, reducidos a 16 px en pantallas angostas. Los filtros y ayudas disponen de espacio propio para no mezclarse con valores.

## Image Treatment

No se agregan imágenes ni fotografías de ejemplo al producto. El panel utiliza los pictogramas existentes, series y tablas; los registros reales permanecen detrás de la autorización administradora.

## Cards and Content Blocks

Cada indicador importante tiene definición visible y botón de información. Las distribuciones muestran tamaño de muestra, mediana y p95 solo cuando corresponde. Se distinguen ausencia de datos, cero y datos anteriores al seguimiento. Las tablas de inventario no se presentan como publicidad vendida.

## Buttons and CTAs

Se reutilizan botones secundarios para actualizar, aplicar período o zona y descargar CSV. La pregunta de recuperación utiliza un select y la confirmación existente del estado, con una opción explícita para no responder y una salida para cancelar. La medición no agrega pasos al registro ni al reporte de un avistamiento.

## Overall Design Feel

El cambio amplía el panel actual con datos explicados y controles familiares. Se conserva el rediseño local del footer: marca, grupos de navegación y bloque comunitario mantienen su estructura y alineación; únicamente se retiran sus variantes de rutas del experimento descartado.
