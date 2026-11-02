import type { Metadata } from "next";
import Link from "next/link";
import { Icon } from "../ui/pictogram";

export const metadata: Metadata = {
  title: "Términos y condiciones — MascoMatch",
  description: "Condiciones de uso de MascoMatch: publicaciones, avistamientos, posibles coincidencias, cuentas y aportes voluntarios.",
};

const sections = [
  {
    id: "servicio",
    title: "1. Objeto y alcance del servicio",
    content: <>
      <p>MascoMatch es una plataforma de colaboración destinada a la publicación de avisos de mascotas perdidas, el registro de avistamientos y mascotas encontradas, y la revisión de posibles coincidencias. El servicio admite exclusivamente perros y gatos. La denominación MascoMatch identifica al proyecto. Su canal de contacto es <a href="mailto:info@mascomatch.com">info@mascomatch.com</a>.</p>
      <p>La información publicada es aportada por las personas que participan en la plataforma. El servicio facilita la organización de los reportes, pero no garantiza su exactitud, la identidad de las mascotas ni su recuperación. La plataforma no sustituye la asistencia veterinaria, los servicios de rescate ni la intervención de las autoridades competentes.</p>
    </>,
  },
  {
    id: "cuentas",
    title: "2. Registro, cuentas y acceso",
    content: <>
      <p>La publicación de reportes mediante una cuenta requiere datos de contacto válidos y la confirmación de la dirección de correo electrónico. Las personas usuarias podrán identificarse mediante un nombre o apodo. Los avistamientos breves vinculados a la ficha de una mascota perdida podrán enviarse sin crear una cuenta.</p>
      <p>Las personas usuarias deberán mantener la confidencialidad de sus contraseñas y evitar compartir el acceso a sus cuentas. Ante la detección de un acceso no reconocido, deberán modificar la contraseña o utilizar el procedimiento de recuperación de cuenta. Se prohíbe la suplantación de identidad y el uso de datos de contacto de terceros sin autorización.</p>
    </>,
  },
  {
    id: "publicaciones",
    title: "3. Publicación de reportes y uso responsable",
    content: <>
      <p>Las personas usuarias deberán proporcionar información que conozcan y distinguir los hechos de las suposiciones. Antes del envío de un reporte, deberán revisar la especie, la descripción, la ubicación y la fecha. La incorporación de fotografías es opcional y puede facilitar el reconocimiento de la mascota.</p>
      <p>Los avisos deberán mantenerse actualizados. Cuando se produzca la recuperación de una mascota, la persona titular del aviso deberá registrar ese estado. La confirmación de un avistamiento únicamente incorpora una pista a la búsqueda, que permanecerá activa hasta que se indique la recuperación de la mascota o se cierre el aviso.</p>
      <p>Quedan prohibidas las siguientes conductas:</p>
      <ul>
        <li>La publicación de reportes falsos, duplicados deliberados, mensajes no solicitados o publicidad ajena a la finalidad del servicio.</li>
        <li>El uso de la plataforma para la venta de mascotas, la comisión de fraudes, el acoso o la difusión de acusaciones contra personas.</li>
        <li>La publicación de documentos, domicilios particulares o datos personales de terceros sin la autorización correspondiente.</li>
        <li>Los intentos de acceso a cuentas ajenas, la extracción de información privada o la interferencia con el funcionamiento del servicio.</li>
      </ul>
    </>,
  },
  {
    id: "contenido",
    title: "4. Fotografías, textos y reseñas",
    content: <>
      <p>Las personas usuarias deberán publicar contenido propio o respecto del cual cuenten con autorización de uso. Conservarán los derechos que les correspondan sobre sus fotografías y textos. Su publicación autoriza a MascoMatch, de forma no exclusiva, a almacenarlos, adaptarlos técnicamente y mostrarlos dentro del servicio para difundir reportes y comparar posibles coincidencias. Dicha autorización no implica una transferencia de propiedad.</p>
      <p>Los reportes públicos podrán mostrar la descripción de la mascota, las fotografías, la zona y la fecha. Las personas usuarias deberán evitar la inclusión de personas identificables o información sensible en las imágenes y los textos. La eliminación de metadatos de una fotografía no suprime la información visible en su contenido.</p>
      <p>La publicación de reseñas es voluntaria y deberá reflejar una experiencia real. Sus autores podrán elegir un apodo o una publicación anónima y retirar la reseña desde la sección Mis avisos. El cierre de una búsqueda no implica necesariamente que se haya producido un reencuentro.</p>
    </>,
  },
  {
    id: "coincidencias",
    title: "5. Coincidencias e inteligencia artificial",
    content: <>
      <p>MascoMatch podrá comparar fotografías, características, fechas y ubicaciones para proponer posibles coincidencias. Los resultados automáticos pueden contener errores y requieren revisión humana. Una puntuación de similitud no constituye una prueba de identidad ni una probabilidad garantizada de correspondencia entre las mascotas comparadas.</p>
      <p>Los avistamientos enviados desde un aviso se presentan a su titular como reportes vinculados al caso. La recepción del reporte es independiente del resultado de la comparación, que puede encontrarse pendiente de análisis o resultar incompatible. La vinculación de un reporte, la recepción de una alerta o la confirmación de una pista no acreditan por sí solas la propiedad de la mascota.</p>
      <p>La extracción automática de características utiliza Gemma 3. El uso de esta funcionalidad queda sujeto a los <a href="https://ai.google.dev/gemma/terms" target="_blank" rel="noopener noreferrer">Términos de uso de Gemma</a>, incluidos los límites de su sección 3.2 y la <a href="https://ai.google.dev/gemma/prohibited_use_policy" target="_blank" rel="noopener noreferrer">Política de usos prohibidos de Gemma</a>, que se incorporan a estas condiciones. Las personas usuarias no podrán utilizar dicha funcionalidad para los usos allí prohibidos ni en infracción de la legislación aplicable.</p>
    </>,
  },
  {
    id: "ubicacion",
    title: "6. Ubicación y seguridad en las comunicaciones",
    content: <>
      <p>Los mapas públicos muestran ubicaciones aproximadas. La ubicación precisa de un avistamiento podrá compartirse de forma privada con la persona titular del aviso mediante las alertas correspondientes. Las direcciones sugeridas y la ubicación proporcionada por el dispositivo pueden ser inexactas; las personas usuarias deberán revisar el lugar y ajustar el marcador del mapa cuando corresponda.</p>
      <p>Los datos de contacto almacenados en las cuentas no se muestran automáticamente en las fichas públicas. Cuando la persona autora de un reporte elija compartir su correo, este se facilitará de forma privada a los titulares de avisos que reciban la posible coincidencia. La inclusión de un correo, teléfono o domicilio en una descripción pública puede hacer que dicha información resulte visible.</p>
      <p>Antes de coordinar un encuentro, las personas usuarias deberán verificar la información y adoptar medidas para proteger su seguridad. No deberán enviar dinero, contraseñas, códigos de acceso ni documentos a terceros que afirmen haber encontrado una mascota. Ante una situación de peligro o la necesidad de atención urgente de una mascota, deberán recurrir a la asistencia correspondiente.</p>
    </>,
  },
  {
    id: "notificaciones",
    title: "7. Notificaciones y correo electrónico",
    content: <>
      <p>Las alertas pueden consultarse dentro de la cuenta y también podrán enviarse por correo electrónico. Las personas usuarias podrán activar o desactivar los correos de alertas y recordatorios desde la sección Mi cuenta. Los mensajes solicitados para confirmar o modificar el correo electrónico y recuperar la contraseña conservarán su finalidad de acceso y seguridad.</p>
      <p>Los envíos y los análisis pueden experimentar demoras o fallos. La aceptación de un correo por el servicio de envío no garantiza su recepción inmediata ni su ubicación en la bandeja de entrada. El estado de los reportes también podrá consultarse en las secciones de avisos y notificaciones.</p>
    </>,
  },
  {
    id: "datos",
    title: "8. Información sobre datos personales y solicitudes",
    content: <>
      <p>El servicio utiliza los datos necesarios para gestionar cuentas, publicar reportes, almacenar fotografías, comparar posibles coincidencias, enviar comunicaciones y atender consultas. La información pública y los datos privados de cuenta y contacto tienen finalidades diferentes. La publicación de un reporte no autoriza otros usos de los datos personales.</p>
      <p>Las personas usuarias podrán actualizar sus datos de contacto y preferencias desde la sección Mi cuenta. Las solicitudes de acceso, rectificación o supresión de datos personales y las consultas sobre su utilización podrán dirigirse a <a href="mailto:info@mascomatch.com">info@mascomatch.com</a> o presentarse mediante el <Link href="/contacto">formulario de contacto</Link>. MascoMatch podrá solicitar la información mínima necesaria para verificar que la solicitud corresponde a la persona titular de los datos.</p>
    </>,
  },
  {
    id: "eliminacion",
    title: "9. Gestión de avisos y eliminación de cuentas",
    content: <>
      <p>Las personas usuarias podrán gestionar y cerrar sus avisos desde la sección Mis avisos. El cierre de un aviso lo retira de las búsquedas activas y no equivale a la eliminación de la cuenta.</p>
      <p>La eliminación de una cuenta desde la sección Mi cuenta implica la eliminación de sus registros de mascotas, avisos de pérdida, reseñas, perfil, sesiones y notificaciones. Los avistamientos y reportes de mascotas encontradas se conservan como información de la comunidad, desvinculados de la cuenta y sin compartir los datos de contacto de esta. Dichos reportes también pueden conservar sus fotografías y descripciones.</p>
      <p>La desvinculación de un reporte no suprime los datos personales que su autor haya incluido en el texto o las fotografías. Las solicitudes de retiro de esa información deberán dirigirse al canal de contacto de MascoMatch. Las copias de respaldo están sujetas a un ciclo de conservación propio y no desaparecen inmediatamente con la eliminación de un registro.</p>
    </>,
  },
  {
    id: "moderacion",
    title: "10. Denuncias y moderación",
    content: <>
      <p>Las personas usuarias podrán denunciar un aviso desde su ficha o informar un problema mediante la sección Contacto. La presentación de una denuncia inicia un procedimiento de revisión y no acredita que el reporte sea falso.</p>
      <p>La administración de MascoMatch podrá ocultar contenido o restringir cuentas ante el incumplimiento de estas condiciones, la afectación de derechos, el fraude, el abuso o un riesgo de seguridad. Las solicitudes de aclaración de decisiones de moderación o de corrección de publicaciones podrán presentarse mediante el canal de contacto, indicando la referencia del reporte.</p>
    </>,
  },
  {
    id: "aportes",
    title: "11. Gratuidad y aportes voluntarios",
    content: <>
      <p>La publicación de avisos, el registro de avistamientos y la consulta de búsquedas son gratuitos. Los aportes vinculados a la sección Apoyanos tienen carácter voluntario y se expresan en pesos uruguayos.</p>
      <p>La realización de aportes no otorga prioridad sobre otras búsquedas ni garantiza resultados.</p>
      <p>Los aportes puntuales se completan mediante Mercado Pago y no generan renovaciones automáticas ni suscripciones. Su confirmación depende del resultado informado por dicho proveedor. Las consultas relacionadas con un aporte podrán dirigirse a <a href="mailto:info@mascomatch.com">info@mascomatch.com</a>, indicando su referencia.</p>
    </>,
  },
  {
    id: "disponibilidad",
    title: "12. Disponibilidad y limitaciones del servicio",
    content: <>
      <p>La plataforma puede experimentar interrupciones por mantenimiento, incidencias técnicas o fallos de los servicios de mapas, almacenamiento y correo electrónico. La información aportada por la comunidad y los resultados de las herramientas automáticas pueden ser incompletos o encontrarse desactualizados.</p>
      <p>Estas limitaciones describen el alcance del servicio. No implican una renuncia a los derechos reconocidos a las personas usuarias por la legislación aplicable ni excluyen las responsabilidades que legalmente correspondan a quien opere MascoMatch.</p>
    </>,
  },
  {
    id: "versiones",
    title: "13. Actualizaciones y contacto",
    content: <>
      <p>Las actualizaciones de las presentes condiciones indicarán su fecha y los cambios correspondientes. El silencio de las personas usuarias no se considerará aceptación de nuevas obligaciones.</p>
      <p>Las consultas relacionadas con estas condiciones, las publicaciones o los datos personales podrán dirigirse a <a href="mailto:info@mascomatch.com">info@mascomatch.com</a> o presentarse mediante la sección <Link href="/contacto">Contacto y sugerencias</Link>.</p>
    </>,
  },
] as const;

export default function TermsPage() {
  return <main id="main-content" className="page legal-page">
    <header className="legal-heading">
      <p className="eyebrow">Uso de la plataforma</p>
      <h1>Términos y condiciones</h1>
      <p className="page-intro">Condiciones aplicables a la publicación de avisos, el registro de avistamientos y la participación en MascoMatch.</p>
      <p className="legal-version">Última actualización: <time dateTime="2026-10-11">11 de octubre de 2026</time></p>
    </header>
    <details className="legal-index">
      <summary>Índice de contenidos <Icon name="chevron" /></summary>
      <nav aria-label="Secciones de los términos y condiciones"><ol>{sections.map(section => <li key={section.id}><a href={`#${section.id}`}>{section.title}</a></li>)}</ol></nav>
    </details>
    <article className="legal-content" aria-label="Condiciones de uso de MascoMatch">
      {sections.map(section => <section key={section.id} id={section.id} aria-labelledby={`${section.id}-title`}><h2 id={`${section.id}-title`}>{section.title}</h2>{section.content}</section>)}
    </article>
  </main>;
}
