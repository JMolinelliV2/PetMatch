"use client";
import { useEffect, useId, useRef, useState } from "react";
import Link from "next/link";
import { AdminDateRange, adminDate, periodQuery } from "./date-range";
import type { AdminPeriod } from "./date-range";
import { ModerationDialog } from "./moderation-dialog";
import type { ModerationAction } from "./moderation-dialog";
import { ReportId } from "../ui/report-id";
import { OverviewWidgets } from "./overview-widgets";
import type { OverviewCharts } from "./overview-widgets";
import { AdminFieldLabel, AdminHeading, AdminLabel } from "./admin-info";
import { operationStateHelp } from "./admin-help";
import {useAdminReload} from "./admin-reload";
import { BackupStatusWidget } from "./backup-status";
import type { BackupStatus } from "./backup-status";

export type OperationSection = "overview" | "users" | "jobs" | "mail" | "contacts" | "publications" | "audit";
type Section = OperationSection;
type Entry = {
  id: string; name?: string; email?: string; phone?: string; status?: string; verified?: boolean; is_self?: boolean;
  created_at: string; last_active_at?: string; lost_cases?: number; observations?: number;
  source_type?: string; provider?: string; model?: string; owner_type?: string; owner_id?: string;
  attempts?: number; max_attempts?: number; available_at?: string; started_at?: string; finished_at?: string; error_code?: string;
  kind?: string; item_count?: number; recipient_name?: string; source_ids?: string[];
  topic?: string; message?: string; email_status?: string; email_sent_at?: string; email_attempts?: number;
  title?: string; public_id?: string; species?: string; description?: string; visibility?: string;
  author_name?: string; author_status?: string; case_status?: string; public_location?: string;
  action?: string; target_type?: string; target_id?: string; reason?: string;
};
type Data = { items?: Entry[]; total?: number; limit?: number; summary?: Record<string, number>;
  metrics?: { label: string; value: number; help: string }[]; mail_queue?: { pending: number; failed: number };
  charts?: OverviewCharts; backups?: BackupStatus;
  tracking_started_at?: string; generated_at: string };
const sections: [Section, string][] = [["overview", "Resumen"], ["users", "Usuarios"], ["jobs", "Trabajos"], ["mail", "Correos"], ["contacts", "Contactos"], ["publications", "Publicaciones"], ["audit", "Auditoría"]];
const labels: Record<string, string> = {
  ACTIVE: "Habilitada", BLOCKED: "Bloqueada", verified: "Correo confirmado", unverified: "Sin confirmar", recent: "Actividad en los últimos 15 min",
  waiting: "En espera", PENDING: "Pendiente", DISPATCHING: "Preparando envío a la cola", QUEUED: "En cola", RUNNING: "En proceso",
  SUCCEEDED: "Completado", FAILED: "Fallido", STALE: "Reemplazado", SENT: "Enviado", PREVIEWED: "Vista previa",
  VISIBLE: "Visible", HIDDEN: "Oculta", CANCELLED: "Cancelado", SKIPPED: "Omitido", CONSUMED: "Enlace usado",
  ALERT: "Alerta de avistamiento", VERIFY_EMAIL: "Confirmación de correo", RESET_PASSWORD: "Recuperación de contraseña",
  CHANGE_EMAIL: "Cambio de correo", PHOTO_REMINDER: "Recordatorio de fotos", CONTACT_FORWARD: "Contacto a administración",
  USER_SIGHTING: "Avistamiento", FOUND_ANIMAL: "Animal encontrado", FOUND: "Animal recuperado", CLOSED: "Búsqueda cerrada",
  text: "Texto", image: "Foto", embedding: "Comparación visual", lost_case: "Aviso perdido", observation: "Reporte", pet: "Animal",
  improvement: "Sugerencia", problem: "Problema", other: "Otro",
  BLOCK_USER: "Cuenta bloqueada", UNBLOCK_USER: "Cuenta reactivada", HIDE_PUBLICATION: "Publicación oculta",
  RESTORE_PUBLICATION: "Publicación restaurada", CORRECT_DESCRIPTION: "Descripción corregida", HIDE: "Publicación oculta",
  RESTORE: "Publicación restaurada", DISMISS: "Denuncia descartada", BLOCK_AUTHOR: "Autor bloqueado",
};
const stateOptions: Record<Section, string[]> = { overview: [], users: ["ACTIVE", "BLOCKED", "verified", "unverified", "recent"],
  jobs: ["waiting", "RUNNING", "SUCCEEDED", "FAILED", "STALE"], mail: ["SENT", "FAILED", "PREVIEWED"],
  contacts: ["SENT", "PENDING", "FAILED", "PREVIEWED"], publications: ["VISIBLE", "HIDDEN"], audit: [] };
