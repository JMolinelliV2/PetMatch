"use client";

import { useState } from "react";
import type { FormEvent } from "react";

export function ChangePassword({ disabled, onBusyChange, onSaved }: {
  disabled: boolean;
  onBusyChange: (busy: boolean) => void;
  onSaved: (message: string) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (disabled || busy) return;
    const form = event.currentTarget;
    const values = new FormData(form);
    const current = String(values.get("currentPassword") || "");
    const password = String(values.get("newPassword") || "");
    const confirmation = String(values.get("confirmPassword") || "");
    setError(""); setMessage("");
    if (password !== confirmation) {
      setError("Las contraseñas nuevas no coinciden.");
      (form.elements.namedItem("confirmPassword") as HTMLInputElement)?.focus();
      return;
    }
    if (password === current) {
      setError("Elegí una contraseña diferente de la actual.");
      (form.elements.namedItem("newPassword") as HTMLInputElement)?.focus();
      return;
    }
    setBusy(true); onBusyChange(true);
    try {
      const response = await fetch("/api/account-settings?action=password", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ current_password: current, new_password: password, confirm_password: confirmation }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(response.status === 401 ? "Tu sesión venció. Ingresá nuevamente."
        : typeof data?.detail === "string" ? data.detail : "Revisá los datos e intentá de nuevo.");
      form.reset();
      const success = "Tu contraseña quedó actualizada. Las demás sesiones se cerraron; podés seguir usando esta cuenta acá.";
      setMessage(success); onSaved(success);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No pudimos cambiar tu contraseña. Intentá de nuevo.");
    } finally { setBusy(false); onBusyChange(false); }
  }

  return <section className="notification-login account-form account-settings" aria-labelledby="password-settings-title">
    <h2 id="password-settings-title">Cambiar contraseña</h2>
    <p className="field-help">Al guardar, se cerrarán las sesiones abiertas en otros dispositivos. Tu sesión actual seguirá disponible.</p>
    <form onSubmit={save} aria-busy={busy}>
      <fieldset className="section-fields" disabled={disabled || busy}>
        <label className="field-label">Contraseña actual<input className="form-input" name="currentPassword" type="password" required maxLength={128} autoComplete="current-password" /></label>
        <label className="field-label">Nueva contraseña<input className="form-input" name="newPassword" type="password" required minLength={12} maxLength={128} autoComplete="new-password" aria-describedby="password-settings-help" /><span id="password-settings-help" className="field-help">Usá entre 12 y 128 caracteres y elegí una diferente de la actual.</span></label>
        <label className="field-label">Repetí la nueva contraseña<input className="form-input" name="confirmPassword" type="password" required minLength={12} maxLength={128} autoComplete="new-password" /></label>
        <button className="button button-primary" type="submit">{busy ? "Guardando…" : "Cambiar contraseña"}</button>
      </fieldset>
    </form>
    {message && <p className="notice" role="status">{message}</p>}
    {error && <p className="notice notice-warning" role="alert">{error}</p>}
  </section>;
}
