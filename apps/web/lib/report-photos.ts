export const MAX_REPORT_PHOTOS = 5;
export const MAX_PHOTO_BYTES = 10 * 1024 * 1024;
export type PhotoOwnerType = "pet" | "lost_case" | "observation";
export type AlbumPhoto = { id: string; owner_type: PhotoOwnerType; owner_id: string; is_primary: boolean };
export type PhotoAlbum = { items: AlbumPhoto[]; primary_photo_id: string | null; max_photos: number };

export function photoSelectionError(files: File[], maxFiles = MAX_REPORT_PHOTOS): string | null {
  if (files.length > maxFiles) return `Podés adjuntar hasta ${maxFiles} fotos.`;
  if (files.some(file => file.size > MAX_PHOTO_BYTES)) return "Cada foto debe pesar hasta 10 MB.";
  if (files.some(file => !["image/jpeg", "image/png", "image/webp"].includes(file.type))) return "Las fotos deben ser JPEG, PNG o WebP.";
  return null;
}

export async function uploadReportPhotos(files: File[], ownerType: PhotoOwnerType, ownerId: string, primaryIndex: number | null): Promise<PhotoAlbum> {
  const error = photoSelectionError(files);
  if (error) throw new Error(error);
  const body = new FormData();
  body.set("owner_type", ownerType); body.set("owner_id", ownerId);
  for (const file of files) body.append("files", file);
  if (primaryIndex !== null) body.set("primary_index", String(primaryIndex));
  const response = await fetch("/api/account/photos/upload-batch", { method: "POST", body });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "No pudimos guardar las fotos. Intentá de nuevo.");
  return data;
}
