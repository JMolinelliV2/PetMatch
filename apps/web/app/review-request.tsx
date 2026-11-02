"use client";
import { useEffect, useId, useState } from "react";
import type { FormEvent } from "react";
import { VerifyEmailNotice } from "./verify-email-notice";
import { Icon } from "./ui/pictogram";
import {RecoveryExperience} from "./recovery-experience";

type Review = { id: string; display_name: string; rating: number; comment: string; created_at: string; visibility: string };
type ReviewState = { eligible: boolean; email_verified: boolean; review: Review | null };

export function ReviewRequest({ caseId, recovered = false }: { caseId: string; recovered?: boolean }) {
  const id = useId();
  const [state, setState] = useState<ReviewState | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const [rating, setRating] = useState(0);
  const [name, setName] = useState("");
  const [comment, setComment] = useState("");
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  const endpoint = `/api/reviews/lost-cases/${caseId}`;

  useEffect(() => {
    const controller = new AbortController();
    const reload = () => setRefresh(value => value + 1);
    window.addEventListener("mascomatch:reviews", reload);
    window.addEventListener("mascomatch:session", reload);
    window.addEventListener("focus", reload);
    void fetch(endpoint, { cache: "no-store", signal: controller.signal }).then(async response => {
      if (!response.ok) throw new Error(response.status === 401 ? "Ingresá de nuevo para dejar tu reseña." : "No pudimos consultar tu reseña.");
      const data: ReviewState = await response.json();
      if (!controller.signal.aborted) { setState(data); setError(""); }
    }).catch(cause => { if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "No pudimos consultar tu reseña."); });
    return () => { controller.abort(); window.removeEventListener("mascomatch:reviews", reload); window.removeEventListener("mascomatch:session", reload); window.removeEventListener("focus", reload); };
  }, [endpoint, refresh]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    if (!rating || comment.trim().length < 20 || !consent) { setError("Elegí una puntuación, escribí al menos 20 caracteres y autorizá la publicación."); return; }
    setBusy(true); setError("");
    try {
      const response = await fetch(endpoint, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ rating, display_name: name.trim(), comment: comment.trim(), consent }) });
      const data = await response.json();
      if (!response.ok) { if (response.status === 409) setRefresh(value => value + 1); throw new Error(typeof data.detail === "string" ? data.detail : "No pudimos guardar tu reseña."); }
      setState(current => current ? { ...current, review: data } : current);
      setExpanded(false);
      window.dispatchEvent(new Event("mascomatch:reviews"));
    } catch (cause) { setError(cause instanceof Error ? cause.message : "No pudimos guardar tu reseña."); }
    finally { setBusy(false); }
  }

  async function withdraw() {
    if (busy) return;
    setBusy(true); setError("");
    try {
      const response = await fetch(endpoint, { method: "DELETE" });
      if (!response.ok) throw new Error("No pudimos retirar tu reseña. Intentá de nuevo.");
      setState(current => current?.review ? { ...current, review: { ...current.review, visibility: "WITHDRAWN" } } : current);
      window.dispatchEvent(new Event("mascomatch:reviews"));
    } catch (cause) { setError(cause instanceof Error ? cause.message : "No pudimos retirar tu reseña."); }
    finally { setBusy(false); }
  }

  if (!state && !error) return null;
  if (state && !state.eligible && !state.review) return null;
  if (dismissed && !expanded && state?.eligible && !state.review) return <div className="review-later"><button type="button" className="text-button" onClick={() => { setExpanded(true); setDismissed(false); }}>Dejar una reseña de MascoMatch</button></div>;
  return <section className="review-request" aria-labelledby={`${id}-title`}>
    {recovered&&<RecoveryExperience caseId={caseId}/>}
    <div className="review-request-heading"><span className="feature-icon"><Icon name="heart" /></span><div><h3 id={`${id}-title`}>{state?.review ? "Tu reseña de MascoMatch" : "¿Cómo fue tu experiencia con MascoMatch?"}</h3><p>{state?.review ? state.review.visibility === "WITHDRAWN" ? "Retiraste tu reseña de la portada." : state.review.visibility === "HIDDEN" ? "Tu reseña está guardada, pero no se muestra en la portada." : "Gracias por compartir tu experiencia con la comunidad." : recovered ? "Nos alegra que tu mascota esté con vos. Si querés, contanos cómo fue la búsqueda." : "Ahora que cerraste el aviso, podés contarnos cómo fue la búsqueda, cualquiera haya sido el resultado."}</p></div></div>
    {state?.review ? <>
      {state.review.visibility !== "WITHDRAWN" && <><p className="review-rating">{state.review.rating} de 5 estrellas</p><p className="review-own-comment">{state.review.comment}</p><p className="field-help">Nombre público: {state.review.display_name}</p><button type="button" disabled={busy} className="text-button" onClick={() => void withdraw()}>{busy ? "Retirando…" : "Retirar mi reseña de la portada"}</button></>}
    </> : state?.eligible ? <>
      {!expanded ? <div className="location-actions"><button type="button" className={dismissed ? "text-button" : "button button-secondary"} onClick={() => { setExpanded(true); setDismissed(false); }}>{dismissed ? "Dejar una reseña" : "Escribir una reseña"}</button>{!dismissed && <button type="button" className="text-button" onClick={() => setDismissed(true)}>Ahora no</button>}<p className="field-help">Es opcional. Tu aviso ya quedó {recovered ? "marcado como encontrado" : "cerrado"}.</p></div> : <>
        {!state.email_verified && <VerifyEmailNotice />}
        <form onSubmit={submit} className="review-form">
          <fieldset disabled={busy || !state.email_verified} className="section-fields">
            <fieldset className="review-rating-options"><legend>¿Cómo valorarías tu experiencia?</legend><div>{[1, 2, 3, 4, 5].map(value => <label key={value} className={rating === value ? "is-selected" : ""}><input type="radio" name={`${id}-rating`} value={value} required checked={rating === value} onChange={() => setRating(value)} /><span>{value}<span aria-hidden="true"> ★</span><span className="sr-only"> {value === 1 ? "estrella" : "estrellas"} de 5</span></span></label>)}</div></fieldset>
            <label className="field-label" htmlFor={`${id}-name`}>Nombre público <span className="optional">(opcional)</span><input id={`${id}-name`} className="form-input" maxLength={80} placeholder="Tu nombre o un apodo" autoComplete="off" value={name} onChange={event => setName(event.target.value)} aria-describedby={`${id}-name-help`} /><span className="field-help" id={`${id}-name-help`}>Si lo dejás vacío, aparecerás como «Anónimo» y no mostraremos tu foto. Tu correo no se publica.</span></label>
            <label className="field-label" htmlFor={`${id}-comment`}>Tu experiencia<textarea id={`${id}-comment`} className="form-input" rows={4} required minLength={20} maxLength={800} value={comment} onChange={event => setComment(event.target.value)} placeholder="Contanos qué te resultó útil y qué podríamos mejorar." aria-describedby={`${id}-comment-help`} /><span className="field-help" id={`${id}-comment-help`}>{comment.length}/800 · Mínimo 20 caracteres. Evitá incluir teléfonos, direcciones o datos de otras personas.</span></label>
            <label className="review-consent"><input type="checkbox" checked={consent} required onChange={event => setConsent(event.target.checked)} /><span>Autorizo que mi reseña, el nombre público elegido y mi foto de perfil aparezcan en la portada de MascoMatch. Si publico como «Anónimo», no se mostrará mi foto.</span></label>
            <div className="location-actions"><button type="submit" className="button button-primary">{busy ? "Publicando…" : "Publicar reseña"}</button><button type="button" className="text-button" onClick={() => setExpanded(false)}>Cancelar</button></div>
          </fieldset>
        </form>
      </>}
    </> : null}
    {error && <p className="notice notice-warning" role="alert">{error}{!state && <button type="button" className="text-button" onClick={() => setRefresh(value => value + 1)}>Reintentar</button>}</p>}
  </section>;
}
