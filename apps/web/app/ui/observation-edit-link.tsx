"use client";

import { PublicationEditLink } from "./publication-edit-link";

export function ObservationEditLink({ id, found = false, onLayout }: { id: string; found?: boolean; onLayout?: () => void }) {
  return <PublicationEditLink id={id} kind="observation" found={found} onLayout={onLayout} compact />;
}
