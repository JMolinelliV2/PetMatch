"use client";
import { useEffect, useId, useState } from "react";
import Link from "next/link";
import { AccountSession } from "../account-session";
import { ReportId } from "../ui/report-id";
import { AdminRecords } from "./admin-records";
import { MatchingDashboard } from "./matching-dashboard";
import { OperationsDashboard } from "./operations-dashboard";
import { AdminDateRange, adminDate, emptyPeriod, periodQuery } from "./date-range";
import type { AdminPeriod } from "./date-range";
import { AdminWorkspace } from "./admin-workspace";
import {AnalyticsDashboard} from "./analytics-dashboard";
import type { SessionUser } from "../account-session";
import { AdminFieldLabel, AdminHeading } from "./admin-info";
type Report = { id: string; target_type: string; target_id: string; public_id: string | null; title: string;
  reason: string; detail: string; status: string; created_at: string; visibility: string | null;
  publication?: { description: string; photo_ids: string[] } };
type ReportData = { items: Report[]; total: number; limit: number };
const reasons: Record<string, string> = { SPAM: "Spam", FALSE_INFORMATION: "Información falsa", INAPPROPRIATE_PHOTO: "Foto inapropiada", OTHER: "Otro motivo" };

function PlatformManagement({period,onPeriodChange}:{period:AdminPeriod;onPeriodChange:(value:AdminPeriod)=>void}) {
  const fieldId = useId();
  const [data, setData] = useState<ReportData | null>(null);
  const [status, setStatus] = useState("OPEN");
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [busy, setBusy] = useState<string | null>(null);
  useEffect(() => {
    const controller = new AbortController(); setData(null); setError("");
    const params = new URLSearchParams({ status, offset: String(offset), ...periodQuery(period) });
    void fetch(`/api/admin/reports?${params}`, { cache: "no-store", signal: AbortSignal.any([controller.signal, AbortSignal.timeout(20000)]) }).then(async response => {
      if (!response.ok) throw new Error("No pudimos consultar las denuncias. Revisá tu sesión y permisos.");
      const next: ReportData = await response.json(); if (!controller.signal.aborted) setData(next);
    }).catch(cause => { if (!controller.signal.aborted) setError(cause.message); });
    return () => controller.abort();
  }, [status, period, offset, refresh]);
  async function action(id: string, value: string) {
    setBusy(id); setError(""); setSaved("");
    try {
      const response = await fetch(`/api/admin/reports/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action: value }) });
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "No pudimos aplicar la acción.");
      setSaved("Acción aplicada y registrada en la auditoría."); setRefresh(value => value + 1);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "No pudimos aplicar la acción."); }
    finally { setBusy(null); }
  }
  return <section aria-labelledby="admin-reports-title">
    <div className="admin-section-heading"><div><AdminHeading level={2} id="admin-reports-title" label="Denuncias" /><p>Revisá las publicaciones denunciadas y registrá la acción correspondiente.</p></div><button type="button" className="button button-secondary" onClick={() => setRefresh(value => value + 1)}>Actualizar</button></div>
    <AdminDateRange value={period} onApply={next => { onPeriodChange(next); setOffset(0); }} />
    <p className="field-help">El período se aplica a la recepción de la denuncia. Las correcciones del final conservan su listado de registros recientes.</p>
    <div className="field-label"><AdminFieldLabel htmlFor={`${fieldId}-status`} label="Estado de la denuncia" help="Pendiente significa que falta revisión; con acción aplicada indica que administración intervino; descartada indica que se revisó sin mantener una acción sobre la publicación." /><select id={`${fieldId}-status`} className="form-input" value={status} onChange={event => { setStatus(event.target.value); setOffset(0); }}><option value="OPEN">Pendientes</option><option value="ACTION_TAKEN">Con acción aplicada</option><option value="DISMISSED">Descartadas</option><option value="">Todas</option></select></div>
    {error && <p className="notice notice-warning" role="alert">{error}</p>}{saved && <p className="notice" role="status">{saved}</p>}
    {!data && !error && <p role="status">Cargando denuncias…</p>}
    {data && <><p className="field-help">{data.total} denuncias con estos filtros.</p>{!data.items.length && <p>No hay denuncias con estos filtros.</p>}
      {data.items.map(report => <article key={report.id} className="notification-card"><h3>{report.title}</h3>{report.public_id && <ReportId publicId={report.public_id} />}<p>{reasons[report.reason] || report.reason} · {report.visibility === "HIDDEN" ? "Publicación oculta" : report.visibility ? "Publicación visible" : "Publicación eliminada"}</p><p className="field-help">Recibida: {adminDate(report.created_at)}</p><p className="admin-contact-message">{report.detail || "Sin detalles adicionales"}</p>
        {report.publication && <details><summary>Ver publicación denunciada</summary><p>{report.publication.description}</p><div className="notification-photos">{report.publication.photo_ids.map(id => <img key={id} src={`/api/admin/reports/${report.id}/photos/${id}`} alt="Foto de la publicación denunciada" loading="lazy" />)}</div></details>}
        <div className="location-actions"><button className="text-button" type="button" disabled={busy !== null || !report.visibility} onClick={() => void action(report.id, "HIDE")}>Ocultar publicación</button><button className="text-button" type="button" disabled={busy !== null || !report.visibility} onClick={() => void action(report.id, "RESTORE")}>Restaurar publicación</button><button className="text-button" type="button" disabled={busy !== null} onClick={() => void action(report.id, "DISMISS")}>Descartar denuncia</button></div>
        {report.visibility && <details><summary>Bloquear al autor</summary><p className="field-help">Cierra las sesiones de la cuenta y oculta todos sus avisos y reportes. Las acciones quedan registradas.</p><button className="button button-secondary" type="button" disabled={busy !== null} onClick={() => void action(report.id, "BLOCK_AUTHOR")}>Confirmar bloqueo del autor</button></details>}
      </article>)}
      {data.total > data.limit && <nav className="lost-dogs-pagination" aria-label="Páginas de denuncias"><button type="button" className="button button-secondary" disabled={!offset} onClick={() => setOffset(value => Math.max(0, value - data.limit))}>Anterior</button><span>Página {Math.floor(offset / data.limit) + 1} de {Math.ceil(data.total / data.limit)}</span><button type="button" className="button button-secondary" disabled={offset + data.limit >= data.total} onClick={() => setOffset(value => value + data.limit)}>Siguiente</button></nav>}
    </>}
    <AdminRecords />
  </section>;
}

function AdminPanel({user,logout}:{user:SessionUser;logout:()=>Promise<void>}) {
  const [period,setPeriod]=useState<AdminPeriod>(emptyPeriod);
  return <AdminWorkspace user={user} logout={logout}>{(view,navigate)=>view==="growth"||view==="usage"||view==="analytics-matching"||view==="impact"||view==="inventory"?<AnalyticsDashboard section={view} period={period} onPeriodChange={setPeriod}/>:view==="matching"?<MatchingDashboard period={period} onPeriodChange={setPeriod}/>:view==="management"?<PlatformManagement period={period} onPeriodChange={setPeriod}/>:<OperationsDashboard section={view} onNavigate={navigate} period={period} onPeriodChange={setPeriod}/>}</AdminWorkspace>;
}
export function Administration() { return <AccountSession showAccountHeader={false}>{(user,actions) => user.admin_access ? <AdminPanel user={user} logout={actions.logout}/> : <div className="notice notice-warning"><h2>Acceso restringido</h2><p>Este panel está reservado a la cuenta administradora con su correo confirmado. Tu sesión actual no tiene acceso.</p><div className="location-actions"><Link className="text-button" href="/mi-cuenta">Ir a mi cuenta</Link><button className="text-button" type="button" onClick={()=>void actions.logout()}>Cerrar sesión</button></div></div>}</AccountSession>; }
