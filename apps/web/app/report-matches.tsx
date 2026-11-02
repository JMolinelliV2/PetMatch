"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { DogPhoto } from "./perdidos/dog-photo";
import type { LostDogNotice } from "@/lib/lost-dogs";
import { MatchScore } from "./ui/match-score";
import { ReportId } from "./ui/report-id";
import { Icon } from "./ui/pictogram";
type Result = { status: string; items: { animal: LostDogNotice; match: { id: string; explanation: string[]; final_score: number } }[] };
export function ReportMatches({ observationId }: { observationId: string }) {
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    const deadline = Date.now() + 300000;
    async function load() {
      try {
        const response = await fetch(`/api/matches/observations/${observationId}`, { cache: "no-store", signal: controller.signal });
        if (!response.ok) throw new Error(response.status === 401 ? "Volvé a iniciar sesión para consultar las coincidencias." : "No pudimos consultar las coincidencias. Tu reporte sigue guardado.");
        const data: Result = await response.json();
        if (controller.signal.aborted) return;
        setResult(data); setError("");
        if (["PENDING", "WAITING_ANALYSIS"].includes(data.status) && Date.now() < deadline) timer = setTimeout(load, 5000);
      } catch (cause) { if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "No pudimos consultar las coincidencias."); }
    }
    void load();
    return () => { controller.abort(); if (timer) clearTimeout(timer); };
  }, [observationId, refresh]);
  return <section className="report-analysis" aria-labelledby="matches-heading">
    <header className="report-analysis-header"><span className="report-analysis-icon"><Icon name="search" /></span><div><h2 id="matches-heading">Posibles coincidencias</h2>
      <p>Comparamos las características, la zona, la fecha y las fotos disponibles. La identidad necesita confirmación.</p></div></header>
    {(!result || ["PENDING", "WAITING_ANALYSIS"].includes(result.status)) && !error && <div className="report-analysis-progress" role="status"><span className="report-analysis-progress-icon"><span className="report-analysis-spinner" /></span><div><h3>Buscando avisos compatibles</h3><p>Comparamos tu reporte con las mascotas perdidas. Si hay posibles coincidencias, aparecerán acá.</p></div></div>}
    {result && !result.items.length && !["PENDING", "WAITING_ANALYSIS"].includes(result.status) && <p>No encontramos avisos con suficiente información compatible por ahora. Conservamos tu reporte para compararlo con nuevos avisos.</p>}
    {result?.items.map(item => <article className="match-card" key={item.match.id}><DogPhoto dog={item.animal} /><div><h3>{item.animal.name}</h3>
      <MatchScore score={item.match.final_score} />
      <ReportId id={item.animal.id} publicId={item.animal.public_id} />
      <ul>{item.match.explanation.map(reason => <li key={reason}>{reason}</li>)}</ul>
      <Link href={`/perdidos/${item.animal.id}`} className="text-button">Ver aviso</Link></div></article>)}
    {error && <p role="alert" className="notice notice-warning">{error}</p>}
    <button type="button" className="text-button" onClick={() => setRefresh(value => value + 1)}><Icon name="refresh" />Actualizar coincidencias</button>
  </section>;
}
