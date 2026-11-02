import type { Metadata } from "next";
import { EditObservation } from "../../../edit-observation";

export const metadata: Metadata = { title: "Editar mi reporte — MascoMatch" };

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <main id="main-content" className="page report-page observation-edit-page"><h1>Editar mi reporte</h1><p className="page-intro">Actualizá los detalles, la ubicación y las fotos de tu avistamiento o de la mascota que encontraste.</p><EditObservation id={id} /></main>;
}