const sectionDescription: Record<Section, string> = {
  overview: "Actividad, procesamiento y comunicación en un solo lugar.",
  users: "Consultá las cuentas registradas, su actividad y el estado del correo.",
  jobs: "Seguí el procesamiento de textos y fotos, sus tiempos y sus errores.",
  mail: "Consultá los envíos reales y las solicitudes que esperan un envío.",
  contacts: "Leé los mensajes recibidos desde el formulario de contacto.",
  publications: "Buscá avisos y reportes por su ID y controlá su visibilidad.",
  audit: "Revisá cuándo se aplicaron las acciones administrativas y sus motivos.",
};
const number = (value: number) => new Intl.NumberFormat("es-UY").format(value);
function Badge({ value, section }: { value?: string; section: Section }) { return value ? <span className={`admin-outcome-label ${["BLOCKED", "FAILED", "HIDDEN"].includes(value) ? "admin-outcome-false" : ["SUCCEEDED", "SENT", "ACTIVE", "VISIBLE"].includes(value) ? "admin-outcome-positive" : "admin-outcome-pending"}`}><AdminLabel label={labels[value] || value} help={operationStateHelp(value, section)} /></span> : null; }
function Detail({ label, value }: { label: string; value?: string | number | null }) { return <div><dt aria-label={label}><AdminLabel label={label} /></dt><dd>{value ?? "Sin registro"}</dd></div>; }

