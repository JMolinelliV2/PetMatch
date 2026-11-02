"use client";

import Image from "next/image";
import { useEffect, useRef, useState } from "react";
import { Icon } from "./ui/pictogram";
import "./home-how-it-works.css";

const steps = [
  {
    id: "notice", tone: "coral", icon: "camera",
    image: { src: "/images/how-notice-manypixels.svg", width: 500, height: 500, kind: "library" },
    title: "Publicá su aviso.",
    description: [
      "Publicar un aviso es gratis. Si querés colaborar con las mejoras de MascoMatch, podés hacer una donación voluntaria. Creá una cuenta y confirmá tu correo para publicar. Contanos cómo es tu mascota, dónde la viste por última vez y cuándo.",
      "Una foto clara ayuda a reconocerla y facilita compartir el aviso. Las fotos son opcionales: podés agregarlas después desde Mis avisos.",
    ],
  },
  {
    id: "sighting", tone: "blue", icon: "pin",
    image: { src: "/images/how-sighting-reference.webp", width: 1536, height: 1024, kind: "adapted" },
    title: "Cada pista suma.",
    description: [
      "Si reconocés a una mascota publicada, enviá un avistamiento desde su aviso indicando dónde y cuándo la viste. Sumá una foto si tenés; ese reporte breve se puede enviar sin cuenta.",
      "Si todavía no hay un aviso, con una cuenta podés reportarla desde “Vi una mascota”. Si la mascota está a salvo con vos, usá “Encontré una mascota” para que su familia pueda encontrarla.",
    ],
  },
  {
    id: "review", tone: "blue", icon: "spark",
    image: { src: "/images/how-review-reference.webp", width: 1685, height: 933, kind: "adapted" },
    title: "La tecnología conecta. Vos revisás.",
    description: [
      "La IA de MascoMatch compara fotos, características, zona y fecha para sugerir posibles coincidencias. Vos revisás las imágenes y los detalles para evaluar si se trata de tu mascota.",
      "Las alertas llegan a tu cuenta y, según tus preferencias, también por correo. Los avistamientos enviados desde tu aviso siempre llegan como pistas, aunque la comparación esté pendiente o no resulte compatible.",
    ],
  },
  {
    id: "reunion", tone: "green", icon: "heart",
    image: { src: "/images/how-reunion-reference.webp", width: 1222, height: 1287, kind: "adapted" },
    title: "El reencuentro cierra la búsqueda.",
    description: [
      "Confirmar que un avistamiento corresponde a tu mascota registra una pista y mantiene la búsqueda abierta.",
      "Cuando ya esté con vos, marcá “Ya la recuperé” desde Mis avisos. El aviso deja de aparecer en el listado público y podés compartir una reseña sobre tu experiencia.",
    ],
  },
] as const;

type Route = { path: string; width: number; height: number };

