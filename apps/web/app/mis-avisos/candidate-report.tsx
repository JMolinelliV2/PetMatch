"use client";
import { useState } from "react";
import { observationDate } from "@/lib/public-observations";
import { MatchFeedback } from "../match-feedback";
import type { FeedbackSaved } from "../match-feedback";
import { LocationMap } from "../location-map";
import { ObservationPhoto } from "../ui/observation-photo";
import { SightingComparison } from "../ui/sighting-comparison";
import { MatchScore } from "../ui/match-score";
import { ReportId } from "../ui/report-id";
import { useMatchVisibility } from "../product-tracking";

export type Candidate = {
  match: { id: string; status: string; explanation: string[]; final_score?: number; presentation?:string };
  observation: { id: string; public_id?: string; description: string; public_location: string | null; observed_at: string;
    latitude: number | null; longitude: number | null; source_type: string; photo_url: string | null;
    matching_status: string; linked_to_notice: boolean };
};

export function CandidateReport({ candidate, caseId, caseActive, onSaved }: { candidate: Candidate; caseId: string; caseActive: boolean; onSaved: (result: FeedbackSaved) => void }) {
  const [mapOpen, setMapOpen] = useState(false);
  const { match, observation } = candidate;
  const visibility=useMatchVisibility(match.presentation);
  return <article ref={visibility} className="analysis-result case-candidate">
    <div className="case-candidate-summary">
      <div className="case-candidate-photo"><ObservationPhoto id={observation.id} hasPhoto={Boolean(observation.photo_url)} found={observation.source_type === "FOUND_ANIMAL"} /></div>
      <div>
        <ReportId id={observation.id} publicId={observation.public_id} label="ID del reporte" />
        {observation.linked_to_notice && <SightingComparison status={observation.matching_status} reviewStatus={match.status} />}
        {(!observation.linked_to_notice || (observation.matching_status === "POSSIBLE_MATCH" && match.status !== "FALSE_MATCH")) && <MatchScore score={match.final_score} />}
        <p className="field-help">{observation.source_type === "FOUND_ANIMAL" ? "Encontrado" : "Visto"} el <time dateTime={observation.observed_at}>{observationDate(observation.observed_at)}</time> (hora de Uruguay)</p>
        <p className="field-help">{observation.public_location || "Zona indicada en el reporte"}</p>
      </div>
    </div>
    <p className="case-candidate-description">{observation.description}</p>
    <ul>{match.explanation.map(reason => <li key={reason}>{reason}</li>)}</ul>
    {observation.latitude != null && observation.longitude != null && <><button type="button" className="text-button" aria-expanded={mapOpen} onClick={() => setMapOpen(value => !value)}>{mapOpen ? "Ocultar lugar" : "Ver lugar del avistamiento"}</button>{mapOpen && <LocationMap latitude={observation.latitude} longitude={observation.longitude} editable={false} label="Lugar del reporte compartido de forma privada con el dueño" />}</>}
    <MatchFeedback id={match.id} caseId={caseId} caseActive={caseActive} status={match.status} onSaved={onSaved} />
  </article>;
}
