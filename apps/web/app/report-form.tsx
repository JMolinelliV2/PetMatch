"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { speciesOptions } from "@/lib/species";
import type { Place } from "@/lib/places";
import {analyticsGeo} from "@/lib/places";
import {track} from "@/lib/product-analytics";
import { LocationPicker } from "./location-picker";
import { ReportMatches } from "./report-matches";
import { ReportConfirmation } from "./report-confirmation";
import { Stepper } from "./ui/stepper";
import { PhotoUploader } from "./ui/photo-uploader";
import {usePhotoSelection} from "./use-photo-selection";
import {MAX_REPORT_PHOTOS,photoSelectionError,uploadReportPhotos} from "@/lib/report-photos";
import { SexSelector } from "./ui/sex-selector";
import { Icon } from "./ui/pictogram";
import type { SessionUser } from "./account-session";
import { VerifyEmailNotice } from "./verify-email-notice";
import { ReportPurpose } from "./ui/report-purpose";

type ReportKind = "lost" | "sighting" | "found";
type AccountMode = "register" | "login";
type Step = 1 | 2 | 3;
type Review = { animal: string; description: string; when: string; note: string };
type FormControl = HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement;
const inputClass = "form-input";
const labels: Record<ReportKind, { title: string; intro: string; submit: string; event: string }> = {
  lost: { title: "Perdí una mascota", intro: "Si perdiste a tu mascota, completá sus datos y el último lugar donde la viste.", submit: "Publicar mascota perdida", event: "Dónde y cuándo se perdió" },
  sighting: { title: "Vi una mascota", intro: "Si viste una mascota que parece perdida, describila e indicá dónde la viste.", submit: "Publicar avistamiento", event: "Dónde y cuándo la viste" },
  found: { title: "Encontré una mascota", intro: "Si encontraste una mascota, registrá sus datos y dónde la encontraste.", submit: "Publicar mascota encontrada", event: "Dónde y cuándo la encontraste" },
};

class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

async function readResponse<T>(response: Response): Promise<T> {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof data.detail === "string" ? data.detail : "";
    if (response.status === 401) throw new ApiError("El correo o la contraseña no son correctos.", 401);
    if (response.status === 409 && detail.includes("email")) {
      throw new ApiError("Ya existe una cuenta con ese correo. Elegí “Ya tengo cuenta” para ingresar.", 409);
    }
    throw new ApiError(detail || "No pudimos guardar el reporte. Revisá los datos e intentá de nuevo.", response.status);
  }
  return data as T;
}

