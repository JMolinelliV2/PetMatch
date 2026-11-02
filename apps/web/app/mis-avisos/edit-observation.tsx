"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { analyticsGeo } from "@/lib/places";
import type { Place } from "@/lib/places";
import type { OwnedObservation } from "@/lib/owned-observations";
import { localDateTime } from "@/lib/linked-sightings";
import { speciesOptions } from "@/lib/species";
import { editableReportDescription } from "@/lib/report-description";
import { AccountSession } from "../account-session";
import { LocationPicker } from "../location-picker";
import { PhotoManager } from "../ui/photo-manager";
import { ReportId } from "../ui/report-id";
import { Icon } from "../ui/pictogram";

export function EditObservationForm({ observation }: { observation: OwnedObservation }) {
  const [location, setLocation] = useState<Place | null>(() => observation.latitude !== null && observation.longitude !== null ? {
    id: `stored:${observation.id}`, label: observation.public_location || "Ubicación guardada", detail: "Lugar actual del reporte",
    locality: observation.public_location ?? undefined, latitude: observation.latitude, longitude: observation.longitude,
    accuracyMeters: observation.location_accuracy_meters ?? undefined, source: "map",
  } : null);
  const [locationChanged, setLocationChanged] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const found = observation.source_type === "FOUND_ANIMAL";
  const linked = Boolean(observation.linked_case_id);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setSaved(false); setError("");
    const form = new FormData(event.currentTarget);
    const when = new Date(String(form.get("observedAt")));
    if (!Number.isFinite(when.getTime()) || when.getTime() > Date.now() + 60_000) { setError("Ingresá una fecha y hora válidas, que no estén en el futuro."); return; }
    const description = String(form.get("description") || "").trim();
    if (!description && !linked) { setError("Ingresá una descripción del reporte."); return; }
    if (!location && String(form.get("locationSearch") || "").trim()) { setError("Elegí un resultado de la búsqueda para guardar ese lugar."); return; }
    const payload = {
      description, observed_at: when.toISOString(), share_contact: form.get("shareContact") === "on",
      ...(!linked ? { species: form.get("species"), sex: form.get("sex"), primary_color: form.get("color"), size: form.get("size") } : {}),
      ...(locationChanged && location ? { latitude: location.latitude, longitude: location.longitude, location_accuracy_meters: location.accuracyMeters ?? null,
        public_location: location.locality ?? null, analytics_geo: analyticsGeo(location) } : {}),
    };
    setBusy(true);
    try {
      const response = await fetch(`/api/account/observations/${encodeURIComponent(observation.id)}`, {
        method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (response.status === 401) throw new Error("Tu sesión venció. Volvé a ingresar para guardar los cambios.");
      if (response.status === 404) throw new Error("No encontramos ese reporte en tu cuenta.");
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "No pudimos guardar los cambios. Revisá los datos e intentá de nuevo.");
      setSaved(true);
      window.dispatchEvent(new Event("mascomatch:cases"));
    } catch (cause) { setError(cause instanceof Error && cause.name !== "TypeError" ? cause.message : "No pudimos conectarnos para guardar los cambios. Intentá de nuevo."); }
    finally { setBusy(false); }
  }

  const select = (name: string, label: string, value: string, options: ReadonlyArray<readonly [string, string]>) => {
    const choices = options.some(([key]) => key === value) ? options : [[value, value], ...options];
    return <label className="field-label">{label}<select name={name} className="form-input" defaultValue={value}>{choices.map(([key, text]) => <option key={key} value={key}>{text}</option>)}</select></label>;
  };

  return <div className="observation-edit-layout">
    <form className="observation-edit-card" onSubmit={submit} onChange={() => setSaved(false)} aria-busy={busy}>
      <h2>{found ? "Datos de la mascota encontrada" : "Datos del avistamiento"}</h2>
      <ReportId id={observation.id} publicId={observation.public_id} label="ID del reporte" copyable />
      {linked && <p className="field-help">Este avistamiento está vinculado a un aviso. Podés corregir cuándo y dónde lo viste, sumar detalles y actualizar las fotos.</p>}
      <fieldset disabled={busy} className="section-fields">
        {!linked && <div className="form-grid">
          {select("species", "Mascota", observation.species, speciesOptions)}
          {select("sex", "Sexo", observation.sex, [["unknown", "No lo sé"], ["male", "Macho"], ["female", "Hembra"]])}
          {select("color", "Color principal", observation.primary_color, [["unknown", "No lo sé"], ["brown", "Marrón"], ["black", "Negro"], ["white", "Blanco"], ["gray", "Gris"], ["cream", "Crema"], ["orange", "Naranja"], ["tan", "Beige / canela"], ["red", "Rojizo"], ["multicolor", "Varios colores"]])}
          {select("size", "Tamaño", observation.size, [["unknown", "No lo sé"], ["tiny", "Muy pequeño"], ["small", "Pequeño"], ["medium", "Mediano"], ["large", "Grande"]])}
        </div>}
        <label className="field-label">{found ? "Cuándo lo encontraste" : "Cuándo lo viste"}<input name="observedAt" className="form-input" type="datetime-local" required defaultValue={localDateTime(new Date(observation.observed_at))} /></label>
        <label className="field-label">Descripción{linked && <span className="optional">(opcional)</span>}<textarea name="description" className="form-input" required={!linked} maxLength={4000} rows={4} defaultValue={editableReportDescription(observation.description,observation.description_format,linked)} placeholder="Ej.: tiene una mancha blanca en el pecho, una oreja caída y un collar azul." /></label>
        <div><h3>Ubicación</h3><p className="field-help">Si no elegís otro lugar, conservamos la ubicación actual.</p>
          <LocationPicker value={location} onChange={place => { setLocation(place); setLocationChanged(true); setSaved(false); }} />
        </div>
        <label className="sighting-recent"><input name="shareContact" type="checkbox" defaultChecked={observation.share_contact} />Compartir mi contacto con el dueño si hay una posible coincidencia.</label>
        <p className="form-privacy">El contacto y la ubicación exacta no aparecen en el mapa público.</p>
        {error && <p role="alert" className="notice notice-warning">{error}</p>}
        {saved && <p role="status" className="notice notice-success">Los cambios quedaron guardados. Vamos a volver a comparar el reporte con la información actualizada.</p>}
        <div className="location-actions"><button type="submit" className="button button-primary">{busy ? "Guardando…" : "Guardar cambios"}</button><Link href="/mis-avisos" className="button button-secondary">Cancelar</Link></div>
      </fieldset>
    </form>
    <section className="observation-edit-card" aria-labelledby="observation-photos-title"><h2 id="observation-photos-title"><Icon name="camera" /> Fotos y miniatura</h2>
      <p className="field-help">Podés agregar hasta cinco fotos, quitar las que no correspondan y elegir la principal. Los cambios de fotos se guardan por separado.</p>
      <PhotoManager ownerType="observation" ownerId={observation.id} onChanged={() => window.dispatchEvent(new Event("mascomatch:cases"))} />
    </section>
  </div>;
}

