import Link from "next/link";
import type { Metadata } from "next";
import { LostDogs } from "./lost-dogs";

export const metadata: Metadata = { title: "Mascotas reportadas — MascoMatch" };

export default function LostDogsPage() {
  return <main id="main-content" className="page lost-dogs-page">
    <div className="lost-dogs-heading">
      <div><h1>Mascotas reportadas</h1><p className="page-intro">Mirá los avisos y ayudá a que vuelvan a casa.</p></div>
      <Link href="/perdi" className="button button-secondary">Publicar un aviso</Link>
    </div>
    <LostDogs />
  </main>;
}
