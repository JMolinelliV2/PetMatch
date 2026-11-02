"use client";

import { useCallback, useEffect, useId, useRef, useState } from "react";
import { countryName, placeAtMapPoint } from "@/lib/places";
import type { Place, SearchOrigin } from "@/lib/places";
import { LocationMap } from "./location-map";

type Props = { value: Place | null; onChange: (place: Place | null) => void; required?: boolean; lost?: boolean };
const configuredCountry = (process.env.NEXT_PUBLIC_SEARCH_COUNTRY || "UY").toUpperCase();
const defaultCountry = /^[A-Z]{2}$/.test(configuredCountry) ? configuredCountry : "UY";

export function LocationPicker({ value, onChange, required = false, lost = false }: Props) {
  const id = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const operation = useRef(0);
  const reverseController = useRef<AbortController | null>(null);
  const nearbyController = useRef<AbortController | null>(null);
  const nearbyOperation = useRef(0);
  const [query, setQuery] = useState("");
  const [places, setPlaces] = useState<Place[]>([]);
  const [active, setActive] = useState(-1);
  const [open, setOpen] = useState(false);
  const [searching, setSearching] = useState(false);
  const [locating, setLocating] = useState(false);
  const [error, setError] = useState("");
  const [searched, setSearched] = useState(false);
  const [countryCode, setCountryCode] = useState(defaultCountry);
  const [searchOrigin, setSearchOrigin] = useState<SearchOrigin | null>(null);
  const [nearbyLoading, setNearbyLoading] = useState(false);
  const [nearbyError, setNearbyError] = useState("");
  const [mapOpen, setMapOpen] = useState(false);
  const [mapResolving, setMapResolving] = useState(false);

  const enableNearby = useCallback(async (silent = false) => {
    if (!navigator.geolocation || !window.isSecureContext) {
      if (!silent) setNearbyError("No pudimos usar la ubicación del dispositivo. Podés seguir buscando dentro del país indicado.");
      return;
    }
    const requestId = ++nearbyOperation.current;
    nearbyController.current?.abort();
    const controller = new AbortController();
    nearbyController.current = controller;
    setNearbyLoading(true);
    setNearbyError("");
    try {
      const position = await new Promise<GeolocationPosition>((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(resolve, reject, {
          enableHighAccuracy: false, timeout: 10000, maximumAge: 300000,
        });
      });
      if (requestId !== nearbyOperation.current) return;
      const { latitude, longitude } = position.coords;
      const response = await fetch(`/api/places?lat=${latitude}&lon=${longitude}`, { signal: controller.signal });
      const data = await response.json();
      const code = data.places?.[0]?.countryCode;
      if (!response.ok || typeof code !== "string" || !/^[A-Z]{2}$/.test(code)) {
        throw new Error("No pudimos identificar el país de tu ubicación. La búsqueda sigue limitada al país indicado.");
      }
      if (requestId !== nearbyOperation.current) return;
      setCountryCode(code);
      setSearchOrigin({ latitude, longitude, countryCode: code });
    } catch (cause) {
      if (controller.signal.aborted || requestId !== nearbyOperation.current) return;
      if (!silent) setNearbyError(cause instanceof Error ? cause.message
        : "No pudimos obtener tu ubicación. Podés habilitar el permiso del navegador o seguir buscando dentro del país indicado.");
    } finally {
      if (requestId === nearbyOperation.current) setNearbyLoading(false);
    }
  }, []);

  useEffect(() => {
    let disposed = false;
    // Reuse an existing grant; typing into the search box never triggers a permission prompt.
    navigator.permissions?.query({ name: "geolocation" }).then(permission => {
      if (!disposed && permission.state === "granted") void enableNearby(true);
    }).catch(() => {});
    return () => { disposed = true; nearbyOperation.current += 1; nearbyController.current?.abort(); };
  }, [enableNearby]);

  useEffect(() => () => {
    operation.current += 1;
    reverseController.current?.abort();
  }, []);

  useEffect(() => {
    if (value || query.trim().length < 3) {
      setPlaces([]);
      setSearching(false);
      setSearched(false);
      return;
    }
    if (nearbyLoading) { setPlaces([]); setSearching(true); return; }
    const controller = new AbortController();
    setError("");
    setSearching(true);
    setSearched(false);
    const timer = setTimeout(async () => {
      try {
        const params = new URLSearchParams({ q: query.trim(), country: countryCode });
        if (searchOrigin) {
          params.set("bias_lat", String(searchOrigin.latitude));
          params.set("bias_lon", String(searchOrigin.longitude));
        }
        const response = await fetch(`/api/places?${params}`, { signal: controller.signal });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error);
        if (controller.signal.aborted) return;
        setPlaces(data.places);
        setActive(-1);
        setSearched(true);
      } catch (cause) {
        if (controller.signal.aborted) return;
        setError(cause instanceof Error ? cause.message : "No pudimos buscar ese lugar.");
        setPlaces([]);
      } finally {
        if (!controller.signal.aborted) setSearching(false);
      }
    }, 600);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [query, value, searchOrigin, countryCode, nearbyLoading]);

  function edit(next: string) {
    operation.current += 1;
    reverseController.current?.abort();
    setLocating(false);
    setMapResolving(false);
    setMapOpen(false);
    onChange(null);
    setQuery(next);
    setOpen(true);
    setPlaces([]);
    setActive(-1);
    setError("");
  }

  function select(place: Place) {
    operation.current += 1;
    reverseController.current?.abort();
    setLocating(false);
    setMapResolving(false);
    onChange(place);
    setQuery(place.label);
    setOpen(false);
    setPlaces([]);
    setError("");
  }

  async function movePin(latitude: number, longitude: number) {
    const place = placeAtMapPoint(latitude, longitude);
    // Save the new point immediately; never retain the old address or GPS accuracy after a move.
    select(place);
    const requestId = operation.current;
    const controller = new AbortController();
    reverseController.current = controller;
    setMapResolving(true);
    try {
      const response = await fetch(`/api/places?lat=${latitude}&lon=${longitude}`, { signal: controller.signal });
      const data = await response.json();
      if (!response.ok || !data.places?.[0]) throw new Error("No address");
      if (requestId !== operation.current) return;
      const address: Place = data.places[0];
      const resolved = { ...place, label: address.label, detail: address.detail, locality: address.locality, city:address.city, department:address.department, countryCode: address.countryCode };
      onChange(resolved);
      setQuery(resolved.label);
    } catch {
      if (!controller.signal.aborted && requestId === operation.current) {
        setError("El punto del mapa quedó seleccionado, pero no pudimos obtener su dirección.");
      }
    } finally {
      if (requestId === operation.current) setMapResolving(false);
    }
  }

  function locate() {
    if (!navigator.geolocation) {
      setError("Este dispositivo no permite obtener la ubicación. Podés buscar el lugar por su nombre.");
      return;
    }
    if (!window.isSecureContext) {
      setError("Para usar el GPS, abrí el sitio con HTTPS. Mientras tanto, podés buscar una dirección.");
      return;
    }
    const requestId = ++operation.current;
    nearbyOperation.current += 1;
    nearbyController.current?.abort();
    setNearbyLoading(false);
    reverseController.current?.abort();
    setMapResolving(false);
    onChange(null);
    setQuery("");
    setPlaces([]);
    setLocating(true);
    setError("");
    setOpen(false);
    navigator.geolocation.getCurrentPosition(async (position) => {
      if (requestId !== operation.current) return;
      const { latitude, longitude, accuracy } = position.coords;
      let place: Place = {
        id: `device:${latitude}:${longitude}`, label: "Ubicación actual del dispositivo", detail: "Ubicación obtenida del GPS",
        latitude, longitude, accuracyMeters: Math.ceil(accuracy), source: "device",
      };
      // Reverse search supplies a readable address; the original GPS point is kept.
      const controller = new AbortController();
      reverseController.current = controller;
      try {
        const response = await fetch(`/api/places?lat=${latitude}&lon=${longitude}`, { signal: controller.signal });
        const data = await response.json();
        if (response.ok && data.places?.[0]) {
          place = { ...place, label: data.places[0].label, detail: data.places[0].detail,
            locality: data.places[0].locality, city:data.places[0].city, department:data.places[0].department, countryCode: data.places[0].countryCode };
        }
      } catch { /* GPS remains usable when reverse search is unavailable. */ }
      if (requestId === operation.current) {
        if (place.countryCode) {
          setCountryCode(place.countryCode);
          setSearchOrigin({ latitude, longitude, countryCode: place.countryCode });
          setNearbyError("");
        }
        select(place);
      }
    }, (failure) => {
      if (requestId !== operation.current) return;
      setLocating(false);
      const messages: Record<number, string> = {
        1: "No diste permiso para usar la ubicación. Podés habilitarlo en el navegador o buscar el lugar.",
        2: "No pudimos encontrar tu ubicación actual. Probá buscar una dirección o lugar.",
        3: "El dispositivo tardó demasiado en responder. Intentá de nuevo o buscá el lugar.",
      };
      setError(messages[failure.code] || "No pudimos obtener tu ubicación.");
    }, { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 });
  }

  const suggestionsVisible = open && !value && places.length > 0;
  return (
    <div className="location-picker">
      <div className="location-search">
        <label htmlFor={`${id}-input`} className="field-label">
          {lost ? "Último lugar donde la viste" : "Dirección o lugar"} {!required && <span className="optional">(opcional)</span>}
        </label>
        <input
          ref={inputRef} id={`${id}-input`} name="locationSearch"
          role="combobox" aria-autocomplete="list" aria-expanded={suggestionsVisible}
          aria-controls={`${id}-results`}
          aria-activedescendant={suggestionsVisible && active >= 0 ? `${id}-result-${active}` : undefined}
          aria-describedby={`${id}-help`} autoComplete="off" maxLength={200}
          required={required && !value} value={query}
          placeholder="Buscá una dirección, barrio o lugar"
          onChange={event => edit(event.target.value)}
          onFocus={() => setOpen(true)} onBlur={() => setOpen(false)}
          onKeyDown={event => {
            if (event.key === "Escape") setOpen(false);
            if (event.key === "ArrowDown" && places.length) {
              event.preventDefault(); setOpen(true); setActive(index => (index + 1) % places.length);
            }
            if (event.key === "ArrowUp" && places.length) {
              event.preventDefault(); setOpen(true); setActive(index => index <= 0 ? places.length - 1 : index - 1);
            }
            if (event.key === "Enter" && !value) {
              event.preventDefault();
              if (suggestionsVisible) select(places[active >= 0 ? active : 0]);
            }
          }}
          className="form-input"
        />
        {suggestionsVisible && <ul id={`${id}-results`} role="listbox" aria-label="Lugares encontrados" className="location-results">
          {places.map((place, index) => (
            <li key={place.id} id={`${id}-result-${index}`} role="option" aria-selected={active === index}
              onPointerDown={event => event.preventDefault()} onClick={() => select(place)}
              className={`location-option ${active === index ? "location-option-active" : ""}`}>
              <span className="location-option-name">{place.label}</span>
              <span className="location-option-detail">{place.detail}</span>
              {place.distanceMeters !== undefined && <span className="location-option-detail">
                Aprox. {place.distanceMeters < 1000
                  ? `${Math.max(50, Math.round(place.distanceMeters / 50) * 50)} m`
                  : `${new Intl.NumberFormat("es-UY", { maximumFractionDigits: 1 }).format(place.distanceMeters / 1000)} km`} de vos
              </span>}
            </li>
          ))}
        </ul>}
      </div>

      <div className="location-context">
        <span>{nearbyLoading ? "Buscando tu ubicación…" : searchOrigin
          ? `${countryName(countryCode)} · resultados cercanos` : `País: ${countryName(countryCode)}`}</span>
        <button type="button" onClick={() => void enableNearby()} disabled={nearbyLoading || locating} className="text-button">
          {searchOrigin ? "Actualizar cercanía" : "Buscar cerca de mí"}
        </button>
      </div>
      <p id={`${id}-help`} className="status-text">Escribí al menos 3 caracteres y elegí un resultado.</p>

      <div>
        <button type="button" onClick={locate} disabled={locating || nearbyLoading} className="button button-secondary">
          {locating ? "Buscando ubicación…" : "Usar mi ubicación actual"}
        </button>
        <p className="field-help">{lost ? "Usala si estás en el lugar donde se perdió." : "Usala si estás donde viste o encontraste a la mascota."}</p>
      </div>

      <div aria-live="polite">
        {searching && <p className="status-text">Buscando lugares…</p>}
        {!searching && searched && !places.length && !value && <p className="status-text">
          No hay resultados en {countryName(countryCode)}. Probá agregando la ciudad.
        </p>}
        {nearbyError && <p role="alert" className="notice notice-warning">{nearbyError}</p>}
        {error && <p role="alert" className="notice notice-warning">{error}</p>}
      </div>

      {value && <div className="location-selected">
        <p className="location-selected-name">{value.label}</p>
        <p className="status-text">{value.detail}</p>
        {value.source === "device" && <p className="field-help">Precisión aproximada: {value.accuracyMeters} m.</p>}
        <div className="location-actions">
          <button type="button" onClick={() => { edit(""); inputRef.current?.focus(); }} className="text-button">Cambiar lugar</button>
          <button type="button" className="text-button" aria-expanded={mapOpen} aria-controls={`${id}-map`}
            onClick={() => setMapOpen(current => !current)}>{mapOpen ? "Ocultar mapa" : "Ver en mapa"}</button>
        </div>
      </div>}
      {value && mapOpen && <div id={`${id}-map`}>
        <LocationMap latitude={value.latitude} longitude={value.longitude} onMove={(lat, lon) => void movePin(lat, lon)} />
        {mapResolving && <p role="status" className="status-text">Actualizando la dirección del punto elegido…</p>}
      </div>}
      <p className="location-attribution">
        Datos de <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">© OpenStreetMap</a>.
      </p>
    </div>
  );
}
