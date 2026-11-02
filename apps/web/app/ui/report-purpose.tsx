import Link from "next/link";
import { Icon } from "./pictogram";

export function ReportPurpose({ kind }: { kind: "sighting" | "found" }) {
  const found = kind === "found";
  return <aside className={`report-purpose ${found ? "report-purpose-found" : "report-purpose-sighting"}`} aria-label="Cuándo usar este formulario">
    <div className="report-purpose-main">
      <span className="report-purpose-icon"><Icon name={found ? "heart" : "eye"} /></span>
      <div className="report-purpose-copy">
        <h2>{found ? "La mascota está a salvo con vos" : "La viste, pero no está con vos"}</h2>
        <p>{found ? "Usá este formulario si la mascota está bajo tu cuidado o la resguardaste en un lugar seguro. Sus datos y fotos ayudarán a que su familia la reconozca." : "Si viste una mascota que parece perdida y no está bajo tu cuidado, contanos dónde y cuándo. Sumá una foto si tenés para ayudar a su familia a reconocerla."}</p>
      </div>
    </div>
    <div className="report-purpose-alternative">
      <p>{found ? "¿Solo la viste pasar?" : "¿La tenés a salvo con vos?"}</p>
      <Link className="report-purpose-switch" href={found ? "/avistamiento" : "/encontre"}><span>{found ? "Reportar un avistamiento" : "Reportar una mascota encontrada"}</span><Icon name="arrow" /></Link>
    </div>
  </aside>;
}