export function HomeHowItWorks() {
  const journey = useRef<HTMLOListElement>(null);
  const progressPath = useRef<SVGPathElement>(null);
  const [route, setRoute] = useState<Route | null>(null);

  useEffect(() => {
    const list = journey.current;
    if (!list) return;

    const rows = Array.from(list.querySelectorAll<HTMLElement>(".how-journey-step"));
    const markers = Array.from(list.querySelectorAll<HTMLElement>("[data-how-marker]"));
    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    let frame = 0;
    let needsLayout = true;
    let disposed = false;

    function update() {
      frame = 0;
      if (!list || disposed) return;
      const bounds = list.getBoundingClientRect();
      const points = markers.map(marker => {
        const rect = marker.getBoundingClientRect();
        return { x: rect.left + rect.width / 2 - bounds.left, y: rect.top + rect.height / 2 - bounds.top };
      });
      if (points.length !== steps.length || !bounds.width || !bounds.height) return;

      if (needsLayout) {
        const bend = window.matchMedia("(max-width: 760px)").matches ? 12 : 58;
        let path = `M ${points[0].x} ${points[0].y}`;
        points.slice(1).forEach((point, index) => {
          const previous = points[index];
          const offset = (index % 2 === 0 ? 1 : -1) * bend;
          const distance = point.y - previous.y;
          path += ` C ${previous.x + offset} ${previous.y + distance * .3}, ${point.x + offset} ${point.y - distance * .3}, ${point.x} ${point.y}`;
        });
        setRoute({ path, width: bounds.width, height: bounds.height });
        needsLayout = false;
      }

      const readingLine = window.innerHeight * .6 - bounds.top;
      const first = points[0].y;
      const last = points[points.length - 1].y;
      const progress = Math.min(1, Math.max(0, (readingLine - first) / Math.max(1, last - first)));
      if (progressPath.current) progressPath.current.style.strokeDashoffset = String(1000 * (1 - progress));
      const active = points.reduce((current, point, index) => point.y <= readingLine ? index : current, -1);
      rows.forEach((row, index) => {
        row.dataset.visited = String(index <= active);
        row.dataset.current = String(index === active);
      });
    }

    function schedule(layout = false) {
      needsLayout ||= layout;
      if (!frame) frame = window.requestAnimationFrame(update);
    }

    const onScroll = () => schedule();
    const onResize = () => schedule(true);
    const resizeObserver = typeof ResizeObserver !== "undefined" ? new ResizeObserver(onResize) : null;
    resizeObserver?.observe(list);
    rows.forEach(row => resizeObserver?.observe(row));
    const enterObserver = typeof IntersectionObserver !== "undefined" ? new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        if (!motion.matches) (entry.target as HTMLElement).dataset.entered = "true";
        enterObserver?.unobserve(entry.target);
      });
    }, { threshold: .12 }) : null;
    rows.forEach(row => enterObserver?.observe(row));

    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onResize);
    // Recalculate after fonts settle, including browsers without ResizeObserver.
    document.fonts?.ready.then(() => { if (!disposed) schedule(true); });
    schedule(true);

    return () => {
      disposed = true;
      window.cancelAnimationFrame(frame);
      resizeObserver?.disconnect();
      enterObserver?.disconnect();
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onResize);
    };
  }, []);

  // The initial SVG mount happens after the first layout calculation.
  useEffect(() => {
    const list = journey.current;
    if (!route || !list || !progressPath.current) return;
    const markers = list.querySelectorAll<HTMLElement>("[data-how-marker]");
    const first = markers[0].getBoundingClientRect();
    const last = markers[markers.length - 1].getBoundingClientRect();
    const start = first.top + first.height / 2;
    const end = last.top + last.height / 2;
    const progress = Math.min(1, Math.max(0, (window.innerHeight * .6 - start) / Math.max(1, end - start)));
    progressPath.current.style.strokeDashoffset = String(1000 * (1 - progress));
  }, [route]);

  return <section id="como-funciona" className="how-it-works" aria-labelledby="how-title">
    <header className="how-heading">
      <h2 id="how-title">Cómo funciona <span className="title-accent">MascoMatch</span></h2>
      <p className="how-intro">Desde el primer aviso hasta el reencuentro,<br className="how-desktop-break" /> cada persona puede sumar una pista.</p>
    </header>

    <ol ref={journey} className="how-journey" data-route-ready={route !== null} aria-label="Los cuatro pasos de MascoMatch">
      {steps.map((step, index) => <li key={step.id} id={`how-${step.id}`} className="how-journey-step" data-tone={step.tone}>
        {index === 0 && route && <svg className="how-route how-route-layer" viewBox={`0 0 ${route.width} ${route.height}`} preserveAspectRatio="none" aria-hidden="true" focusable="false">
          <path className="how-route-base" d={route.path} />
          <path ref={progressPath} className="how-route-progress" d={route.path} pathLength="1000" />
        </svg>}
        <span className="how-checkpoint" data-how-marker aria-hidden="true">0{index + 1}</span>
        <div className="how-illustration" data-image-kind={step.image.kind} aria-hidden="true">
          <Image src={step.image.src} alt="" width={step.image.width} height={step.image.height} sizes="(max-width: 760px) 300px, (max-width: 1000px) 280px, 360px" />
          <span className="how-illustration-stamp"><Icon name={step.icon} /></span>
        </div>
        <div className="how-step-copy">
          <h3><span className="sr-only">Paso {index + 1}: </span>{step.title}</h3>
          <div className="how-step-description">
            {step.description.map((paragraph, paragraphIndex) => <p key={paragraphIndex}>{paragraph}</p>)}
          </div>
        </div>
      </li>)}
    </ol>
  </section>;
}
