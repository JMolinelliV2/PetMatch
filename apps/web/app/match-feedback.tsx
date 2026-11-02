"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import {RecoveryQuestion} from "./recovery-question";
import type {RecoveryReason} from "./recovery-question";
import {useMatchVisibility} from "./product-tracking";

type FeedbackStatus = "CONFIRMED_RELEVANT" | "FALSE_MATCH" | "RESOLVED";
export type FeedbackSaved = { status: FeedbackStatus; recovered: boolean; caseId: string };

export function MatchFeedback({ id, caseId, status, caseActive = true, onSaved, presentation }: {
  presentation?:string|null;
  id: string;
  caseId: string;
  status: string | null;
  caseActive?: boolean;
  onSaved?: (result: FeedbackSaved) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [current, setCurrent] = useState(status);
  const [recovered, setRecovered] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [recovering,setRecovering]=useState(false);
  const visibility=useMatchVisibility(presentation);

  useEffect(() => { setCurrent(status); }, [status]);

  async function save(value: FeedbackStatus, wasRecovered = false, reason:RecoveryReason="PREFER_NOT_TO_SAY") {
    if (busy || !caseActive || recovered) return;
    setBusy(true); setMessage(""); setError("");
    try {
      const response = await fetch(`/api/matches/${id}/feedback`, {
        method: "PATCH", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: value, recovered: wasRecovered,...(wasRecovered?{recovery_reason:reason}:{}) }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "No pudimos guardar tu respuesta. Intentá de nuevo.");
      setCurrent(data.status); setRecovered(wasRecovered);
      setMessage(wasRecovered ? "Tu mascota quedó marcada como encontrada. La búsqueda está cerrada."
        : value === "RESOLVED" ? "Confirmaste el avistamiento. Tu búsqueda sigue activa y la mascota sigue publicada como perdida."
        : value === "FALSE_MATCH" ? "Descartaste este avistamiento. Tu búsqueda sigue activa."
        : "Guardaste este avistamiento como posible coincidencia. Tu búsqueda sigue activa.");
      onSaved?.({ status: data.status as FeedbackStatus, recovered: wasRecovered, caseId });
      window.dispatchEvent(new Event("mascomatch:notifications"));
      if (wasRecovered) window.dispatchEvent(new Event("mascomatch:cases"));
    } catch (cause) { setError(cause instanceof Error ? cause.message : "No pudimos guardar tu respuesta."); }
    finally { setBusy(false); }
  }

  return <section ref={visibility} className="match-feedback" aria-label="Revisar avistamiento">
    {!caseActive || recovered ? <>
      <p className="field-help">{recovered ? "Tu mascota está encontrada y este aviso ya no aparece en las búsquedas activas." : "La búsqueda de este aviso ya está cerrada."}</p>
      <Link className="text-button" href="/mis-avisos">Ver el estado en Mis avisos</Link>
    </> : <>
      <h3>¿Es tu mascota?</h3>
      <div className="location-actions">
        <button type="button" className="text-button" disabled={busy || current === "CONFIRMED_RELEVANT"} onClick={() => void save("CONFIRMED_RELEVANT")}>Podría ser, todavía no estoy seguro</button>
        <button type="button" className="text-button" disabled={busy || current === "FALSE_MATCH"} onClick={() => void save("FALSE_MATCH")}>No es mi mascota</button>
        <button type="button" className="text-button" disabled={busy || current === "RESOLVED"} onClick={() => void save("RESOLVED")}>Es mi mascota, sigo buscándola</button>
      </div>
      {current === "RESOLVED" && <p className="field-help">Este avistamiento está confirmado. La búsqueda sigue abierta hasta que recuperes a tu mascota.</p>}
      <div className="match-recovery">
        <h3>¿Ya está con vos?</h3>
        <p className="field-help">Si ya recuperaste a tu mascota, marcala como encontrada. El aviso dejará de aparecer en el listado público y de generar alertas.</p>
        {recovering?<RecoveryQuestion busy={busy} onConfirm={reason=>void save("RESOLVED",true,reason)} onCancel={()=>setRecovering(false)}/>:<button type="button" className="button button-primary" disabled={busy} onClick={() => setRecovering(true)}>Ya la recuperé</button>}
      </div>
    </>}
    {message && <p role="status" className="field-help">{message}</p>}
    {error && <p role="alert" className="notice notice-warning">{error}</p>}
  </section>;
}
