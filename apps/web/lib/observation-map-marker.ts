import type { LayerGroup, Map as LeafletMap, Popup } from "leaflet";
import type { MapReportPoint } from "./public-observations";
import { observationDate, observationTraits, publicObservationsEndpoint } from "./public-observations";

export type ObservationMapSelection = { points: MapReportPoint[]; selectedId: string; content: HTMLDivElement; popup: Popup; onLayout: () => void };
export type ObservationMapHandle = { open: (id?: string) => void; dispose: () => void };

export function observationMapLocations(points: MapReportPoint[]): MapReportPoint[][] {
  const locations = new Map<string, MapReportPoint[]>();
  for (const point of points) {
    const key = `${point.latitude},${point.longitude}`;
    const location = locations.get(key) || [];
    location.push(point); locations.set(key, location);
  }
  return [...locations.values()].map(location => [...location].sort((a, b) => Number(Boolean(b.photo_url)) - Number(Boolean(a.photo_url))));
}

export function addObservationMapMarker(L: typeof import("leaflet"), map: LeafletMap, group: LayerGroup, points: MapReportPoint[], onOpen: (selection: ObservationMapSelection) => void, onClose: (content: HTMLDivElement) => void, shiftX = 0): ObservationMapHandle {
  const point = points[0];
  const title = points.length > 1 ? `${points.length} avistamientos en esta zona. Ver miniaturas.` : `${point.title} · ${observationTraits(point)} · ${observationDate(point.when)}. Ver foto y detalles.`;
  const content = document.createElement("div");
  const icon = document.createElement("span");
  const avatar = document.createElement("span");
  avatar.className = "observation-map-avatar";
  const fallback = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  fallback.setAttribute("viewBox", "0 0 24 24"); fallback.setAttribute("fill", "none");
  fallback.setAttribute("stroke", "currentColor"); fallback.setAttribute("stroke-width", "1.8");
  fallback.setAttribute("stroke-linecap", "round"); fallback.setAttribute("stroke-linejoin", "round");
  fallback.setAttribute("aria-hidden", "true"); fallback.setAttribute("focusable", "false");
  fallback.classList.add("observation-map-avatar-fallback");
  const eye = document.createElementNS("http://www.w3.org/2000/svg", "path");
  eye.setAttribute("d", "M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z");
  const pupil = document.createElementNS("http://www.w3.org/2000/svg", "circle");
  pupil.setAttribute("cx", "12"); pupil.setAttribute("cy", "12"); pupil.setAttribute("r", "3");
  fallback.append(eye, pupil); avatar.append(fallback);
  let photo: HTMLImageElement | undefined;
  if (point.photo_url) {
    photo = document.createElement("img");
    photo.className = "observation-map-avatar-photo"; photo.alt = ""; photo.hidden = true; photo.decoding = "async";
    const image = photo;
    image.onload = () => { fallback.remove(); image.hidden = false; };
    image.onerror = () => { image.remove(); };
    image.src = `${publicObservationsEndpoint}/${encodeURIComponent(point.id)}/photo`;
    avatar.append(image);
  }
  icon.append(avatar);
  if (points.length > 1) { const count = document.createElement("span"); count.className = "home-map-pin-count"; count.textContent = String(points.length); icon.append(count); }
  const popup = L.popup({ minWidth: 200, maxWidth: 260, maxHeight: Math.max(120, Math.min(340, map.getContainer().clientHeight - 80)), className: "home-case-popup observation-map-popup", autoPan: false, autoPanPadding: [16, 16] }).setContent(content);
  const marker = L.marker([point.latitude, point.longitude], { title, alt: title, keyboard: true, riseOnHover: true,
    icon: L.divIcon({ className: "observation-map-pin", html: icon, iconSize: [56, 56], iconAnchor: [28 - shiftX, 28], popupAnchor: [shiftX, -30] }),
  }).addTo(group).bindPopup(popup);
  marker.off("click").off("keypress");
  const element = marker.getElement()!;
  element.setAttribute("aria-label", title); element.setAttribute("aria-expanded", "false");
  let disposed = false;
  let pinned = false;
  let closeTimer: ReturnType<typeof setTimeout> | undefined;
  let selectedId = point.id;
  let popupElement: HTMLElement | undefined;
  const onLayout = () => {
    if (disposed || !popup.isOpen()) return;
    popup.options.maxWidth = Math.max(160, Math.min(260, map.getContainer().clientWidth - 64));
    popup.options.minWidth = Math.min(200, popup.options.maxWidth);
    popup.options.maxHeight = Math.max(120, Math.min(340, map.getContainer().clientHeight - 80));
    popup.update();
    const card = popup.getElement();
    if (!card) return;
    const bounds = map.getContainer().getBoundingClientRect();
    const rect = card.getBoundingClientRect();
    const circle = element.getBoundingClientRect();
    let left = Math.max(bounds.left + 16, Math.min(rect.left, bounds.right - 16 - rect.width));
    if (rect.top < bounds.top + 16 || card.classList.contains("lost-map-popup-shifted")) {
      if (bounds.right - 16 - circle.right >= rect.width + 12) left = circle.right + 12;
      else if (circle.left - bounds.left - 16 >= rect.width + 12) left = circle.left - 12 - rect.width;
    }
    const dx = left - rect.left;
    const dy = rect.top < bounds.top + 16 ? bounds.top + 16 - rect.top : rect.bottom > bounds.bottom - 16 ? bounds.bottom - 16 - rect.bottom : 0;
    if (dx || dy) {
      popup.options.offset = L.point(popup.options.offset || [0, 7]).add([dx, dy]);
      card.classList.add("lost-map-popup-shifted"); popup.update();
    }
  };
  function cancelClose() { if (closeTimer !== undefined) clearTimeout(closeTimer); closeTimer = undefined; }
  function scheduleClose() { cancelClose(); if (!pinned) closeTimer = setTimeout(() => { if (!disposed && !pinned) marker.closePopup(); }, 450); }
  function pinPreview() { cancelClose(); pinned = true; }
  function hover(event: PointerEvent) {
    if (event.pointerType !== "mouse" || disposed) return;
    cancelClose();
    if (!popup.isOpen()) { pinned = false; selectedId = point.id; marker.openPopup(); }
  }
  function open(id = point.id) {
    if (disposed) return;
    pinPreview();
    selectedId = points.some(item => item.id === id) ? id : point.id;
    if (popup.isOpen()) { onOpen({ points, selectedId, content, popup, onLayout }); onLayout(); }
    else marker.openPopup();
    popup.getElement()?.querySelector<HTMLAnchorElement>(".leaflet-popup-close-button")?.focus();
  }
  function escape(event: KeyboardEvent) {
    if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); marker.closePopup(); element.focus(); }
  }
  function keyboard(event: KeyboardEvent) {
    if (event.key === "Enter" || event.key === " ") { event.preventDefault(); event.stopPropagation(); open(); }
    else escape(event);
  }
  function detachPopup() {
    popupElement?.removeEventListener("keydown", escape);
    popupElement?.removeEventListener("pointerenter", cancelClose);
    popupElement?.removeEventListener("pointerleave", scheduleClose);
    popupElement?.removeEventListener("focusin", pinPreview);
    popupElement?.removeEventListener("click", pinPreview);
    popupElement = undefined;
  }
  marker.on("click", () => open());
  marker.on("popupopen", () => {
    if (disposed) return;
    cancelClose(); element.setAttribute("aria-expanded", "true"); detachPopup(); popupElement = popup.getElement();
    popupElement?.addEventListener("keydown", escape);
    popupElement?.addEventListener("pointerenter", cancelClose);
    popupElement?.addEventListener("pointerleave", scheduleClose);
    popupElement?.addEventListener("focusin", pinPreview);
    popupElement?.addEventListener("click", pinPreview);
    const close = popupElement?.querySelector(".leaflet-popup-close-button");
    close?.setAttribute("aria-label", "Cerrar detalles"); close?.setAttribute("title", "Cerrar detalles");
    onOpen({ points, selectedId, content, popup, onLayout });
  });
  marker.on("popupclose", () => {
    cancelClose(); pinned = false; element.setAttribute("aria-expanded", "false"); detachPopup();
    popup.options.offset = [0, 7]; popup.getElement()?.classList.remove("lost-map-popup-shifted");
    if (!disposed) onClose(content);
  });
  element.addEventListener("pointerenter", hover);
  element.addEventListener("pointerleave", scheduleClose);
  element.addEventListener("keydown", keyboard);
  map.on("resize", onLayout);
  function dispose() {
    if (disposed) return;
    disposed = true; cancelClose(); detachPopup();
    element.removeEventListener("pointerenter", hover);
    element.removeEventListener("pointerleave", scheduleClose);
    element.removeEventListener("keydown", keyboard);
    map.off("resize", onLayout);
    if (photo) { photo.onload = null; photo.onerror = null; }
    marker.closePopup(); marker.off();
  }
  marker.on("remove", dispose);
  return { open, dispose };
}
