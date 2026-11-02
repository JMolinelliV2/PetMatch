import Link from "next/link";
import { lostDate } from "@/lib/lost-dogs";
import { observationDate, observationTraits } from "@/lib/public-observations";
import type { MapReportPoint } from "@/lib/public-observations";
import { DogPhoto } from "../perdidos/dog-photo";
import { Icon } from "../ui/pictogram";
import { ObservationPhoto } from "../ui/observation-photo";
import { ReportId } from "../ui/report-id";

export type { MapReportPoint } from "@/lib/public-observations";
const reportLabels = { lost: "Mascota perdida", sighting: "Avistamiento", found: "Mascota encontrada" };
const dateLabels = { lost: "Perdido desde el", sighting: "Visto el", found: "Encontrado el" };

export function MapReportCard({ point, href, onShowOnMap }: { point: MapReportPoint; href?: string; onShowOnMap?: () => void }) {
  const photo = point.layer === "lost"
    ? <DogPhoto dog={{ id: point.id, name: point.title, photo_url: point.photo_url || null }} href={href} />
    : <ObservationPhoto id={point.id} hasPhoto={Boolean(point.photo_url)} found={point.layer === "found"} onOpenReport={onShowOnMap} />;
  return <article className={`map-report-card map-report-${point.layer}`}>
    <div className="map-report-photo">{photo}</div>
    <div className="map-report-content">
      <span className="map-report-type">{reportLabels[point.layer]}</span>
      <h3>{href ? <Link href={href}>{point.title}</Link> : point.title}</h3>
      <ReportId id={point.id} publicId={point.public_id} label={point.layer === "lost" ? "ID del aviso" : "ID del reporte"} />
      <p className="map-report-species">{observationTraits(point)}</p>
      <p className="map-report-area"><Icon name="pin" />{point.area || "Zona aproximada"}</p>
      <p className="map-report-date"><Icon name="calendar" /><span>{dateLabels[point.layer]} <time dateTime={point.when}>{point.layer === "lost" ? lostDate(point.when) : observationDate(point.when)}</time></span></p>
      {point.layer !== "lost" && point.description_excerpt && <p className="map-report-description">{point.description_excerpt}</p>}
      {href && <Link href={href} className="text-button map-report-action">Ver aviso <Icon name="arrow" /></Link>}
      {!href && onShowOnMap && <button type="button" onClick={onShowOnMap} className="text-button map-report-action">Ver detalles en el mapa <Icon name="arrow" /></button>}
    </div>
  </article>;
}
