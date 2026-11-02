"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { AccountSession } from "../account-session";
import type { SessionUser } from "../account-session";
import { SavedChangesDialog } from "../ui/saved-changes-dialog";
import { ProfilePhoto } from "./profile-photo";
import { ChangePassword } from "./change-password";

async function requestChange(method: string, payload?: object, action?: "cancel" | "resend") {
  const response = await fetch(`/api/account-settings${action ? `?action=${action}` : ""}`, {
    method, headers: { "Content-Type": "application/json" }, body: payload ? JSON.stringify(payload) : undefined,
  });
  const data = response.status === 204 ? null : await response.json();
  if (!response.ok) throw new Error(response.status === 401 ? "Tu sesión venció. Ingresá nuevamente."
    : typeof data?.detail === "string" ? data.detail : "Revisá los datos e intentá de nuevo.");
  return data;
}

function Settings({ user, onDeleted }: { user: SessionUser; onDeleted: () => void }) {
  const [name, setName] = useState(user.name);
  const [phone, setPhone] = useState(user.phone || "");
  const [email, setEmail] = useState(user.email || "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [savedConfirmation, setSavedConfirmation] = useState<string | null>(null);
  const [savedScope, setSavedScope] = useState<"contact" | "photo" | "password">("contact");
  const [deleteError, setDeleteError] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [emailNotifications, setEmailNotifications] = useState(user.notification_preferences?.email !== false);
  const [preferencesBusy, setPreferencesBusy] = useState(false);
  const [preferencesError, setPreferencesError] = useState("");
  const [preferencesMessage, setPreferencesMessage] = useState("");
  const [photoBusy, setPhotoBusy] = useState(false);
  const [passwordBusy, setPasswordBusy] = useState(false);
  const controlsDisabled = busy || preferencesBusy || photoBusy || passwordBusy;
  const changingEmail = email.trim().toLowerCase() !== user.email;
  useEffect(() => { setName(user.name); setPhone(user.phone || ""); setEmail(user.email || ""); }, [user.name, user.phone, user.email]);
  useEffect(() => { setEmailNotifications(user.notification_preferences?.email !== false); }, [user.notification_preferences?.email]);
  useEffect(() => { if (window.location.hash === "#notificaciones") document.getElementById("notificaciones")?.scrollIntoView({ block: "start" }); }, []);

  async function saveNotificationPreference(email: boolean) {
    if (controlsDisabled) return;
    setPreferencesBusy(true); setPreferencesError(""); setPreferencesMessage("");
    try {
      const response = await fetch("/api/session", { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email }) });
      const updated: SessionUser & { detail?: string } = await response.json();
      if (!response.ok) throw new Error(response.status === 401 ? "Tu sesión venció. Ingresá nuevamente." : typeof updated.detail === "string" ? updated.detail : "No pudimos guardar la preferencia de correo.");
      setEmailNotifications(updated.notification_preferences?.email !== false);
      setPreferencesMessage("Tu preferencia de notificaciones quedó guardada.");
      window.dispatchEvent(new Event("mascomatch:session"));
    } catch (cause) { setPreferencesError(cause instanceof Error ? cause.message : "No pudimos guardar la preferencia de correo."); }
    finally { setPreferencesBusy(false); }
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (controlsDisabled) return;
    const form = event.currentTarget;
    const values = new FormData(form);
    setBusy(true); setError(""); setMessage("");
    try {
      const updated: SessionUser = await requestChange("PATCH", { name: name.trim(), phone: phone.trim() || null, email: email.trim(),
        ...(changingEmail ? { password: String(values.get("password") || "") } : {}) });
      const password = form.elements.namedItem("password");
      if (password instanceof HTMLInputElement) password.value = "";
      setEmail(updated.email || "");
      setSavedScope("contact");
      setSavedConfirmation(updated.pending_email ? "Tus datos se guardaron. Para completar el cambio de correo, abrí el enlace enviado a la nueva dirección. Hasta confirmarlo, seguirá funcionando tu correo actual." : "Tus datos de contacto quedaron actualizados.");
      window.dispatchEvent(new Event("mascomatch:session"));
    } catch (cause) { setError(cause instanceof Error ? cause.message : "No pudimos guardar tus datos."); }
    finally { setBusy(false); }
  }

  async function emailAction(action: "cancel" | "resend") {
    if (controlsDisabled) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await requestChange("POST", undefined, action);
      setMessage(action === "cancel" ? "El cambio de correo fue cancelado." : "Te enviamos otro enlace a la nueva dirección.");
      window.dispatchEvent(new Event("mascomatch:session"));
    } catch (cause) { setError(cause instanceof Error ? cause.message : "No pudimos completar la solicitud."); }
    finally { setBusy(false); }
  }

  async function remove(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (controlsDisabled || confirmation !== "ELIMINAR") return;
    const values = new FormData(event.currentTarget);
    setBusy(true); setDeleteError("");
    try {
      await requestChange("DELETE", { password: String(values.get("password") || ""), confirmation });
      onDeleted();
      window.dispatchEvent(new Event("mascomatch:session"));
      window.dispatchEvent(new Event("mascomatch:cases"));
    } catch (cause) { setDeleteError(cause instanceof Error ? cause.message : "No pudimos eliminar tu cuenta."); }
    finally { setBusy(false); }
  }

  return <>
    {user.admin_access && <Link href="/admin" className="button button-secondary">Abrir panel de administración</Link>}
    {savedConfirmation && <SavedChangesDialog description={savedConfirmation} onClose={() => { if (savedScope === "contact") setMessage(savedConfirmation); setSavedConfirmation(null); }} />}
    <ProfilePhoto user={user} disabled={busy || preferencesBusy || passwordBusy} onBusyChange={setPhotoBusy} onSaved={message => { setSavedScope("photo"); setSavedConfirmation(message); }} />
    <section className="notification-login account-form account-settings" aria-labelledby="contact-title">
      <h2 id="contact-title">Datos de contacto</h2>
      <p className="field-help">El correo se usa para ingresar y recibir alertas. Tu teléfono solo se comparte en los reportes donde lo hayas autorizado.</p>
      <form onSubmit={save} aria-busy={busy}>
        <fieldset className="section-fields" disabled={controlsDisabled}>
          <label className="field-label">Nombre o apodo<input className="form-input" required maxLength={120} autoComplete="nickname" value={name} onChange={event => setName(event.target.value)} /><span className="field-help">En tus publicaciones mostramos solo la primera palabra de este nombre o apodo.</span></label>
          <label className="field-label">Teléfono <span className="field-help">(opcional)</span><input className="form-input" type="tel" maxLength={32} autoComplete="tel" value={phone} onChange={event => setPhone(event.target.value)} /></label>
          <label className="field-label">Correo electrónico<input className="form-input" type="email" required maxLength={320} autoComplete="email" value={email} onChange={event => setEmail(event.target.value)} /><span className="field-help">Para cambiarlo, confirmá la nueva dirección. Hasta entonces seguirá funcionando {user.email}.</span></label>
          {changingEmail && <label className="field-label">Contraseña actual<input className="form-input" type="password" name="password" required maxLength={128} autoComplete="current-password" /><span className="field-help">Al confirmar el nuevo correo, tendrás que ingresar nuevamente.</span></label>}
          <button className="button button-primary" type="submit">{busy ? "Guardando…" : "Guardar cambios"}</button>
        </fieldset>
      </form>
      {user.pending_email && <aside className="notice account-pending"><h3>Cambio de correo pendiente</h3><p>Confirmá el enlace enviado a <strong>{user.pending_email}</strong>. Vence a las 24 horas. Tu dirección actual todavía no cambió.</p><div className="location-actions"><button className="text-button" type="button" disabled={controlsDisabled} onClick={() => void emailAction("resend")}>Reenviar confirmación</button><button className="text-button" type="button" disabled={controlsDisabled} onClick={() => void emailAction("cancel")}>Cancelar cambio</button></div></aside>}
      {message && <p className="notice" role="status">{message}</p>}
      {error && <p className="notice notice-warning" role="alert">{error}</p>}
    </section>
    <ChangePassword disabled={busy || preferencesBusy || photoBusy} onBusyChange={setPasswordBusy} onSaved={message => { setSavedScope("password"); setSavedConfirmation(message); }} />
    <section id="notificaciones" className="notification-login account-form account-notification-settings" aria-labelledby="notification-settings-title">
      <h2 id="notification-settings-title">Notificaciones</h2>
      <label className="sighting-recent"><input type="checkbox" checked={emailNotifications} disabled={controlsDisabled} onChange={event => void saveNotificationPreference(event.target.checked)} aria-describedby="notification-settings-help" />Recibir alertas y recordatorios por correo</label>
      <p id="notification-settings-help" className="field-help">Incluye posibles avistamientos y recordatorios para completar tus avisos. Las alertas también están disponibles en Notificaciones.</p>
      <p className="field-help">Esta preferencia no afecta los correos que solicites para confirmar tu dirección o recuperar tu cuenta.</p>
      {preferencesBusy && <p role="status" className="field-help">Guardando preferencia…</p>}
      {preferencesMessage && <p role="status" className="notice">{preferencesMessage}</p>}
      {preferencesError && <p role="alert" className="notice notice-warning">{preferencesError}</p>}
      <Link href="/notificaciones" className="text-button">Ver mis notificaciones</Link>
    </section>
    <details className="account-danger">
      <summary>Eliminar mi cuenta</summary>
      <h2>Esta acción es definitiva</h2>
      <p>Se eliminarán tu cuenta, tu foto de perfil, todos tus avisos de mascotas perdidas —incluidos los cerrados—, las fotos de esos avisos y tus reseñas.</p>
      <p>Tus avistamientos y reportes de mascotas encontradas se conservarán para ayudar en otras búsquedas, sin vincularlos a tu cuenta ni compartir tu contacto.</p>
      <form onSubmit={remove} aria-busy={busy}><fieldset className="section-fields" disabled={controlsDisabled}>
        <label className="field-label">Contraseña actual<input className="form-input" type="password" name="password" required maxLength={128} autoComplete="current-password" /></label>
        <label className="field-label">Escribí ELIMINAR para confirmar<input className="form-input" required value={confirmation} autoComplete="off" spellCheck={false} onChange={event => setConfirmation(event.target.value)} /></label>
        <button type="submit" className="button button-primary" disabled={confirmation !== "ELIMINAR"}>{busy ? "Eliminando…" : "Eliminar cuenta definitivamente"}</button>
      </fieldset></form>
      {deleteError && <p role="alert" className="notice notice-warning">{deleteError}</p>}
    </details>
  </>;
}

export function AccountSettings() {
  const [deleted, setDeleted] = useState(false);
  if (deleted) return <section className="notification-login account-form"><h2>Tu cuenta fue eliminada</h2><p role="status">Se quitaron tus avisos de mascotas perdidas. Los avistamientos se conservaron sin vincularlos a tu cuenta.</p></section>;
  return <AccountSession>{user => <Settings key={user.id} user={user} onDeleted={() => setDeleted(true)} />}</AccountSession>;
}
