export const pages=["HOME","REGISTER","LOGIN","LOST_CASE","MATCHES","MAP","MY_REPORTS","SIGHTING","FOUND","SUPPORT","RECOVERY","ACCOUNT","OTHER_PUBLIC"] as const;
export type AnalyticsPage=typeof pages[number];
export function pageCategory(path:string):AnalyticsPage|null{
  const clean=path.split(/[?#]/)[0];
  if(clean.startsWith("/admin")||clean.startsWith("/api")||clean.startsWith("/_next"))return null;
  if(clean==="/")return "HOME";
  if(/^\/perdidos\/[0-9a-f-]{36}$/i.test(clean))return "LOST_CASE";
  return ({"/crear-cuenta":"REGISTER","/login":"LOGIN","/mapa":"MAP","/mis-avisos":"MY_REPORTS",
    "/avistamiento":"SIGHTING","/encontre":"FOUND","/apoyanos":"SUPPORT","/mi-cuenta":"ACCOUNT","/notificaciones":"MATCHES"} as Record<string,AnalyticsPage>)[clean]||"OTHER_PUBLIC";
}
export type BrowserFact={name:"page_view"|"landing_view"|"registration_started"|"match_shown"|"match_viewed";
  page:AnalyticsPage;event_id?:string;entity_id?:string;presentation?:string};
let chain:Promise<unknown>=Promise.resolve();
export function track(fact:BrowserFact){
  // Serialize first navigation and visibility events so concurrent requests share the same cookies.
  chain=chain.catch(()=>{}).then(async()=>{
    if(typeof document==="undefined"||document.visibilityState!=="visible")return;
    const body={...fact,event_id:fact.event_id||crypto.randomUUID()};
    for(let attempt=0;attempt<2;attempt++)try{
      const result=await fetch("/api/analytics",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body),
        keepalive:true,signal:AbortSignal.timeout(3000)});
      if(result.ok||result.status<500)return;
    }catch{}
  });
  return chain;
}

export function viewQualified(ratio:number,visible:boolean,elapsed:number){return visible&&ratio>=.5&&elapsed>=1000;}
