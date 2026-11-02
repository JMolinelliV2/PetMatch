"use client";

import { useEffect, useId, useRef, useState } from "react";
import type { DragEvent, RefObject } from "react";
import { Icon } from "./pictogram";
import {MAX_REPORT_PHOTOS, photoSelectionError} from "@/lib/report-photos";

type Props = {
  name: string;
  label?: string;
  maxFiles?: number;
  required?: boolean;
  inputRef?: RefObject<HTMLInputElement | null>;
  files?: File[];
  onFilesChange?: (files: File[]) => void;
  primaryIndex?: number | null;
  onPrimaryChange?: (index: number) => void;
};

export function PhotoUploader({ name, label = "Fotos", maxFiles = MAX_REPORT_PHOTOS, required = false, inputRef, files, onFilesChange, primaryIndex = 0, onPrimaryChange }: Props) {
  const id = useId();
  const ownRef = useRef<HTMLInputElement>(null);
  const ref = inputRef ?? ownRef;
  const [selected, setSelected] = useState<File[]>([]);
  const [previews, setPreviews] = useState<string[]>([]);
  const [dragging, setDragging] = useState(false);
  const [dropError, setDropError] = useState("");
  const currentFiles = files ?? selected;
  const changeRef = useRef(onFilesChange);
  changeRef.current = onFilesChange;

  useEffect(() => {
    const urls = currentFiles.map(file => ["image/jpeg", "image/png", "image/webp"].includes(file.type) && file.size <= 10 * 1024 * 1024 ? URL.createObjectURL(file) : "");
    setPreviews(urls);
    return () => urls.forEach(url => { if (url) URL.revokeObjectURL(url); });
  }, [currentFiles]);

  useEffect(() => {
    const form = ref.current?.form;
    const reset = () => { setSelected([]); setDropError(""); changeRef.current?.([]); };
    form?.addEventListener("reset", reset);
    return () => form?.removeEventListener("reset", reset);
  }, [ref]);

  function changed(next: File[]) {
    setDropError(""); setSelected(next); onFilesChange?.(next);
  }

  function syncInput(next: File[]) {
    if (!ref.current) return;
    try {
      const transfer = new DataTransfer();
      next.forEach(file => transfer.items.add(file));
      ref.current.files = transfer.files;
    } catch { ref.current.value = ""; }
  }

  function add(incoming: File[]) {
    const next = [...currentFiles];
    for (const file of incoming) if (!next.some(existing => existing.name === file.name && existing.size === file.size && existing.lastModified === file.lastModified && existing.type === file.type)) next.push(file);
    if (next.length > maxFiles) {
      syncInput(currentFiles); setDropError(`Podés adjuntar hasta ${maxFiles} fotos. Quitá una antes de agregar otra.`); return;
    }
    syncInput(next);
    if(next.length === currentFiles.length){setDropError("");return;}
    changed(next);
  }

  function drop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault(); setDragging(false);
    if (!ref.current || ref.current.matches(":disabled")) return;
    const next = Array.from(event.dataTransfer.files);
    if (!next.length) return;
    add(next);
  }

  function remove(index: number) {
    const next = currentFiles.filter((_, position) => position !== index);
    syncInput(next);
    changed(next);
  }

  const invalid = photoSelectionError(currentFiles,maxFiles);
  return <div className="photo-uploader">
    <div className="field-label">{label} {!required && <span className="optional">(opcional)</span>}</div>
    <label htmlFor={id} className={`photo-dropzone ${dragging ? "photo-dragging" : ""}`} onDragOver={event => { event.preventDefault(); if (!ref.current?.matches(":disabled")) setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={drop}>
      <Icon name="camera" />
      <strong>{currentFiles.length >= maxFiles ? `${maxFiles} ${maxFiles === 1 ? "foto seleccionada" : "fotos seleccionadas"}` : currentFiles.length ? "Agregar más fotos" : maxFiles === 1 ? "Subí una foto" : "Subí fotos de la mascota"}</strong>
      <span>{currentFiles.length >= maxFiles ? "Quitá una foto para agregar otra." : `Arrastrá ${maxFiles === 1 ? "la foto" : "las fotos"} acá o hacé clic para elegir`}</span>
      <span id={`${id}-help`} className="field-help">JPEG, PNG o WebP · Máximo 10 MB{maxFiles > 1 ? ` por foto · Hasta ${maxFiles} fotos` : " · 1 foto"}</span>
      <input id={id} ref={ref} type="file" name={name} multiple={maxFiles > 1} accept="image/jpeg,image/png,image/webp" required={required && !currentFiles.length} className="photo-file-input" aria-label={`${label}${required ? "" : " (opcional)"}`} aria-describedby={`${id}-help`} onChange={event => add(Array.from(event.target.files || []))} />
    </label>
    {currentFiles.length > 0 && <><p className="field-help">{currentFiles.length} de {maxFiles} fotos{onPrimaryChange ? " · Elegí cuál se mostrará como miniatura." : ""}</p><ul className="photo-thumbnails">{currentFiles.map((file, index) => <li key={`${file.name}-${index}`} className={onPrimaryChange && primaryIndex === index ? "photo-is-primary" : undefined}>
      {previews[index] ? <img src={previews[index]} alt={`Foto seleccionada ${index + 1}`} /> : <div className="photo-unavailable"><Icon name="camera" /></div>}
      <span className="photo-filename" title={file.name}>{file.name}</span>
      <button type="button" className="photo-remove" aria-label={`Quitar la foto ${index + 1}`} onClick={() => remove(index)}><Icon name="close" /></button>
      {onPrimaryChange && <button type="button" className="photo-cover-choice" aria-pressed={primaryIndex === index} aria-label={`Usar la foto ${index + 1} como miniatura`} onClick={() => {if(primaryIndex !== index)onPrimaryChange(index);}}>{primaryIndex === index && <Icon name="check" />}{primaryIndex === index ? "Miniatura" : "Usar miniatura"}</button>}
    </li>)}</ul></>}
    {(invalid || dropError) && <p role="alert" className="field-error">{dropError || invalid}</p>}
  </div>;
}
