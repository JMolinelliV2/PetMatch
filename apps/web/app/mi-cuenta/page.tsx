import type { Metadata } from "next";
import { AccountSettings } from "./account-settings";

export const metadata: Metadata = { title: "Mi cuenta — MascoMatch" };

export default function AccountPage() {
  return <main id="main-content" className="page account-page">
    <header className="account-heading"><h1>Mi cuenta</h1>
    <p className="page-intro">Actualizá tus datos, cambiá tu contraseña y configurá tus notificaciones.</p></header>
    <AccountSettings />
  </main>;
}
