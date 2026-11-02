import Link from "next/link";
import { Icon } from "./ui/pictogram";

const navigation = [
  {
    id: "footer-explore-title",
    title: "Explorá",
    links: [
      { href: "/perdidos", label: "Mascotas reportadas" },
      { href: "/mapa", label: "Mapa de reportes" },
      { href: "/#como-funciona", label: "Cómo funciona" },
    ],
  },
  {
    id: "footer-help-title",
    title: "Ayudá a encontrar",
    links: [
      { href: "/perdi", label: "Perdí una mascota" },
      { href: "/avistamiento", label: "Vi una mascota" },
      { href: "/encontre", label: "Encontré una mascota" },
    ],
  },
  {
    id: "footer-legal-title",
    title: "Legales",
    links: [
      { href: "/terminos", label: "Términos y condiciones" },
      { href: "/privacidad", label: "Privacidad" },
    ],
  },
] as const;

export function SiteFooter() {
  return (
    <footer id="site-footer" className="site-footer">
      <div className="site-footer-inner">
        <div className="footer-content">
          <div className="footer-brand">
            <Link href="/" className="site-name" aria-label="MascoMatch, inicio">
              <span className="brand-mark"><Icon name="paw" /></span>
              <span>Masco<span className="brand-accent">Match</span></span>
            </Link>
            <p className="footer-description">Avisos, fotos y avistamientos para ayudar a que más mascotas vuelvan a casa.</p>
            <p className="footer-free"><Icon name="heart" />Publicar y buscar es gratis.</p>
          </div>
          <div className="footer-navigation-groups">
            {navigation.map(group => (
              <nav key={group.id} className="footer-navigation" aria-labelledby={group.id}>
                <h2 id={group.id}>{group.title}</h2>
                <ul>{group.links.map(link => <li key={link.href}><Link href={link.href}>{link.label}</Link></li>)}</ul>
              </nav>
            ))}
          </div>
          <section className="footer-community" aria-labelledby="footer-community-title">
            <div className="footer-community-copy">
              <h2 id="footer-community-title">Sumate a MascoMatch</h2>
              <p>Tus ideas y tu apoyo ayudan a mejorar la plataforma.</p>
            </div>
            <div className="footer-community-actions">
              <Link href="/contacto" className="footer-contact">Contacto y sugerencias <Icon name="arrow" /></Link>
              <Link href="/apoyanos" className="button footer-support"><Icon name="heart" />Conocé cómo apoyar</Link>
            </div>
          </section>
        </div>
        <div className="footer-bottom">
          <p>© {new Date().getFullYear()} MascoMatch</p>
        </div>
      </div>
    </footer>
  );
}
