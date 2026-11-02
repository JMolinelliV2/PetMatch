"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { LocationMap } from "../location-map";
import { MatchFeedback } from "../match-feedback";
import type { FeedbackSaved } from "../match-feedback";

import { VerifyEmailNotice } from "../verify-email-notice";
import { useSessionRefresh } from "../use-session-refresh";
import { ReviewRequest } from "../review-request";
import { SightingComparison } from "../ui/sighting-comparison";
import { PhotoGallery } from "../ui/photo-viewer";
import { ReportId } from "../ui/report-id";
type User = { email_verified?: boolean; email_verification_required?: boolean; id: string; name: string; email: string; notification_preferences: { email?: boolean } };
type Notice = { id: string; kind: string; title: string; body: string; read_at: string | null; archived_at: string | null; created_at: string; lost_case_id: string; lost_case_public_id?: string; observation_public_id?: string; pet_name: string; observed_at: string; public_location: string | null; latitude: number | null; longitude: number | null; reasons: string[]; photo_ids: string[]; email_status: string; match_id: string | null; match_status: string | null; presentation?:string|null; reporter_contact:string|null; linked_to_notice?:boolean; matching_status?:string|null };
type Inbox = { items: Notice[]; unread_count: number; total: number };
type InboxView = "unread" | "all" | "archived";
type NoticeAction = "read" | "archive" | "restore";
const inboxViews: { value: InboxView; label: string }[] = [{ value: "unread", label: "Sin leer" }, { value: "all", label: "Todas" }, { value: "archived", label: "Archivadas" }];

function date(value: string) { return new Intl.DateTimeFormat("es-UY", { dateStyle: "medium", timeStyle: "short", timeZone:"America/Montevideo" }).format(new Date(value)); }

