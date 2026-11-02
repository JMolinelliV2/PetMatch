"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { dogTraits, lostDate, lostDogsEndpoint, speciesLabel } from "@/lib/lost-dogs";
import type { LostDogNotice } from "@/lib/lost-dogs";
import type { LostMapPoint, LostMapSelection } from "@/lib/lost-map-marker";
import { DogPhoto } from "./perdidos/dog-photo";
import { Icon } from "./ui/pictogram";
import { ReportId } from "./ui/report-id";
import { PublicationAuthor } from "./ui/publication-author";
import { PublicationEditLink } from "./ui/publication-edit-link";

function LostMapPreview({ point, origin, onLayout, onRefresh }: { point: LostMapPoint; origin: "inicio" | "mapa"; onLayout: () => void; onRefresh: () => void }) {
  const [animal, setAnimal] = useState<LostDogNotice | null>(null);
  const [error, setError] = useState("");
  const [missing, setMissing] = useState(false);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setAnimal(null); setError(""); setMissing(false);
    void fetch(`${lostDogsEndpoint}/${encodeURIComponent(point.id)}`, { cache: "no-store", signal: controller.signal }).then(async response => {
      if (response.status === 404) { if (!controller.signal.aborted) setMissing(true); return; }
      if (!response.ok) throw new Error("No pudimos cargar la miniatura.");
      const data: LostDogNotice = await response.json();
      if (!controller.signal.aborted) setAnimal(data);
    }).catch(cause => { if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "No pudimos cargar la miniatura."); });
    return () => controller.abort();
  }, [point.id, refresh]);
  useEffect(() => { onLayout(); }, [animal, error, missing, onLayout]);
  const href = `/perdidos/${encodeURIComponent(point.id)}?origen=${origin}`;
  return <div className="home-map-preview">
    {missing ? <><h4>Este aviso ya no está disponible</h4><p>Puede que la mascota haya sido encontrada o que el aviso se haya cerrado.</p><button type="button" className="text-button" onClick={onRefresh}>Actualizar mapa</button></>
      : error ? <><h4>{point.title}</h4><p role="alert">{error}</p><button type="button" className="text-button" onClick={() => setRefresh(value => value + 1)}>Reintentar</button></>
        : !animal ? <><h4>{point.title}</h4><p role="status">Cargando miniatura…</p></>
          : <><DogPhoto dog={animal} href={href} /><span className="lost-status">Sigue perdido</span><h4>{animal.name}</h4><ReportId id={animal.id} publicId={animal.public_id} /><PublicationAuthor name={animal.publisher_name} /><PublicationEditLink id={animal.id} kind="lost_case" compact onLayout={onLayout} /><p className="home-map-traits">{[speciesLabel(animal.species), ...dogTraits(animal)].join(" · ")}</p><p>{animal.public_location || "Zona aproximada"}</p><p className="home-map-date">Perdido desde el {lostDate(animal.lost_at)}</p><Link href={href} className="button button-primary">Ver aviso <Icon name="arrow" /></Link></>}
  </div>;
}

export function LostLocationPreview({ selection, origin, onRefresh }: { selection: LostMapSelection; origin: "inicio" | "mapa"; onRefresh: () => void }) {
  const [selectedId, setSelectedId] = useState(selection.points[0].id);
  const point = selection.points.find(item => item.id === selectedId) || selection.points[0];
  return <div className="home-map-popup-content">
    {selection.points.length > 1 && <label className="field-label">{selection.points.length} mascotas en esta zona<select className="form-input" value={point.id} onChange={event => setSelectedId(event.target.value)}>{selection.points.map(item => <option value={item.id} key={item.id}>{item.title}{item.public_id && ` · ${item.public_id}`}</option>)}</select></label>}
    <LostMapPreview key={point.id} point={point} origin={origin} onLayout={selection.onLayout} onRefresh={onRefresh} />
  </div>;
}
