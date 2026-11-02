"use client";
import {useState} from "react";

export function usePhotoSelection(selectFirst = true) {
  const [photos, setPhotos] = useState<File[]>([]);
  const [primaryIndex, setPrimaryIndex] = useState<number | null>(selectFirst ? 0 : null);
  function changePhotos(next: File[]) {
    const selected = primaryIndex !== null ? photos[primaryIndex] : null;
    const nextIndex = selected ? next.indexOf(selected) : -1;
    setPrimaryIndex(nextIndex >= 0 ? nextIndex : selectFirst || selected ? 0 : null);
    setPhotos(next);
  }
  return {photos, primaryIndex, changePhotos, setPrimaryIndex};
}
