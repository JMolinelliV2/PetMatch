"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { lostDogsEndpoint } from "@/lib/lost-dogs";
import type { LostDogList } from "@/lib/lost-dogs";
import { PetCard } from "../ui/pet-card";

const pageSize = 24;

export function LostDogs() {
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [result, setResult] = useState<LostDogList | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const resultsHeading = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError("");
    const params = new URLSearchParams({ q: search, offset: String(offset), limit: String(pageSize) });
    void fetch(`${lostDogsEndpoint}?${params}`, { signal: controller.signal, cache: "no-store" })
      .then(async response => {
        if (!response.ok) throw new Error("No pudimos cargar los avisos. Intentá de nuevo en un momento.");
        const data: LostDogList = await response.json();
        if (!controller.signal.aborted) {
          if (data.total > 0 && !data.items.length && offset > 0) {
            setOffset(Math.floor((data.total - 1) / pageSize) * pageSize);
          } else setResult(data);
        }
      }).catch(cause => {
        if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "No pudimos cargar los avisos.");
      }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [search, offset, refresh]);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setSearch(query.trim()); setOffset(0); setRefresh(value => value + 1);
  }
  function changePage(next: number) {
    setOffset(next); resultsHeading.current?.focus();
  }

  return <>
    <form className="lost-dogs-search" role="search" onSubmit={submit}>
      <label className="field-label" htmlFor="lost-dogs-query">Buscar por nombre, zona, descripción o ID
        <input id="lost-dogs-query" name="q" type="search" maxLength={120} placeholder="Por ejemplo: Luna, El Pinar o MM-000123" value={query} onChange={event => setQuery(event.target.value)} className="form-input" />
      </label>
      <button type="submit" className="button button-primary">Buscar</button>
      {search && <button type="button" className="text-button" onClick={() => { setQuery(""); setSearch(""); setOffset(0); }}>Ver todos</button>}
    </form>
    <section className="lost-dogs-results" aria-labelledby="lost-results-title" aria-busy={loading}>
      <h2 id="lost-results-title" ref={resultsHeading} tabIndex={-1} className="lost-results-title">{search ? "Resultados de búsqueda" : "Últimos avisos"}</h2>
      <div aria-live="polite">
        {loading && <p className="status-text">Cargando mascotas reportadas…</p>}
        {!loading && !error && result && <p className="status-text">{result.total === 1 ? "1 mascota sigue perdida" : `${result.total} mascotas siguen perdidas`}</p>}
      </div>
      {error && <div className="notice notice-warning" role="alert">{error} <button type="button" className="text-button" onClick={() => setRefresh(value => value + 1)}>Reintentar</button></div>}
      {!loading && !error && result?.items.length === 0 && <div className="lost-dogs-empty">
        <h3>{search ? "No encontramos avisos con esa búsqueda" : "Todavía no hay avisos activos"}</h3>
        <p>{search ? "Probá con otro nombre, zona o característica." : "Cuando alguien publique una mascota perdida, su aviso aparecerá acá."}</p>
        {!search && <Link href="/perdi" className="button button-secondary">Publicar una mascota perdida</Link>}
      </div>}
      {!loading && !error && Boolean(result?.items.length) && <>
        <div className="lost-dogs-grid">
          {result!.items.map(dog => <PetCard key={dog.id} animal={dog} />)}
        </div>
        <nav className="lost-dogs-pagination" aria-label="Páginas de mascotas reportadas">
          <button type="button" className="button button-secondary" disabled={offset === 0} onClick={() => changePage(Math.max(0, offset - pageSize))}>Anterior</button>
          <span>Página {Math.floor(offset / pageSize) + 1} de {Math.max(1, Math.ceil(result!.total / pageSize))}</span>
          <button type="button" className="button button-secondary" disabled={offset + result!.items.length >= result!.total} onClick={() => changePage(offset + pageSize)}>Siguiente</button>
        </nav>
      </>}
    </section>
  </>;
}
