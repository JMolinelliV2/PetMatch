"use client";
import {useEffect,useRef,useState} from "react";
import {createPortal} from "react-dom";
import type {Map as LeafletMap,LayerGroup} from "leaflet";
import {addLostMapMarker,lostMapLocations} from "@/lib/lost-map-marker";
import type {LostMapSelection} from "@/lib/lost-map-marker";
import {addObservationMapMarker,observationMapLocations} from "@/lib/observation-map-marker";
import type {ObservationMapSelection} from "@/lib/observation-map-marker";
import {LostLocationPreview} from "../lost-map-preview";
import {ObservationLocationPreview} from "./observation-preview";
import {MapReportCard} from "./map-report-card";
import type {MapReportPoint as Point} from "./map-report-card";
const API=(process.env.NEXT_PUBLIC_API_URL||"http://localhost:8000/api/v1").replace(/\/$/,"");
const mapLayers=["lost","sighting"] as const;
type MapLayer=typeof mapLayers[number];
const layerClasses={lost:"map-layer-lost",sighting:"map-layer-sighting"};
const labels={lost:"Perdidos",sighting:"Avistamientos"};
function noticeFromMap(url:string){return `${url}${url.includes("?")?"&":"?"}origen=mapa`;}
type MapSelection={kind:"lost";data:LostMapSelection}|{kind:"observation";data:ObservationMapSelection};
export function CommunityMap(){
  const container=useRef<HTMLDivElement>(null);const map=useRef<LeafletMap|null>(null);const group=useRef<LayerGroup|null>(null);
  const [selection,setSelection]=useState<MapSelection|null>(null);
  const observationOpeners=useRef(new Map<string,()=>void>());
  const [ready,setReady]=useState(false);const [points,setPoints]=useState<Point[]>([]);const [species,setSpecies]=useState("");const [days,setDays]=useState("30");const [radius,setRadius]=useState("15");const [compatible,setCompatible]=useState(false);const [center,setCenter]=useState<{latitude:number;longitude:number}|null>(null);const [layers,setLayers]=useState<MapLayer[]>([...mapLayers]);const [error,setError]=useState("");const [busy,setBusy]=useState(false);const [refresh,setRefresh]=useState(0);
  useEffect(()=>{let disposed=false;void import("leaflet").then(L=>{if(disposed||!container.current)return;map.current=L.map(container.current,{scrollWheelZoom:false}).setView([-34.9,-56.16],11);L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",{maxZoom:19,attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'}).addTo(map.current).on("tileerror",()=>{if(!disposed)setError("No pudimos cargar algunas imágenes del mapa. Los reportes siguen disponibles en la lista.");});group.current=L.layerGroup().addTo(map.current);setReady(true);});return()=>{disposed=true;map.current?.remove();map.current=null;};},[]);
  useEffect(()=>{const controller=new AbortController();setBusy(true);const params=new URLSearchParams({species,days,radius_km:radius,compatible_only:String(compatible)});if(center){params.set("latitude",String(center.latitude));params.set("longitude",String(center.longitude));}void fetch(`${API}/public/map?${params}`,{cache:"no-store",signal:controller.signal}).then(async response=>{if(!response.ok)throw new Error("No pudimos cargar los puntos. Intentá de nuevo.");const data=await response.json();if(!controller.signal.aborted){setPoints(data.points);setError("");}}).catch(cause=>{if(!controller.signal.aborted)setError(cause.message);}).finally(()=>{if(!controller.signal.aborted)setBusy(false);});return()=>controller.abort();},[species,days,radius,compatible,center,refresh]);
  const visible=points.filter(point=>point.layer!=="found"&&layers.includes(point.layer));
  useEffect(()=>{
    if(!ready||!map.current||!group.current)return;
    let disposed=false;
    const cleanups:(()=>void)[]=[];
    void import("leaflet").then(L=>{
      if(disposed||!map.current||!group.current)return;
      group.current.clearLayers();setSelection(null);observationOpeners.current.clear();
      const filtered=points.filter(point=>point.layer!=="found"&&layers.includes(point.layer));
      const bounds:L.LatLngTuple[]=filtered.map(point=>[point.latitude,point.longitude]);
      for(const location of lostMapLocations(filtered.filter(point=>point.layer==="lost"))){
        cleanups.push(addLostMapMarker(L,map.current,group.current,location,
          next=>{if(!disposed)setSelection({kind:"lost",data:next});},
          content=>{if(!disposed)setSelection(current=>current?.data.content===content?null:current);},
        ));
      }
      const lostLocations=new Set(filtered.filter(point=>point.layer==="lost").map(point=>`${point.latitude},${point.longitude}`));
      for(const location of observationMapLocations(filtered.filter(point=>point.layer==="sighting"))){
        const handle=addObservationMapMarker(L,map.current,group.current,location,
          next=>{if(!disposed)setSelection({kind:"observation",data:next});},
          content=>{if(!disposed)setSelection(current=>current?.data.content===content?null:current);},
          lostLocations.has(`${location[0].latitude},${location[0].longitude}`)?64:0,
        );
        cleanups.push(handle.dispose);
        for(const point of location)observationOpeners.current.set(point.id,()=>handle.open(point.id));
      }
      if(bounds.length)map.current.fitBounds(bounds,{padding:[64,32],maxZoom:13});
      else if(center)map.current.setView([center.latitude,center.longitude],12);
    });
    return()=>{disposed=true;observationOpeners.current.clear();cleanups.forEach(cleanup=>cleanup());};
  },[points,layers,ready,center]);
  function showObservation(point:Point){const open=observationOpeners.current.get(point.id);if(!open||!map.current)return;map.current.setView([point.latitude,point.longitude],Math.max(13,map.current.getZoom()),{animate:false});container.current?.scrollIntoView({block:"center"});open();}
  function nearby(){if(!navigator.geolocation){setError("Tu navegador no ofrece ubicación. Podés recorrer el mapa manualmente.");return;}navigator.geolocation.getCurrentPosition(position=>setCenter({latitude:position.coords.latitude,longitude:position.coords.longitude}),()=>setError("No pudimos obtener tu ubicación. Revisá el permiso del navegador."),{timeout:15000,maximumAge:60000});}
  return <><div className="map-filters"><label className="field-label">Mascota<select className="form-input" value={species} onChange={event=>setSpecies(event.target.value)}><option value="">Todos</option>{[["dog","Perros"],["cat","Gatos"]].map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label><label className="field-label">Fecha<select className="form-input" value={days} onChange={event=>setDays(event.target.value)}><option value="7">Últimos 7 días</option><option value="30">Últimos 30 días</option><option value="90">Últimos 90 días</option><option value="0">Todas las fechas</option></select></label><label className="field-label">Radio cerca de mí<select className="form-input" value={radius} onChange={event=>setRadius(event.target.value)}><option value="5">5 km</option><option value="15">15 km</option><option value="30">30 km</option></select></label></div>
    <div className="location-actions"><button className="text-button" type="button" onClick={nearby}>Buscar cerca de mí</button>{center&&<button type="button" className="text-button" onClick={()=>setCenter(null)}>Ver todas las zonas</button>}<button className="text-button" type="button" onClick={()=>setRefresh(value=>value+1)}>Actualizar</button></div>
    <p className="field-help">El radio se aplica después de elegir “Buscar cerca de mí”. Los puntos aproximados no indican una dirección exacta.</p>
    <fieldset className="map-legend"><legend>Mostrar capas</legend>{mapLayers.map(layer=><label key={layer}><input type="checkbox" checked={layers.includes(layer)} onChange={event=>setLayers(current=>event.target.checked?[...current,layer]:current.filter(item=>item!==layer))}/><span aria-hidden="true" className={`map-legend-dot ${layerClasses[layer]}`} /> {labels[layer]}</label>)}</fieldset>
    <label className="sighting-recent"><input type="checkbox" checked={compatible} onChange={event=>setCompatible(event.target.checked)}/>Solo avistamientos con posibles coincidencias</label>
    {error&&<p className="notice notice-warning" role="alert">{error}</p>}<p role="status">{busy?"Cargando puntos…":`${visible.length} reportes en las capas seleccionadas`}</p>
    <p className="field-help" id="community-map-help">Los círculos rojos son avisos de mascotas perdidas y los azules, avistamientos. Pasá el mouse o tocá una foto para ver su tarjeta. Las horas se muestran en horario de Uruguay.</p>
    <div ref={container} className="community-map" role="region" aria-label="Mapa de ubicaciones aproximadas" aria-describedby="community-map-help"/>
    {selection&&createPortal(selection.kind==="lost"?<LostLocationPreview key={selection.data.points[0].id} selection={selection.data} origin="mapa" onRefresh={()=>setRefresh(value=>value+1)}/>:<ObservationLocationPreview key={selection.data.selectedId} selection={selection.data} onRefresh={()=>setRefresh(value=>value+1)}/>,selection.data.content)}
    {!busy&&!visible.length&&<p>No hay reportes para estos filtros.</p>}<details className="map-report-list"><summary>Ver reportes en una lista</summary><ul className="map-report-grid" aria-label="Reportes en las capas seleccionadas">{visible.slice(0,100).map(point=><li key={`${point.layer}-${point.id}`}><MapReportCard point={point} href={point.url?noticeFromMap(point.url):undefined} onShowOnMap={point.layer==="sighting"&&ready?()=>showObservation(point):undefined}/></li>)}</ul>{visible.length>100&&<p>La lista muestra los primeros 100. Ajustá los filtros para ver menos resultados.</p>}</details>
  </>;
}
