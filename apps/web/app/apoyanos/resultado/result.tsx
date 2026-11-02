"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Icon } from "../../ui/pictogram";
import { formatSupportAmount } from "../support-levels";

type Receipt = { id: string; amount_uyu: number; status: string; environment: "test" | "production"; confirmed_at: string | null };
const messages: Record<string, { title: string; description: string }> = {
  CREATING: { title: "Estamos preparando tu aporte", description: "Todavía no tenemos una confirmación de Mercado Pago." },
  PENDING: { title: "Tu aporte está pendiente de confirmación", description: "Mercado Pago todavía no confirmó el resultado. Si ya completaste el pago, esperá la actualización antes de iniciar otro aporte." },
  APPROVED: { title: "Gracias por apoyar a MascoMatch", description: "Mercado Pago confirmó tu aporte. Tu ayuda acompaña las búsquedas y las mejoras de la plataforma." },
  REJECTED: { title: "El pago no fue aprobado", description: "Mercado Pago no aprobó esta operación. Podés revisar el motivo allí o elegir otro medio de pago en un nuevo aporte." },
  CANCELLED: { title: "Este aporte fue cancelado", description: "La operación se canceló o venció sin completarse." },
  REFUNDED: { title: "El aporte fue reembolsado", description: "Mercado Pago informa la devolución del importe. Los plazos de acreditación dependen del medio de pago." },
  PARTIALLY_REFUNDED: { title: "El aporte tiene un reembolso parcial", description: "Mercado Pago informa una devolución parcial. Podés consultar los detalles en tu comprobante de Mercado Pago." },
  CHARGEBACK: { title: "Mercado Pago informó un contracargo", description: "La operación tiene un contracargo. Consultá sus detalles en Mercado Pago." },
};

export function DonationResult({ identity }: { identity: string | null }) {
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [refresh, setRefresh] = useState(0);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [waiting, setWaiting] = useState(false);
  useEffect(() => {
    if (!identity) { setError("No encontramos la referencia de este aporte. El estado del pago se puede consultar en Mercado Pago."); setLoading(false); return; }
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    const deadline = Date.now() + 90_000;
    setError(""); setLoading(true); setWaiting(false);
    async function load() {
      try {
        const response = await fetch(`/api/payments/donations/${identity}`, { cache: "no-store", signal: AbortSignal.any([controller.signal, AbortSignal.timeout(15000)]) });
        const data = await response.json();
        if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "No pudimos consultar el resultado. No significa que el pago haya fallado.");
        if (controller.signal.aborted) return;
        setReceipt(data);
        if (["CREATING", "PENDING"].includes(data.status)) {
          if (Date.now() < deadline) timer = setTimeout(load, 5000);
          else setWaiting(true);
        }
      } catch (cause) { if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "No pudimos consultar el resultado del aporte."); }
      finally { if (!controller.signal.aborted) setLoading(false); }
    }
    void load();
    return () => { controller.abort(); if (timer) clearTimeout(timer); };
  }, [identity, refresh]);

  async function update() {
    if (!identity || refreshing) return;
    setRefreshing(true); setError("");
    try {
      const response = await fetch(`/api/payments/donations/${identity}/refresh`, { method: "POST" });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "No pudimos actualizar el estado.");
      setRefresh(value => value + 1);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "No pudimos actualizar el estado."); }
    finally { setRefreshing(false); }
  }

  const confirmed = receipt?.status === "APPROVED";
  const message = receipt ? messages[receipt.status] || messages.PENDING : null;
  return <section className="notification-login account-form donation-result-card" aria-live="polite" aria-busy={loading || refreshing}>
    <span className={`donation-result-icon${confirmed ? " is-confirmed" : ""}`}><Icon name={confirmed ? "heart" : receipt?.status === "REJECTED" ? "close" : "clock"} /></span>
    {receipt?.environment === "test" && <p className="donation-test-label">Operación de prueba · Sin dinero real</p>}
    <h1>{loading && !receipt ? "Consultando tu aporte…" : confirmed && receipt?.environment === "test" ? "Prueba de aporte confirmada" : message?.title || "No pudimos consultar tu aporte"}</h1>
    {receipt && <p className="donation-result-amount">{formatSupportAmount(receipt.amount_uyu)}<span>Aporte puntual · UYU</span></p>}
    {message && <p>{confirmed && receipt?.environment === "test" ? "La prueba fue confirmada por Mercado Pago. No se movió dinero real." : message.description}</p>}
    {receipt && <p className="field-help">Referencia: {receipt.id}</p>}
    {waiting && <p className="notice">La confirmación puede demorar. Podés actualizar el estado o consultar tu comprobante en Mercado Pago.</p>}
    {error && <p className="notice notice-warning" role="alert">{error}</p>}
    <div className="donation-result-actions">
      {identity && !confirmed && <button className="button button-secondary" type="button" disabled={loading || refreshing} onClick={() => void update()}><Icon name="refresh" />{refreshing ? "Actualizando…" : "Actualizar estado"}</button>}
      {receipt && !["CREATING", "PENDING"].includes(receipt.status) && <Link href="/apoyanos" className="button button-primary">Hacer otro aporte</Link>}
      <Link href="/perdidos" className="text-button">Ver mascotas reportadas</Link>
    </div>
  </section>;
}
