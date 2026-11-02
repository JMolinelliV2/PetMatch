"use client";
import { useEffect, useId, useRef, useState } from "react";
import type { KeyboardEvent, PointerEvent } from "react";
import { avatarCropArea, defaultAvatarCrop, fitAvatarCrop } from "@/lib/avatar-crop";
import type { AvatarCrop } from "@/lib/avatar-crop";
import { Icon } from "./pictogram";

export function AvatarCropper({ src, crop, onChange, onReady, onError, disabled = false }: {
  src: string; crop: AvatarCrop; onChange: (crop: AvatarCrop) => void;
  onReady: (image: HTMLImageElement) => void; onError: (message: string) => void; disabled?: boolean;
}) {
  const id = useId();
  const [loaded, setLoaded] = useState<{ src: string; width: number; height: number } | null>(null);
  const [failedSource, setFailedSource] = useState<string | null>(null);
  const size = loaded?.src === src ? loaded : null;
  const [dragging, setDragging] = useState(false);
  const drag = useRef<{ pointer: number; x: number; y: number; crop: AvatarCrop } | null>(null);
  useEffect(() => { drag.current = null; setDragging(false); }, [src]);
  const area = size ? avatarCropArea(size.width, size.height, crop) : null;
  function fail(message: string) { setFailedSource(src); onError(message); }

  function start(event: PointerEvent<HTMLDivElement>) {
    if (disabled || !size || !event.isPrimary || event.button !== 0) return;
    event.preventDefault(); event.currentTarget.focus();
    drag.current = { pointer: event.pointerId, x: event.clientX, y: event.clientY, crop: fitAvatarCrop(size.width, size.height, crop) };
    event.currentTarget.setPointerCapture(event.pointerId); setDragging(true);
  }
  function move(event: PointerEvent<HTMLDivElement>) {
    const current = drag.current;
    if (disabled || !size || !current || current.pointer !== event.pointerId) return;
    const initial = avatarCropArea(size.width, size.height, current.crop);
    const scale = initial.size / event.currentTarget.clientWidth;
    onChange(fitAvatarCrop(size.width, size.height, {
      ...current.crop, x: current.crop.x - (event.clientX - current.x) * scale / size.width,
      y: current.crop.y - (event.clientY - current.y) * scale / size.height,
    }));
  }
  function stop(event: PointerEvent<HTMLDivElement>) {
    if (drag.current?.pointer !== event.pointerId) return;
    drag.current = null; setDragging(false);
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
  }
  function keyboard(event: KeyboardEvent<HTMLDivElement>) {
    if (disabled || !size || !area) return;
    const step = area.size * (event.shiftKey ? .1 : .025);
    const directions: Record<string, [number, number]> = { ArrowLeft: [step, 0], ArrowRight: [-step, 0], ArrowUp: [0, step], ArrowDown: [0, -step] };
    const direction = directions[event.key];
    if (!direction) return;
    event.preventDefault();
    onChange(fitAvatarCrop(size.width, size.height, { ...crop, x: area.centerX / size.width + direction[0] / size.width, y: area.centerY / size.height + direction[1] / size.height }));
  }

  return <div className="avatar-cropper">
    <div className={`avatar-crop-stage ${dragging ? "is-dragging" : ""}`} role="group" aria-label="Posición de la foto de perfil" aria-describedby={`${id}-help`} aria-disabled={disabled} tabIndex={disabled ? -1 : 0}
      onPointerDown={start} onPointerMove={move} onPointerUp={stop} onPointerCancel={stop} onLostPointerCapture={() => { drag.current = null; setDragging(false); }} onKeyDown={keyboard}>
      <img src={src} alt="Foto que estás ajustando" draggable={false} hidden={!area}
        style={size && area ? { width: `${size.width / area.size * 100}%`, height: `${size.height / area.size * 100}%`, left: `${50 - area.centerX / area.size * 100}%`, top: `${50 - area.centerY / area.size * 100}%` } : undefined}
        onLoad={event => {
          const image = event.currentTarget;
          if (!image.naturalWidth || !image.naturalHeight || image.naturalWidth * image.naturalHeight > 24_000_000) { fail("Elegí una imagen de hasta 24 megapíxeles."); return; }
          setLoaded({ src, width: image.naturalWidth, height: image.naturalHeight }); onReady(image);
        }} onError={() => fail("No pudimos abrir esa imagen. Elegí otra foto.")} />
      {!area && <span role={failedSource === src ? undefined : "status"}>{failedSource === src ? "Elegí otra foto" : "Preparando foto…"}</span>}
    </div>
    <p className="field-help" id={`${id}-help`}>Arrastrá la foto para acomodarla dentro del círculo.<span className="sr-only"> También podés usar las flechas del teclado; con Mayúsculas, el movimiento es mayor.</span></p>
    <label className="avatar-crop-zoom" htmlFor={`${id}-zoom`}><span><Icon name="search" />Zoom <output htmlFor={`${id}-zoom`}>{Math.round(crop.zoom * 100)}%</output></span>
      <input id={`${id}-zoom`} type="range" min={1} max={3} step={.01} value={crop.zoom} disabled={disabled || !size} onChange={event => size && onChange(fitAvatarCrop(size.width, size.height, { ...crop, zoom: Number(event.target.value) }))} />
    </label>
    <button className="text-button" type="button" disabled={disabled || !size} onClick={() => onChange({ ...defaultAvatarCrop })}><Icon name="refresh" />Restablecer ajuste</button>
  </div>;
}