export function NotificationsInbox({ selectedId }: { selectedId?: string }) {
  const sessionVersion = useSessionRefresh();
  const [user, setUser] = useState<User | null>(null);
  const [checking, setChecking] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [inbox, setInbox] = useState<Inbox | null>(null);
  const [refresh, setRefresh] = useState(0);
  const [offset, setOffset] = useState(0);
  const [map, setMap] = useState<string | null>(null);
  const [view, setView] = useState<InboxView>("unread");
  const [action, setAction] = useState<{ id: string | null; kind: NoticeAction | "read-all" } | null>(null);
  const [actionMessage, setActionMessage] = useState("");
  const mutating = useRef(false);
  const requestEpoch = useRef(0);
  const inboxController = useRef<AbortController | null>(null);
  const inboxScope = useRef("");
  const automaticReadAttempt = useRef("");
  const [feedbackMessage, setFeedbackMessage] = useState("");
  const [selectedReviewed, setSelectedReviewed] = useState(false);
  const [reviewCaseId, setReviewCaseId] = useState<string | null>(null);

  useEffect(() => { setSelectedReviewed(false); setFeedbackMessage(""); setActionMessage(""); setReviewCaseId(null); automaticReadAttempt.current = ""; }, [selectedId, user?.id]);

  useEffect(() => {
    const controller = new AbortController();
    void fetch("/api/session", { cache: "no-store", signal: controller.signal }).then(async response => {
      if (!response.ok) throw new Error("No pudimos consultar tu sesión.");
      const session = await response.json();
      if (!controller.signal.aborted) setUser(session.user);
    }).catch(cause => { if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "No pudimos consultar tu sesión."); })
      .finally(() => { if (!controller.signal.aborted) setChecking(false); });
    return () => controller.abort();
  }, [sessionVersion]);

  useEffect(() => {
    if (!user || selectedReviewed) return;
    let disposed = false;
    let controller: AbortController | undefined;
    async function load() {
      if (mutating.current) return;
      controller?.abort(); controller = new AbortController();
      inboxController.current = controller;
      const signal = controller.signal;
      const epoch = requestEpoch.current;
      try {
        const response = await fetch(selectedId ? `/api/notifications/${encodeURIComponent(selectedId)}` : `/api/notifications?limit=20&offset=${offset}&view=${view}`, { cache: "no-store", signal });
        if (disposed || signal.aborted || epoch !== requestEpoch.current) return;
        if (response.status === 401) { setUser(null); setInbox(null); throw new Error("Tu sesión venció. Volvé a ingresar para ver tus avisos."); }
        if (response.status === 404) throw new Error("El aviso de esta alerta ya no está disponible. Podés consultar tus otras notificaciones.");
        if (!response.ok) throw new Error("No pudimos cargar las notificaciones. Intentá de nuevo.");
        const payload = await response.json();
        const data: Inbox = selectedId ? { items: [payload], total: 1, unread_count: payload.read_at ? 0 : 1 } : payload;
        if (!disposed && !signal.aborted && epoch === requestEpoch.current) {
          if (!selectedId && offset > 0 && offset >= data.total) { setOffset(Math.max(0, Math.floor((data.total - 1) / 20) * 20)); return; }
          setInbox(data); setError("");
        }
      } catch (cause) { if (!disposed && !signal.aborted && epoch === requestEpoch.current) setError(cause instanceof Error ? cause.message : "No pudimos cargar las notificaciones."); }
    }
    const scope = `${user.id}:${selectedId || view}:${offset}`;
    if (inboxScope.current !== scope) { inboxScope.current = scope; setInbox(null); }
    void load();
    const timer = setInterval(load, 20000);
    window.addEventListener("focus", load);
    window.addEventListener("mascomatch:notifications", load);
    return () => { disposed = true; controller?.abort(); clearInterval(timer); window.removeEventListener("focus", load); window.removeEventListener("mascomatch:notifications", load); };
  }, [user?.id, refresh, offset, selectedId, selectedReviewed, view]);

  function feedbackSaved(noticeId: string, result: FeedbackSaved) {
    requestEpoch.current += 1; inboxController.current?.abort();
    if (result.recovered) setReviewCaseId(result.caseId);
    setFeedbackMessage(result.recovered ? "Tu mascota quedó marcada como encontrada. La búsqueda está cerrada y el aviso ya no aparece en el listado público."
      : result.status === "RESOLVED" ? "Confirmaste el avistamiento. La búsqueda sigue activa hasta que recuperes a tu mascota."
      : result.status === "FALSE_MATCH" ? "Descartaste este avistamiento. Tu búsqueda sigue activa." : "Guardaste el avistamiento como posible coincidencia. Tu búsqueda sigue activa.");
    setInbox(current => {
      if (!current) return current;
      const removed = current.items.filter(item => result.recovered ? item.lost_case_id === result.caseId : result.status === "FALSE_MATCH" && item.id === noticeId);
      const confirmed = result.status === "RESOLVED" && !result.recovered ? current.items.find(item => item.id === noticeId) : undefined;
      return { ...current, total: Math.max(0, current.total - removed.length - (confirmed && view === "unread" && !selectedId ? 1 : 0)),
        unread_count: Math.max(0, current.unread_count - removed.filter(item => !item.read_at).length - (confirmed && !confirmed.read_at ? 1 : 0)),
        items: current.items.filter(item => !removed.includes(item) && !(view === "unread" && !selectedId && item.id === confirmed?.id)).map(item => item.id === noticeId ? { ...item, match_status: result.status,
          read_at: confirmed ? item.read_at || new Date().toISOString() : item.read_at,
          email_status: confirmed && item.email_status === "PENDING" ? "CANCELLED" : item.email_status,
        } : item),
      };
    });
    if (selectedId && (result.recovered || result.status === "FALSE_MATCH")) setSelectedReviewed(true);
    else setRefresh(value => value + 1);
    window.dispatchEvent(new Event("mascomatch:notifications"));
  }

  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError("");
    const formElement = event.currentTarget;
    const fields = new FormData(formElement);
    try {
      const response = await fetch("/api/session", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ mode: "login", email: fields.get("email"), password: fields.get("password") }) });
      const data = await response.json();
      if (!response.ok) throw new Error(response.status === 401 ? "El correo o la contraseña no son correctos." : "No pudimos iniciar sesión. Intentá de nuevo.");
      formElement.reset(); setUser(data.user); setOffset(0);
      window.dispatchEvent(new Event("mascomatch:session"));
    } catch (cause) { setError(cause instanceof Error ? cause.message : "No pudimos iniciar sesión."); }
    finally { setBusy(false); }
  }

  async function logout() {
    const response = await fetch("/api/session", { method: "DELETE" });
    if (!response.ok) { setError("No pudimos cerrar la sesión. Intentá de nuevo."); return; }
    setUser(null); setInbox(null); window.dispatchEvent(new Event("mascomatch:session"));
  }

  async function updateNotice(id: string, kind: NoticeAction, automatic = false) {
    if (mutating.current) return;
    mutating.current = true; requestEpoch.current += 1; inboxController.current?.abort();
    setAction({ id, kind }); setError("");
    if (!automatic) setActionMessage("");
    try {
      const response = await fetch(`/api/notifications/${encodeURIComponent(id)}/${kind}`, { method: "PATCH" });
      if (response.status === 401) { setUser(null); setInbox(null); throw new Error("Tu sesión venció. Volvé a ingresar."); }
      if (!response.ok) throw new Error(kind === "read" ? "No pudimos marcar la notificación como leída." : kind === "archive" ? "No pudimos archivar la notificación." : "No pudimos restaurar la notificación.");
      const notice: Notice = await response.json();
      setInbox(current => {
        if (!current) return current;
        const previous = current.items.find(item => item.id === id);
        const visible = selectedId ? kind !== "archive" : view === "archived" ? Boolean(notice.archived_at) : !notice.archived_at && (view !== "unread" || !notice.read_at);
        const newlyRead = previous && !previous.read_at && !previous.archived_at && (notice.read_at || notice.archived_at);
        return { ...current, unread_count: Math.max(0, current.unread_count - (newlyRead ? 1 : 0)), total: Math.max(0, current.total - (previous && !visible ? 1 : 0)), items: visible ? current.items.map(item => item.id === id ? notice : item) : current.items.filter(item => item.id !== id) };
      });
      if (selectedId && kind === "archive") setSelectedReviewed(true);
      if (!automatic) setActionMessage(kind === "read" ? "Notificación marcada como leída. Podés volver a verla en Todas." : kind === "archive" ? "Notificación archivada. Podés recuperarla desde Archivadas." : "Notificación restaurada. La encontrás en Todas.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "No pudimos actualizar la notificación."); }
    finally { mutating.current = false; requestEpoch.current += 1; setAction(null); setRefresh(value => value + 1); window.dispatchEvent(new Event("mascomatch:notifications")); }
  }

  async function readAll() {
    if (mutating.current) return;
    mutating.current = true; requestEpoch.current += 1; inboxController.current?.abort();
    setAction({ id: null, kind: "read-all" }); setError(""); setActionMessage("");
    try {
      const response = await fetch("/api/notifications/read-all", { method: "PATCH" });
      if (response.status === 401) { setUser(null); setInbox(null); throw new Error("Tu sesión venció. Volvé a ingresar."); }
      if (!response.ok) throw new Error("No pudimos marcar las notificaciones como leídas.");
      const result: { updated: number; read_at: string } = await response.json();
      setInbox(current => current ? { ...current, unread_count: Math.max(0, current.unread_count - result.updated), total: view === "unread" ? Math.max(0, current.total - result.updated) : current.total,
        items: view === "unread" ? current.items.filter(item => Date.parse(item.created_at) > Date.parse(result.read_at)) : current.items.map(item => !item.read_at && !item.archived_at && Date.parse(item.created_at) <= Date.parse(result.read_at) ? { ...item, read_at: result.read_at, email_status: item.email_status === "PENDING" ? "CANCELLED" : item.email_status } : item) } : current);
      setOffset(0); setActionMessage(result.updated ? "Notificaciones marcadas como leídas. Podés consultarlas en Todas." : "Ya no tenías notificaciones sin leer.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "No pudimos actualizar las notificaciones."); }
    finally { mutating.current = false; requestEpoch.current += 1; setAction(null); setRefresh(value => value + 1); window.dispatchEvent(new Event("mascomatch:notifications")); }
  }

  useEffect(() => {
    const notice = selectedId && inbox?.items.find(item => item.id === selectedId);
    if (!user || !selectedId || !notice || notice.read_at || mutating.current) return;
    const key = `${user.id}:${selectedId}`;
    if (automaticReadAttempt.current === key) return;
    automaticReadAttempt.current = key;
    void updateNotice(selectedId, "read", true);
  }, [selectedId, user?.id, inbox, action]);

  return <main id="main-content" className="page notifications-page">
    <h1>Notificaciones</h1><p className="page-intro">Avistamientos que podrían ayudar a encontrar a tus mascotas.</p>
    {checking ? <p role="status" className="page-intro">Consultando tu sesión…</p> : !user ? <form onSubmit={login} className="notification-login">
      <h2>Ingresá con la cuenta de tu aviso</h2><p className="field-help">Así podrás ver los lugares y las fotos que compartieron.</p>
      <fieldset disabled={busy} className="form-controls section-fields">
        <label className="field-label">Correo electrónico<input name="email" type="email" required maxLength={320} autoComplete="email" className="form-input" /></label>
        <label className="field-label">Contraseña<input name="password" type="password" required maxLength={128} autoComplete="current-password" className="form-input" /></label>
        <button type="submit" className="button button-primary">{busy ? "Ingresando…" : "Ingresar"}</button>
      </fieldset>
      <p>¿Todavía no tenés cuenta? <Link className="text-button" href="/crear-cuenta">Crear cuenta</Link></p>
      <Link className="text-button" href="/recuperar">Olvidé mi contraseña</Link>
    </form> : <>
      {user.email_verification_required && !user.email_verified && <VerifyEmailNotice email={user.email} />}
      <div className="notifications-account"><span>{user.name}</span><button type="button" className="text-button" disabled={Boolean(action)} onClick={() => void logout()}>Cerrar sesión</button></div>
      <p><Link href="/mi-cuenta#notificaciones" className="text-button">Configurar notificaciones en Mi cuenta</Link></p>
      {!selectedId && <>
        <div className="notifications-filters" role="group" aria-label="Mostrar notificaciones">{inboxViews.map(option => <button type="button" key={option.value} className="notification-filter" aria-pressed={view === option.value} disabled={Boolean(action)} onClick={() => { setView(option.value); setOffset(0); setActionMessage(""); setError(""); }}>{option.label}</button>)}</div>
        <p className="field-help">Al abrir una alerta se marca como leída. Las leídas quedan en Todas; podés archivarlas y recuperarlas desde Archivadas.</p>
      </>}
      <div className="notifications-toolbar"><span aria-live="polite">{selectedId ? "Avistamiento de la alerta" : inbox ? `${inbox.unread_count} sin leer` : "Cargando avisos…"}</span><div className="notifications-toolbar-actions">{!selectedId && view !== "archived" && Boolean(inbox?.unread_count) && <button type="button" className="text-button" disabled={Boolean(action)} onClick={() => void readAll()}>{action?.kind === "read-all" ? "Guardando…" : "Marcar todas como leídas"}</button>}<button type="button" className="text-button" disabled={Boolean(action)} onClick={() => setRefresh(value => value + 1)}>Actualizar</button></div></div>
      {actionMessage && <p className="notice" role="status">{actionMessage}</p>}
      {feedbackMessage && <div className="notice" role="status"><p>{feedbackMessage}</p><Link className="text-button" href="/mis-avisos">Ver el estado en Mis avisos</Link></div>}
      {reviewCaseId && <ReviewRequest key={reviewCaseId} caseId={reviewCaseId} recovered />}
      {inbox?.total === 0 && !selectedReviewed && <div className="lost-dogs-empty"><h2>{view === "unread" ? "No tenés notificaciones sin leer" : view === "archived" ? "No tenés notificaciones archivadas" : "No tenés notificaciones en la bandeja"}</h2><p>{view === "unread" ? "Las alertas que ya leíste están en Todas. Los nuevos avistamientos aparecerán acá." : view === "archived" ? "Cuando archives una alerta, podrás recuperarla desde esta sección." : "Acá aparecerán los avistamientos enviados desde tus avisos y las posibles coincidencias de otros reportes."}</p></div>}
      {inbox && <div className="notifications-list">{inbox.items.map(notice => <article key={notice.id} className={`notification-card ${notice.read_at ? "" : "notification-unread"}`}>
        <p className="notification-read-status">{notice.archived_at ? "Archivada" : notice.read_at ? "Leída" : "Sin leer"}{notice.read_at && <span> · <time dateTime={notice.read_at}>{date(notice.read_at)}</time></span>}</p>
        {notice.linked_to_notice ? <SightingComparison status={notice.matching_status} reviewStatus={notice.match_status} /> : <span className="lost-status">{notice.match_status === "RESOLVED" ? "Avistamiento confirmado · búsqueda activa" : notice.kind === "POSSIBLE_MATCH" ? "Posible coincidencia" : notice.photo_ids.length ? "Con fotos · por confirmar" : "Sin foto · por confirmar"}</span>}
        <h2>{notice.title}</h2><p>{notice.body}</p>
        <ReportId id={notice.lost_case_id} publicId={notice.lost_case_public_id} />
        <ReportId publicId={notice.observation_public_id} label="ID del avistamiento" />
        <dl className="review-details"><div><dt>Cuándo lo vieron</dt><dd>{date(notice.observed_at)}</dd></div><div><dt>Zona del avistamiento</dt><dd>{notice.public_location || "Lugar indicado en el mapa"}</dd></div></dl>
        {notice.reasons.length > 0 && <ul className="notification-reasons">{notice.reasons.map(reason => <li key={reason}>{reason}</li>)}</ul>}
        {notice.reporter_contact&&<p>La persona autorizó compartir su contacto: <a href={`mailto:${encodeURIComponent(notice.reporter_contact)}`}>{notice.reporter_contact}</a></p>}
        {notice.photo_ids.length > 0 && <PhotoGallery title={`Fotos del avistamiento para ${notice.pet_name}`} photos={notice.photo_ids.map((photoId, index) => ({ id: photoId, thumbnailSrc: `/api/notifications/${encodeURIComponent(notice.id)}/photos/${encodeURIComponent(photoId)}`, src: `/api/notifications/${encodeURIComponent(notice.id)}/photos/${encodeURIComponent(photoId)}/large`, alt: `foto ${index + 1} del avistamiento para ${notice.pet_name}` }))} />}
        <div className="location-actions"><Link href={`/perdidos/${notice.lost_case_id}`} className="text-button">Ver mi aviso</Link>
          {!selectedId && <Link href={`/notificaciones?aviso=${encodeURIComponent(notice.id)}`} className="text-button">Abrir alerta</Link>}
          {notice.latitude !== null && notice.longitude !== null && <button type="button" className="text-button" aria-expanded={map === notice.id} onClick={() => setMap(current => current === notice.id ? null : notice.id)}>{map === notice.id ? "Ocultar mapa" : "Ver lugar del avistamiento"}</button>}
          {!notice.read_at && <button type="button" className="text-button" disabled={Boolean(action)} onClick={() => void updateNotice(notice.id, "read")}>{action?.id === notice.id && action.kind === "read" ? "Guardando…" : "Marcar como leída"}</button>}
          <button type="button" className="text-button" disabled={Boolean(action)} onClick={() => void updateNotice(notice.id, notice.archived_at ? "restore" : "archive")}>{action?.id === notice.id && ["archive", "restore"].includes(action.kind) ? "Guardando…" : notice.archived_at ? "Restaurar notificación" : "Archivar notificación"}</button>
        </div>
        {map === notice.id && notice.latitude !== null && notice.longitude !== null && <LocationMap latitude={notice.latitude} longitude={notice.longitude} editable={false} />}
        {notice.match_id && <MatchFeedback presentation={notice.presentation} id={notice.match_id} caseId={notice.lost_case_id} status={notice.match_status} onSaved={result => feedbackSaved(notice.id, result)} />}
        {notice.email_status === "SENT" && <p className="field-help">Alerta enviada también por correo.</p>}
        {notice.email_status === "PREVIEWED" && <p className="field-help">Correo generado en el servidor local de pruebas.</p>}
        {notice.email_status === "FAILED" && <p className="field-help">El correo no pudo enviarse. La notificación quedó guardada acá.</p>}
        {notice.email_status === "PENDING" && <p className="field-help">La alerta por correo está pendiente de envío.</p>}
      </article>)}</div>}
      {inbox && inbox.total > 20 && <nav className="lost-dogs-pagination" aria-label="Páginas de notificaciones"><button type="button" className="button button-secondary" disabled={Boolean(action) || offset === 0} onClick={() => setOffset(Math.max(0, offset - 20))}>Anterior</button><span>Página {Math.floor(offset / 20) + 1}</span><button type="button" className="button button-secondary" disabled={Boolean(action) || offset + inbox.items.length >= inbox.total} onClick={() => setOffset(offset + 20)}>Siguiente</button></nav>}
    </>}
    {error && <p role="alert" className="notice notice-error">{error}</p>}
  </main>;
}
