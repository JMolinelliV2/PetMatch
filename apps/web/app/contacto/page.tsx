import type { Metadata } from "next";
import { ContactForm } from "./contact-form";

export const metadata: Metadata = {
  title: "Contacto — MascoMatch",
  description: "Compartí sugerencias, contanos un problema o hacenos una consulta para mejorar MascoMatch.",
};

export default function ContactPage() {
  return <main id="main-content" className="page account-page">
    <h1>Ayudanos a mejorar</h1>
    <p className="page-intro">¿Tenés una idea o encontraste algo que no funciona? Contanos. Podés escribirnos sin crear una cuenta.</p>
    <ContactForm />
    <p className="contact-direct">También podés escribir a <a className="text-button" href="mailto:info@mascomatch.com">info@mascomatch.com</a>.</p>
  </main>;
}
