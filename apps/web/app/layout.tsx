import type { Metadata } from "next";
import "leaflet/dist/leaflet.css";
import "./globals.css";
import { SiteHeader } from "./site-header";
import { SiteFooter } from "./site-footer";
import { ProductTracking } from "./product-tracking";

export const metadata: Metadata = {
  title: "MascoMatch — Mascotas perdidas",
  description: "Registrá una mascota perdida, un avistamiento o un animal encontrado.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="es-UY" data-scroll-behavior="smooth">
      <body><SiteHeader /><ProductTracking />{children}<SiteFooter /></body>
    </html>
  );
}

