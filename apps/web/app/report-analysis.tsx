"use client";

import { useEffect, useId, useState } from "react";
import { Icon } from "./ui/pictogram";

type Attribute = { value: string | string[]; confidence: number; source: "text" | "image" };
type Job = {
  id: string;
  source_type: "text" | "image";
  status: string;
  feature_set: { features: Record<string, Attribute> } | null;
};
export type Analysis = { enabled: boolean; jobs: Job[] };
const pendingStates = new Set(["PENDING", "DISPATCHING", "QUEUED", "RUNNING"]);
const unknownValues = new Set(["unknown", "not_visible", "uncertain"]);
const featureLabels: Record<string, string> = {
  species: "Mascota", breed_type: "Tipo o raza", size: "Tamaño", primary_color: "Color principal",
  secondary_colors: "Otros colores", coat_length: "Pelaje", coat_pattern: "Patrón del pelaje",
  ear_shape: "Orejas", tail_description: "Cola", face_features: "Rasgos de la cara",
  distinctive_features: "Rasgos distintivos", accessories: "Collar y accesorios",
};
const valueLabels: Record<string, string> = {
  dog: "Perro", cat: "Gato", unsupported: "Especie fuera del alcance actual",
  tiny: "Muy pequeño", small: "Pequeño", medium: "Mediano", large: "Grande",
  black: "Negro", white: "Blanco", brown: "Marrón", gray: "Gris", cream: "Crema", orange: "Naranja",
  tan: "Beige / canela", red: "Rojizo", multicolor: "Varios colores",
  short: "Corto", long: "Largo", curly: "Rizado", wire: "Áspero", hairless: "Sin pelo",
  solid: "Uniforme", spotted: "Manchado", striped: "Rayado", tuxedo: "Bicolor tipo esmoquin",
  merle: "Merle", brindle: "Atigrado", mixed: "Mixto",
};

function visibleFeatures(features: Record<string, Attribute>) {
  return Object.entries(features).filter(([, attribute]) => attribute.confidence > 0
    && (Array.isArray(attribute.value) ? attribute.value.length > 0 : !unknownValues.has(attribute.value)));
}

export function ReportAnalysis({ ownerType, ownerId }: { ownerType: "lost_case" | "observation"; ownerId: string }) {
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [message, setMessage] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [retrying, setRetrying] = useState<string | null>(null);
  const [paused, setPaused] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    const deadline = Date.now() + 5 * 60_000;
    setPaused(false);
    setLoading(true);
    async function load() {
      try {
        const response = await fetch(`/api/backend/analysis/${ownerType}/${ownerId}`, {
          signal: controller.signal,
        });
        if (!response.ok) throw new Error("No pudimos consultar el análisis. Tu reporte sigue guardado.");
        const data: Analysis = await response.json();
        if (controller.signal.aborted) return;
        setAnalysis(data);
        setMessage("");
        const pending = data.enabled && data.jobs.some(job => pendingStates.has(job.status));
        if (pending && Date.now() < deadline) timer = setTimeout(load, 5000);
        else if (pending) setPaused(true);
      } catch (error) {
        if (!controller.signal.aborted) setMessage(error instanceof Error ? error.message : "No pudimos consultar el análisis.");
      } finally { if (!controller.signal.aborted) setLoading(false); }
    }
    void load();
    return () => { controller.abort(); if (timer) clearTimeout(timer); };
  }, [ownerType, ownerId, refresh]);

  async function retry(id: string) {
    setRetrying(id);
    setMessage("");
    try {
      const response = await fetch(`/api/backend/analysis/jobs/${id}/retry`, { method: "POST" });
      if (response.status === 429) throw new Error("Esperá un minuto antes de volver a intentar el análisis.");
      if (!response.ok) throw new Error("El análisis no pudo reiniciarse. Tu reporte sigue guardado.");
      setRefresh(count => count + 1);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "No pudimos volver a intentar el análisis.");
    } finally { setRetrying(null); }
  }

  return <ReportAnalysisContent analysis={analysis} message={message} paused={paused} loading={loading} retrying={retrying}
    onRetry={id => void retry(id)} onRefresh={() => setRefresh(count => count + 1)} />;
}

