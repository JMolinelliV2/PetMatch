"use client";
import { useEffect, useState } from "react";
import { Icon } from "./ui/pictogram";
import { UserAvatar } from "./ui/user-avatar";

type PublicReview = { id: string; display_name: string; rating: number; comment: string; created_at: string; avatar_version?: string | null };

export function HomeReviews() {
  const [items, setItems] = useState<PublicReview[]>([]);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    const reload = () => setRefresh(value => value + 1);
    window.addEventListener("focus", reload); window.addEventListener("mascomatch:reviews", reload);
    void fetch("/api/reviews", { cache: "no-store", signal: controller.signal }).then(async response => {
      if (!response.ok) throw new Error("Reviews unavailable");
      const data = await response.json();
      if (!controller.signal.aborted) setItems(data.items);
    }).catch(() => { if (!controller.signal.aborted) setItems([]); });
    return () => { controller.abort(); window.removeEventListener("focus", reload); window.removeEventListener("mascomatch:reviews", reload); };
  }, [refresh]);
  return <ReviewsSection items={items} />;
}

export function ReviewsSection({ items }: { items: PublicReview[] }) {
  const [expanded, setExpanded] = useState(false);
  if (!items.length) return null;
  return <section className="home-reviews" aria-labelledby="home-reviews-title">
    <div className="home-reviews-panel">
      <header className="home-reviews-heading"><h2 id="home-reviews-title">Quienes buscaron a su mascota nos cuentan</h2></header>
      <div id="home-reviews-list" className={`home-reviews-grid${items.length === 1 ? " is-single" : ""}`}>
        {items.map((item, index) => <article className="home-review-card" key={item.id} hidden={!expanded && index >= 2}>
          <div className="review-card-top">
            <span className="review-quote" aria-hidden="true">“</span>
            <p className="review-stars" role="img" aria-label={`${item.rating} de 5 estrellas`}><span aria-hidden="true">{"★".repeat(item.rating)}<span className="review-stars-empty">{"☆".repeat(5 - item.rating)}</span></span></p>
          </div>
          <blockquote><p>{item.comment}</p></blockquote>
          <footer><UserAvatar name={item.display_name} src={item.avatar_version ? `/api/reviews/${encodeURIComponent(item.id)}/avatar?v=${encodeURIComponent(item.avatar_version)}` : null} className="review-avatar" /><div className="review-author"><strong>{item.display_name}</strong><time dateTime={item.created_at}>{new Intl.DateTimeFormat("es-UY", { month: "long", year: "numeric", timeZone: "America/Montevideo" }).format(new Date(item.created_at))}</time></div></footer>
        </article>)}
      </div>
      {items.length > 2 && <div className="home-reviews-actions"><button type="button" className="button button-secondary home-reviews-more" aria-controls="home-reviews-list" aria-expanded={expanded} onClick={() => setExpanded(value => !value)}>{expanded ? "Ver menos reseñas" : "Ver más reseñas"}<Icon name="chevron" /></button></div>}
    </div>
  </section>;
}
