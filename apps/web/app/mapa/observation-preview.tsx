"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { observationDate, observationTraits, publicObservationsEndpoint } from "@/lib/public-observations";
import { speciesLabel } from "@/lib/lost-dogs";
import type { PublicObservation } from "@/lib/public-observations";
import type { ObservationMapSelection } from "@/lib/observation-map-marker";
import { ObservationPhoto } from "../ui/observation-photo";
import { Icon } from "../ui/pictogram";
import { ReportId } from "../ui/report-id";
import { ObservationEditLink } from "../ui/observation-edit-link";
import { PublicationAuthor } from "../ui/publication-author";

function ObservationPreview({ id, onLayout, onRefresh }: { id: string; onLayout: () => void; onRefresh: () => void }) {
  const [report, setReport] = useState<PublicObservation | null>(null);
  const [missing, setMissing] = useState(false);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setReport(null); setMissing(false); setError("");
    void fetch(`${publicObservationsEndpoint}/${encodeURIComponent(id)}`, { cache: "no-store", signal: AbortSignal.any([controller.signal, AbortSignal.timeout(15000)]) }).then(async response => {
      if (response.status === 404) { if (!controller.signal.aborted) setMissing(true); return; }
      if (!response.ok) throw new Error("No pudimos cargar los detalles.");
      const data: PublicObservation = await response.json();
      if (!controller.signal.aborted) setReport(data);
    }).catch(() => { if (!controller.signal.aborted) setError("No pudimos cargar los detalles."); });
    return () => controller.abort();
  }, [id, refresh]);
  useEffect(() => { onLayout(); }, [report, missing, error, onLayout]);
  if (missing) return <div className="home-map-preview observation-map-preview"><h3>Este reporte ya no está disponible</h3><button type="button" className="text-button" onClick={onRefresh}>Actualizar mapa</button></div>;
  if (error) return <div className="home-map-preview observation-map-preview"><p role="alert">{error}</p><button type="button" className="text-button" onClick={() => setRefresh(value => value + 1)}>Reintentar</button></div>;
  if (!report) return <div className="home-map-preview observation-map-preview"><p role="status">Cargando detalles del reporte…</p></div>;
  const found = report.source_type === "FOUND_ANIMAL";
  return <div className={`home-map-preview observation-map-preview map-report-${found ? "found" : "sighting"}`}>
    <ObservationPhoto id={report.id} hasPhoto={Boolean(report.photo_url)} found={found} onLoad={onLayout} />
    <span className="map-report-type">{found ? "Mascota encontrada" : "Avistamiento"}</span>
    <h3>{speciesLabel(report.species)} {found ? "encontrado" : "avistado"}</h3>
    <ReportId id={report.id} publicId={report.public_id} label="ID del reporte" copyable />
    <PublicationAuthor name={report.publisher_name} />
    <p className="home-map-traits">{observationTraits(report)}</p>
    <p className="map-report-area"><Icon name="pin" />{report.public_location || "Zona aproximada"}</p>
    <p className="map-report-date"><Icon name="calendar" /><span>{found ? "Encontrado el" : "Visto el"} <time dateTime={report.observed_at}>{observationDate(report.observed_at)}</time></span></p>
    <p className="observation-map-help">Hora de Uruguay · Ubicación aproximada</p>
    <h4 className="observation-map-description-title">Detalles del reporte</h4>
    <p className="observation-map-description">{report.description}</p>
    <ObservationEditLink id={report.id} found={found} onLayout={onLayout} />
    {report.related_notice && <div className="observation-map-related"><p>Enviado para el aviso de <strong>{report.related_notice.name}</strong>. El vínculo no confirma que sea la misma mascota.</p><ReportId id={report.related_notice.id} publicId={report.related_notice.public_id} /><Link className="text-button" href={`/perdidos/${encodeURIComponent(report.related_notice.id)}?origen=mapa`}>Ver aviso relacionado <Icon name="arrow" /></Link></div>}
  </div>;
}

export function ObservationLocationPreview({ selection, onRefresh }: { selection: ObservationMapSelection; onRefresh: () => void }) {
  const [selectedId, setSelectedId] = useState(selection.selectedId);
  const point = selection.points.find(item => item.id === selectedId) || selection.points[0];
  return <div className="home-map-popup-content observation-map-popup-content">
    {selection.points.length > 1 && <label className="field-label">{selection.points.length} reportes en esta zona<select className="form-input" value={point.id} onChange={event => setSelectedId(event.target.value)}>{selection.points.map(item => <option key={item.id} value={item.id}>{item.title}{item.public_id && ` · ${item.public_id}`} · {observationTraits(item)} · {observationDate(item.when)}</option>)}</select></label>}
    <ObservationPreview key={point.id} id={point.id} onLayout={selection.onLayout} onRefresh={onRefresh} />
  </div>;
}
