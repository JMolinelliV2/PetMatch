export const linkedSightingDescription = "Avistamiento enviado desde un aviso. La identidad de la mascota está por confirmar.";

// Keep recognizing the former system message when editing older reports.
const legacyLinkedSightingDescription = "Avistamiento enviado desde un aviso. La identidad del animal está por confirmar.";

export function editableReportDescription(description: string, format = "LEGACY", linked = false): string {
  if (format === "USER_TEXT") return description;
  if (format === "SYSTEM" || (linked && [linkedSightingDescription, legacyLinkedSightingDescription].includes(description))) return "";

  // Older web forms appended these paragraphs in this order. Strip only that
  // trailing block, never matching words inside the person's own narrative.
  let text = description.replace(/\r\n/g, "\n");
  let note = "";
  const marker = "\n\nDetalles del reporte: ";
  const noteIndex = text.lastIndexOf(marker);
  if (noteIndex >= 0) { note = text.slice(noteIndex + marker.length); text = text.slice(0, noteIndex); }
  const suffixes = [
    /\n\nZona: [^\n]{1,350}$/,
    /\n\nTamaño: (?:Muy pequeño|Pequeño|Mediano|Grande)\.$/,
    /\n\nColor principal: (?:Marrón|Negro|Blanco|Gris|Crema|Naranja|Beige(?: \/ canela)?|Rojizo|Varios colores)\.$/,
  ];
  for (const suffix of suffixes) text = text.replace(suffix, "");
  return note ? `${text}\n\n${note}` : text;
}
