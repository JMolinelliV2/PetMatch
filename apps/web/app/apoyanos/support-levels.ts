export const supportLevels = [
  { id: "amigo", name: "Amigo", amount: 100, icon: "heart" as const, description: "Un pequeño aporte para acompañar a la comunidad.", focus: "Ayudá a sostener el espacio donde se publican y comparten los avisos." },
  { id: "colaborador", name: "Colaborador", amount: 300, icon: "paw" as const, description: "Sumá tu apoyo a las búsquedas de cada día.", focus: "Contribuí al mantenimiento de la web, las fotos y los reportes." },
  { id: "aliado", name: "Aliado", amount: 600, icon: "spark" as const, description: "Impulsá las herramientas que ayudan a reunir las pistas.", focus: "Apoyá las alertas y las mejoras en la comparación de posibles coincidencias." },
  { id: "impulsor", name: "Impulsor", amount: 1200, icon: "shield" as const, description: "Acompañá el crecimiento de MascoMatch.", focus: "Contribuí a la infraestructura, el mantenimiento y el desarrollo del proyecto." },
] as const;

export function formatSupportAmount(amount: number) {
  return `$U ${new Intl.NumberFormat("es-UY", { maximumFractionDigits: 0 }).format(amount)}`;
}