function OwnedEditor({ id }: { id: string }) {
  const [observation, setObservation] = useState<OwnedObservation | null>(null);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setObservation(null); setError("");
    void fetch(`/api/account/observations/${encodeURIComponent(id)}/edit`, { cache: "no-store", signal: AbortSignal.any([controller.signal, AbortSignal.timeout(15000)]) })
      .then(async response => {
        const data = await response.json();
        if (response.status === 401) throw new Error("Tu sesión venció. Volvé a ingresar para editar el reporte.");
        if (!response.ok) throw new Error(response.status === 404 ? "No encontramos ese reporte en tu cuenta." : typeof data.detail === "string" ? data.detail : "No pudimos abrir el reporte.");
        if (!controller.signal.aborted) setObservation(data);
      }).catch(cause => { if (!controller.signal.aborted) setError(cause instanceof Error && !["TypeError", "TimeoutError", "AbortError"].includes(cause.name) ? cause.message : "No pudimos abrir el reporte. Intentá de nuevo."); });
    return () => controller.abort();
  }, [id, refresh]);
  if (error) return <div className="notice notice-warning observation-edit-error" role="alert">{error}<button type="button" className="text-button" onClick={() => setRefresh(value => value + 1)}>Reintentar</button></div>;
  return observation ? <EditObservationForm key={observation.id} observation={observation} /> : <p role="status" className="page-intro">Cargando tu reporte…</p>;
}

export function EditObservation({ id }: { id: string }) {
  return <AccountSession showAccountHeader={false}>{user => <OwnedEditor key={`${user.id}:${id}`} id={id} />}</AccountSession>;
}
