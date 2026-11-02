"use client";
import { useEffect, useId, useState } from "react";
import { AdminDateRange, adminDate, periodQuery } from "./date-range";
import type { AdminPeriod } from "./date-range";
import { AdminFieldLabel, AdminHeading, AdminLabel } from "./admin-info";
import { useAdminReload } from "./admin-reload";
import { formatSupportAmount } from "../apoyanos/support-levels";

type Entry = { id: string; amount_uyu: number; status: string; created_at: string; confirmed_at: string | null; last_synced_at: string | null; provider_order_id: string | null; last_error: string | null };
type Data = { items: Entry[]; total: number; limit: number; summary: Record<string, number>; approved_amount_uyu: string; queue: { pending: number; retrying: number }; enabled: boolean; active_environment: string };
const states: Record<string, string> = { CREATING: "Preparando checkout", PENDING: "Pendiente", APPROVED: "Confirmado", REJECTED: "Rechazado", CANCELLED: "Cancelado", REFUNDED: "Reembolsado", PARTIALLY_REFUNDED: "Reembolso parcial", CHARGEBACK: "Contracargo" };

export function DonationsDashboard({ period, onPeriodChange }: { period: AdminPeriod; onPeriodChange: (value: AdminPeriod) => void }) {
  const id = useId();
  const { version, beginRequest } = useAdminReload();
  const [environment, setEnvironment] = useState("production");
  const [state, setState] = useState("all");
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController(); const finish = beginRequest(); setError("");
    const params = new URLSearchParams({ environment, state, offset: String(offset), ...periodQuery(period) });
    void fetch(`/api/admin/donations?${params}`, { cache: "no-store", signal: AbortSignal.any([controller.signal, AbortSignal.timeout(20000)]) }).then(async response => {
      if (!response.ok) throw new Error("No pudimos consultar los aportes. Revisá tu sesión y permisos.");
      const next = await response.json(); if (!controller.signal.aborted) setData(next);
    }).catch(cause => { if (!controller.signal.aborted) setError(cause.message); }).finally(finish);
    return () => { controller.abort(); finish(); };
  }, [environment, state, offset, period, version, beginRequest]);
  return <section>
    <div className="admin-section-heading"><div><AdminHeading level={2} label="Aportes" help="Aportes puntuales con estado confirmado desde la API de Mercado Pago. Las pruebas y los aportes reales se consultan por separado." /><p>Importes, resultados y confirmaciones de Mercado Pago.</p></div></div>
    <AdminDateRange value={period} onApply={next => { onPeriodChange(next); setOffset(0); }} />
    <div className="form-grid">
      <div className="field-label"><AdminFieldLabel htmlFor={`${id}-environment`} label="Entorno" help="Producción muestra operaciones con dinero real. Pruebas muestra simulaciones y nunca se suma al total de producción." /><select id={`${id}-environment`} className="form-input" value={environment} onChange={event => { setEnvironment(event.target.value); setData(null); setOffset(0); }}><option value="production">Producción · dinero real</option><option value="test">Pruebas · sin dinero real</option></select></div>
      <div className="field-label"><AdminFieldLabel htmlFor={`${id}-state`} label="Estado" help="Confirmado indica que Mercado Pago acreditó el importe. Pendiente y preparando checkout todavía no significan un aporte recibido." /><select id={`${id}-state`} className="form-input" value={state} onChange={event => { setState(event.target.value); setData(null); setOffset(0); }}><option value="all">Todos los estados</option>{Object.entries(states).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div>
    </div>
    <p className="field-help">El período se aplica a la fecha de inicio del aporte. No se guardan datos de tarjetas ni la identidad de quien aporta.</p>
    {error && <p className="notice notice-warning" role="alert">{error}</p>}
    {!data && !error && <p role="status">Consultando aportes…</p>}
    {data && <>
      <div className="admin-widget"><AdminHeading level={3} label={environment === "test" ? "Total confirmado de prueba" : "Total confirmado"} help="Suma de importes de aportes con estado actual Confirmado, en el entorno y período elegidos. Excluye reembolsos, reembolsos parciales, contracargos y operaciones pendientes. No descuenta comisiones de Mercado Pago ni representa el saldo disponible." /><strong className="support-selection-amount">$U {new Intl.NumberFormat("es-UY").format(BigInt(data.approved_amount_uyu))}</strong><p className="field-help">{data.summary.APPROVED || 0} confirmados · {data.queue.pending} confirmaciones en cola · {data.queue.retrying} con reintento. La cola corresponde al estado actual del entorno, sin filtro de fechas.</p><p className="field-help">Recepción {data.enabled ? "habilitada" : "desactivada"} · Entorno activo: {data.active_environment === "test" ? "pruebas" : "producción"}.</p></div>
      <p className="field-help">{data.total} aportes con estos filtros.</p>
      {!data.items.length && <p>No hay aportes con estos filtros.</p>}
      <div className="admin-record-list">{data.items.map(item => <article className="admin-record-card" key={item.id}><div className="admin-recommendation-heading"><h3>{formatSupportAmount(item.amount_uyu)}</h3><strong>{states[item.status] || item.status}</strong></div><dl className="admin-recommendation-details"><div><dt><AdminLabel label="Referencia" help="Identificador propio del aporte. No concede acceso al detalle del donante ni permite realizar cobros." /></dt><dd>{item.id}</dd></div><div><dt>Iniciado</dt><dd>{adminDate(item.created_at)}</dd></div><div><dt>Confirmado</dt><dd>{adminDate(item.confirmed_at)}</dd></div><div><dt>Última consulta</dt><dd>{adminDate(item.last_synced_at)}</dd></div></dl>{item.provider_order_id && <p className="field-help">Orden de Mercado Pago: {item.provider_order_id}</p>}{item.last_error && <p className="notice notice-warning">Revisión técnica: {item.last_error}. No se confirmó un aporte nuevo a partir de este error.</p>}</article>)}</div>
      {data.total > data.limit && <nav className="lost-dogs-pagination" aria-label="Páginas de aportes"><button className="button button-secondary" disabled={!offset} onClick={() => setOffset(value => Math.max(0, value - data.limit))}>Anterior</button><span>Página {Math.floor(offset / data.limit) + 1}</span><button className="button button-secondary" disabled={offset + data.limit >= data.total} onClick={() => setOffset(value => value + data.limit)}>Siguiente</button></nav>}
    </>}
  </section>;
}
