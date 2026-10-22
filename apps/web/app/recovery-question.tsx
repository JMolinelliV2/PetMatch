"use client";
import {useId,useState} from "react";

export const recoveryReasons=[
  ["MASCOMATCH_MATCH","Encontré la pista a través de una coincidencia de MascoMatch"],
  ["MASCOMATCH_SIGHTING","Me ayudó un avistamiento recibido por MascoMatch"],
  ["SOCIAL_MEDIA","Redes sociales"],["WHATSAPP","Grupo o contacto de WhatsApp"],
  ["VET_OR_SHELTER","Veterinaria, refugio o institución"],["STREET_OR_POSTERS","Carteles o búsqueda en la zona"],
  ["RETURNED_ALONE","Volvió por su cuenta"],["OTHER","Otra forma"],["PREFER_NOT_TO_SAY","Prefiero no responder"],
] as const;
export type RecoveryReason=typeof recoveryReasons[number][0];
export function RecoveryQuestion({busy,onConfirm,onCancel}:{busy:boolean;onConfirm:(reason:RecoveryReason)=>void;onCancel:()=>void}){
  const id=useId();const [reason,setReason]=useState<RecoveryReason>("PREFER_NOT_TO_SAY");
  return <div className="recovery-question" role="group" aria-labelledby={`${id}-title`}>
    <h3 id={`${id}-title`}>¿Cómo lograste encontrarla?</h3>
    <p className="field-help">Tu respuesta nos ayuda a entender qué pistas sirven. También podés elegir no responder.</p>
    <label className="sr-only" htmlFor={id}>Cómo volvió tu mascota</label>
    <select id={id} className="form-input" value={reason} onChange={e=>setReason(e.target.value as RecoveryReason)} disabled={busy}>
      {recoveryReasons.map(([value,label])=><option key={value} value={value}>{label}</option>)}
    </select><div className="location-actions"><button type="button" className="button button-primary" disabled={busy} onClick={()=>onConfirm(reason)}>{busy?"Guardando…":"Confirmar que está encontrada"}</button><button type="button" className="text-button" disabled={busy} onClick={onCancel}>Cancelar</button></div>
  </div>;
}