export function OperationsDashboard({section,onNavigate,period,onPeriodChange}:{section:Section;onNavigate:(value:Section)=>void;period:AdminPeriod;onPeriodChange:(value:AdminPeriod)=>void}) {
  const {version,beginRequest}=useAdminReload();
  const appliedReload=useRef(version);
  const fieldId = useId();
  const [state, setState] = useState("all");
  const [dateField, setDateField] = useState("created");
  const [kind, setKind] = useState("all");
  const [mailView, setMailView] = useState("mail");
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [action, setAction] = useState<ModerationAction | null>(null);
  const [saved, setSaved] = useState("");
  function navigate(next: Section) { onNavigate(next); }
  useEffect(()=>{setOffset(0);setState("all");setDateField("created");setKind("all");setSearch("");setQ("");setSaved("");if(section!=="mail")setMailView("mail");setAction(null);},[section]);
  function filter(setter: (value: string) => void, value: string) { setter(value); setOffset(0); }
  useEffect(() => {
    const controller = new AbortController(); const finish=beginRequest();
    if(appliedReload.current===version)setData(null);
    appliedReload.current=version; setError("");
    const params = new URLSearchParams({ ...periodQuery(period), state, date_field: dateField, kind, q, offset: String(offset) });
    const path = section === "overview" ? "" : `/${section === "mail" ? mailView : section}`;
    void fetch(`/api/admin/operations${path}?${params}`, { cache: "no-store", signal: AbortSignal.any([controller.signal, AbortSignal.timeout(20000)]) }).then(async response => {
      if (!response.ok) throw new Error(response.status === 401 || response.status === 403 ? "Tu sesión no tiene acceso. Ingresá con la cuenta administradora." : "No pudimos consultar esta sección.");
      const next: Data = await response.json(); if (!controller.signal.aborted) setData(next);
    }).catch(cause => { if (!controller.signal.aborted) setError(cause instanceof Error && cause.name !== "TimeoutError" ? cause.message : "La consulta demoró demasiado. Intentá nuevamente."); }).finally(finish);
    return () => {controller.abort();finish();};
  }, [section, period, state, dateField, kind, q, offset, mailView, refresh, version, beginRequest]);
  function userAction(item: Entry) {
    const blocked = item.status === "BLOCKED";
    setAction({ url: `/api/admin/users/${item.id}/status`, status: blocked ? "ACTIVE" : "BLOCKED",
      title: `${blocked ? "Reactivar" : "Bloquear"} a ${item.name}`,
      description: blocked ? "La persona podrá iniciar una nueva sesión. Sus publicaciones ocultas deben restaurarse por separado." : "Se cerrarán sus sesiones y se ocultarán todos sus avisos, avistamientos y reportes de animales encontrados. La cuenta conservará sus datos." });
  }
  function publicationAction(item: Entry) {
    const hidden = item.visibility === "HIDDEN";
    setAction({ url: `/api/admin/publications/${item.kind}/${item.id}/visibility`, status: hidden ? "VISIBLE" : "HIDDEN",
      title: `${hidden ? "Restaurar" : "Ocultar"} ${item.public_id}`,
      description: hidden ? "La publicación volverá a estar disponible según el estado de la búsqueda. La cuenta de su autor debe estar habilitada." : "La publicación dejará de aparecer en las páginas públicas y en el mapa. Sus datos se conservarán y dejará de participar en las coincidencias." });
  }
  const title = sections.find(([value]) => value === section)?.[1];
  const options = section === "mail" && mailView === "mail_queue" ? ["PENDING", "FAILED"] : stateOptions[section];
  return <section className="admin-operations" aria-labelledby="admin-operations-title">
    <div className="admin-section-heading"><div><span className="admin-section-eyebrow">{section==="overview"?"Vista general":"Gestión de la plataforma"}</span><AdminHeading level={2} id="admin-operations-title" label={section==="overview"?"Resumen de la plataforma":title || "Gestión"} help={sectionDescription[section]} /><p>{sectionDescription[section]}</p></div></div>
    <AdminDateRange value={period} onApply={next => { onPeriodChange(next); setOffset(0); }} />
    {section !== "overview" && <div className="admin-matching-filters admin-operations-filters">
      {section === "mail" && <div className="field-label"><AdminFieldLabel htmlFor={`${fieldId}-mail`} label="Consultar" help="El historial muestra intentos de correo realizados; las solicitudes pendientes y fallidas muestran mensajes que todavía esperan su envío o necesitan revisión." /><select id={`${fieldId}-mail`} className="form-input" value={mailView} onChange={event => { setMailView(event.target.value); setState("all"); setOffset(0); }}><option value="mail">Historial de envíos</option><option value="mail_queue">Solicitudes pendientes y fallidas</option></select></div>}
      {options.length > 0 && <div className="field-label"><AdminFieldLabel htmlFor={`${fieldId}-state`} label="Estado" help="Limita la lista al estado elegido. Los totales por estado respetan el período y la búsqueda, antes de aplicar este filtro." /><select id={`${fieldId}-state`} className="form-input" value={state} onChange={event => filter(setState, event.target.value)}><option value="all">Todos los estados</option>{options.map(value => <option key={value} value={value}>{labels[value]}</option>)}</select></div>}
      {(section === "users" || section === "jobs") && <div className="field-label"><AdminFieldLabel htmlFor={`${fieldId}-date`} label="Filtrar fechas por" help={section === "users" ? "El período puede aplicarse a la creación de la cuenta o a cualquier actividad registrada dentro del rango, aunque la persona haya vuelto después." : "El período puede aplicarse a la creación del trabajo o al momento en que finalizó. La segunda opción permite revisar cuándo terminaron los trabajos."} /><select id={`${fieldId}-date`} className="form-input" value={dateField} onChange={event => filter(setDateField, event.target.value)}><option value="created">{section === "users" ? "Fecha de registro" : "Fecha de creación del trabajo"}</option><option value={section === "users" ? "activity" : "finished"}>{section === "users" ? "Actividad registrada en el período" : "Fecha de finalización del trabajo"}</option></select></div>}
      {section === "publications" && <div className="field-label"><AdminFieldLabel htmlFor={`${fieldId}-kind`} label="Tipo" help="Distingue los avisos de pérdida de los reportes de avistamiento o animal encontrado. Recuperar una mascota conserva su aviso de pérdida con estado encontrado." /><select id={`${fieldId}-kind`} className="form-input" value={kind} onChange={event => filter(setKind, event.target.value)}><option value="all">Todos los avisos y reportes</option><option value="lost_case">Animales perdidos</option><option value="observation">Avistamientos y encontrados</option></select></div>}
      <form className="admin-record-search" onSubmit={event => { event.preventDefault(); setQ(search.trim()); setOffset(0); }}><div className="field-label"><AdminFieldLabel htmlFor={`${fieldId}-search`} label="Buscar" help={section === "users" ? "Busca cuentas por nombre o correo." : section === "publications" ? "Busca publicaciones por ID, nombre del animal, descripción o autor." : section === "jobs" ? "Busca trabajos por modelo de procesamiento o código de error." : section === "contacts" ? "Busca contactos por nombre, correo o contenido del mensaje." : "Busca registros por tipo de correo o nombre de la acción administrativa."} /><input id={`${fieldId}-search`} type="search" className="form-input" maxLength={120} value={search} placeholder={section === "users" ? "Nombre o correo" : section === "publications" ? "ID, animal, descripción o autor" : section === "jobs" ? "Modelo o código de error" : section === "contacts" ? "Nombre, correo o mensaje" : "Tipo o acción"} onChange={event => setSearch(event.target.value)} /></div><button type="submit" className="button button-secondary">Buscar</button></form>
    </div>}
    {saved && <p role="status" className="notice">{saved}</p>}{error && <p role="alert" className="notice notice-warning">{error}</p>}
    {!data && !error && <p role="status" className="admin-matching-loading">Cargando {title?.toLowerCase()}…</p>}
    {data && <>
      {section === "overview" ? <><OverviewWidgets metrics={data.metrics||[]} charts={data.charts} queue={data.mail_queue} onQueue={()=>{navigate("mail");setMailView("mail_queue");}}/><BackupStatusWidget status={data.backups}/></>
        : <>
          {data.summary && Object.keys(data.summary).length > 0 && <div className="admin-state-totals" aria-label="Totales antes del filtro de estado">{Object.entries(data.summary).filter(([key]) => key !== "DISPATCHING" && key !== "QUEUED" && !(section === "jobs" && key === "PENDING")).map(([key, value]) => <span key={key}><AdminLabel label={labels[key] || key} help={operationStateHelp(key, section)} />: <strong>{number(value)}</strong></span>)}</div>}
          <p className="field-help" role="status">{number(data.total || 0)} {data.total === 1 ? "registro" : "registros"} con estos filtros. Los totales por estado respetan el período y la búsqueda, antes del filtro de estado.</p>
          {section === "users" && <p className="field-help">“Habilitada” es el estado de la cuenta. La actividad indica uso de la sesión e incluye consultas automáticas del sitio; no confirma que la persona esté mirando la página en este momento.</p>}
          {section === "jobs" && <p className="field-help">En espera incluye pendientes, preparación y cola. “Reemplazado” indica que el trabajo quedó obsoleto por cambios en el reporte. El período se aplica a la fecha elegida arriba.</p>}
          {section === "mail" && <p className="field-help">{mailView === "mail" ? "Cada registro corresponde a un intento de envío. Enviado significa aceptado por el servidor SMTP; no confirma entrega ni lectura. Las vistas previas no se cuentan como enviados." : "Son solicitudes creadas en el período, no correos enviados. Un envío puede agrupar varias alertas. El horario de disponibilidad puede cambiar al reintentar."}</p>}
          {section === "contacts" && <p className="field-help">Los contactos reenviados se conservan durante 30 días después del envío. El correo del remitente es declarado por la persona y no está verificado.</p>}
          {!data.items?.length ? <div className="lost-dogs-empty"><h3>No hay registros con estos filtros</h3><p>Ajustá el período, la búsqueda o el estado para consultar otros resultados.</p></div> : <div className="admin-recommendations">{data.items.map(item => <article className="admin-recommendation admin-operation-record" key={`${item.source_type || item.kind || section}-${item.id}`}>
            {section === "users" && <><div className="admin-recommendation-heading"><h3>{item.name}</h3><Badge value={item.status} section={section} /></div><p className="admin-private-contact">{item.email}{item.phone && ` · ${item.phone}`}</p><dl className="admin-recommendation-details"><Detail label="Registro" value={adminDate(item.created_at)} /><Detail label="Última actividad registrada" value={adminDate(item.last_active_at)} /><Detail label="Correo" value={item.verified ? "Confirmado" : "Sin confirmar"} /><Detail label="Publicaciones actuales" value={`${item.lost_cases || 0} avisos · ${item.observations || 0} reportes`} /></dl>{item.is_self ? <p className="field-help">Tu cuenta administradora. Su bloqueo está deshabilitado.</p> : <button type="button" className="button button-secondary" onClick={() => userAction(item)}>{item.status === "BLOCKED" ? "Reactivar cuenta" : "Bloquear cuenta"}</button>}</>}
            {section === "jobs" && <><div className="admin-recommendation-heading"><h3>{labels[item.source_type || ""] || item.source_type} · {item.model}</h3><Badge value={item.status} section={section} /></div><dl className="admin-recommendation-details"><Detail label="Creado" value={adminDate(item.created_at)} /><Detail label="Disponible desde" value={adminDate(item.available_at)} /><Detail label="Inicio del último intento" value={adminDate(item.started_at)} /><Detail label="Finalizado" value={adminDate(item.finished_at)} /><Detail label="Intentos" value={`${item.attempts} / ${item.max_attempts}`} /><Detail label="Error" value={item.error_code || "Sin error registrado"} /></dl><details><summary>Referencia del trabajo</summary><p className="field-help">Trabajo: {item.id}<br />{labels[item.owner_type || ""] || item.owner_type}: {item.owner_id}<br />Proveedor: {item.provider}</p></details></>}
            {section === "mail" && <><div className="admin-recommendation-heading"><h3>{labels[item.kind || ""] || item.kind}</h3><Badge value={item.status} section={section} /></div><dl className="admin-recommendation-details"><Detail label={mailView === "mail" ? "Intento de envío" : "Solicitud creada"} value={adminDate(item.created_at)} />{mailView === "mail" ? <><Detail label="Destino" value={item.kind === "CONTACT_FORWARD" ? "Administración" : item.recipient_name || "Cuenta eliminada o no disponible"} /><Detail label="Elementos en el mensaje" value={item.item_count} /></> : <><Detail label="Intentos" value={item.attempts} /><Detail label="Disponible desde" value={adminDate(item.available_at)} /></>}</dl><details><summary>Referencias</summary><p className="field-help">Registro: {item.id}{item.source_ids && <><br />Solicitudes: {item.source_ids.join(", ")}</>}</p></details></>}
            {section === "contacts" && <><div className="admin-recommendation-heading"><h3>{item.name} · {labels[item.topic || ""] || item.topic}</h3><Badge value={item.email_status} section={section} /></div><p className="admin-private-contact">{item.email}</p><p className="admin-contact-message">{item.message}</p><dl className="admin-recommendation-details"><Detail label="Recibido" value={adminDate(item.created_at)} /><Detail label="Reenviado a administración" value={adminDate(item.email_sent_at)} /><Detail label="Intentos de reenvío" value={item.email_attempts} /></dl></>}
            {section === "publications" && <><div className="admin-recommendation-heading"><h3>{item.kind === "lost_case" ? item.title : labels[item.title || ""] || "Reporte de animal"}</h3><Badge value={item.visibility} section={section} /></div><ReportId publicId={item.public_id || ""} label={item.kind === "lost_case" ? "ID del aviso" : "ID del reporte"} /><p className="admin-contact-message">{item.description || "Sin descripción"}</p><dl className="admin-recommendation-details"><Detail label="Publicado" value={adminDate(item.created_at)} /><Detail label="Autor" value={item.author_name || "Sin cuenta"} /><Detail label="Zona" value={item.public_location || "Sin referencia"} /><Detail label="Estado" value={item.case_status ? (item.case_status === "ACTIVE" ? "Búsqueda activa" : labels[item.case_status] || item.case_status) : "Reporte de avistamiento o encontrado"} /></dl><div className="location-actions">{item.visibility === "VISIBLE" && <Link className="text-button" href={item.kind === "lost_case" ? `/perdidos/${item.id}` : "/mapa"}>{item.kind === "lost_case" ? "Ver publicación" : "Abrir mapa de reportes"}</Link>}<button type="button" className="button button-secondary" disabled={item.visibility === "HIDDEN" && item.author_status === "BLOCKED"} onClick={() => publicationAction(item)}>{item.visibility === "HIDDEN" ? "Restaurar publicación" : "Ocultar publicación"}</button></div>{item.author_status === "BLOCKED" && <p className="field-help">El autor está bloqueado. Reactivá su cuenta antes de restaurar.</p>}</>}
            {section === "audit" && <><h3>{labels[item.action || ""] || item.action}</h3><p>{adminDate(item.created_at)}</p><p className="admin-contact-message">{item.reason || "Sin motivo adicional registrado"}</p><details><summary>Referencia de la acción</summary><p className="field-help">{labels[item.target_type || ""] || item.target_type}: {item.target_id}</p></details></>}
          </article>)}</div>}
          {(data.total || 0) > (data.limit || 25) && <nav className="lost-dogs-pagination" aria-label={`Páginas de ${title}`}><button type="button" className="button button-secondary" disabled={!offset} onClick={() => setOffset(value => Math.max(0, value - (data.limit || 25)))}>Anterior</button><span>Página {Math.floor(offset / (data.limit || 25)) + 1} de {Math.ceil((data.total || 0) / (data.limit || 25))}</span><button type="button" className="button button-secondary" disabled={offset + (data.limit || 25) >= (data.total || 0)} onClick={() => setOffset(value => value + (data.limit || 25))}>Siguiente</button></nav>}
        </>}
      {(section === "overview" || section === "users" || section === "mail") && <p className="field-help">Actividad y envíos registrados desde {adminDate(data.tracking_started_at)}. Se conservan 90 días de historial; no se reconstruyeron eventos anteriores.</p>}
      <p className="field-help">Actualizado: {adminDate(data.generated_at)} · Horarios de Uruguay.</p>
    </>}
    {action && <ModerationDialog action={action} onClose={() => setAction(null)} onSaved={message => { setSaved(message); setAction(null); setRefresh(value => value + 1); }} />}
  </section>;
}
