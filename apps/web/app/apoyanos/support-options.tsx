"use client";
import { useEffect, useId, useRef, useState } from "react";
import { Icon } from "../ui/pictogram";
import { formatSupportAmount, supportLevels } from "./support-levels";

export function SupportOptions() {
  const groupId = useId();
  const [selected, setSelected] = useState<string>(supportLevels[0].id);
  const frequency = "once";
  const [configuration, setConfiguration] = useState<{ enabled: boolean; environment: "test" | "production" } | null>(null);
  const [availabilityVersion, setAvailabilityVersion] = useState(0);
  const [paymentError, setPaymentError] = useState("");
  const [busy, setBusy] = useState(false);
  const attempt = useRef<{ amount: number; requestId: string } | null>(null);
  const [customAmount, setCustomAmount] = useState("");
  const [customTouched, setCustomTouched] = useState(false);
  const level = supportLevels.find(item => item.id === selected);
  const custom = selected === "custom";
  const parsed = Number(customAmount);
  const customValid = customAmount.trim() !== "" && Number.isSafeInteger(parsed) && parsed >= 1;
  const amount = custom ? customValid ? parsed : null : level?.amount ?? null;
  const name = custom ? "Aporte personalizado" : level?.name;
  const amountError = custom && customTouched && !customValid;
  const cadence = "por única vez";

  useEffect(() => {
    const controller = new AbortController();
    void fetch("/api/payments/config", { cache: "no-store", signal: controller.signal }).then(async response => {
      if (!response.ok) throw new Error("No pudimos consultar la disponibilidad de los aportes.");
      const data = await response.json();
      if (!controller.signal.aborted) { setConfiguration(data); setPaymentError(""); }
    }).catch(cause => { if (!controller.signal.aborted) { setConfiguration(null); setPaymentError(cause.message); } });
    return () => controller.abort();
  }, [availabilityVersion]);

  async function pay() {
    if (busy || !configuration?.enabled || amount === null) return;
    setBusy(true); setPaymentError("");
    try {
      if (!attempt.current || attempt.current.amount !== amount) {
        let stored: { amount?: unknown; requestId?: unknown } | null = null;
        try { stored = JSON.parse(sessionStorage.getItem("mascomatch:donation-attempt") || "null"); } catch {}
        attempt.current = stored?.amount === amount && typeof stored.requestId === "string" && /^[0-9a-f-]{36}$/i.test(stored.requestId)
          ? { amount, requestId: stored.requestId } : { amount, requestId: crypto.randomUUID() };
        try { sessionStorage.setItem("mascomatch:donation-attempt", JSON.stringify(attempt.current)); } catch {}
      }
      const response = await fetch("/api/payments/checkout", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ request_id: attempt.current.requestId, amount_uyu: amount, frequency }) });
      const data = await response.json();
      if (!response.ok) {
        if (response.status === 409) { attempt.current = null; try { sessionStorage.removeItem("mascomatch:donation-attempt"); } catch {} }
        throw new Error(typeof data.detail === "string" ? data.detail : "No pudimos preparar el aporte. Intentá de nuevo.");
      }
      if (typeof data.donation_id !== "string" || !/^[0-9a-f-]{36}$/i.test(data.donation_id)) throw new Error("No pudimos abrir el aporte de forma segura.");
      let target = `/apoyanos/resultado?aporte=${encodeURIComponent(data.donation_id)}`;
      if (data.checkout_url) {
        const url = new URL(data.checkout_url);
        if (url.protocol !== "https:" || !["www.mercadopago.com.uy", "mercadopago.com.uy"].includes(url.hostname) || url.username || url.password || (url.port && url.port !== "443") || !url.pathname.startsWith("/checkout/")) throw new Error("No pudimos abrir Mercado Pago de forma segura.");
        target = url.toString();
      }
      try { sessionStorage.removeItem("mascomatch:donation-attempt"); } catch {}
      window.location.assign(target);
    } catch (cause) { setPaymentError(cause instanceof Error ? cause.message : "No pudimos abrir Mercado Pago."); setBusy(false); }
  }

  return <section className="support-options" aria-labelledby="support-options-title">
    <div className="support-options-heading"><h2 id="support-options-title">Elegí cómo querés apoyar</h2><p>Todos los montos están expresados en pesos uruguayos (UYU).</p></div>
    <p className={`support-availability${configuration?.enabled && configuration.environment === "test" ? " support-test-mode" : ""}`} role="status"><Icon name={configuration?.enabled ? "shield" : "clock"} />{!configuration ? paymentError ? "No pudimos consultar la disponibilidad de los aportes." : "Consultando la disponibilidad de los aportes…" : configuration.enabled ? configuration.environment === "test" ? "Modo de prueba: no se realizan aportes con dinero real." : "Los aportes puntuales se completan en Mercado Pago." : "Los aportes estarán disponibles próximamente."}</p>
    <fieldset className="support-frequency" disabled={busy}>
      <legend>Frecuencia del aporte</legend>
      <div className="support-frequency-options">
        <label className="is-selected"><input type="radio" name={`${groupId}-frequency`} value="once" checked readOnly />Aporte puntual</label>
        <label className="is-unavailable"><input type="radio" name={`${groupId}-frequency`} value="monthly" disabled />Aporte mensual <small>Próximamente</small></label>
      </div>
    </fieldset>
    <fieldset className="support-levels" disabled={busy}>
      <legend className="sr-only">Aporte voluntario</legend>
      <div className="support-level-grid">
        {supportLevels.map((item, index) => <label key={item.id} className={`support-level ${selected === item.id ? "is-selected" : ""}`}>
          <input type="radio" name={`${groupId}-level`} value={item.id} checked={selected === item.id} onChange={() => { setSelected(item.id); setCustomTouched(false); }} />
          <span className="support-level-top"><span className={`feature-icon ${index > 1 ? "feature-icon-2" : index === 1 ? "feature-icon-1" : ""}`}><Icon name={item.icon} /></span><span className="support-level-state">{selected === item.id && <Icon name="check" />}<span>{selected === item.id ? "Elegido" : "Elegir aporte"}</span></span></span>
          <span className="support-level-name">{item.name}</span>
          <span className="support-level-price">{formatSupportAmount(item.amount)}<span>{cadence}</span></span>
          <span className="support-level-description">{item.description}</span>
          <span className="support-level-focus">{item.focus}</span>
        </label>)}
      </div>
      {level && <p className="support-level-detail"><strong>{level.name}:</strong> {level.focus}</p>}
      <div className={`support-custom ${custom ? "is-selected" : ""}`}>
        <label className="support-custom-choice"><input type="radio" name={`${groupId}-level`} value="custom" checked={custom} onChange={() => setSelected("custom")} /><span><strong>Otro monto</strong><span>Elegí un aporte que se ajuste a vos.</span></span></label>
        <label className="field-label support-custom-amount" htmlFor={`${groupId}-amount`}>Importe en pesos uruguayos<input id={`${groupId}-amount`} className="form-input" type="number" min={1} step={1} inputMode="numeric" placeholder="Por ejemplo, 500" value={customAmount} disabled={!custom} aria-invalid={amountError || undefined} aria-describedby={`${groupId}-amount-help`} onChange={event => setCustomAmount(event.target.value)} onBlur={() => setCustomTouched(true)} /><span className="field-help" id={`${groupId}-amount-help`}>{amountError ? "Ingresá un monto entero de al menos $U 1, sin centésimos." : "Monto sugerido en pesos, sin centésimos."}</span></label>
      </div>
    </fieldset>
    <div className="support-selection">
      <div><p className="eyebrow">Tu aporte elegido</p><p className="support-selection-amount" role="status">{amount !== null ? <>{formatSupportAmount(amount)} <span>{cadence}</span></> : "Ingresá el monto que querés aportar"}</p><p className="field-help">{name} · Aporte puntual</p></div>
      <div className="support-payment"><button type="button" className="button button-primary" disabled={busy || !configuration?.enabled || amount === null} onClick={() => void pay()}>{busy ? "Preparando tu aporte…" : configuration?.enabled ? "Continuar con Mercado Pago" : "Aportes próximamente"}</button><p>Un único aporte, sin renovación automática. Confirmás el monto y el medio de pago en Mercado Pago.</p></div>
    </div>
    {paymentError && <div className="notice notice-warning" role="alert">{paymentError}{!configuration && <button type="button" className="text-button" onClick={() => setAvailabilityVersion(value => value + 1)}>Reintentar consulta</button>}</div>}
  </section>;
}
