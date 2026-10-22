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
        <div className="hero-content">
          <p className="eyebrow">Más miradas. Más oportunidades.</p>
          <h1 id="home-title">Cada avistamiento<br /><span className="title-accent">puede ayudar a volver a casa.</span></h1>
          <p className="hero-description">Compartí fotos, reportá lo que viste y revisá posibles coincidencias. Tu información puede ayudar a reunir a una mascota con su familia.</p>
          <div className="hero-actions" aria-label="Crear un reporte">
            <Link href="/perdi" className="button button-primary hero-primary"><Icon name="paw" />Perdí una mascota <Icon name="chevron" /></Link>
            <Link href="/avistamiento" className="button button-secondary"><Icon name="eye" />Vi una mascota</Link>
          </div>
          <Link href="/encontre" className="text-button hero-found"><Icon name="heart" />¿Encontraste una mascota? Reportá un animal encontrado <Icon name="arrow" /></Link>
          <p className="hero-note"><Icon name="shield" />Perros, gatos y otros animales. Fotos opcionales.</p>
        </div>
        <div className="hero-photo">
          <Image src="/images/dog-hero-generated.jpg" alt="Imagen ilustrativa de un golden retriever en un jardín" fill priority sizes="(max-width: 760px) 100vw, 50vw" />
        </div>
      </section>

      <HomeHowItWorks />
      <HomeLostAnimals />
      <HomeReviews />
      <section className="home-support" aria-labelledby="home-support-title"><span className="feature-icon"><Icon name="heart" /></span><div><p className="eyebrow">Apoyo voluntario</p><h2 id="home-support-title">Colaborá con MascoMatch</h2><p>Buscar y reportar mascotas es gratis. Si querés ayudarnos a seguir mejorando, podés hacer un aporte voluntario.</p></div><Link href="/apoyanos" className="button button-secondary">Conocé cómo apoyar <Icon name="arrow" /></Link></section>
    </main>
  );
}

