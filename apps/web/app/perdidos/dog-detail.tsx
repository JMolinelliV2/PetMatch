"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { dogTraits, lostDate, lostDogsEndpoint, sexLabel, speciesLabel } from "@/lib/lost-dogs";
import type { LostDogNotice } from "@/lib/lost-dogs";
import { ReportPhotoAlbum } from "../ui/report-photo-album";
import { ReportPublication } from "../report-publication";
import { ReportId } from "../ui/report-id";
import { PublicationAuthor } from "../ui/publication-author";
import { PublicationEditLink } from "../ui/publication-edit-link";

export function DogDetail({ id }: { id: string }) {
  const [dog, setDog] = useState<LostDogNotice | null>(null);
  const [error, setError] = useState("");
  const [missing, setMissing] = useState(false);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    const reload = () => setRefresh(value => value + 1);
    window.addEventListener("focus", reload);
    window.addEventListener("mascomatch:cases", reload);
    return () => { window.removeEventListener("focus", reload); window.removeEventListener("mascomatch:cases", reload); };
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    setError(""); setMissing(false); setDog(null);
    void fetch(`${lostDogsEndpoint}/${encodeURIComponent(id)}`, { signal: controller.signal, cache: "no-store" }).then(async response => {
      if (response.status === 404 || response.status === 422) { if (!controller.signal.aborted) setMissing(true); return; }
      if (!response.ok) throw new Error("No pudimos cargar el aviso. Intentá de nuevo en un momento.");
      const data: LostDogNotice = await response.json();
      if (!controller.signal.aborted) setDog(data);
    }).catch(cause => { if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "No pudimos cargar el aviso."); });
    return () => controller.abort();
  }, [id, refresh]);

  return <main id="main-content" className="page dog-detail-page">
    {missing ? <><h1>Este aviso ya no está disponible</h1><p className="page-intro">Puede que la mascota haya sido encontrada o que su dueño haya cerrado el aviso.</p></>
      : error ? <div className="notice notice-warning" role="alert">{error} <button type="button" className="text-button" onClick={() => setRefresh(value => value + 1)}>Reintentar</button></div>
      : !dog ? <p role="status" className="page-intro">Cargando aviso…</p>
      : <article className="dog-detail">
        <ReportPhotoAlbum key={dog.id} src={dog.photo_url ? `${lostDogsEndpoint}/${encodeURIComponent(dog.id)}/photo` : null} galleryEndpoint={`${lostDogsEndpoint}/${encodeURIComponent(dog.id)}/photos`} alt={`Foto de ${dog.name}`} />
        <div className="dog-detail-info">
          <div className="dog-detail-status"><span className="lost-status">Sigue perdido</span><PublicationEditLink id={dog.id} kind="lost_case" /></div>
          <h1>{dog.name}</h1>
          <ReportId id={dog.id} publicId={dog.public_id} copyable />
          <PublicationAuthor name={dog.publisher_name} />
          <p className="dog-traits">{[speciesLabel(dog.species), ...dogTraits(dog)].join(" · ")}</p>
          <dl className="review-details">
            <div><dt>Sexo</dt><dd>{sexLabel(dog.sex)}</dd></div>
            <div><dt>Zona donde se perdió</dt><dd>{dog.public_location || "No indicada"}</dd></div>
            <div><dt>Perdido desde el</dt><dd><time dateTime={dog.lost_at}>{lostDate(dog.lost_at)}</time></dd></div>
          </dl>
          <h2>Descripción</h2><p className="dog-full-description">{dog.description || "Sin descripción adicional."}</p>
          <div className="dog-help"><h2>¿La viste?</h2><p>Compartí el lugar y fotos si tenés. El avistamiento quedará vinculado a este aviso.</p><Link href={`/avistamiento?aviso=${dog.id}`} className="button button-primary">Publicar un avistamiento</Link></div>
          <ReportPublication id={dog.id}/>
        </div>
      </article>}
  </main>;
}
