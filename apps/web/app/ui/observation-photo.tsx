"use client";
import { publicObservationsEndpoint } from "@/lib/public-observations";
import { ReportPhoto } from "./report-photo";

export function ObservationPhoto({ id, hasPhoto, found = false, onLoad, onOpenReport }: { id: string; hasPhoto: boolean; found?: boolean; onLoad?: () => void; onOpenReport?: () => void }) {
  const endpoint = `${publicObservationsEndpoint}/${encodeURIComponent(id)}`;
  return <ReportPhoto src={hasPhoto ? `${endpoint}/photo` : null} alt={found ? "Foto de la mascota encontrada" : "Foto de la mascota avistada"} galleryEndpoint={`${endpoint}/photos`} placeholderIcon={found ? "heart" : "eye"} onLoad={onLoad} onOpenReport={onOpenReport} />;
}
