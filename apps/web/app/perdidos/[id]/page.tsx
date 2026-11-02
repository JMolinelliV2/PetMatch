import type { Metadata } from "next";
import { DogDetail } from "../dog-detail";

export const metadata: Metadata = { title: "Aviso de mascota perdida — MascoMatch" };

export default async function DogNoticePage({ params }: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <DogDetail id={id} />;
}
