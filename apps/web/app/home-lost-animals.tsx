"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { lostDogsEndpoint } from "@/lib/lost-dogs";
import type { LostDogList } from "@/lib/lost-dogs";
import { PetCard } from "./ui/pet-card";
import { Icon } from "./ui/pictogram";
import { HomeLostMap } from "./home-lost-map";

export function HomeLostAnimals() {
  const [result, setResult] = useState<LostDogList | null>(null);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    void fetch(`${lostDogsEndpoint}?limit=4&offset=0`, { cache: "no-store", signal: controller.signal }).then(async response => {
      if (!response.ok) throw new Error("No pudimos cargar los avisos en este momento.");
      const data: LostDogList = await response.json();
      if (!controller.signal.aborted) { setResult(data); setError(""); }
    }).catch(cause => { if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "No pudimos cargar los avisos."); });
    return () => controller.abort();
  }, [refresh]);
  return <section className="home-animals" aria-labelledby="home-animals-title">
    <div className="section-heading"><div><h2 id="home-animals-title">Mascotas reportadas</h2></div><Link href="/perdidos" className="text-button">Ver todos los avisos <Icon name="arrow" /></Link></div>
    {error ? <p className="notice notice-warning" role="alert">{error} <button className="text-button" type="button" onClick={() => setRefresh(value => value + 1)}>Reintentar</button></p>
      : !result ? <div className="home-animals-loading" role="status" aria-label="Cargando mascotas reportadas"><div className="skeleton skeleton-card" /><div className="skeleton skeleton-card" /></div>
        : result.items.length ? <div className="home-animals-grid">{result.items.map(animal => <PetCard key={animal.id} animal={animal} compact />)}</div>
          : <div className="lost-dogs-empty"><h3>Todavía no hay avisos activos</h3><p>Las mascotas con avisos activos aparecerán acá.</p><Link href="/perdi" className="button button-secondary">Publicar un aviso</Link></div>}
    <HomeLostMap />
  </section>;
}
