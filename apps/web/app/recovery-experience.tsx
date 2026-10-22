"use client";
import {useEffect,useRef} from "react";
import {track} from "@/lib/product-analytics";
export function RecoveryExperience({caseId}:{caseId:string}){
 const ref=useRef<HTMLSpanElement>(null);const eventId=useRef<string|null>(null);
 useEffect(()=>{const element=ref.current;if(!element)return;let sent=false;
  const observer=new IntersectionObserver(entries=>{if(entries[0]?.isIntersecting&&document.visibilityState==="visible"&&!sent){sent=true;eventId.current ||=crypto.randomUUID();void track({name:"page_view",page:"RECOVERY",entity_id:caseId,event_id:eventId.current});}},{threshold:1});observer.observe(element);return()=>observer.disconnect();
 },[caseId]);
 return <span ref={ref} aria-hidden="true" style={{display:"block",height:1,width:1}}/>;
}
