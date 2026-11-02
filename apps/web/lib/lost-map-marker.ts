import type { LayerGroup, Map as LeafletMap, Popup } from "leaflet";
import { lostDogsEndpoint } from "./lost-dogs";

export type LostMapPoint = { id: string; public_id?: string; title: string; latitude: number; longitude: number; photo_url?: string | null };
export type LostMapSelection = { points: LostMapPoint[]; content: HTMLDivElement; popup: Popup; onLayout: () => void };

export function lostMapLocations(points: LostMapPoint[]): LostMapPoint[][] {
  const locations = new Map<string, LostMapPoint[]>();
  for (const point of points) {
    const key = `${point.latitude},${point.longitude}`;
    const location = locations.get(key) || [];
    location.push(point); locations.set(key, location);
  }
  // Prefer a real photo for the shared marker and its initial preview.
  return [...locations.values()].map(location => [...location].sort((a, b) => Number(Boolean(b.photo_url)) - Number(Boolean(a.photo_url))));
}

export function addLostMapMarker(
  L: typeof import("leaflet"), map: LeafletMap, group: LayerGroup, points: LostMapPoint[],
  onOpen: (selection: LostMapSelection) => void, onClose: (content: HTMLDivElement) => void,
): () => void {
  const point = points[0];
  const avatar = document.createElement("span");
  avatar.className = "lost-map-avatar";
  const fallback = document.createElement("img");
  fallback.src = "/icon.svg"; fallback.alt = ""; fallback.className = "lost-map-avatar-fallback";
  avatar.append(fallback);
  let photo: HTMLImageElement | undefined;
  if (point.photo_url) {
    photo = document.createElement("img");
    photo.className = "lost-map-avatar-photo"; photo.alt = ""; photo.hidden = true; photo.decoding = "async";
    const image = photo;
    image.onload = () => { fallback.remove(); image.hidden = false; };
    image.onerror = () => { image.remove(); };
    // Always use the public, metadata-cleaned photo endpoint, never a storage URL.
    image.src = `${lostDogsEndpoint}/${encodeURIComponent(point.id)}/photo`;
    avatar.append(image);
  }
  const iconContent = document.createElement("span");
  iconContent.append(avatar);
  if (points.length > 1) {
    const count = document.createElement("span");
    count.className = "home-map-pin-count"; count.textContent = String(points.length);
    iconContent.append(count);
  }
  const title = points.length > 1 ? `${points.length} mascotas reportadas en esta zona. Ver miniaturas.` : `${point.title}. Ver miniatura y aviso.`;
  const content = document.createElement("div");
  const popup = L.popup({ minWidth: 200, maxWidth: 260, maxHeight: 340, className: "home-case-popup", autoPan: false, autoPanPadding: [20, 20] }).setContent(content);
  const marker = L.marker([point.latitude, point.longitude], {
    title, alt: title, keyboard: true, riseOnHover: true,
    icon: L.divIcon({ className: "lost-map-pin", html: iconContent, iconSize: [56, 56], iconAnchor: [28, 28], popupAnchor: [0, -30] }),
  }).addTo(group).bindPopup(popup);
  // Clicking an already hovered marker should keep the preview open.
  marker.off("click").off("keypress");
  const element = marker.getElement()!;
  element.setAttribute("aria-label", title); element.setAttribute("aria-expanded", "false");
  let pinned = false;
  let closeTimer: ReturnType<typeof setTimeout> | undefined;
  let popupElement: HTMLElement | undefined;
  let disposed = false;
  function cancelClose() { if (closeTimer !== undefined) clearTimeout(closeTimer); closeTimer = undefined; }
  function scheduleClose() {
    cancelClose();
    if (!pinned) closeTimer = setTimeout(() => { if (!disposed && !pinned) marker.closePopup(); }, 450);
  }
  function updateLayout() {
    if (disposed || !popup.isOpen()) return;
    popup.options.maxWidth = Math.max(160, Math.min(260, map.getContainer().clientWidth - 64));
    popup.options.minWidth = Math.min(200, popup.options.maxWidth);
    popup.options.maxHeight = Math.max(120, Math.min(340, map.getContainer().clientHeight - 80));
    popup.update();
    if (popup.options.autoPan) return;
    // Keep hover previews inside the map without moving the marker out from under the pointer.
    const card = popup.getElement();
    if (!card) return;
    const bounds = map.getContainer().getBoundingClientRect();
    const rect = card.getBoundingClientRect();
    const circle = element.getBoundingClientRect();
    let left = Math.max(bounds.left + 16, Math.min(rect.left, bounds.right - 16 - rect.width));
    if (rect.top < bounds.top + 16 || popup.getElement()?.classList.contains("lost-map-popup-shifted")) {
      if (bounds.right - 16 - circle.right >= rect.width + 12) left = circle.right + 12;
      else if (circle.left - bounds.left - 16 >= rect.width + 12) left = circle.left - 12 - rect.width;
    }
    const dx = left - rect.left;
    const dy = rect.top < bounds.top + 16 ? bounds.top + 16 - rect.top : rect.bottom > bounds.bottom - 16 ? bounds.bottom - 16 - rect.bottom : 0;
    if (dx || dy) {
      const offset = L.point(popup.options.offset || [0, 7]);
      popup.options.offset = offset.add([dx, dy]);
      card.classList.add("lost-map-popup-shifted");
      popup.update();
    }
  }
  function pinPreview() { cancelClose(); pinned = true; }
  function pinOpen() {
    pinPreview();
    if (popup.isOpen()) updateLayout(); else marker.openPopup();
  }
  function hover(event: PointerEvent) {
    if (event.pointerType !== "mouse" || disposed) return;
    cancelClose();
    if (!popup.isOpen()) { pinned = false; popup.options.autoPan = false; marker.openPopup(); }
  }
  function keyboard(event: KeyboardEvent) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault(); event.stopPropagation(); pinOpen();
      popup.getElement()?.querySelector<HTMLAnchorElement>(".leaflet-popup-close-button")?.focus();
    } else if (event.key === "Escape") { marker.closePopup(); }
  }
  function detachPopup() {
    popupElement?.removeEventListener("pointerenter", cancelClose);
    popupElement?.removeEventListener("pointerleave", scheduleClose);
    popupElement?.removeEventListener("focusin", pinPreview);
    popupElement?.removeEventListener("click", pinPreview);
    popupElement = undefined;
  }
  marker.on("click", pinOpen);
  marker.on("popupopen", () => {
    if (disposed) return;
    cancelClose(); element.setAttribute("aria-expanded", "true");
    detachPopup(); popupElement = popup.getElement();
    popupElement?.addEventListener("pointerenter", cancelClose);
    popupElement?.addEventListener("pointerleave", scheduleClose);
    popupElement?.addEventListener("focusin", pinPreview);
    popupElement?.addEventListener("click", pinPreview);
    const close = popupElement?.querySelector(".leaflet-popup-close-button");
    close?.setAttribute("aria-label", "Cerrar miniatura"); close?.setAttribute("title", "Cerrar miniatura");
    onOpen({ points, content, popup, onLayout: updateLayout });
  });
  marker.on("popupclose", () => {
    cancelClose(); pinned = false; detachPopup(); element.setAttribute("aria-expanded", "false");
    popup.options.offset = [0, 7]; popup.getElement()?.classList.remove("lost-map-popup-shifted");
    if (!disposed) onClose(content);
  });
  element.addEventListener("pointerenter", hover);
  element.addEventListener("pointerleave", scheduleClose);
  element.addEventListener("keydown", keyboard);
  map.on("resize", updateLayout);
  function dispose() {
    if (disposed) return;
    disposed = true; cancelClose(); detachPopup();
    element.removeEventListener("pointerenter", hover);
    element.removeEventListener("pointerleave", scheduleClose);
    element.removeEventListener("keydown", keyboard);
    map.off("resize", updateLayout);
    if (photo) { photo.onload = null; photo.onerror = null; }
    marker.closePopup(); marker.off();
  }
  marker.on("remove", dispose);
  return dispose;
}
