import type { SupportedSpecies } from "./species";

export type LostDogNotice = {
  id: string; public_id?: string; name: string; species: SupportedSpecies; sex: string; breed: string; size: string;
  primary_color: string; description: string; public_location: string | null;
  lost_at: string; photo_url: string | null; publisher_name?: string | null;
};
export type LostDogList = { items: LostDogNotice[]; total: number; limit: number; offset: number };
export const lostDogsEndpoint = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1"}/public/lost-animals`;

export function speciesLabel(species: string): string {
  return species === "dog" ? "Perro" : species === "cat" ? "Gato" : "Especie fuera del alcance actual";
}

export function sexLabel(sex: string): string {
  return sex === "male" ? "Macho" : sex === "female" ? "Hembra" : "No indicado";
}

export function dogTraits(dog: Pick<LostDogNotice, "breed" | "size" | "primary_color" | "sex">): string[] {
  const sizes: Record<string, string> = { tiny: "Muy pequeño", small: "Pequeño", medium: "Mediano", large: "Grande" };
  const colors: Record<string, string> = { brown: "Marrón", black: "Negro", white: "Blanco", gray: "Gris", cream: "Crema", orange: "Naranja", tan: "Beige / canela", red: "Rojizo", multicolor: "Varios colores" };
  return [dog.breed !== "unknown" ? dog.breed : "", dog.sex === "male" || dog.sex === "female" ? sexLabel(dog.sex) : "", sizes[dog.size], colors[dog.primary_color]].filter((trait): trait is string => Boolean(trait));
}

export function lostDate(value: string): string {
  const date = new Date(value);
  return Number.isFinite(date.getTime()) ? new Intl.DateTimeFormat("es-UY", { dateStyle: "medium" }).format(date) : "Fecha no indicada";
}
