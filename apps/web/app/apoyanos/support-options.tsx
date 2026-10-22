"use client";
import { useId, useState } from "react";
import { Icon } from "../ui/pictogram";
import { formatSupportAmount, supportLevels } from "./support-levels";

export function SupportOptions() {
  const groupId = useId();
  const [selected, setSelected] = useState<string>(supportLevels[0].id);
  const [frequency, setFrequency] = useState<"once" | "monthly">("once");
  const [customAmount, setCustomAmount] = useState("");
  const [customTouched, setCustomTouched] = useState(false);
  const level = supportLevels.find(item => item.id === selected);
  const custom = selected === "custom";
  const parsed = Number(customAmount);
  const customValid = customAmount.trim() !== "" && Number.isSafeInteger(parsed) && parsed >= 1;
  const amount = custom ? customValid ? parsed : null : level?.amount ?? null;
  const name = custom ? "Aporte personalizado" : level?.name;
  const amountError = custom && customTouched && !customValid;
  const cadence = frequency === "monthly" ? "por mes" : "por única vez";

  return <section className="support-options" aria-labelledby="support-options-title">
    <div className="support-options-heading"><h2 id="support-options-title">Elegí cómo querés apoyar</h2><p>Todos los montos están expresados en pesos uruguayos (UYU).</p></div>
    <fieldset className="support-frequency">
      <legend>Frecuencia del aporte</legend>
      <div className="support-frequency-options">
        <label className={frequency === "once" ? "is-selected" : ""}><input type="radio" name={`${groupId}-frequency`} value="once" checked={frequency === "once"} onChange={() => setFrequency("once")} />Aporte puntual</label>
        <label className={frequency === "monthly" ? "is-selected" : ""}><input type="radio" name={`${groupId}-frequency`} value="monthly" checked={frequency === "monthly"} onChange={() => setFrequency("monthly")} />Aporte mensual</label>
      </div>
    </fieldset>
    <fieldset className="support-levels">
      <legend className="sr-only">Aporte voluntario</legend>
      <div className="support-level-grid">
        {supportLevels.map((item, index) => <label key={item.id} className={`support-level ${selected === item.id ? "is-selected" : ""}`}>
          <input type="radio" name={`${groupId}-level`} value={item.id} checked={selected === item.id} onChange={() => { setSelected(item.id); setCustomTouched(false); }} />
          <span className="support-level-top"><span className={`feature-icon ${index > 1 ? "feature-icon-2" : index === 1 ? "feature-icon-1" : ""}`}><Icon name={item.icon} /></span><span className="support-level-state">{selected === item.id ? <><Icon name="check" />Elegido</> : "Elegir aporte"}</span></span>
          <span className="support-level-name">{item.name}</span>
          <span className="support-level-price">{formatSupportAmount(item.amount)}<span>{cadence}</span></span>
          <span className="support-level-description">{item.description}</span>
          <span className="support-level-focus">{item.focus}</span>
        </label>)}
      </div>
      <div className={`support-custom ${custom ? "is-selected" : ""}`}>
        <label className="support-custom-choice"><input type="radio" name={`${groupId}-level`} value="custom" checked={custom} onChange={() => setSelected("custom")} /><span><strong>Otro monto</strong><span>Elegí un aporte que se ajuste a vos.</span></span></label>
        <label className="field-label" htmlFor={`${groupId}-amount`}>Importe en pesos uruguayos<input id={`${groupId}-amount`} className="form-input" type="number" min={1} step={1} inputMode="numeric" placeholder="Por ejemplo, 500" value={customAmount} disabled={!custom} aria-invalid={amountError || undefined} aria-describedby={`${groupId}-amount-help`} onChange={event => setCustomAmount(event.target.value)} onBlur={() => setCustomTouched(true)} /><span className="field-help" id={`${groupId}-amount-help`}>{amountError ? "Ingresá un monto entero de al menos $U 1, sin centésimos." : "Monto sugerido en pesos, sin centésimos."}</span></label>
      </div>
    </fieldset>
    <div className="support-selection">
      <div><p className="eyebrow">Tu aporte elegido</p><p className="support-selection-amount" role="status">{amount !== null ? <>{formatSupportAmount(amount)} <span>{cadence}</span></> : "Ingresá el monto que querés aportar"}</p><p className="field-help">{name}{frequency === "monthly" ? " · Frecuencia mensual" : " · Aporte puntual"}</p></div>
      <div className="support-payment"><button type="button" className="button button-primary" disabled>Donaciones próximamente</button><p>Las opciones de pago estarán disponibles cuando habilitemos los aportes.</p></div>
    </div>
  </section>;
}
