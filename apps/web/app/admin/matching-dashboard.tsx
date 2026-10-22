"use client";

import { useEffect, useId, useRef, useState } from "react";
import { ReportId } from "../ui/report-id";
import { AdminDateRange, periodQuery } from "./date-range";
import type { AdminPeriod } from "./date-range";
import { AdminFieldLabel, AdminHeading, AdminLabel } from "./admin-info";
import {useAdminReload} from "./admin-reload";

type Outcome = "positive" | "false" | "uncertain" | "pending";
type Counts = Record<Outcome, number> & { total: number; decided: number; reviewed: number; positive_rate: number | null; review_rate: number | null };
type Recommendation = {
  feature_score:number;visual_score:number|null;raw_visual_similarity:number|null;geo_score:number;temporal_score:number;evidence_coverage:number;distance_meters:number;
  recommendation_snapshot:Record<string,unknown>;first_viewed_at:string|null;first_viewed_rank:number|null;best_viewed_rank:number|null;
  id: string; lost_case_public_id: string; observation_public_id: string; pet_name: string; species: string;
  source: "GENERAL" | "LINKED"; outcome: Outcome; recommended_score: number | null; current_score: number;
  recommended_at: string; feedback_at: string | null; case_status: string; active: boolean; history_count: number; legacy: boolean;
};
type Dashboard = { summary: Counts; sources: (Counts & { source: "GENERAL" | "LINKED" })[]; legacy_count: number; items: Recommendation[]; total: number; limit: number; offset: number; generated_at: string };
type FeedbackEvent = { id: string; status: string; previous_status: string | null; recovered: boolean; score: number | null; legacy: boolean; created_at: string };
const labels: Record<Outcome, string> = { positive: "Confirmadas", false: "Falsas", uncertain: "Dudosas", pending: "Sin respuesta" };
const outcomeClasses: Record<Outcome, string> = { positive: "admin-outcome-positive", false: "admin-outcome-false", uncertain: "admin-outcome-uncertain", pending: "admin-outcome-pending" };
const feedbackLabels: Record<string, string> = { RESOLVED: "Es mi mascota", FALSE_MATCH: "No es mi mascota", CONFIRMED_RELEVANT: "Podría ser; todavía no está seguro" };
const sourceLabels = { GENERAL: "Búsqueda general", LINKED: "Desde un aviso" };
const caseLabels: Record<string, string> = { ACTIVE: "Búsqueda activa", FOUND: "Animal encontrado", CLOSED: "Aviso cerrado", CANCELLED: "Aviso cancelado" };
const number = (value: number) => new Intl.NumberFormat("es-UY").format(value);
const percentage = (value: number | null) => value === null ? "—" : `${new Intl.NumberFormat("es-UY", { maximumFractionDigits: 1 }).format(value)}%`;
const date = (value: string) => new Intl.DateTimeFormat("es-UY", { dateStyle: "medium", timeStyle: "short", timeZone: "America/Montevideo" }).format(new Date(value));
const score = (value: number | null) => value === null ? "Sin puntaje" : `${new Intl.NumberFormat("es-UY", { maximumFractionDigits: 2 }).format(value)} / 1`;

function ResponseHistory({ id }: { id: string }) {
  const {version,beginRequest}=useAdminReload();
  const [events, setEvents] = useState<FeedbackEvent[] | null>(null);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    const controller = new AbortController(); const finish=beginRequest();
    setError("");
    void fetch(`/api/admin/matching/${id}/history`, { cache: "no-store", signal: AbortSignal.any([controller.signal,AbortSignal.timeout(20000)]) }).then(async response => {
      if (!response.ok) throw new Error("No pudimos consultar el historial.");
      const data: { items: FeedbackEvent[] } = await response.json();
      if (!controller.signal.aborted) setEvents(data.items);
    }).catch(cause => { if (!controller.signal.aborted) setError(cause.message); }).finally(finish);
    return () => {controller.abort();finish();};
  }, [id, refresh, version, beginRequest]);
  return <div className="admin-response-history">
    <AdminHeading level={4} label="Historial de respuestas" />
    {error ? <p role="alert">{error} <button type="button" className="text-button" onClick={() => setRefresh(value => value + 1)}>Reintentar</button></p>
      : !events ? <p role="status">Cargando respuestas…</p>
        : !events.length ? <p>El dueño todavía no respondió.</p>
          : <ol>{events.map(event => <li key={event.id}><strong>{feedbackLabels[event.status] || event.status}{event.recovered && " · Ya la recuperó"}</strong><time dateTime={event.created_at}>{date(event.created_at)}</time>{event.legacy && <span className="field-help">Respuesta anterior al seguimiento; no hay historial previo disponible.</span>}</li>)}</ol>}
    {events && events.length === 50 && <p className="field-help">Se muestran las últimas 50 respuestas.</p>}
  </div>;
}

