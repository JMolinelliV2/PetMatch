import type { Metadata } from "next";
import { DonationResult } from "./result";

export const metadata: Metadata = { title: "Tu aporte — MascoMatch", robots: { index: false, follow: false }, referrer: "no-referrer" };

export default async function Page({ searchParams }: { searchParams: Promise<{ aporte?: string | string[] }> }) {
  const { aporte } = await searchParams;
  const identity = typeof aporte === "string" && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(aporte) ? aporte : null;
  return <main id="main-content" className="page account-page"><DonationResult identity={identity} /></main>;
}
