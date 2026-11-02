export type SupportedSpecies = "dog" | "cat";

export function isSupportedSpecies(value: unknown): value is SupportedSpecies {
  return value === "dog" || value === "cat";
}

export const speciesOptions = [["dog", "Perro"], ["cat", "Gato"]] as const;
