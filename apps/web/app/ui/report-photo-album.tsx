"use client";

import { useEffect, useState } from "react";
import { Icon } from "./pictogram";
import { PhotoViewer } from "./photo-viewer";
import type { ViewerPhoto } from "./photo-viewer";

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function AlbumImage({ src, alt, thumbnail = false }: { src: string | null; alt: string; thumbnail?: boolean }) {
  const [failed, setFailed] = useState(false);
  return src && !failed ? <img src={src} alt={alt} loading={thumbnail ? "lazy" : "eager"} onError={() => setFailed(true)} />
    : <span className="dog-photo-placeholder"><Icon name={src ? "camera" : "paw"} /><span>{src ? "Foto no disponible" : "Sin foto"}</span></span>;
}

export function ReportPhotoAlbum({ src, alt, galleryEndpoint }: { src: string | null; alt: string; galleryEndpoint: string }) {
  const [photos, setPhotos] = useState<ViewerPhoto[]>([]);
  const [selected, setSelected] = useState(0);
  const [expanded, setExpanded] = useState(false);
  const [loading, setLoading] = useState(Boolean(src));
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setPhotos([]); setSelected(0); setExpanded(false); setError("");
    if (!src) { setLoading(false); return () => controller.abort(); }
    setLoading(true);
    void fetch(galleryEndpoint, { cache: "no-store", signal: AbortSignal.any([controller.signal, AbortSignal.timeout(15000)]) }).then(async response => {
      if (!response.ok) throw new Error("No pudimos cargar las otras fotos del aviso.");
      const data: { items: { id: string; is_primary?: boolean }[] } = await response.json();
      if (!Array.isArray(data?.items) || data.items.some(photo => !photo || typeof photo.id !== "string" || !uuid.test(photo.id))) throw new Error("No pudimos cargar las otras fotos del aviso.");
      const ordered = [...data.items].sort((a, b) => Number(Boolean(b.is_primary)) - Number(Boolean(a.is_primary)));
      if (!controller.signal.aborted) setPhotos(ordered.map((photo, index) => ({
        id: photo.id, src: `${galleryEndpoint}/${encodeURIComponent(photo.id)}`, alt: `${alt}, foto ${index + 1}`,
      })));
    }).catch(() => { if (!controller.signal.aborted) setError("No pudimos cargar las otras fotos del aviso."); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [src, alt, galleryEndpoint, retry]);

  const currentIndex = Math.min(selected, Math.max(0, photos.length - 1));
  const current = photos[currentIndex];
  const imageSrc = current?.src ?? src;
  const viewerPhotos = photos.length ? photos : src ? [{ id: "cover", src, alt }] : [];

  return <div className="report-photo-album" role="group" aria-label={`Fotos del aviso: ${alt}`}>
    {imageSrc ? <button type="button" className="report-album-main dog-photo" aria-label={`Ampliar ${current?.alt ?? alt}`} aria-haspopup="dialog" onClick={() => setExpanded(true)}>
      <AlbumImage key={imageSrc} src={imageSrc} alt={current?.alt ?? alt} />
      {photos.length > 1 && <span className="report-album-count" aria-hidden="true"><Icon name="camera" />{currentIndex + 1} / {photos.length}</span>}
      <span className="photo-enlarge-mark" aria-hidden="true"><Icon name="expand" /></span>
    </button> : <div className="report-album-main dog-photo"><AlbumImage src={null} alt={alt} /></div>}
    {photos.length > 1 && <ul className="report-album-thumbnails" aria-label="Elegí una foto para verla en grande">
      {photos.map((photo, index) => <li key={photo.id}><button type="button" className="report-album-thumbnail" aria-label={`Ver ${photo.alt}${index === 0 ? ", foto principal" : ""}`} aria-pressed={currentIndex === index} onClick={() => setSelected(index)}>
        <AlbumImage src={photo.src} alt="" thumbnail />
        {currentIndex === index && <span className="report-album-selected" aria-hidden="true"><Icon name="check" /></span>}
      </button></li>)}
    </ul>}
    {loading && <p className="report-album-message" role="status">Cargando fotos del aviso…</p>}
    {error && <div className="report-album-error"><p role="status">{error}</p><button type="button" className="text-button" onClick={() => setRetry(value => value + 1)}>Reintentar</button></div>}
    {expanded && <PhotoViewer photos={viewerPhotos} title={alt} initialIndex={currentIndex} onClose={() => setExpanded(false)} />}
  </div>;
}
