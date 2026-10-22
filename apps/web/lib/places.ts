export type Place = {
  id: string;
  label: string;
  detail: string;
  locality?: string;
  city?: string;
  department?: string;
  countryCode?: string;
  distanceMeters?: number;
  latitude: number;
  longitude: number;
  accuracyMeters?: number;
  source: "search" | "device" | "map";
};

export function placeAtMapPoint(latitude: number, longitude: number): Place {
  return {
    id: `map:${latitude}:${longitude}`, label: "Punto elegido en el mapa",
    detail: "Ubicación ajustada manualmente", latitude, longitude, source: "map",
  };
}

function record(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" ? value as Record<string, unknown> : {};
}

function text(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

export function normalizePlaces(payload: unknown, limit = 6): Place[] {
  const features = record(payload).features;
  if (!Array.isArray(features)) return [];
  const seen = new Set<string>();
  const places: Place[] = [];
  for (const raw of features) {
    const feature = record(raw);
    const geometry = record(feature.geometry);
    const coordinates = geometry.coordinates;
    if (geometry.type !== "Point" || !Array.isArray(coordinates)) continue;
    const [longitude, latitude] = coordinates;
    if (typeof latitude !== "number" || typeof longitude !== "number"
      || !Number.isFinite(latitude) || !Number.isFinite(longitude)
      || Math.abs(latitude) > 90 || Math.abs(longitude) > 180) continue;
    const properties = record(feature.properties);
    const street = [text(properties.street), text(properties.housenumber)].filter(Boolean).join(" ");
    const name = text(properties.name);
    const label = (street && (!name || name === text(properties.street)) ? street
      : name || street || text(properties.city) || text(properties.country)).slice(0, 180);
    if (!label) continue;
    const detail = [...new Set([
      street !== label ? street : "", text(properties.district), text(properties.city),
      text(properties.state), text(properties.country),
    ].filter(part => part && part !== label))].join(", ").slice(0, 350);
    const locality = [...new Set([text(properties.district), text(properties.city), text(properties.state), text(properties.country)].filter(Boolean))].join(", ").slice(0, 350);
    const id = `${latitude}:${longitude}:${label}:${detail}`;
    if (seen.has(id)) continue;
    seen.add(id);
    const rawCountry = text(properties.countrycode || properties.country_code).toUpperCase();
    const countryCode = /^[A-Z]{2}$/.test(rawCountry) ? rawCountry : undefined;
    places.push({ id, label, detail, locality, city: text(properties.city), department:text(properties.state),countryCode, latitude, longitude, source: "search" });
  }
  return places.slice(0, limit);
}

export type SearchOrigin = { latitude: number; longitude: number; countryCode: string };

export function analyticsGeo(place?:Place|null){
  const coarse=(value?:string)=>value&&value.length<=80&&/^[\p{L} '\-.,()]+$/u.test(value)?value:"unknown";
  return {country:place?.countryCode&&/^[A-Z]{2}$/.test(place.countryCode)?place.countryCode:"ZZ",department:coarse(place?.department),locality:coarse(place?.city)};
}

export function countryName(code: string): string {
  return new Intl.DisplayNames(["es"], { type: "region" }).of(code) || code;
}

function normalizedText(value: string): string {
  return value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase()
    .replace(/[^a-z0-9]+/g, " ").trim();
}

function exactMatch(place: Place, query: string): boolean {
  const normalizedQuery = normalizedText(query);
  if (["plaza", "parque", "calle", "avenida", "barrio", "ruta"].includes(normalizedQuery)) return false;
  return [place.label, place.city ? `${place.label}, ${place.city}` : "",
    place.locality ? `${place.label}, ${place.locality}` : "", `${place.label}, ${place.detail}`]
    .filter(Boolean).some(term => normalizedText(term) === normalizedQuery);
}

function distanceTo(place: Place, origin: SearchOrigin): number {
  const radians = (degrees: number) => degrees * Math.PI / 180;
  const latDelta = radians(place.latitude - origin.latitude);
  const lonDelta = radians(place.longitude - origin.longitude);
  const a = Math.sin(latDelta / 2) ** 2 + Math.cos(radians(origin.latitude))
    * Math.cos(radians(place.latitude)) * Math.sin(lonDelta / 2) ** 2;
  return Math.round(6_371_000 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(Math.max(0, 1 - a))));
}

export function rankPlaces(places: Place[], query: string, countryCode: string, origin?: SearchOrigin): Place[] {
  const unique = new Map<string, Place>();
  for (const place of places) {
    // Filter again after retrieval: neither an exact name nor proximity crosses countries.
    if (place.countryCode !== countryCode.toUpperCase() || unique.has(place.id)) continue;
    unique.set(place.id, origin ? { ...place, distanceMeters: distanceTo(place, origin) } : place);
  }
  return [...unique.values()].map((place, index) => ({ place, index, exact: exactMatch(place, query) }))
    .sort((a, b) => Number(b.exact) - Number(a.exact)
      || (origin ? a.place.distanceMeters! - b.place.distanceMeters! : 0) || a.index - b.index)
    .slice(0, 6).map(result => result.place);
}

