"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { observationEditHref } from "@/lib/owned-observations";
import { useSessionRefresh } from "../use-session-refresh";
import { Icon } from "./pictogram";

export function PublicationEditLink({ id, kind, found = false, compact = false, onLayout }: {
  id: string; kind: "lost_case" | "observation"; found?: boolean; compact?: boolean; onLayout?: () => void;
}) {
  const version = useSessionRefresh();
  const [grant, setGrant] = useState<{ id: string; kind: string; version: number } | null>(null);
  const layout = useRef(onLayout);
  layout.current = onLayout;
  const allowed = grant?.id === id && grant.kind === kind && grant.version === version;

  useEffect(() => {
    const controller = new AbortController();
    setGrant(null);
    async function check() {
      try {
        const signal = AbortSignal.any([controller.signal, AbortSignal.timeout(15000)]);
        const session = await fetch("/api/session", { cache: "no-store", signal });
        if (!session.ok || !(await session.json()).user) return;
        const path = kind === "lost_case" ? `lost-cases/${encodeURIComponent(id)}` : `observations/${encodeURIComponent(id)}/edit`;
        const response = await fetch(`/api/account/${path}`, { cache: "no-store", signal });
        if (response.ok && !controller.signal.aborted) setGrant({ id, kind, version });
      } catch { /* Only a successful owner-only server response grants access. */ }
    }
    void check();
    return () => controller.abort();
  }, [id, kind, version]);
  useEffect(() => { if (allowed) layout.current?.(); }, [allowed]);

  if (!allowed) return null;
  const href = kind === "lost_case" ? `/mis-avisos?editar=${encodeURIComponent(id)}#editar-${encodeURIComponent(id)}` : observationEditHref(id);
  return <Link href={href} className={compact ? "text-button observation-edit-link" : "button button-secondary publication-edit-button"}>
    <Icon name="edit" />{kind === "lost_case" ? "Editar mi aviso" : found ? "Editar mi reporte" : "Editar mi avistamiento"}
  </Link>;
}
