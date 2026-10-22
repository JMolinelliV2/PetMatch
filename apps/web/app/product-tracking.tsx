"use client";
import {useEffect,useRef} from "react";
import {usePathname} from "next/navigation";
import {pageCategory,track} from "@/lib/product-analytics";

// A shared navigation ID survives React StrictMode's effect replay, but changes on real navigation.
let lastPath="";let navigationId="";
export function ProductTracking(){
  const path=usePathname();
  useEffect(()=>{
    if(lastPath!==path){lastPath=path;navigationId=crypto.randomUUID();}
    const page=pageCategory(path);if(page===null)return;
    function send(){
      if(document.visibilityState!=="visible")return;
      if(lastPath!==path){lastPath=path;navigationId=crypto.randomUUID();}
      if(page)void track({name:"page_view",page,event_id:navigationId,...(page==="LOST_CASE"?{entity_id:path.split("/")[2]}:{})});
      if(page==="HOME")void track({name:"landing_view",page,event_id:navigationId});
    }
    send();document.addEventListener("visibilitychange",send);
    return()=>document.removeEventListener("visibilitychange",send);
  },[path]);
  return null;
}

export function useMatchVisibility(presentation?:string|null){
  const ref=useRef<HTMLElement|null>(null);
  useEffect(()=>{
    const element=ref.current;if(!element||!presentation)return;
    let ratio=0;let timer:ReturnType<typeof setTimeout>|undefined;let viewed=false;
    function cancel(){if(timer)clearTimeout(timer);timer=undefined;}
    function update(){
      cancel();if(document.visibilityState!=="visible")return;
      if(ratio>0)void track({name:"match_shown",page:"MATCHES",presentation:presentation!});
      if(ratio>=.5&&!viewed)timer=setTimeout(()=>{if(document.visibilityState==="visible"&&ratio>=.5){viewed=true;void track({name:"match_viewed",page:"MATCHES",presentation:presentation!});}},1000);
    }
    const observer=new IntersectionObserver(entries=>{ratio=entries[0]?.intersectionRatio||0;update();},{threshold:[0,.5,1]});
    observer.observe(element);document.addEventListener("visibilitychange",update);
    return()=>{cancel();observer.disconnect();document.removeEventListener("visibilitychange",update);};
  },[presentation]);
  return ref;
}
