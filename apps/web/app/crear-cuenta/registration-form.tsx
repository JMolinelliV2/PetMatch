"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import type { SessionUser } from "../account-session";
import { VerifyEmailNotice } from "../verify-email-notice";
import { useSessionRefresh } from "../use-session-refresh";
import { AccountLoading } from "../ui/account-loading";
import { track } from "@/lib/product-analytics";

export function RegistrationForm() {
  const started=useRef(false);
  const sessionVersion = useSessionRefresh();
  const router = useRouter();
  const [user, setUser] = useState<SessionUser | null>(null);
  const [checking, setChecking] = useState(true);
  const [sessionUnavailable, setSessionUnavailable] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const [busy, setBusy] = useState(false);
  const [created, setCreated] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    setSessionUnavailable(false); setError("");
    void fetch("/api/session", { cache: "no-store", signal: controller.signal }).then(async response => {
      if (!response.ok) throw new Error("No pudimos consultar tu sesión. Intentá de nuevo.");
      const data = await response.json();
      if (!controller.signal.aborted) setUser(data.user);
    }).catch(cause => {
      if (!controller.signal.aborted) { setSessionUnavailable(true); setError(cause instanceof Error ? cause.message : "No pudimos consultar tu sesión."); }
    }).finally(() => { if (!controller.signal.aborted) setChecking(false); });
    return () => controller.abort();
  }, [refresh, sessionVersion]);

  useEffect(() => {
    if (user && !created) router.replace(user.email_verified ? "/mis-avisos" : "/confirmar-correo");
  }, [user, created, router]);

  async function register(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || user) return;
    const form = event.currentTarget;
    const values = new FormData(form);
    const name = String(values.get("name") || "").trim();
    const password = String(values.get("password") || "");
    setError("");
    if (!name) { setError("Ingresá tu nombre o un apodo."); return; }
    if (password !== values.get("confirmPassword")) { setError("Las contraseñas no coinciden. Volvé a escribirlas."); return; }
    setBusy(true);
    try {
      const response = await fetch("/api/session", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: "register", name, email: String(values.get("email") || "").trim(), password }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(response.status === 409 ? "Ya existe una cuenta con ese correo. Ingresá o recuperá tu contraseña."
        : response.status === 422 ? "Revisá tus datos: ingresá un correo válido y una contraseña de entre 12 y 128 caracteres."
        : response.status === 429 ? "Se alcanzó el límite de intentos de registro. Probá más tarde."
        : response.status === 503 && typeof data.detail === "string" ? data.detail
        : "No pudimos crear tu cuenta. Intentá de nuevo.");
      form.reset(); setUser(data.user); setCreated(true);
      window.dispatchEvent(new Event("mascomatch:session"));
    } catch (cause) { setError(cause instanceof Error ? cause.message : "No pudimos crear tu cuenta. Intentá de nuevo."); }
    finally { setBusy(false); }
  }

  async function logout() {
    setBusy(true); setError("");
    try {
      const response = await fetch("/api/session", { method: "DELETE" });
      if (!response.ok) throw new Error("No pudimos cerrar tu sesión. Intentá de nuevo.");
      setUser(null); setCreated(false);
      window.dispatchEvent(new Event("mascomatch:session"));
    } catch (cause) { setError(cause instanceof Error ? cause.message : "No pudimos cerrar tu sesión."); }
    finally { setBusy(false); }
  }

  if (checking) return <AccountLoading description="Estamos abriendo tu espacio en MascoMatch." />;
  if (sessionUnavailable) return <div className="notice notice-warning" role="alert"><p>{error}</p><button type="button" className="text-button" onClick={() => { setChecking(true); setRefresh(value => value + 1); }}>Reintentar</button></div>;
  if (user && !created) return <AccountLoading title="Abriendo tu cuenta" description="Enseguida vas a poder continuar." />;
  if (user) return <section className="notification-login account-form">
    <h2>Tu cuenta está creada</h2>
    <p role="status">{user.email_verified ? "Ya podés publicar desde tu cuenta." : "Ahora confirmá tu correo para empezar a publicar. Recibirás un mensaje con el enlace."}</p>
    {user.email_verification_required && !user.email_verified && <VerifyEmailNotice email={user.email} />}
    <div className="location-actions"><Link href={user.email_verified ? "/mi-cuenta" : "/confirmar-correo"} className="button button-primary">{user.email_verified ? "Ir a mi cuenta" : "Confirmar mi correo"}</Link><Link href="/perdidos" className="text-button">Ver mascotas reportadas</Link></div>
    <button type="button" className="text-button" disabled={busy} onClick={() => void logout()}>{busy ? "Cerrando sesión…" : "Cerrar sesión"}</button>
    {error && <p role="alert" className="notice notice-warning">{error}</p>}
  </section>;

  return <form className="notification-login account-form" onSubmit={register} aria-busy={busy} onFocusCapture={()=>{if(!started.current){started.current=true;void track({name:"registration_started",page:"REGISTER"});}}}>
    <fieldset className="section-fields" disabled={busy}>
      <label className="field-label">Nombre o apodo<input className="form-input" name="name" required minLength={1} maxLength={120} autoComplete="nickname" /><span className="field-help">En tus publicaciones mostramos solo la primera palabra de este nombre o apodo.</span></label>
      <label className="field-label">Correo electrónico<input className="form-input" name="email" type="email" required maxLength={320} autoComplete="email" /><span className="field-help">Para recibir alertas y recuperar el acceso a tu cuenta.</span></label>
      <label className="field-label">Contraseña<input className="form-input" name="password" type="password" required minLength={12} maxLength={128} autoComplete="new-password" /><span className="field-help">Usá al menos 12 caracteres.</span></label>
      <label className="field-label">Repetí la contraseña<input className="form-input" name="confirmPassword" type="password" required minLength={12} maxLength={128} autoComplete="new-password" /></label>
      <p className="form-privacy form-legal">Antes de crear tu cuenta, consultá los <Link href="/terminos" target="_blank" rel="noopener noreferrer" aria-label="Términos y condiciones, se abre en otra pestaña">Términos y condiciones</Link>.</p>
      <button className="button button-primary" type="submit">{busy ? "Creando cuenta…" : "Crear cuenta"}</button>
    </fieldset>
    {error && <p role="alert" className="notice notice-warning">{error}</p>}
    <p>¿Ya tenés una cuenta? <Link className="text-button" href="/login">Ingresar</Link></p>
    <Link className="text-button" href="/recuperar">Olvidé mi contraseña</Link>
  </form>;
}
