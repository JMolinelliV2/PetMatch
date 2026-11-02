"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { LayerGroup, Map as LeafletMap, TileLayer } from "leaflet";
import { addLostMapMarker, lostMapLocations } from "@/lib/lost-map-marker";
import type { LostMapPoint, LostMapSelection } from "@/lib/lost-map-marker";
import { LostLocationPreview } from "./lost-map-preview";
import { Icon } from "./ui/pictogram";

type Point = LostMapPoint & { layer: "lost" | "sighting" | "found" };
const API = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1").replace(/\/$/, "");

export function HomeLostMap() {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<LeafletMap | null>(null);
  const group = useRef<LayerGroup | null>(null);
  const tiles = useRef<TileLayer | null>(null);
  const [ready, setReady] = useState(false);
  const [mapError, setMapError] = useState("");
  const [points, setPoints] = useState<Point[]>([]);
  const [selection, setSelection] = useState<LostMapSelection | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [mapRefresh, setMapRefresh] = useState(0);

  useEffect(() => {
    let disposed = false;
    let observer: ResizeObserver | undefined;
    setReady(false); setMapError("");
    void import("leaflet").then(L => {
      if (disposed || !container.current) return;
      const instance = L.map(container.current, { scrollWheelZoom: false, zoomControl: false }).setView([-34.9, -56.16], 11);
      map.current = instance;
      L.control.zoom({ zoomInTitle: "Acercar", zoomOutTitle: "Alejar" }).addTo(instance);
      tiles.current = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      }).addTo(instance).on("tileerror", () => { if (!disposed) setMapError("No pudimos cargar algunas partes del mapa. Los avisos siguen disponibles en el catálogo."); });
      group.current = L.layerGroup().addTo(instance);
      observer = new ResizeObserver(() => instance.invalidateSize({ pan: false }));
      observer.observe(container.current);
      setReady(true);
    }).catch(() => { if (!disposed) setMapError("No pudimos abrir el mapa. Podés consultar las mascotas reportadas en el catálogo."); });
    return () => { disposed = true; observer?.disconnect(); map.current?.remove(); map.current = null; group.current = null; tiles.current = null; };
  }, [mapRefresh]);

  useEffect(() => {
    const controller = new AbortController();
    const reload = () => setRefresh(value => value + 1);
    window.addEventListener("focus", reload); window.addEventListener("mascomatch:cases", reload);
    setBusy(true);
    void fetch(`${API}/public/map?days=0&layer=lost`, { cache: "no-store", signal: controller.signal }).then(async response => {
      if (!response.ok) throw new Error("No pudimos cargar las mascotas en el mapa.");
      const data: { points: Point[] } = await response.json();
      if (!controller.signal.aborted) { setPoints(data.points.filter(point => point.layer === "lost")); setError(""); }
    }).catch(cause => { if (!controller.signal.aborted) { setPoints([]); setError(cause instanceof Error ? cause.message : "No pudimos cargar las mascotas en el mapa."); } })
      .finally(() => { if (!controller.signal.aborted) setBusy(false); });
    return () => { controller.abort(); window.removeEventListener("focus", reload); window.removeEventListener("mascomatch:cases", reload); };
  }, [refresh]);

  useEffect(() => {
    if (!ready) return;
    let disposed = false;
    const cleanups: (() => void)[] = [];
    void import("leaflet").then(L => {
      if (disposed || !map.current || !group.current) return;
      group.current.clearLayers(); setSelection(null);
      const bounds: [number, number][] = [];
      for (const location of lostMapLocations(points)) {
        const point = location[0];
        cleanups.push(addLostMapMarker(L, map.current, group.current, location,
          next => { if (!disposed) setSelection(next); },
          content => { if (!disposed) setSelection(current => current?.content === content ? null : current); },
        ));
        bounds.push([point.latitude, point.longitude]);
      }
      if (bounds.length) map.current.fitBounds(bounds, { padding: [32, 32], maxZoom: 13 });
    });
    return () => { disposed = true; cleanups.forEach(cleanup => cleanup()); };
  }, [points, ready]);

  function retryMap() {
    setMapError("");
    if (map.current) tiles.current?.redraw();
    else setMapRefresh(value => value + 1);
  }

  return <section id="mapa-perdidos" className="home-lost-map" aria-labelledby="home-lost-map-title">
    <div className="home-lost-map-heading"><div><h3 id="home-lost-map-title"><Icon name="pin" />Mascotas reportadas en el mapa</h3><p>Pasá el mouse sobre una foto o tocala para ver la miniatura y abrir el aviso.</p></div><Link href="/mapa" className="text-button">Abrir mapa completo <Icon name="arrow" /></Link></div>
    <p className="home-map-status" role="status">{busy || !ready && !mapError ? "Cargando mapa…" : error ? "Los avisos del mapa no están disponibles en este momento." : points.length ? `${points.length} ${points.length === 1 ? "mascota reportada con ubicación" : "mascotas reportadas con ubicación"}` : "No hay avisos activos con ubicación por ahora."}</p>
    <div ref={container} className="home-lost-map-canvas" role="region" aria-label="Mapa de mascotas reportadas" aria-describedby="home-lost-map-help" />
    {selection && createPortal(<LostLocationPreview key={selection.points[0].id} selection={selection} origin="inicio" onRefresh={() => setRefresh(value => value + 1)} />, selection.content)}
    <p className="field-help" id="home-lost-map-help">Los puntos muestran zonas aproximadas. Los avisos sin ubicación se pueden consultar en el catálogo.</p>
    {error && <p className="notice notice-warning" role="alert">{error} <button type="button" className="text-button" onClick={() => setRefresh(value => value + 1)}>Reintentar</button></p>}
    {mapError && <p className="notice notice-warning" role="alert">{mapError} <button type="button" className="text-button" onClick={retryMap}>Reintentar mapa</button></p>}
  </section>;
}
