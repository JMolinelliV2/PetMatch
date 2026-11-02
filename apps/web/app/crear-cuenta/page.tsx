import type { Metadata } from "next";
import { RegistrationForm } from "./registration-form";

export const metadata: Metadata = { title: "Crear cuenta — MascoMatch" };

export default function CreateAccountPage() {
  return <main id="main-content" className="page account-page">
    <h1>Creá tu cuenta</h1>
    <RegistrationForm />
  </main>;
}
