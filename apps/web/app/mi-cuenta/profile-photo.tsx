"use client";
import { useEffect, useId, useRef, useState } from "react";
import type { ChangeEvent, FormEvent } from "react";
import type { SessionUser } from "../account-session";
import { Icon } from "../ui/pictogram";
import { UserAvatar } from "../ui/user-avatar";
import { AvatarCropper } from "../ui/avatar-cropper";
import { avatarCropBlob, defaultAvatarCrop } from "@/lib/avatar-crop";
import type { AvatarCrop } from "@/lib/avatar-crop";

const maxBytes = 10 * 1024 * 1024;

export function ProfilePhoto({ user, disabled = false, onBusyChange, onSaved }: {
  user: SessionUser; disabled?: boolean; onBusyChange?: (busy: boolean) => void; onSaved: (message: string) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const id = useId();
  const [version, setVersion] = useState(user.avatar_version || null);
  const [selected, setSelected] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [previewFailed, setPreviewFailed] = useState(false);
  const [crop, setCrop] = useState<AvatarCrop>({ ...defaultAvatarCrop });
  const [cropImage, setCropImage] = useState<HTMLImageElement | null>(null);
  const [loadingPhoto, setLoadingPhoto] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const unverified = user.email_verification_required !== false && user.email_verified === false;
  const controlsDisabled = disabled || busy || loadingPhoto;
  useEffect(() => { setVersion(user.avatar_version || null); }, [user.avatar_version]);
  useEffect(() => {
    if (!selected) { setPreview(null); return; }
    const url = URL.createObjectURL(selected);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [selected]);

  function selectPhoto(file: File, zoom = 1) {
    setCropImage(null); setCrop({ ...defaultAvatarCrop, zoom }); setPreviewFailed(false); setSelected(file);
  }

  function cancelAdjustment() {
    setSelected(null); setCropImage(null); setCrop({ ...defaultAvatarCrop }); setError(""); setPreviewFailed(false);
  }

  function choose(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setError(""); setMessage(""); setPreviewFailed(false);
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type) || file.size > maxBytes) {
      cancelAdjustment();
      setError(file.size > maxBytes ? "Elegí una foto de hasta 10 MB." : "Elegí una foto JPG, PNG o WebP.");
      return;
    }
    selectPhoto(file);
  }

  async function adjustExisting() {
    if (controlsDisabled || !version || unverified) return;
    setLoadingPhoto(true); onBusyChange?.(true); setError(""); setMessage("");
    try {
      const response = await fetch(`/api/account-avatar?v=${encodeURIComponent(version)}`, { cache: "no-store" });
      if (!response.ok) throw new Error(response.status === 401 ? "Tu sesión venció. Ingresá nuevamente." : "No pudimos cargar la foto para ajustarla. Intentá de nuevo o subí otra.");
      const blob = await response.blob();
      selectPhoto(new File([blob], "perfil.jpg", { type: "image/jpeg" }), 1.2);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "No pudimos cargar la foto para ajustarla."); }
    finally { setLoadingPhoto(false); onBusyChange?.(false); }
  }

  async function change(method: "POST" | "DELETE") {
    if (controlsDisabled || (method === "POST" && (!selected || !cropImage || previewFailed || unverified))) return;
    setBusy(true); onBusyChange?.(true); setError(""); setMessage("");
    try {
      const body = method === "POST" && selected ? new FormData() : undefined;
      if (body && cropImage) body.set("file", await avatarCropBlob(cropImage, crop), "perfil.jpg");
      const response = await fetch("/api/account-avatar", { method, body });
      const data: SessionUser & { detail?: string } = await response.json();
      if (!response.ok) throw new Error(response.status === 401 ? "Tu sesión venció. Ingresá nuevamente." : typeof data.detail === "string" ? data.detail : "No pudimos actualizar tu foto.");
      setVersion(data.avatar_version || null); setSelected(null); setCropImage(null);
      const confirmation = method === "POST" ? "Tu foto de perfil quedó actualizada." : "Tu foto de perfil fue eliminada.";
      setMessage(confirmation); onSaved(confirmation);
      window.dispatchEvent(new Event("mascomatch:session"));
      window.dispatchEvent(new Event("mascomatch:reviews"));
    } catch (cause) { setError(cause instanceof Error ? cause.message : "No pudimos actualizar tu foto."); }
    finally { setBusy(false); onBusyChange?.(false); }
  }

  function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); void change("POST"); }

  return <section className="notification-login account-form profile-photo-settings" aria-labelledby={`${id}-title`}>
    <h2 id={`${id}-title`}>Foto de perfil</h2>
    <p className="field-help">Se muestra en tu cuenta, en el menú y junto a tus reseñas públicas. Las reseñas anónimas no muestran tu foto.</p>
    <form className={`profile-photo-form ${selected ? "is-editing" : ""}`} onSubmit={submit} aria-busy={busy || loadingPhoto}>
      {selected && preview ? <AvatarCropper key={preview} src={preview} crop={crop} onChange={setCrop} onReady={setCropImage} disabled={controlsDisabled}
        onError={message => { setCropImage(null); setPreviewFailed(true); setError(message); }} /> : <div className="profile-photo-preview">
        <UserAvatar name={user.name} version={version} className="profile-photo-avatar" label={version ? "Tu foto de perfil" : "Tus iniciales"} />
        <span className="profile-photo-camera" aria-hidden="true"><Icon name="camera" /></span>
      </div>}
      <div className="profile-photo-controls">
        <p className="profile-photo-caption">{selected ? "Vista previa · Todavía sin guardar" : version ? "Tu foto en MascoMatch" : "Dale una cara a tu cuenta"}</p>
        <p className="field-help" id={`${id}-help`}>JPG, PNG o WebP · Hasta 10 MB.{!selected && <><br />Antes de guardar podés mover la foto y ajustar el zoom.</>}</p>
        <input ref={input} id={`${id}-file`} type="file" accept="image/jpeg,image/png,image/webp" hidden disabled={controlsDisabled || unverified} onChange={choose} />
        <div className="profile-photo-actions">
          <button type="button" className={`button ${selected ? "button-secondary" : "button-primary"}`} disabled={controlsDisabled || unverified} aria-controls={`${id}-file`} aria-describedby={`${id}-help`} onClick={() => input.current?.click()}><Icon name="camera" />{selected ? "Elegir otra foto" : version ? "Cambiar foto" : "Subir foto"}</button>
          {selected && <button type="submit" className="button button-primary" disabled={controlsDisabled || !cropImage || previewFailed || unverified}>{busy ? "Guardando…" : "Guardar foto"}</button>}
          {!selected && version && <button type="button" className="button button-secondary" disabled={controlsDisabled || unverified} onClick={() => void adjustExisting()}><Icon name="edit" />Ajustar foto</button>}
          {selected ? <button type="button" className="text-button" disabled={controlsDisabled} onClick={cancelAdjustment}>Cancelar</button>
            : version && <button type="button" className="text-button profile-photo-remove" disabled={controlsDisabled} onClick={() => void change("DELETE")}>Quitar foto</button>}
        </div>
        {unverified && <p className="field-help">Confirmá tu correo para subir una foto.</p>}
      </div>
    </form>
    {(busy || loadingPhoto) && <p className="field-help" role="status">{loadingPhoto ? "Preparando tu foto para ajustarla…" : "Actualizando tu foto…"}</p>}
    {message && <p className="notice" role="status">{message}</p>}
    {error && <p className="notice notice-warning" role="alert">{error}</p>}
  </section>;
}
