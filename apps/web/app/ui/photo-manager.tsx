"use client";

import {useEffect, useState} from "react";
import type {FormEvent} from "react";
import {MAX_REPORT_PHOTOS,photoSelectionError,uploadReportPhotos} from "@/lib/report-photos";
import type {PhotoAlbum,PhotoOwnerType} from "@/lib/report-photos";
import {usePhotoSelection} from "../use-photo-selection";
import {Icon} from "./pictogram";
import {PhotoUploader} from "./photo-uploader";
import {PhotoViewer} from "./photo-viewer";

export function PhotoManager({ownerType,ownerId,onChanged,active=true}:{ownerType:PhotoOwnerType;ownerId:string;onChanged?:()=>void;active?:boolean}) {
  const [album,setAlbum]=useState<PhotoAlbum|null>(null);
  const [loading,setLoading]=useState(true);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [message,setMessage]=useState("");
  const [revision,setRevision]=useState(0);
  const [viewer,setViewer]=useState<number|null>(null);
  const {photos,primaryIndex,changePhotos,setPrimaryIndex}=usePhotoSelection(false);
  const endpoint=`/api/account/photos/album?${new URLSearchParams({owner_type:ownerType,owner_id:ownerId})}`;
  const remaining=Math.max(0,MAX_REPORT_PHOTOS-(album?.items.length??0));

  useEffect(()=>{
    if(!active)return;
    const controller=new AbortController(); setLoading(true);
    void fetch(endpoint,{cache:"no-store",signal:controller.signal}).then(async response=>{
      if(!response.ok)throw new Error("No pudimos consultar las fotos.");
      const data:PhotoAlbum=await response.json();if(!controller.signal.aborted)setAlbum(data);
    }).catch(cause=>{if(!controller.signal.aborted)setError(cause instanceof Error?cause.message:"No pudimos consultar las fotos.");})
      .finally(()=>{if(!controller.signal.aborted)setLoading(false);});
    return()=>controller.abort();
  },[active,endpoint,revision]);

  async function cover(id:string) {
    setBusy(true);setError("");setMessage("");
    try {
      const response=await fetch("/api/account/photos/cover",{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({owner_type:ownerType,owner_id:ownerId,photo_id:id})});
      const data=await response.json();if(!response.ok)throw new Error(typeof data.detail==="string"?data.detail:"No pudimos cambiar la miniatura.");
      setAlbum(data);setMessage("La miniatura quedó actualizada.");onChanged?.();
    } catch(cause){setError(cause instanceof Error?cause.message:"No pudimos cambiar la miniatura.");}
    finally{setBusy(false);}
  }

  async function remove(id:string) {
    if(!window.confirm("¿Querés quitar esta foto del reporte? Esta acción no se puede deshacer."))return;
    setBusy(true);setError("");setMessage("");
    try {
      const response=await fetch(`/api/account/photos/${id}`,{method:"DELETE"});
      if(!response.ok)throw new Error("No pudimos quitar la foto.");
      setRevision(value=>value+1);setMessage("La foto quedó eliminada.");onChanged?.();
    } catch(cause){setError(cause instanceof Error?cause.message:"No pudimos quitar la foto.");}
    finally{setBusy(false);}
  }

  async function upload(event:FormEvent<HTMLFormElement>) {
    event.preventDefault();const form=event.currentTarget;
    const invalid=photoSelectionError(photos,remaining);if(invalid){setError(invalid);return;}
    setBusy(true);setError("");setMessage("");
    try {
      const data=await uploadReportPhotos(photos,ownerType,ownerId,primaryIndex);
      setAlbum(data);changePhotos([]);form.reset();setMessage("Las fotos quedaron guardadas. Podés cambiar la miniatura cuando quieras.");onChanged?.();
    } catch(cause){setError(cause instanceof Error?cause.message:"No pudimos guardar las fotos.");setRevision(value=>value+1);}
    finally{setBusy(false);}
  }

  return <div className="photo-manager" aria-busy={busy||loading}>
    {loading&&<p role="status" className="field-help">Consultando fotos…</p>}
    {error&&<p role="alert" className="notice notice-warning">{error}</p>}
    {message&&<p role="status" className="notice">{message}</p>}
    {!album&&!loading&&<button type="button" className="text-button" onClick={()=>{setError("");setRevision(value=>value+1);}}>Reintentar</button>}
    {album&&<>
      <p className="field-help">{album.items.length} de {MAX_REPORT_PHOTOS} fotos. La miniatura se muestra en el aviso, los listados y el mapa.</p>
      {!!album.items.length&&<ul className="photo-thumbnails photo-album">{album.items.map((photo,index)=><li key={photo.id} className={photo.is_primary?"photo-is-primary":undefined}>
        <button type="button" className="photo-album-image" aria-label={`Ampliar la foto ${index+1}`} onClick={()=>setViewer(index)}><img src={`/api/account/photos/${photo.id}/image`} alt={`Foto ${index+1} del reporte`} loading="lazy"/><span className="photo-enlarge-mark" aria-hidden="true"><Icon name="expand"/></span></button>
        <button type="button" className="photo-cover-choice" aria-pressed={photo.is_primary} disabled={busy||loading||photo.is_primary} onClick={()=>void cover(photo.id)}>{photo.is_primary&&<Icon name="check"/>}{photo.is_primary?"Miniatura":"Usar miniatura"}</button>
        <button type="button" className="photo-delete-choice" disabled={busy||loading} onClick={()=>void remove(photo.id)}>Quitar foto</button>
      </li>)}</ul>}
      {remaining>0?<form className="photo-add-form" onSubmit={event=>void upload(event)}><fieldset disabled={busy||loading}>
        <PhotoUploader name="files" label="Agregar fotos" maxFiles={remaining} required files={photos} primaryIndex={primaryIndex??(!album.items.length?0:null)} onPrimaryChange={setPrimaryIndex} onFilesChange={changePhotos}/>
        <p className="field-help">Podés agregar {remaining} {remaining===1?"foto más":"fotos más"}.{album.items.length>0&&" Si no elegís otra miniatura, se conserva la actual."}</p>
        <button type="submit" className="button button-secondary" disabled={busy||loading||!photos.length||Boolean(photoSelectionError(photos,remaining))}>{busy?"Guardando…":`Guardar ${photos.length||"las"} ${photos.length===1?"foto":"fotos"}`}</button>
      </fieldset></form>:<p className="field-help">Alcanzaste el límite de cinco fotos. Podés elegir otra miniatura o quitar una foto para agregar otra.</p>}
      {viewer!==null&&<PhotoViewer title="Fotos del reporte" initialIndex={viewer} photos={album.items.map((photo,index)=>({id:photo.id,src:`/api/account/photos/${photo.id}/image`,alt:`Foto ${index+1} del reporte`}))} onClose={()=>setViewer(null)}/>}
    </>}
  </div>;
}
