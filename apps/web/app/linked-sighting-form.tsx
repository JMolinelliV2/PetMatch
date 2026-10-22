"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import type { Place } from "@/lib/places";
import {analyticsGeo} from "@/lib/places";
import { lostDogsEndpoint, speciesLabel } from "@/lib/lost-dogs";
import type { LostDogNotice } from "@/lib/lost-dogs";
import { localDateTime, sightingMessage } from "@/lib/linked-sightings";
import type { SightingResult } from "@/lib/linked-sightings";
import { LocationPicker } from "./location-picker";
import { DogPhoto } from "./perdidos/dog-photo";
import { PhotoUploader } from "./ui/photo-uploader";
import { ReportId } from "./ui/report-id";
import { ReportPurpose } from "./ui/report-purpose";

export function LinkedSightingForm({ caseId }: { caseId: string }) {
  const [target, setTarget] = useState<LostDogNotice | null>(null);
  const [missing, setMissing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [locationError, setLocationError] = useState("");
  const [location, setLocation] = useState<Place | null>(null);
  const [photos, setPhotos] = useState<File[]>([]);
  const [recent, setRecent] = useState(true);
  const [when, setWhen] = useState(() => localDateTime());
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<SightingResult | null>(null);
  const [refresh, setRefresh] = useState(0);
  const [statusError, setStatusError] = useState("");
  const [paused, setPaused] = useState(false);
  const submission = useRef<{ id: string; date: string } | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const resultId = result?.id;

  useEffect(() => {
    const controller = new AbortController();
    void fetch(`${lostDogsEndpoint}/${encodeURIComponent(caseId)}`, { cache: "no-store", signal: controller.signal }).then(async response => {
      if (response.status === 404 || response.status === 422) { setMissing(true); return; }
      if (!response.ok) throw new Error("No pudimos cargar el aviso. Intentá de nuevo.");
      const data: LostDogNotice = await response.json();
      if (!controller.signal.aborted) setTarget(data);
    }).catch(cause => { if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "No pudimos cargar el aviso."); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [caseId]);


  useEffect(() => {
    if (!resultId) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    const deadline = Date.now() + 5 * 60000;
    setPaused(false); setStatusError("");
    async function update() {
      try {
        const response = await fetch(`/api/sightings/${caseId}?id=${resultId}`, { cache: "no-store", signal: controller.signal });
        if (!response.ok) throw new Error("No pudimos consultar la revisión. Tu avistamiento sigue guardado.");
        const next: SightingResult = await response.json();
        if (controller.signal.aborted) return;
        setResult(next);
        if (next.status === "PENDING" && Date.now() < deadline) timer = setTimeout(update, 5000);
        else if (next.status === "PENDING") setPaused(true);
      } catch (cause) { if (!controller.signal.aborted) setStatusError(cause instanceof Error ? cause.message : "No pudimos consultar la revisión."); }
    }
    void update();
    return () => { controller.abort(); if (timer) clearTimeout(timer); };
  }, [resultId, caseId, refresh]);

  function changed() { submission.current = null; setError(""); }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || !target) return;
    setError(""); setLocationError("");
    if (!location) { setLocationError("Elegí un lugar de la lista o usá tu ubicación actual."); return; }
    if (photos.length > 4 || photos.some(photo => photo.size > 10 * 1024 * 1024 || !["image/jpeg", "image/png", "image/webp"].includes(photo.type))) {
      setError("Adjuntá hasta 4 fotos JPEG, PNG o WebP, de hasta 10 MB cada una."); return;
    }
    const date = recent ? new Date() : new Date(when);
    if (!Number.isFinite(date.getTime()) || date.getTime() > Date.now() + 60000) { setError("Indicá una fecha y hora válidas, que no estén en el futuro."); return; }
    if (!submission.current) submission.current = { id: crypto.randomUUID(), date: date.toISOString() };
    const form = new FormData();
    form.set("request_id", submission.current.id); form.set("observed_at", submission.current.date);
    form.set("latitude", String(location.latitude)); form.set("longitude", String(location.longitude));
    if (location.accuracyMeters !== undefined) form.set("location_accuracy_meters", String(Math.min(location.accuracyMeters, 100000)));
    if (location.locality) form.set("public_location", location.locality);
    form.set("analytics_geo",JSON.stringify(analyticsGeo(location)));
    for (const photo of photos) form.append("photos", photo);
    setBusy(true);
    try {
      const response = await fetch(`/api/sightings/${caseId}`, { method: "POST", body: form });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "No pudimos guardar el avistamiento. Intentá de nuevo.");
      setResult(data);
      window.dispatchEvent(new Event("mascomatch:notifications"));
      requestAnimationFrame(() => heading.current?.focus());
    } catch (cause) { setError(cause instanceof Error ? cause.message : "No pudimos guardar el avistamiento. Intentá de nuevo."); }
    finally { setBusy(false); }
  }

  return <main id="main-content" className="page linked-sighting-page">
    <Link href={`/perdidos/${encodeURIComponent(caseId)}`} className="back-link"><span aria-hidden="true">←</span> Volver al aviso</Link>
    {loading ? <p role="status" className="page-intro">Cargando aviso…</p>
      : missing ? <><h1>Este aviso ya no está disponible</h1><p className="page-intro">Podés publicar un avistamiento general.</p><Link href="/avistamiento" className="button button-secondary">Publicar un avistamiento</Link></>
      : !target ? <><h1>No pudimos abrir el aviso</h1><p role="alert" className="notice notice-warning">{error}</p></>
      : result ? <>
        <h1 ref={heading} tabIndex={-1}>Avistamiento guardado</h1>
        <p className="page-intro">Gracias por ayudar a encontrar a {target.name}.</p>
        <ReportId id={result.id} publicId={result.public_id} label="ID del reporte" copyable />
        <p role="status" className="notice notice-success sighting-result">{sightingMessage(result, photos.length > 0)}</p>
        {statusError && <p className="notice notice-warning" role="alert">{statusError}</p>}
        {(paused || statusError) && <button type="button" className="text-button" onClick={() => setRefresh(value => value + 1)}>Actualizar revisión</button>}
        <div className="success-actions"><Link href={`/perdidos/${caseId}`} className="button button-primary">Volver al aviso</Link><Link href="/perdidos" className="button button-secondary">Ver animales perdidos</Link></div>
      </> : <>
        <h1>¿Viste a {target.name}?</h1>
        <p className="page-intro">Indicá el lugar y adjuntá fotos si tenés. Tu avistamiento quedará vinculado a este aviso.</p>
        <ReportPurpose kind="sighting" />
        <div className="sighting-target"><DogPhoto dog={target} /><div><strong>{target.name}</strong><ReportId id={target.id} publicId={target.public_id} /><p>{speciesLabel(target.species)} · Aviso de animal perdido</p></div></div>
        <form onSubmit={submit} className="linked-sighting-form" aria-busy={busy}>
          <fieldset disabled={busy} className="form-controls section-fields">
            <div><h2>¿Dónde lo viste?</h2><LocationPicker value={location} required onChange={place => { changed(); setLocation(place); setLocationError(""); }} />{locationError && <p role="alert" className="notice notice-error">{locationError}</p>}</div>
            <div>
              <PhotoUploader name="photos" label="Fotos" maxFiles={4} inputRef={fileInput} files={photos} onFilesChange={next => { changed(); setPhotos(next); }} />
              <p className="field-help">Las fotos del animal pueden verse en el mapa público, junto a una zona aproximada.</p>
            </div>
            <label className="sighting-recent"><input type="checkbox" checked={recent} onChange={event => { changed(); setRecent(event.target.checked); }} />Lo vi recién</label>
            {!recent && <label className="field-label">¿Cuándo lo viste?<input type="datetime-local" value={when} required className="form-input" onChange={event => { changed(); setWhen(event.target.value); }} /><span className="field-help">La fecha y la hora pueden ser aproximadas.</span></label>}
            {error && <p role="alert" className="notice notice-error">{error}</p>}
            <div className="form-footer"><button type="submit" className="button button-primary">{busy ? "Enviando…" : "Enviar avistamiento"}</button><p className="form-privacy">Podés enviarlo sin crear una cuenta. La ubicación exacta se compartirá de forma privada con el dueño si el avistamiento resulta relevante. La identidad del animal siempre está por confirmar.</p></div>
            <p className="form-privacy form-legal">Consultá los <Link href="/terminos" target="_blank" rel="noopener noreferrer" aria-label="Términos y condiciones, se abre en otra pestaña">Términos y condiciones</Link> antes de enviar tu avistamiento.</p>
          </fieldset>
        </form>
      </>}
  </main>;
}
