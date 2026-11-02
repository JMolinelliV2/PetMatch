"use client";
import Link from "next/link";
import {useEffect,useRef,useState} from "react";
import {AccountSession} from "../account-session";
import type {FeedbackSaved} from "../match-feedback";
import {ReportMatches} from "../report-matches";
import {EditCase} from "./edit-case";
import {CaseAvatar} from "./case-avatar";
import {Icon} from "../ui/pictogram";
import {PhotoManager} from "../ui/photo-manager";
import {CandidateReport} from "./candidate-report";
import type {Candidate} from "./candidate-report";
import {LocationMap} from "../location-map";
import {ReviewRequest} from "../review-request";
import {AccountLoading} from "../ui/account-loading";
import {ReportId} from "../ui/report-id";
import {RecoveryQuestion} from "../recovery-question";
import type {RecoveryReason} from "../recovery-question";
import {lostDate,sexLabel,speciesLabel} from "@/lib/lost-dogs";
import {isSupportedSpecies} from "@/lib/species";
import {observationEditHref} from "@/lib/owned-observations";
type Pet={id:string;name:string;species:string;sex:string;primary_color:string;size:string};
type Case={id:string;public_id?:string;pet_id:string;status:string;description:string;description_format?:string;public_location:string|null;lost_at:string;latitude:number|null;longitude:number|null};
type Observation={in_scope?:boolean;species:string;id:string;public_id?:string;description:string;source_type:string;observed_at:string};
type Dashboard={pets:Pet[];cases:Case[];observations:Observation[]};
const states:Record<string,string>={ACTIVE:"Sigue perdido",FOUND:"Encontrado",CLOSED:"Cerrado",CANCELLED:"Cancelado"};
const statusClasses:Record<string,string>={ACTIVE:"status-active",FOUND:"status-found",CLOSED:"status-closed",CANCELLED:"status-cancelled"};

