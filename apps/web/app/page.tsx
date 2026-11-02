import Image from "next/image";
import Link from "next/link";
import { Icon } from "./ui/pictogram";
import { HomeLostAnimals } from "./home-lost-animals";
import { HomeReviews } from "./home-reviews";
import { HomeHowItWorks } from "./home-how-it-works";

export default function Home() {
  return (
    <main id="main-content" className="home-page">
      <section className="home-hero" aria-labelledby="home-title">
        <div className="home-hero-inner">
          <div className="hero-content">
            <h1 id="home-title">Cada avistamiento<br /><span className="title-accent">puede ayudar a que<br />vuelvan a casa.</span></h1>
            <p className="hero-description">Compartí fotos, reportá lo que viste y revisá posibles coincidencias. Tu información puede ayudar a reunir perros y gatos con sus familias.</p>
            <div className="hero-actions" role="group" aria-label="Crear un reporte">
              <Link href="/perdi" className="button button-primary hero-report hero-primary"><span className="hero-action-icon"><Icon name="paw" /></span><span className="hero-action-copy"><strong>Perdí una mascota</strong><small>Publicá su aviso</small></span><span className="hero-action-end"><Icon name="arrow" /></span></Link>
              <Link href="/avistamiento" className="button button-secondary hero-report hero-sighting"><span className="hero-action-icon"><Icon name="eye" /></span><span className="hero-action-copy"><strong>Vi una mascota</strong><small>Compartí una pista</small></span><span className="hero-action-end"><Icon name="arrow" /></span></Link>
              <Link href="/encontre" className="button button-secondary hero-report hero-found"><span className="hero-action-icon"><Icon name="heart" /></span><span className="hero-action-copy"><strong>¿Encontraste una mascota?</strong><small>Reportá una mascota encontrada</small></span><span className="hero-action-end"><Icon name="arrow" /></span></Link>
            </div>
          </div>
        </div>
        <div className="hero-photo">
          <Image src="/images/dog-hero-generated.jpg" alt="Imagen ilustrativa de un golden retriever en un jardín" fill priority sizes="(max-width: 760px) 100vw, 65vw" />
        </div>
      </section>

      <HomeHowItWorks />
      <HomeLostAnimals />
      <HomeReviews />
      <section className="home-support" aria-labelledby="home-support-title"><span className="feature-icon"><Icon name="heart" /></span><div><p className="eyebrow">Apoyo voluntario</p><h2 id="home-support-title">Colaborá con MascoMatch</h2><p>Buscar y reportar mascotas es gratis. Si querés ayudarnos a seguir mejorando, podés hacer un aporte voluntario.</p></div><Link href="/apoyanos" className="button button-secondary">Conocé cómo apoyar <Icon name="arrow" /></Link></section>
    </main>
  );
}