export function ReportAnalysisContent({ analysis, message = "", paused = false, loading = false, retrying = null, onRetry, onRefresh }: {
  analysis: Analysis | null;
  message?: string;
  paused?: boolean;
  loading?: boolean;
  retrying?: string | null;
  onRetry: (id: string) => void;
  onRefresh: () => void;
}) {
  const headingId = useId();
  if (analysis && !analysis.enabled && !analysis.jobs.some(job => job.feature_set)) return null;
  if (analysis && !analysis.jobs.length && !message) return null;
  const pending = Boolean(analysis?.jobs.some(job => pendingStates.has(job.status)));
  const completed = analysis?.jobs.filter(job => job.status === "SUCCEEDED").length ?? 0;
  const failed = Boolean(analysis?.jobs.some(job => job.status === "FAILED"));
  const reviewing = pending || (!analysis && loading);
  const needsAttention = Boolean(message || paused || failed);
  const badge = needsAttention ? "Por revisar" : reviewing ? "En curso" : completed ? "Análisis listo" : "Sin resultados";
  const hasResults = Boolean(analysis?.jobs.some(job => job.status === "SUCCEEDED" || job.status === "FAILED"));
  let imageNumber = 0;

  return (
    <section className="report-analysis" aria-labelledby={headingId}>
      <header className="report-analysis-header">
        <span className="report-analysis-icon"><Icon name="spark" /></span>
        <div><h2 id={headingId}>Características sugeridas</h2><p>Una ayuda de la IA para comparar tu reporte con otros casos.</p></div>
        <span className={`report-analysis-badge${needsAttention ? " needs-attention" : reviewing ? " is-pending" : !completed ? " is-neutral" : ""}`} role="status">{badge}</span>
      </header>
      {reviewing && !message && <div className={`report-analysis-progress${paused ? " is-paused" : ""}`} role="status">
        <span className="report-analysis-progress-icon">{paused ? <Icon name="clock" /> : <span className="report-analysis-spinner" />}</span>
        <div><h3>{paused ? "El análisis necesita un poco más de tiempo" : analysis ? "Estamos revisando sus características" : "Preparando el análisis"}</h3>
          <p>{paused ? "Podés actualizar el estado sin volver a enviar el reporte." : "Podés seguir navegando. El reporte ya está guardado y el análisis continúa en segundo plano."}</p>
          {!!completed && <span className="report-analysis-count">{completed} de {analysis?.jobs.length} análisis completados</span>}
        </div>
      </div>}
      <div className="report-analysis-results">{analysis?.jobs.map(job => {
        const features = job.feature_set ? visibleFeatures(job.feature_set.features) : [];
        const source = job.source_type === "image" ? `Foto ${++imageNumber}` : "Descripción";
        if (job.status !== "SUCCEEDED" && job.status !== "FAILED") return null;
        return (
          <div className="report-analysis-result" key={job.id}>
            <h3><Icon name={job.source_type === "image" ? "camera" : "message"} />{source}</h3>
            {job.status === "FAILED" ? <>
              <p className="status-text">El análisis no pudo completarse. La información del reporte está guardada.</p>
              <button type="button" className="text-button" disabled={retrying === job.id || !analysis.enabled} onClick={() => onRetry(job.id)}><Icon name="refresh" />{retrying === job.id ? "Reintentando…" : "Volver a intentar"}</button>
            </> : features.length ? <dl className="analysis-details report-analysis-details">
              {features.map(([name, attribute]) => <div key={name}>
                <dt>{featureLabels[name] ?? name}</dt>
                <dd>{(Array.isArray(attribute.value) ? attribute.value : [attribute.value]).map(value => valueLabels[value] ?? value).join(", ")}
                  {attribute.confidence < .7 && <span className="analysis-uncertain">Por revisar</span>}
                </dd>
              </div>)}
            </dl> : <p className="status-text">No pudimos extraer características con suficiente información.</p>}
          </div>
        );
      })}</div>
      {!reviewing && !message && !hasResults && <p className="report-analysis-empty">No hay características disponibles por ahora. Tu reporte conserva la información que ingresaste.</p>}
      {message && <p role="alert" className="notice notice-warning">{message}</p>}
      {(paused || message) && <button type="button" className="text-button report-analysis-refresh" disabled={loading} onClick={onRefresh}><Icon name="refresh" />{loading ? "Consultando…" : "Actualizar análisis"}</button>}
      <p className="report-analysis-note"><Icon name="info" />Estas sugerencias pueden tener errores. La descripción y los datos que ingresaste se conservan.</p>
    </section>
  );
}
