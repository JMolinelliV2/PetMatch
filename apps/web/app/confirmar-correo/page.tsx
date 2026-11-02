import {Suspense} from "react";
import {ConfirmationForm} from "./confirmation-form";
export const metadata={title:"Confirmar correo — MascoMatch"};
export default function Page(){return <main id="main-content" className="page account-page"><h1>Confirmá tu correo</h1><p className="page-intro">Verificá tu cuenta para publicar avisos y recibir alertas de posibles avistamientos.</p><Suspense fallback={<p>Cargando…</p>}><ConfirmationForm/></Suspense></main>;}
