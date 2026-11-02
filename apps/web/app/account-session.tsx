"use client";
import {useEffect,useState} from "react";
import Link from "next/link";
import {VerifyEmailNotice} from "./verify-email-notice";
import {useSessionRefresh} from "./use-session-refresh";
import {AccountLoading} from "./ui/account-loading";
import type {FormEvent,ReactNode} from "react";
export type SessionUser={id:string;name:string;avatar_version?:string|null;email?:string;phone?:string|null;pending_email?:string|null;notification_preferences?:{email?:boolean};role?:string;admin_access?:boolean;email_verified?:boolean;email_verification_required?:boolean};
export function AccountSession({children,showAccountHeader=true}:{children:(user:SessionUser,actions:{logout:()=>Promise<void>})=>ReactNode;showAccountHeader?:boolean}) {
  const sessionVersion=useSessionRefresh();
  const [user,setUser]=useState<SessionUser|null>(null);
  const [checking,setChecking]=useState(true);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  useEffect(()=>{const controller=new AbortController();void fetch("/api/session",{cache:"no-store",signal:controller.signal}).then(async response=>{if(!response.ok)throw new Error("No pudimos consultar tu sesión.");const data=await response.json();if(!controller.signal.aborted)setUser(data.user);}).catch(cause=>{if(!controller.signal.aborted)setError(cause.message);}).finally(()=>{if(!controller.signal.aborted)setChecking(false);});return()=>controller.abort();},[sessionVersion]);
  async function login(event:FormEvent<HTMLFormElement>) {
    event.preventDefault();setBusy(true);setError("");const form=event.currentTarget;const values=new FormData(form);
    try {const response=await fetch("/api/session",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({mode:"login",email:values.get("email"),password:values.get("password")})});const data=await response.json();if(!response.ok)throw new Error("El correo o la contraseña no son correctos.");form.reset();setUser(data.user);window.dispatchEvent(new Event("mascomatch:session"));}
    catch(cause){setError(cause instanceof Error?cause.message:"No pudimos iniciar sesión.");}finally{setBusy(false);}
  }
  async function logout(){const response=await fetch("/api/session",{method:"DELETE"});if(response.ok){setUser(null);window.dispatchEvent(new Event("mascomatch:session"));}else setError("No pudimos cerrar tu sesión.");}
  if(checking)return <AccountLoading description="Estamos abriendo tu espacio en MascoMatch."/>;
  return <>{user?<>{showAccountHeader&&<div className="notifications-account"><span>{user.name}</span><button className="text-button" type="button" onClick={()=>void logout()}>Cerrar sesión</button></div>}{user.email_verification_required&&!user.email_verified&&<VerifyEmailNotice email={user.email}/>}{children(user,{logout})}</>:<form onSubmit={login} className="notification-login"><h2>Ingresá con tu cuenta</h2><fieldset disabled={busy} className="section-fields"><label className="field-label">Correo electrónico<input className="form-input" name="email" type="email" required autoComplete="email"/></label><label className="field-label">Contraseña<input className="form-input" name="password" type="password" required autoComplete="current-password"/></label><button className="button button-primary" type="submit">{busy?"Ingresando…":"Ingresar"}</button></fieldset><p>¿Todavía no tenés cuenta? <Link className="text-button" href="/crear-cuenta">Crear cuenta</Link></p><p><Link className="text-button" href="/recuperar">Olvidé mi contraseña</Link></p></form>}{error&&<p className="notice notice-warning" role="alert">{error}</p>}</>;
}