export function MatchingDashboard({period,onPeriodChange,fixedFilters}:{period:AdminPeriod;onPeriodChange:(value:AdminPeriod)=>void;fixedFilters?:Record<string,string>}) {
  const {version,beginRequest}=useAdminReload();
  const appliedReload=useRef(version);
  const fieldId = useId();
  const [source, setSource] = useState("all");
  const [dataset, setDataset] = useState("all");
  const [result, setResult] = useState("all");
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState("");
  const [history, setHistory] = useState<string | null>(null);
  useEffect(() => {
    const controller = new AbortController(); const finish=beginRequest();
    if(appliedReload.current===version){setData(null);setHistory(null);}
    appliedReload.current=version;setError("");
    const query = new URLSearchParams({ days: "0", ...periodQuery(period), source, dataset, result, offset: String(offset),...fixedFilters });
    void fetch(`/api/admin/matching?${query}`, { cache: "no-store", signal: AbortSignal.any([controller.signal, AbortSignal.timeout(20000)]) }).then(async response => {
      if (!response.ok) throw new Error(response.status === 401 || response.status === 403 ? "Tu sesión no tiene acceso al panel. Ingresá con la cuenta administradora y su correo confirmado." : "No pudimos cargar las recomendaciones.");
      const next: Dashboard = await response.json();
      if (!controller.signal.aborted) setData(next);
    }).catch(cause => { if (!controller.signal.aborted) setError(cause instanceof Error && cause.name !== "TimeoutError" ? cause.message : "No pudimos cargar el seguimiento. Revisá tu sesión e intentá nuevamente."); }).finally(finish);
    return () => {controller.abort();finish();};
  }, [period, source, dataset, result, offset, version, beginRequest,JSON.stringify(fixedFilters)]);
  function filter(setter: (value: string) => void, value: string) { setter(value); setOffset(0); }
  const counts = data?.summary;
  return <section className="admin-matching" aria-labelledby="admin-matching-title">
    <div className="admin-section-heading"><div><AdminHeading level={2} id="admin-matching-title" label="Resultados de las coincidencias" /><p>Seguimiento de las recomendaciones del sistema y las respuestas de los dueños.</p></div></div>
    <AdminDateRange value={period} onApply={next => { onPeriodChange(next); setOffset(0); }} />
    <p className="field-help">El período se aplica a la fecha en que se generó la recomendación.</p>
    <div className="admin-matching-filters">
      {!fixedFilters&&<div className="field-label"><AdminFieldLabel htmlFor={`${fieldId}-source`} label="Origen" help="Permite consultar recomendaciones de la búsqueda general o de reportes enviados desde una ficha que fueron considerados una posible coincidencia." /><select id={`${fieldId}-source`} className="form-input" value={source} onChange={event => filter(setSource, event.target.value)}><option value="all">Todos los orígenes</option><option value="GENERAL">Búsqueda general</option><option value="LINKED">Desde un aviso</option></select></div>}
      <div className="field-label"><AdminFieldLabel htmlFor={`${fieldId}-dataset`} label="Registro" help="Distingue registros creados desde el inicio del seguimiento de registros anteriores recuperados de la información disponible. Los anteriores pueden tener un historial incompleto." /><select id={`${fieldId}-dataset`} className="form-input" value={dataset} onChange={event => filter(setDataset, event.target.value)}><option value="all">Todos los registros</option><option value="live">Desde el inicio del seguimiento</option><option value="legacy">Registros anteriores</option></select></div>
    </div>
    {error && <p role="alert" className="notice notice-warning">{error}</p>}
    {!data && !error && <p role="status" className="admin-matching-loading">Preparando el seguimiento de coincidencias…</p>}
    {data && counts && <>
      <div className="admin-matching-summary">
        <div className="admin-metric"><AdminLabel label="Recomendaciones únicas" /><strong>{number(counts.total)}</strong><small>Un aviso y un reporte, una recomendación.</small></div>
        {(["positive", "false", "uncertain", "pending"] as const).map(outcome => <div key={outcome} className={`admin-metric ${outcomeClasses[outcome]}`}><AdminLabel label={labels[outcome]} /><strong>{number(counts[outcome])}</strong><small>{outcome === "positive" ? "El dueño indicó que es su mascota." : outcome === "false" ? "El dueño indicó que no es su mascota." : outcome === "uncertain" ? "El dueño todavía no está seguro." : "Todavía no fueron evaluadas por el dueño."}</small></div>)}
      </div>
      <div className="admin-outcome-analysis">
        <div className="admin-response-rate"><strong>{percentage(counts.positive_rate)}</strong><div><AdminHeading level={3} label="Confirmadas entre las respuestas definitivas" /><p>{counts.decided ? `${number(counts.positive)} ${counts.positive === 1 ? "confirmada" : "confirmadas"} de ${number(counts.decided)} ${counts.decided === 1 ? "respuesta definitiva" : "respuestas definitivas"}.` : "Todavía no hay respuestas definitivas para calcular este porcentaje."}</p><p className="field-help">Las dudosas y sin respuesta quedan fuera del cálculo. Este porcentaje refleja las respuestas recibidas; no mide todas las coincidencias que el sistema pudo omitir.</p></div></div>
        {counts.total > 0 && <div className="admin-outcome-bar" role="img" aria-label={`${counts.positive} ${counts.positive === 1 ? "confirmada" : "confirmadas"}, ${counts.false} ${counts.false === 1 ? "falsa" : "falsas"}, ${counts.uncertain} ${counts.uncertain === 1 ? "dudosa" : "dudosas"} y ${counts.pending} sin respuesta.`}>{(["positive", "false", "uncertain", "pending"] as const).filter(outcome => counts[outcome] > 0).map(outcome => <span key={outcome} className={outcomeClasses[outcome]} style={{ width: `${100 * counts[outcome] / counts.total}%` }} />)}</div>}
        <p className="field-help"><AdminLabel label="Respondidas" />: {percentage(counts.review_rate)} · {number(counts.reviewed)} de {number(counts.total)} recomendaciones.</p>
        <p className="field-help">Los avistamientos recibidos desde una ficha cuentan aquí cuando el sistema los considera una posible coincidencia. Cada recomendación se cuenta una sola vez y se usa la última respuesta, incluso si la búsqueda ya se cerró.</p>
        {data.legacy_count > 0 && <p className="notice notice-warning">Incluye {number(data.legacy_count)} {data.legacy_count === 1 ? "registro anterior" : "registros anteriores"} al seguimiento. Su fecha y puntaje se recuperaron del estado disponible; no se puede reconstruir todo su historial.</p>}
      </div>
      <div className="admin-source-summary"><AdminHeading level={3} label="Resultados por origen" /><div className="admin-table-scroll"><table className="admin-results-table"><thead><tr><th scope="col"><AdminLabel label="Origen" help="Forma en que se inició la comparación que generó estas recomendaciones." /></th>{["Total", "Confirmadas", "Falsas", "Dudosas", "Sin respuesta"].map(label => <th scope="col" key={label}><AdminLabel label={label} /></th>)}</tr></thead><tbody>{data.sources.map(item => <tr key={item.source}><th scope="row"><AdminLabel label={sourceLabels[item.source]} /></th><td>{number(item.total)}</td><td>{number(item.positive)}</td><td>{number(item.false)}</td><td>{number(item.uncertain)}</td><td>{number(item.pending)}</td></tr>)}</tbody></table></div></div>
      <div className="admin-section-heading"><AdminHeading level={3} label="Recomendaciones y respuestas" /><div className="field-label"><AdminFieldLabel htmlFor={`${fieldId}-result`} label="Mostrar en la lista" help="Filtra la lista por la última respuesta del dueño. Los indicadores de arriba conservan el conjunto seleccionado por período, origen y registro." /><select id={`${fieldId}-result`} className="form-input" value={result} onChange={event => filter(setResult, event.target.value)}><option value="all">Todos los estados</option>{Object.entries(labels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div></div>
      <p className="field-help" role="status">{number(data.total)} {data.total === 1 ? "recomendación" : "recomendaciones"} en la lista. El filtro de estado no cambia los totales de arriba. Horarios de Uruguay.</p>
      {!data.items.length ? <div className="lost-dogs-empty"><h3>No hay recomendaciones con estos filtros</h3><p>Los resultados aparecerán cuando el sistema sugiera coincidencias. Las respuestas que den los dueños se actualizarán en este panel.</p></div> : <div className="admin-recommendations">{data.items.map(item => <article className="admin-recommendation" key={item.id}>
        <div className="admin-recommendation-heading"><div><h4>{item.pet_name}</h4><p className="field-help"><AdminLabel label={sourceLabels[item.source]} /> · {caseLabels[item.case_status] || item.case_status}</p></div><span className={`admin-outcome-label ${outcomeClasses[item.outcome]}`}><AdminLabel label={labels[item.outcome]} /></span></div>
        <div className="admin-recommendation-ids"><ReportId publicId={item.lost_case_public_id} /><ReportId publicId={item.observation_public_id} label="ID del reporte" /></div>
        <dl className="admin-recommendation-details"><div><dt><AdminLabel label="Recomendada" /></dt><dd><time dateTime={item.recommended_at}>{date(item.recommended_at)}</time></dd></div><div><dt><AdminLabel label="Respuesta más reciente" /></dt><dd>{item.feedback_at ? <time dateTime={item.feedback_at}>{date(item.feedback_at)}</time> : "Sin respuesta"}</dd></div><div><dt><AdminLabel label={item.legacy ? "Puntaje recuperado" : "Puntaje al recomendar"} /></dt><dd>{score(item.recommended_score)}</dd></div><div><dt><AdminLabel label="Estado actual de la propuesta" /></dt><dd>{item.active ? "Disponible" : "Retirada o búsqueda cerrada"}</dd></div></dl>
        {item.legacy && <p className="field-help">Registro anterior al seguimiento.</p>}
        <details><summary>Inspeccionar evidencia, rank y versión</summary><dl className="admin-recommendation-details">{Object.entries({"Puntaje actual":item.current_score,"Características":item.feature_score,"Visual calibrado":item.visual_score,"Similitud visual sin calibrar":item.raw_visual_similarity,"Geografía":item.geo_score,"Tiempo":item.temporal_score,"Cobertura":item.evidence_coverage,"Distancia (m)":item.distance_meters,"Primer rank visto":item.first_viewed_rank,"Mejor rank visto":item.best_viewed_rank}).map(([label,value])=><div key={label}><dt><AdminLabel label={label} help="Evidencia técnica para revisar una recomendación. El puntaje no representa probabilidad de identidad."/></dt><dd>{value==null?"Sin registro":number(value)}</dd></div>)}</dl><p>Primera vista: {item.first_viewed_at?date(item.first_viewed_at):"Sin registro"}</p><pre className="analytics-version">{JSON.stringify(item.recommendation_snapshot,null,2)}</pre></details>
        <button type="button" className="text-button" aria-expanded={history === item.id} aria-controls={`history-${item.id}`} onClick={() => setHistory(current => current === item.id ? null : item.id)}>{history === item.id ? "Ocultar historial" : "Ver historial de respuestas"}{item.history_count > 0 && ` (${item.history_count})`}</button>
        <div id={`history-${item.id}`} hidden={history !== item.id}>{history === item.id && <ResponseHistory id={item.id} />}</div>
      </article>)}</div>}
      {data.total > data.limit && <nav className="lost-dogs-pagination" aria-label="Páginas de recomendaciones"><button type="button" className="button button-secondary" disabled={!offset} onClick={() => setOffset(value => Math.max(0, value - data.limit))}>Anterior</button><span>Página {Math.floor(offset / data.limit) + 1} de {Math.ceil(data.total / data.limit)}</span><button type="button" className="button button-secondary" disabled={offset + data.limit >= data.total} onClick={() => setOffset(value => value + data.limit)}>Siguiente</button></nav>}
      <p className="field-help">Actualizado el <time dateTime={data.generated_at}>{date(data.generated_at)}</time></p>
    </>}
  </section>;
}
