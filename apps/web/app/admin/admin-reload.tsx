"use client";

import {createContext,useCallback,useContext,useMemo,useState} from "react";
import type {ReactNode} from "react";
import {Icon} from "../ui/pictogram";

type ReloadContext={version:number;pending:number;reload:()=>void;beginRequest:()=>()=>void};
const Context=createContext<ReloadContext|null>(null);

export function AdminReloadProvider({children}:{children:ReactNode}){
  const [version,setVersion]=useState(0);
  const [pending,setPending]=useState(0);
  const reload=useCallback(()=>setVersion(value=>value+1),[]);
  const beginRequest=useCallback(()=>{
    setPending(value=>value+1);
    let finished=false;
    return ()=>{if(!finished){finished=true;setPending(value=>Math.max(0,value-1));}};
  },[]);
  const value=useMemo(()=>({version,pending,reload,beginRequest}),[version,pending,reload,beginRequest]);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function useAdminReload(){
  const context=useContext(Context);
  if(!context)throw new Error("La recarga requiere el panel de administración.");
  return context;
}

export function AdminReloadButton(){
  const {reload,pending}=useAdminReload();
  return <button type="button" className="admin-reload-button" disabled={pending>0}
    aria-label="Recargar datos" aria-busy={pending>0} title={pending>0?"Actualizando datos…":"Recargar datos"} onClick={reload}>
    <Icon name="refresh"/><span className="sr-only" aria-live="polite">{pending>0?"Actualizando datos…":""}</span>
  </button>;
}