async function send<T>(path: string, body: object): Promise<T> {
  const account = path.startsWith("/auth/");
  const response = await fetch(account ? "/api/session" : `/api/backend${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(account ? { ...body, mode: path.split("/").at(-1) } : body),
  });
  const result = await readResponse<T>(response);
  if (account) window.dispatchEvent(new Event("mascomatch:session"));
  return result;
}

function Section({ title, number, active, children }: { title: string; number: Step; active: Step; children: ReactNode }) {
  return (
    <fieldset className="form-section" data-step={number} hidden={active !== number}>
      <legend className="sr-only">{title}</legend>
      <div className="section-fields">{children}</div>
    </fieldset>
  );
}

export function ReportForm({ kind }: { kind: ReportKind }) {
  const feedbackId = useId();
  const formRef = useRef<HTMLFormElement>(null);
  const stepHeadingRef = useRef<HTMLHeadingElement>(null);
  const photoInputRef = useRef<HTMLInputElement>(null);
  const photoNoticeRef = useRef<HTMLDivElement>(null);
  const pendingFocus = useRef<{ name: string; native: boolean } | null>(null);
  const [step, setStep] = useState<Step>(1);
  const [review, setReview] = useState<Review | null>(null);
  const [savedReport, setSavedReport] = useState<{ ownerType: "lost_case" | "observation"; ownerId: string; publicId?: string } | null>(null);
  const [error, setError] = useState("");
  const [errorField, setErrorField] = useState("");
  const [success, setSuccess] = useState("");
  const [photoWarning, setPhotoWarning] = useState("");
  const [busy, setBusy] = useState(false);
  const [accountMode, setAccountMode] = useState<AccountMode>("register");
  const [sessionUser, setSessionUser] = useState<(SessionUser & { email: string }) | null>(null);
  const [sessionChecking, setSessionChecking] = useState(true);
  const [sessionError, setSessionError] = useState("");
  const [sessionRefresh, setSessionRefresh] = useState(0);
  const [location, setLocation] = useState<Place | null>(null);
  const [locationError, setLocationError] = useState("");
  const [resetCount, setResetCount] = useState(0);
  const {photos,primaryIndex,changePhotos,setPrimaryIndex} = usePhotoSelection();
  const photo = photos[primaryIndex ?? 0] ?? null;
  const [missingPhotoNotice, setMissingPhotoNotice] = useState(false);
  const [preview, setPreview] = useState("");
  const copy = labels[kind];
  const needsVerification = Boolean(sessionUser && !sessionUser.email_verified);
  const stepTitles = [kind === "lost" ? "Contanos sobre tu mascota" : "Contanos sobre la mascota", copy.event, "Revisá el reporte y dejá tu contacto"];
  const stepIntros = ["Empezá por sus características. Los campos opcionales pueden quedar vacíos.", "La fecha y la hora pueden ser aproximadas. Elegí el lugar por su nombre o dirección.", "Podés editar los datos antes de publicar. Tu contacto se guarda con tu cuenta."];

  useEffect(() => {
    let disposed = false;
    let controller: AbortController | undefined;
    async function load() {
      controller?.abort(); controller = new AbortController();
      const signal = controller.signal;
      setSessionChecking(true);
      try {
        const response = await fetch("/api/session", { cache: "no-store", signal });
        if (!response.ok) throw new Error("No pudimos consultar tu cuenta. Reintentá antes de publicar.");
        const data = await response.json();
        if (!disposed && !signal.aborted) { setSessionUser(data.user); setSessionError(""); }
      } catch (cause) { if (!disposed && !signal.aborted) setSessionError(cause instanceof Error ? cause.message : "No pudimos consultar tu cuenta."); }
      finally { if (!disposed && !signal.aborted) setSessionChecking(false); }
    }
    void load();
    window.addEventListener("mascomatch:session", load);
    window.addEventListener("focus", load);
    return () => { disposed = true; controller?.abort(); window.removeEventListener("mascomatch:session", load); window.removeEventListener("focus", load); };
  }, [sessionRefresh]);

  async function switchAccount() {
    if (busy || sessionChecking) return;
    setSessionChecking(true); setSessionError("");
    try {
      const response = await fetch("/api/session", { method: "DELETE" });
      if (!response.ok) throw new Error("No pudimos cerrar la sesión. Intentá de nuevo.");
      setSessionUser(null); setAccountMode("login");
      window.dispatchEvent(new Event("mascomatch:session"));
    } catch (cause) { setSessionError(cause instanceof Error ? cause.message : "No pudimos cambiar de cuenta."); }
    finally { setSessionChecking(false); }
  }

  useEffect(() => {
    const target = pendingFocus.current;
    if (!target) return;
    pendingFocus.current = null;
    if (target.name === "heading") { stepHeadingRef.current?.focus(); return; }
    const control = formRef.current?.elements.namedItem(target.name) as FormControl | null;
    control?.focus();
    if (target.native) control?.reportValidity();
  }, [step]);

  useEffect(() => {
    if (!photo) { setPreview(""); return; }
    const url = URL.createObjectURL(photo);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [photo]);

  useEffect(() => { if (missingPhotoNotice) photoNoticeRef.current?.focus(); }, [missingPhotoNotice]);

  function goToStep(next: Step) {
    setMissingPhotoNotice(false);
    setError("");
    setErrorField("");
    pendingFocus.current = { name: "heading", native: false };
    setStep(next);
  }

  function invalid(formElement: HTMLFormElement, target: Step, name: string, message: string, native = false) {
    setError(message);
    setErrorField(name);
    if (target !== step) {
      pendingFocus.current = { name, native };
      setStep(target);
    } else {
      const control = formElement.elements.namedItem(name) as FormControl | null;
      control?.focus();
      if (native) control?.reportValidity();
    }
    return false;
  }

  function fieldAttributes(name: string, help?: string) {
    return {
      "aria-invalid": errorField === name || undefined,
      "aria-describedby": [help, errorField === name ? `${feedbackId}-${name}` : ""].filter(Boolean).join(" ") || undefined,
    };
  }
  function fieldFeedback(name: string) {
    return errorField === name && <span id={`${feedbackId}-${name}`} role="alert" className="field-error">{error}</span>;
  }

  function validateStage(formElement: HTMLFormElement, target: Step) {
    const form = new FormData(formElement);
    const text = (key: string) => String(form.get(key) ?? "").trim();
    const controls = formElement.querySelectorAll<FormControl>(`[data-step="${target}"] input, [data-step="${target}"] select, [data-step="${target}"] textarea`);
    // Only validate the current topic; hidden stages stay mounted to preserve their values.
    for (const control of controls) {
      control.setCustomValidity("");
      if (control.required && ["petName", "description", "name"].includes(control.name) && !text(control.name)) {
        control.setCustomValidity("Completá este campo.");
      }
    }
    for (const control of controls) {
      if (control.name !== "locationSearch" && !control.checkValidity()) {
        return invalid(formElement, target, control.name, control.validationMessage, true);
      }
    }
    if (target === 2 && ((kind === "lost" && !location) || (!location && text("locationSearch")))) {
      const message = kind === "lost"
        ? "Elegí un lugar de la lista o usá la ubicación del dispositivo."
        : "Para guardar ese lugar, elegí uno de los resultados de búsqueda.";
      setLocationError(message);
      return invalid(formElement, 2, "locationSearch", message);
    }
    if (target === 1) {
      const photoError = photoSelectionError(photos);
      if (photoError) return invalid(formElement, 1, "photo", photoError);
    }
    if (target === 2) {
      const when = new Date(text("observedAt"));
      if (!Number.isFinite(when.getTime()) || when.getTime() > Date.now() + 60_000) {
        return invalid(formElement, 2, "observedAt", "Ingresá una fecha y hora válidas, que no estén en el futuro.");
      }
    }
    return true;
  }

  function updateReview(formElement: HTMLFormElement) {
    const form = new FormData(formElement);
    const text = (key: string) => String(form.get(key) ?? "").trim();
    const selected = (key: string) => formElement.querySelector<HTMLSelectElement>(`[name="${key}"]`)?.selectedOptions[0]?.textContent ?? "";
    setReview({
      animal: [kind === "lost" ? text("petName") : "", selected("species"), text("sex") !== "unknown" ? selected("sex") : "", text("color") !== "unknown" ? selected("color") : "", text("size") !== "unknown" ? selected("size") : ""].filter(Boolean).join(" · "),
      description: text("description"),
      when: text("observedAt"),
      note: kind === "lost" ? "" : text("eventNote"),
    });
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const formElement = event.currentTarget;
    setError("");
    setErrorField("");
    setSuccess("");
    setPhotoWarning("");
    setLocationError("");
    const form = new FormData(formElement);
    const text = (key: string) => String(form.get(key) ?? "").trim();
    if (step < 3) {
      if (!validateStage(formElement, step)) return;
      if (kind === "lost" && step === 1 && !photo && !missingPhotoNotice) { setMissingPhotoNotice(true); return; }
      if (step === 2) updateReview(formElement);
      goToStep((step + 1) as Step);
      return;
    }
    if (sessionChecking || sessionError) return;
    for (const target of [1, 2, 3] as const) {
      if (!validateStage(formElement, target)) return;
    }
    const when = new Date(text("observedAt"));
    setBusy(true);
    try {
      let accountUser = sessionUser;
      if (!accountUser) {
        if(accountMode==="register")void track({name:"registration_started",page:"REGISTER"});
        const account = await send<{ user: SessionUser & { email: string } }>(`/auth/${accountMode}`, {
          email: text("email").toLowerCase(),
          password: String(form.get("password") ?? ""),
          ...(accountMode === "register" ? { name: text("name") } : {}),
        });
        setSessionUser(account.user);
        accountUser = account.user;
      }
      if (!accountUser.email_verified) return;
      const species = text("species");
      const sex = text("sex");
      const color = text("color");
      const size = text("size");
      // Only authored text belongs in the description. Traits and location have
      // their own fields and remain available to matching without being appended.
      const description = [text("description"), kind !== "lost" ? text("eventNote") : ""].filter(Boolean).join("\n\n");
      const locationData = location ? {
        analytics_geo:analyticsGeo(location),
        latitude: location.latitude,
        longitude: location.longitude,
        ...(location.accuracyMeters === undefined ? {} : { location_accuracy_meters: location.accuracyMeters }),
      } : {};
      let report: { id: string; public_id?: string };
      let ownerType: "lost_case" | "observation";
      if (kind === "lost") {
        const pet = await send<{ id: string }>("/pets", {
          name: text("petName"), species, sex, primary_color: color, size, breed: "unknown",
        });
        report = await send("/lost-cases", {
          pet_id: pet.id, lost_at: when.toISOString(), last_seen_at: when.toISOString(),
          ...locationData, description,
          public_location: location?.locality ?? null,
        });
        ownerType = "lost_case";
      } else {
        report = await send("/observations", {
          species, sex, primary_color: color, size, public_location: location?.locality ?? null, description, observed_at: when.toISOString(), ...locationData,
          share_contact: form.get("shareContact") === "on",
          source_type: kind === "found" ? "FOUND_ANIMAL" : "USER_SIGHTING",
        });
        ownerType = "observation";
      }
      if (photo) {
        try { await uploadReportPhotos(photos, ownerType, report.id,primaryIndex); }
        catch { setPhotoWarning("El reporte se guardó, pero no pudimos subir las fotos. Podés agregarlas desde Mis avisos y elegir la miniatura."); }
      }
      setSuccess(kind === "lost" ? `El aviso de ${text("petName")} quedó guardado.` : "Gracias por ayudar. Tu reporte quedó guardado.");
      setSavedReport({ ownerType, ownerId: report.id, publicId: report.public_id });
      formElement.reset();
      setLocation(null);
      changePhotos([]);
      setResetCount(count => count + 1);
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 401 && sessionUser) {
        setSessionUser(null); setAccountMode("login");
        setError("Tu sesión venció. Ingresá nuevamente para publicar; los datos del reporte siguen en el formulario.");
        window.dispatchEvent(new Event("mascomatch:session"));
      } else setError(cause instanceof ApiError ? cause.message : "No pudimos conectarnos. Verificá tu conexión e intentá de nuevo.");
    } finally {
      setBusy(false);
    }
  }

  if (success) {
    return (
      <ReportConfirmation kind={kind} report={savedReport} message={success} photoWarning={photoWarning} onCreateAnother={() => {
        setSuccess(""); setPhotoWarning(""); setReview(null); setSavedReport(null); goToStep(1);
      }}>
        {savedReport?.ownerType === "observation" && <ReportMatches observationId={savedReport.ownerId} />}
      </ReportConfirmation>
    );
  }

  return (
    <main id="main-content" className="page report-page">
      <h1>{kind === "lost" ? <>Perdí una <span className="title-accent">mascota</span></> : kind === "sighting" ? <>Reportar un <span className="title-accent">avistamiento</span></> : <>Encontré una <span className="title-accent">mascota</span></>}</h1>
      <p className="page-intro">{copy.intro}</p>
      {kind !== "lost" && <ReportPurpose kind={kind} />}
      <div className="report-layout">
      <form ref={formRef} onSubmit={submit} noValidate aria-busy={busy} className="report-form" onChange={event => { const control = event.target; if ((control instanceof HTMLInputElement || control instanceof HTMLSelectElement || control instanceof HTMLTextAreaElement) && control.name === errorField) { setErrorField(""); setError(""); } }}>
        <Stepper steps={["Mascota", "Fecha y lugar", "Contacto y revisión"]} current={step} />
        <div className="form-card">
        <p className="step-count">Paso {step} de 3</p>
        <h2 ref={stepHeadingRef} tabIndex={-1} className="step-heading">{stepTitles[step - 1]}</h2>
        <p className="step-intro">{stepIntros[step - 1]}</p>
        <fieldset disabled={busy} className="form-controls">
          <Section title={kind === "lost" ? "Mascota" : "Datos de la mascota"} number={1} active={step}>
            <div className="form-grid">
              <label className="field-label">Mascota
                <select name="species" required defaultValue="" className={inputClass} {...fieldAttributes("species")}>
                  <option value="" disabled>Seleccioná una opción</option>
                  {speciesOptions.map(([value,label])=><option key={value} value={value}>{label}</option>)}
                </select>
                {fieldFeedback("species")}
                <span className="field-help">MascoMatch admite perros y gatos.</span>
              </label>
              {kind === "lost" && <label className="field-label">Nombre
                <input name="petName" required minLength={1} maxLength={120} autoComplete="off" placeholder="Nombre de tu mascota" className={inputClass} {...fieldAttributes("petName")} />
                {fieldFeedback("petName")}
              </label>}
              <SexSelector />
              <label className="field-label">Color <span className="optional">(opcional)</span>
                <select name="color" defaultValue="unknown" className={inputClass}>
                  <option value="unknown">No lo sé</option><option value="brown">Marrón</option>
                  <option value="black">Negro</option><option value="white">Blanco</option><option value="gray">Gris</option>
                  <option value="cream">Crema</option><option value="orange">Naranja</option><option value="tan">Beige / canela</option>
                  <option value="red">Rojizo</option><option value="multicolor">Varios colores</option>
                </select>
              </label>
              <label className="field-label">Tamaño <span className="optional">(opcional)</span>
                <select name="size" defaultValue="unknown" className={inputClass}>
                  <option value="unknown">No lo sé</option><option value="tiny">Muy pequeño</option>
                  <option value="small">Pequeño</option><option value="medium">Mediano</option><option value="large">Grande</option>
                </select>
              </label>
            </div>
            <label className="field-label">Descripción
              <textarea name="description" required minLength={1} maxLength={2500} rows={3} placeholder="Ej.: tiene una mancha blanca en el pecho, una oreja caída y un collar azul." className={inputClass} {...fieldAttributes("description", "description-help")} />
              <span id="description-help" className="field-help">Contanos sobre sus colores, manchas, collar u otras características.</span>
              {fieldFeedback("description")}
            </label>
            <PhotoUploader name="photo" inputRef={photoInputRef} maxFiles={MAX_REPORT_PHOTOS} files={photos} primaryIndex={primaryIndex} onPrimaryChange={setPrimaryIndex} onFilesChange={files => { changePhotos(files); setMissingPhotoNotice(false); }} />
            {kind !== "lost" && <p className="field-help">La descripción y las fotos de la mascota pueden verse en el mapa público. Tu contacto y la ubicación exacta se mantienen privados.</p>}
          </Section>

          <Section title={copy.event} number={2} active={step}>
            <label className="field-label">{kind === "lost" ? "Última vez que la viste" : "Fecha y hora"}
              <input name="observedAt" type="datetime-local" required className={inputClass} {...fieldAttributes("observedAt")} />
              <span className="field-help">La hora puede ser aproximada.</span>
              {fieldFeedback("observedAt")}
            </label>
            <div>
              <LocationPicker key={resetCount} lost={kind === "lost"} required={kind === "lost"} value={location} onChange={place => { setLocation(place); setLocationError(""); }} />
              {locationError && <p role="alert" className="notice notice-error">{locationError}</p>}
            </div>
            {kind !== "lost" && <label className="field-label">Otra información <span className="optional">(opcional)</span>
              <textarea name="eventNote" maxLength={500} rows={2} placeholder="Por ejemplo, hacia dónde iba o quién lo está cuidando." className={inputClass} />
            </label>}
          </Section>

          <Section title="Contacto y revisión" number={3} active={step}>
            <section className="review-block" aria-labelledby="review-animal-title">
              <div className="review-heading">
                <h3 id="review-animal-title">Mascota</h3>
                <button type="button" className="text-button" onClick={() => goToStep(1)} aria-label="Editar los datos de la mascota">Editar</button>
              </div>
              <dl className="review-details">
                <div><dt>Datos de la mascota</dt><dd>{review?.animal}</dd></div>
                <div><dt>Descripción</dt><dd>{review?.description}</dd></div>
                <div><dt>Fotos</dt><dd>{photo ? `${photos.length} ${photos.length === 1 ? "foto" : "fotos"} · Miniatura: ${photo.name}` : "Sin fotos"}</dd></div>
              </dl>
              {preview && photo?.type.startsWith("image/") && <img src={preview} alt="Miniatura elegida para el reporte" className="photo-preview" />}
            </section>
            <section className="review-block" aria-labelledby="review-place-title">
              <div className="review-heading">
                <h3 id="review-place-title">Fecha y lugar</h3>
                <button type="button" className="text-button" onClick={() => goToStep(2)} aria-label="Editar la fecha y el lugar">Editar</button>
              </div>
              <dl className="review-details">
                <div><dt>Fecha y hora</dt><dd>{review?.when && new Intl.DateTimeFormat("es-UY", { dateStyle: "medium", timeStyle: "short" }).format(new Date(review.when))}</dd></div>
                <div><dt>Lugar</dt><dd>{location?.label ?? "No indicado"}</dd></div>
                {review?.note && <div><dt>Otra información</dt><dd>{review.note}</dd></div>}
              </dl>
            </section>
            <h3 className="contact-heading">Tu contacto</h3>
            {sessionChecking && <p role="status" className="field-help">Consultando tu cuenta…</p>}
            {sessionError && <p role="alert" className="notice notice-warning">{sessionError} <button type="button" className="text-button" onClick={() => setSessionRefresh(value => value + 1)}>Reintentar</button></p>}
            {sessionUser ? <><div className="notice"><p>Vas a publicar con la cuenta de <strong>{sessionUser.name}</strong>.</p><p className="field-help">Correo de contacto: {sessionUser.email}</p><button type="button" className="text-button" disabled={busy || sessionChecking} onClick={() => void switchAccount()}>Usar otra cuenta</button></div>{needsVerification && <><VerifyEmailNotice email={sessionUser.email} /><p className="field-help">Confirmá el correo y volvé a esta pestaña para publicar. Los datos y la foto siguen en el formulario.</p></>}</> : <>
            <div className="account-options" role="group" aria-label="Opciones de cuenta">
              <label><input type="radio" name="accountMode" checked={accountMode === "register"} onChange={() => setAccountMode("register")} />Crear cuenta</label>
              <label><input type="radio" name="accountMode" checked={accountMode === "login"} onChange={() => setAccountMode("login")} />Ya tengo cuenta</label>
            </div>
            <div className="form-grid">
              {accountMode === "register" && <label className="field-label span-full">Tu nombre o apodo
                <input name="name" required minLength={1} maxLength={120} autoComplete="nickname" className={inputClass} {...fieldAttributes("name")} />
                <span className="field-help">En tus publicaciones mostramos solo la primera palabra de este nombre o apodo.</span>
                {fieldFeedback("name")}
              </label>}
              <label className="field-label">Correo electrónico
                <input name="email" type="email" required maxLength={320} autoComplete="email" className={inputClass} {...fieldAttributes("email")} />
                {fieldFeedback("email")}
              </label>
              <label className="field-label">Contraseña
                <input name="password" type="password" required minLength={accountMode === "register" ? 12 : 1} maxLength={128} autoComplete={accountMode === "register" ? "new-password" : "current-password"} className={inputClass} {...fieldAttributes("password")} />
                {accountMode === "register" && <span className="field-help">Mínimo 12 caracteres.</span>}
                {fieldFeedback("password")}
              </label>
            </div>
            </>}
            {kind !== "lost" && <label className="sighting-recent"><input name="shareContact" type="checkbox"/>Compartir mi correo de forma privada con los dueños que reciban una posible coincidencia de este reporte.</label>}
          </Section>

          <div className="form-footer">
            {error && (!errorField || errorField === "photo") && <p role="alert" className="notice notice-error">{error}</p>}
            {kind === "lost" && step === 1 && missingPhotoNotice && !photo && <div ref={photoNoticeRef} tabIndex={-1} role="alert" className="photo-missing-notice"><div className="photo-missing-heading"><span className="feature-icon feature-icon-1"><Icon name="camera" /></span><h3>Una foto puede ayudar a encontrarla</h3></div><p>Una imagen clara ayuda a que otras personas reconozcan a tu mascota y puede mejorar las posibilidades de encontrarla. Podés publicar sin foto y agregarla después.</p><button type="button" className="button button-secondary" onClick={() => photoInputRef.current?.click()}><Icon name="camera" />Agregar una foto</button><p className="field-help">Si no tenés una ahora, elegí «Continuar sin foto».</p></div>}
            <div className="form-navigation">
              {step > 1 && <button type="button" className="button button-secondary" onClick={() => goToStep((step - 1) as Step)}>Atrás</button>}
              <button type="submit" disabled={busy || (step === 3 && (sessionChecking || Boolean(sessionError) || needsVerification))} className="button button-primary submit-button">{busy ? "Guardando…" : step < 3 ? kind === "lost" && step === 1 && missingPhotoNotice && !photo ? "Continuar sin foto →" : "Continuar →" : needsVerification ? "Confirmá tu correo para publicar" : !sessionUser && accountMode === "register" ? "Crear cuenta y confirmar correo" : copy.submit}</button>
            </div>
            <p className="form-privacy">{step === 3 ? !sessionUser && accountMode === "register" ? "Primero crearemos tu cuenta y te enviaremos el enlace de confirmación. Los datos del aviso seguirán en esta pestaña." : "Tu correo y la ubicación exacta no se muestran públicamente." : "Todavía no se publica nada. Podés revisar los datos al final."}</p>
            {step === 3 && <p className="form-privacy form-legal">Consultá los <Link href="/terminos" target="_blank" rel="noopener noreferrer" aria-label="Términos y condiciones, se abre en otra pestaña">Términos y condiciones</Link> antes de enviar tu reporte.</p>}
          </div>
        </fieldset>
        </div>
      </form>
      <aside className="report-sidebar" aria-label="Ayuda para publicar">
        <div className="help-card help-card-blue"><span className="help-icon"><Icon name="shield" /></span><div><h2>{step === 3 ? "Revisá antes de publicar" : "Cada dato puede ayudar"}</h2><p>{step === 3 ? "Comprobá la descripción y el lugar. Podés volver a editarlos antes de enviar." : "Las fotos son opcionales. Compartí los datos que conozcas y elegí el lugar en el mapa."}</p></div></div>
        <div className="help-card help-steps"><h2>¿Qué sigue?</h2><ol>
          <li><span className="help-icon help-icon-coral"><Icon name="camera" /></span><div><h3>Datos y foto</h3><p>Describí a la mascota y agregá una foto si tenés.</p></div></li>
          <li><span className="help-icon help-icon-green"><Icon name="pin" /></span><div><h3>Fecha y lugar</h3><p>Buscá una dirección o ajustá el pin en la misma página.</p></div></li>
          <li><span className="help-icon"><Icon name="check" /></span><div><h3>Revisión y publicación</h3><p>{kind === "lost" ? "Tu aviso aparecerá en Mascotas reportadas. Las alertas estarán en tu cuenta." : "Una vez guardado, compararemos tu reporte con los avisos activos."}</p></div></li>
        </ol></div>
        <p className="sidebar-note"><Icon name="shield" />Tu correo y la ubicación exacta no se muestran públicamente.</p>
      </aside>
      </div>
    </main>
  );
}