function Reports({userId}:{userId:string}) {
  const pendingPhotoLink=useRef<string|null>(null);
  const pendingEditLink=useRef<string|null>(null);
  const pendingEditFocus=useRef<string|null>(null);
  const [recoveryCase,setRecoveryCase]=useState<string|null>(null);
  const [photoCase,setPhotoCase]=useState<string|null>(null);
  const [mapCase,setMapCase]=useState<string|null>(null);
  const [data,setData]=useState<Dashboard|null>(null);const [error,setError]=useState("");const [message,setMessage]=useState("");const [refresh,setRefresh]=useState(0);const [busy,setBusy]=useState(false);const [editing,setEditing]=useState<Case|null>(null);const [selected,setSelected]=useState<string|null>(null);const [candidates,setCandidates]=useState<Candidate[]>([]);const [candidatesBusy,setCandidatesBusy]=useState(false);const [report,setReport]=useState<string|null>(null);
  useEffect(()=>{const reload=()=>setRefresh(value=>value+1);window.addEventListener("mascomatch:cases",reload);window.addEventListener("focus",reload);return()=>{window.removeEventListener("mascomatch:cases",reload);window.removeEventListener("focus",reload);};},[]);
  useEffect(()=>{const params=new URLSearchParams(window.location.search);const valid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;const target=params.get("foto");if(target&&valid.test(target)){const identity=target.toLowerCase();pendingPhotoLink.current=identity;setPhotoCase(identity);}const edit=params.get("editar");if(edit&&valid.test(edit))pendingEditLink.current=edit.toLowerCase();},[]);
  useEffect(()=>{const target=pendingPhotoLink.current;if(!target||!data)return;pendingPhotoLink.current=null;if(data.cases.some(item=>item.id===target)){document.getElementById(`fotos-${target}`)?.scrollIntoView({block:"start"});}else setError("No encontramos ese aviso en esta cuenta. Revisá que hayas ingresado con la cuenta que lo publicó.");},[data]);
  useEffect(()=>{const target=pendingEditLink.current;if(!target||!data)return;pendingEditLink.current=null;const item=data.cases.find(candidate=>candidate.id===target);const pet=item?data.pets.find(candidate=>candidate.id===item.pet_id):null;if(item&&isSupportedSpecies(pet?.species)){pendingEditFocus.current=item.id;setEditing(item);}else setError("No encontramos un aviso editable con ese ID en tu cuenta.");},[data]);
  useEffect(()=>{if(!editing||pendingEditFocus.current!==editing.id)return;pendingEditFocus.current=null;document.getElementById(`editar-${editing.id}`)?.scrollIntoView({block:"start"});document.getElementById(`editar-titulo-${editing.id}`)?.focus({preventScroll:true});},[editing]);
  function feedbackSaved(matchId:string,result:FeedbackSaved){
    setCandidates(current=>current.map(candidate=>candidate.match.id===matchId?{...candidate,match:{...candidate.match,status:result.status}}:candidate));
    if(result.recovered){setData(current=>current?{...current,cases:current.cases.map(item=>item.id===result.caseId?{...item,status:"FOUND"}:item)}:current);setSelected(null);setMessage("Tu mascota quedó marcada como encontrada. La búsqueda está cerrada y el aviso ya no aparece en el listado público.");}
  }
  useEffect(()=>{const controller=new AbortController();void fetch("/api/account/dashboard",{cache:"no-store",signal:controller.signal}).then(async response=>{if(!response.ok)throw new Error(response.status===401?"Tu sesión venció. Volvé a ingresar.":"No pudimos consultar tus avisos.");const result=await response.json();if(!controller.signal.aborted){setData(result);setError("");}}).catch(cause=>{if(!controller.signal.aborted)setError(cause.message);});return()=>controller.abort();},[userId,refresh]);
  useEffect(()=>{if(!selected)return;const controller=new AbortController();setCandidates([]);setCandidatesBusy(true);void fetch(`/api/matches/lost-cases/${selected}`,{cache:"no-store",signal:controller.signal}).then(async response=>{if(!response.ok)throw new Error("No pudimos consultar las coincidencias.");const result=await response.json();if(!controller.signal.aborted)setCandidates(result.items);}).catch(cause=>{if(!controller.signal.aborted)setError(cause.message);}).finally(()=>{if(!controller.signal.aborted)setCandidatesBusy(false);});return()=>controller.abort();},[selected,refresh]);
  async function change(id:string,values:{status:string;recovery_reason?:RecoveryReason}){setBusy(true);setError("");setMessage("");try{const response=await fetch(`/api/account/lost-cases/${id}`,{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify(values)});if(!response.ok)throw new Error("No pudimos actualizar tu aviso.");const updated:Case=await response.json();setData(current=>current?{...current,cases:current.cases.map(item=>item.id===id?updated:item)}:current);setEditing(null);setRecoveryCase(null);setMessage(updated.status==="FOUND"?"Tu mascota quedó marcada como encontrada. Si querés, podés compartir tu experiencia.":updated.status==="CLOSED"?"El aviso quedó cerrado. Si querés, podés compartir tu experiencia.":"Tu aviso quedó actualizado.");setRefresh(value=>value+1);}catch(cause){setError(cause instanceof Error?cause.message:"No pudimos actualizar tu aviso.");}finally{setBusy(false);}}
  return <>{error&&<p role="alert" className="notice notice-warning">{error}</p>}{message&&<p role="status" className="notice">{message}</p>}{!data&&!error&&<AccountLoading title="Cargando tus avisos" description="Estamos preparando tus publicaciones y posibles coincidencias." reports/>}
    {data&&<div className="dashboard-summary"><div className="summary-card summary-card-coral"><Icon name="paw"/><strong>{data.cases.filter(item=>item.status==="ACTIVE"&&isSupportedSpecies(data.pets.find(pet=>pet.id===item.pet_id)?.species)).length}</strong><span>Búsquedas activas</span></div><div className="summary-card"><Icon name="eye"/><strong>{data.observations.length}</strong><span>Reportes que compartiste</span></div></div>}
    {data?.cases.length===0&&<div className="lost-dogs-empty"><h2>Todavía no publicaste un aviso de pérdida</h2><p>Podés registrar una mascota perdida o consultar los reportes que compartiste.</p><Link className="button button-primary" href="/perdi">Publicar un aviso</Link></div>}
    <div className="case-list">{data?.cases.map(item=>{const pet=data.pets.find(pet=>pet.id===item.pet_id);const supported=isSupportedSpecies(pet?.species);return <article id={`aviso-${item.id}`} className="notification-card" key={item.id}>
      <div className="case-summary"><CaseAvatar id={item.id} active={supported&&item.status==="ACTIVE"} refresh={refresh}/><div><span className={`lost-status ${supported?(statusClasses[item.status]||""):"status-closed"}`}>{supported?(states[item.status]||item.status):"Fuera del alcance actual"}</span><h2>{pet?.name||"Mi mascota"}</h2>
      <ReportId id={item.id} publicId={item.public_id} copyable />
      {pet&&<p className="dog-traits">{speciesLabel(pet.species)}{pet.sex!=="unknown"?` · ${sexLabel(pet.sex)}`:""}</p>}
      <div className="case-traits"><span><Icon name="pin"/>{item.public_location||"Zona no indicada"}</span><span><Icon name="calendar"/>Perdido desde el {lostDate(item.lost_at)}</span></div></div></div>
      <p className="case-description">{item.description||"Sin descripción adicional"}</p>
      {!supported&&<p className="notice">Este aviso se conserva como historial. MascoMatch ahora admite solo perros y gatos, por lo que no se publica ni genera nuevas coincidencias o alertas.</p>}
      <div className="location-actions case-actions">{supported&&item.status==="ACTIVE"&&<Link className="button button-primary" href={`/perdidos/${item.id}`}>Ver publicación <Icon name="arrow"/></Link>}{supported&&<><button className="text-button" type="button" onClick={()=>setEditing(item)}><Icon name="edit"/>Editar aviso</button><button className="text-button" type="button" aria-expanded={selected===item.id} onClick={()=>setSelected(selected===item.id?null:item.id)}><Icon name="search"/>{selected===item.id?"Ocultar avistamientos y coincidencias":"Ver avistamientos y coincidencias"}</button></>}
      {item.latitude!==null&&item.longitude!==null&&<button className="text-button" type="button" aria-expanded={mapCase===item.id} onClick={()=>setMapCase(mapCase===item.id?null:item.id)}><Icon name="pin"/>{mapCase===item.id?"Ocultar ubicación":"Ver última ubicación"}</button>}
      {item.status==="ACTIVE"?<><button className="text-button" type="button" disabled={busy} onClick={()=>setRecoveryCase(item.id)}>Marcar como encontrado</button><button className="text-button" type="button" disabled={busy} onClick={()=>void change(item.id,{status:"CLOSED"})}>Cerrar aviso</button></>:supported?<button className="text-button" type="button" disabled={busy} onClick={()=>void change(item.id,{status:"ACTIVE"})}>Reabrir búsqueda</button>:null}</div>
      {recoveryCase===item.id&&item.status==="ACTIVE"&&<RecoveryQuestion busy={busy} onCancel={()=>setRecoveryCase(null)} onConfirm={reason=>void change(item.id,{status:"FOUND",recovery_reason:reason})}/>}
      {supported&&["FOUND","CLOSED","CANCELLED"].includes(item.status)&&<ReviewRequest caseId={item.id} recovered={item.status==="FOUND"}/>}
      {mapCase===item.id&&item.latitude!==null&&item.longitude!==null&&<div className="case-section"><LocationMap latitude={item.latitude} longitude={item.longitude} editable={false} label="Última ubicación guardada en tu aviso"/></div>}
      {editing?.id===item.id&&pet&&<div id={`editar-${item.id}`} className="case-section case-edit-section"><h3 id={`editar-titulo-${item.id}`} tabIndex={-1}>Editar aviso de {pet.name}</h3><EditCase caseId={item.id} description={item.description} descriptionFormat={item.description_format} lostAt={item.lost_at} pet={pet} onSaved={()=>{setEditing(null);setMessage("Tu aviso quedó actualizado.");setRefresh(value=>value+1);}} onCancel={()=>setEditing(null)}/></div>}
      {supported&&<details id={`fotos-${item.id}`} className="case-section" open={photoCase===item.id} onToggle={event=>{if(event.currentTarget.open)setPhotoCase(item.id);else setPhotoCase(current=>current===item.id?null:current);}}><summary className="text-button"><Icon name="camera"/>Fotos y miniatura</summary><PhotoManager ownerType="lost_case" active={photoCase===item.id} ownerId={item.id} onChanged={()=>setRefresh(value=>value+1)}/></details>}
      {supported&&selected===item.id&&<section className="case-section"><h3>Avistamientos y coincidencias</h3><p className="field-help">Los avistamientos enviados desde este aviso llegan para que los revises, aunque la comparación automática no los considere compatibles. Confirmá si reconocés a tu mascota o si ya la recuperaste.</p>{candidatesBusy?<p role="status">Consultando avistamientos y coincidencias…</p>:!candidates.length&&<p>No hay avistamientos ni coincidencias por ahora.</p>}
        {!!candidates.filter(candidate=>candidate.observation.linked_to_notice).length&&<div className="case-candidates-group"><h4>Enviados desde este aviso</h4>{candidates.filter(candidate=>candidate.observation.linked_to_notice).map(candidate=><CandidateReport key={candidate.match.id} candidate={candidate} caseId={item.id} caseActive={item.status==="ACTIVE"} onSaved={result=>feedbackSaved(candidate.match.id,result)}/>)}</div>}
        {!!candidates.filter(candidate=>!candidate.observation.linked_to_notice).length&&<div className="case-candidates-group"><h4>Posibles coincidencias de otros reportes</h4>{candidates.filter(candidate=>!candidate.observation.linked_to_notice).map(candidate=><CandidateReport key={candidate.match.id} candidate={candidate} caseId={item.id} caseActive={item.status==="ACTIVE"} onSaved={result=>feedbackSaved(candidate.match.id,result)}/>)}</div>}
      </section>}
    </article>;})}</div>
    {!!data?.observations.length&&<section className="analysis-section"><h2>Reportes que compartiste</h2>{data.observations.map(item=><article className="analysis-result" key={item.id}>
      <h3>{item.source_type==="FOUND_ANIMAL"?"Mascota encontrada":"Avistamiento"}</h3><ReportId id={item.id} publicId={item.public_id} label="ID del reporte" copyable/><p>{item.description}</p>
      {item.in_scope!==false&&isSupportedSpecies(item.species)?<>
        <Link href={observationEditHref(item.id)} className="text-button observation-edit-link"><Icon name="edit"/>{item.source_type==="FOUND_ANIMAL"?"Editar mi reporte":"Editar mi avistamiento"}</Link>
        <button type="button" className="text-button" onClick={()=>setReport(report===item.id?null:item.id)}>Ver posibles coincidencias</button>
        {report===item.id&&<ReportMatches observationId={item.id}/>}
        <details className="case-section" open={photoCase===item.id} onToggle={event=>{if(event.currentTarget.open)setPhotoCase(item.id);else setPhotoCase(current=>current===item.id?null:current);}}><summary className="text-button"><Icon name="camera"/>Fotos y miniatura</summary><PhotoManager ownerType="observation" active={photoCase===item.id} ownerId={item.id} onChanged={()=>setRefresh(value=>value+1)}/></details>
      </>:<p className="field-help">Reporte histórico fuera del alcance actual: solo se admiten perros y gatos.</p>}
    </article>)}</section>}
    <p><Link href="/notificaciones" className="text-button">Ver mis notificaciones</Link></p>
  </>;
}
export function MyReports(){return <AccountSession>{user=><><Link href="/mi-cuenta" className="text-button">Editar mi contacto o gestionar mi cuenta</Link><Reports key={user.id} userId={user.id}/></>}</AccountSession>;}
