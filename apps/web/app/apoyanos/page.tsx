import type { Metadata } from "next";
import Link from "next/link";
import { Icon } from "../ui/pictogram";
import { SupportOptions } from "./support-options";

export const metadata: Metadata = { title: "Apoyanos — MascoMatch", description: "Conocé cómo apoyar a MascoMatch y ayudar a sostener las búsquedas de mascotas perdidas." };

const uses = [
  { title: "Una plataforma disponible", description: "Alojamiento de la web, almacenamiento de fotos y mantenimiento de los reportes.", icon: "paw" as const },
  { title: "Alertas, IA y herramientas", description: "Envío de correos, procesamiento de fotos y descripciones con inteligencia artificial y mejoras en el mapa. La IA ayuda a proponer posibles coincidencias que las personas deben revisar.", icon: "bell" as const },
  { title: "Cuidado del proyecto", description: "Respaldos, mantenimiento y mejoras para que la información siga siendo útil.", icon: "shield" as const },
];

const questions = [
  { question: "¿Publicar un aviso tiene costo?", answer: "Publicar avisos y reportar avistamientos es gratuito. Los aportes a MascoMatch son voluntarios." },
  { question: "¿Cómo se realiza el aporte?", answer: "Elegí el monto y continuá a Mercado Pago para confirmar el pago. Al finalizar, podés consultar el resultado en MascoMatch. La confirmación puede demorar si Mercado Pago todavía está procesando la operación." },
  { question: "¿El aporte se renueva automáticamente?", answer: "No. Por ahora ofrecemos aportes puntuales, que se realizan una sola vez. No se crean suscripciones ni cobros mensuales automáticos." },
];

export default function SupportPage() {
  return <main id="main-content" className="page support-page">
    <header className="support-intro">
      <span className="support-mark"><Icon name="heart" /></span>
      <p className="eyebrow">Apoyo voluntario</p>
      <h1>Ayudá a que más mascotas <span className="title-accent">vuelvan a casa.</span></h1>
      <p>MascoMatch es gratuito para quienes buscan y reportan mascotas. Si querés ayudarnos a seguir mejorándolo, podés hacer una donación voluntaria.</p>
      <p className="field-help">Donar no da prioridad, no modifica las coincidencias, no desbloquea funciones y no condiciona el servicio.</p>
    </header>
    <SupportOptions />
    <section className="support-use" aria-labelledby="support-use-title">
      <h2 id="support-use-title">En qué se usarán los aportes</h2>
      <p>Los aportes voluntarios acompañarán el funcionamiento y las mejoras de MascoMatch.</p>
      <div className="support-use-grid">{uses.map(item => <article key={item.title}><span className="feature-icon feature-icon-1"><Icon name={item.icon} /></span><h3>{item.title}</h3><p>{item.description}</p></article>)}</div>
    </section>
    <section className="support-faq" aria-labelledby="support-faq-title">
      <div className="support-faq-intro"><span className="support-faq-mark"><Icon name="message" /></span><h2 id="support-faq-title">Antes de aportar</h2><p>Algunas respuestas para que puedas elegir cómo acompañar a MascoMatch.</p></div>
      <div className="support-faq-list">{questions.map((item, index) => <details key={item.question} className="support-faq-item" open={index === 0}>
        <summary><span>{item.question}</span><span className="support-faq-toggle"><Icon name="chevron" /></span></summary>
        <div className="support-faq-answer"><p>{item.answer}</p></div>
      </details>)}</div>
    </section>
    <aside className="support-community"><span className="feature-icon"><Icon name="heart" /></span><div><h2>Compartir una pista también ayuda</h2><p>Explorá los avisos, compartilos con personas de la zona y reportá un avistamiento si reconocés a alguna de las mascotas publicadas.</p></div><Link href="/perdidos" className="button button-secondary">Ver mascotas reportadas <Icon name="arrow" /></Link></aside>
  </main>;
}
