import { dogTraits, speciesLabel } from "./lost-dogs";
import type { SupportedSpecies } from "./species";
import type { LostMapPoint } from "./lost-map-marker";

export const publicObservationsEndpoint = `${(process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1").replace(/\/$/, "")}/public/observations`;
export type MapReportPoint = LostMapPoint & {
  layer: "lost" | "sighting" | "found";
  species: SupportedSpecies; area: string | null; when: string; url: string | null;
  sex?: string; primary_color?: string; size?: string; description_excerpt?: string;
};
export type PublicObservation = {
  id: string; public_id?: string; species: SupportedSpecies; sex: string; primary_color: string; size: string;
  description: string; source_type: "USER_SIGHTING" | "FOUND_ANIMAL";
  public_location: string | null; observed_at: string; photo_url: string | null;
  related_notice: { id: string; public_id?: string; name: string } | null;
  publisher_name?: string | null;
};

export function observationTraits(animal: { species: string; sex?: string; size?: string; primary_color?: string }): string {
  return [speciesLabel(animal.species), ...dogTraits({ breed: "unknown", sex: animal.sex || "unknown", size: animal.size || "unknown", primary_color: animal.primary_color || "unknown" })].join(" · ");
}

export function observationDate(value: string): string {
  const date = new Date(value);
  return Number.isFinite(date.getTime()) ? new Intl.DateTimeFormat("es-UY", { dateStyle: "medium", timeStyle: "short", timeZone: "America/Montevideo" }).format(date) : "Fecha no indicada";
}
