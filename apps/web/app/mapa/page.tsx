import type {Metadata} from "next";
import {CommunityMap} from "./community-map";
export const metadata:Metadata={title:"Mapa — MascoMatch"};
export default function Page(){return <main id="main-content" className="page"><h1>Mapa de la comunidad</h1><p className="page-intro">Mascotas perdidas y avistamientos. Los puntos públicos muestran zonas aproximadas.</p><CommunityMap/></main>;}
