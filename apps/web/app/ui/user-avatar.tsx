"use client";
import { useState } from "react";

export function UserAvatar({ name, version, src, className = "", label, onError }: {
  name: string; version?: string | null; src?: string | null; className?: string; label?: string; onError?: () => void;
}) {
  const source = src !== undefined ? src : version ? `/api/account-avatar?v=${encodeURIComponent(version)}` : null;
  const [failed, setFailed] = useState<string | null>(null);
  const initials = name.trim().split(/\s+/).slice(0, 2).map(part => part[0]).join("").toLocaleUpperCase("es") || "M";
  return <span className={`user-avatar ${className}`} role={label ? "img" : undefined} aria-label={label} aria-hidden={label ? undefined : true}>
    {source && failed !== source ? <img src={source} alt="" onError={() => { setFailed(source); onError?.(); }} /> : initials}
  </span>;
}
