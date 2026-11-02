"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import { Icon } from "./ui/pictogram";
import { ReportId } from "./ui/report-id";

export function ReportConfirmation({ kind, report, message, photoWarning, onCreateAnother, children }: {
  kind: "lost" | "sighting" | "found";
  report: { ownerType: "lost_case" | "observation"; ownerId: string; publicId?: string } | null;
  message: string;
  photoWarning: string;
  onCreateAnother: () => void;
  children?: ReactNode;
}) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  useEffect(() => { headingRef.current?.focus(); }, []);

  return <main id="main-content" className="page report-page report-confirmation">
    <section className="confirmation-card" aria-labelledby="confirmation-heading">
      <div className="confirmation-summary">
        <span className="confirmation-status"><Icon name="check" /> Reporte guardado</span>
        <h1 id="confirmation-heading" ref={headingRef} tabIndex={-1}>Tu reporte quedó guardado.</h1>
        <p className="confirmation-message">{message}</p>
        {report && <ReportId id={report.ownerId} publicId={report.publicId} label={report.ownerType === "lost_case" ? "ID del aviso" : "ID del reporte"} copyable />}
        <div className="confirmation-actions">
          <Link href="/mis-avisos" className="button button-primary"><Icon name="grid" /> Ir a Mis avisos <Icon name="arrow" /></Link>
          <button type="button" className="button button-secondary" onClick={onCreateAnother}>Crear otro reporte</button>
        </div>
      </div>
      <aside className="confirmation-next" aria-labelledby="confirmation-next-heading">
        <h2 id="confirmation-next-heading">¿Qué sigue?</h2>
        <ul>
          <li><span className="confirmation-next-icon"><Icon name="edit" /></span><div>
            <h3>Tu reporte, siempre a mano</h3>
            <p>Desde Mis avisos podés actualizar los datos, agregar fotos y elegir la miniatura.</p>
          </div></li>
          <li><span className="confirmation-next-icon"><Icon name={kind === "lost" ? "bell" : "search"} /></span><div>
            <h3>{kind === "lost" ? "Seguí las nuevas pistas" : "Revisá las posibles coincidencias"}</h3>
            <p>{kind === "lost" ? "Comparamos las fotos y la descripción en segundo plano. Los avistamientos vinculados y las posibles coincidencias llegan a tus notificaciones." : "Las fotos y la descripción se comparan en segundo plano con avisos de mascotas perdidas para ayudar a encontrar a su familia."}</p>
          </div></li>
        </ul>
        <Link href="/perdidos" className="confirmation-explore">Ver mascotas reportadas <Icon name="arrow" /></Link>
      </aside>
    </section>
    {photoWarning && <div role="alert" className="notice notice-warning confirmation-photo-warning"><Icon name="camera" /><p>{photoWarning}</p></div>}
    {children}
  </main>;
}
