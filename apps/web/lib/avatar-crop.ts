export type AvatarCrop = { x: number; y: number; zoom: number };
export const defaultAvatarCrop: AvatarCrop = { x: .5, y: .5, zoom: 1 };
const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(max, value));
const finite = (value: number, fallback: number) => Number.isFinite(value) ? value : fallback;

export function avatarCropArea(width: number, height: number, crop: AvatarCrop) {
  if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) throw new Error("No pudimos leer el tamaño de la foto.");
  const zoom = clamp(finite(crop.zoom, 1), 1, 3);
  const size = Math.min(width, height) / zoom;
  const centerX = clamp(finite(crop.x, .5) * width, size / 2, width - size / 2);
  const centerY = clamp(finite(crop.y, .5) * height, size / 2, height - size / 2);
  return { left: centerX - size / 2, top: centerY - size / 2, size, centerX, centerY, zoom };
}

export function fitAvatarCrop(width: number, height: number, crop: AvatarCrop): AvatarCrop {
  const area = avatarCropArea(width, height, crop);
  return { x: area.centerX / width, y: area.centerY / height, zoom: area.zoom };
}

export async function avatarCropBlob(image: HTMLImageElement, crop: AvatarCrop): Promise<Blob> {
  const area = avatarCropArea(image.naturalWidth, image.naturalHeight, crop);
  const canvas = document.createElement("canvas");
  canvas.width = 512; canvas.height = 512;
  const context = canvas.getContext("2d");
  if (!context) throw new Error("Tu navegador no pudo preparar la foto. Intentá de nuevo.");
  context.fillStyle = "#ffffff"; context.fillRect(0, 0, 512, 512);
  context.imageSmoothingEnabled = true; context.imageSmoothingQuality = "high";
  context.drawImage(image, area.left, area.top, area.size, area.size, 0, 0, 512, 512);
  const blob = await new Promise<Blob | null>(resolve => canvas.toBlob(resolve, "image/jpeg", .9));
  if (!blob) throw new Error("No pudimos preparar el recorte. Probá con otra foto.");
  return blob;
}
