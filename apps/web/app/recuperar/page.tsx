import {Suspense} from "react";
import {AccountAccessForm} from "../account-access-form";
export const metadata={title:"Recuperar cuenta — MascoMatch"};
export default function Page(){return <main id="main-content" className="page account-page"><h1>Recuperá tu cuenta</h1><p className="page-intro">Solicitá un enlace para elegir una nueva contraseña.</p><Suspense fallback={<p role="status">Cargando…</p>}><AccountAccessForm purpose="recover"/></Suspense></main>;}
