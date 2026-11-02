import { Icon } from "./pictogram";

export function PublicationAuthor({ name }: { name?: string | null }) {
  if (name === undefined) return null;
  return <p className="publication-author"><Icon name="user" /><span>Publicado por <strong>{name || "Anónimo"}</strong></span></p>;
}
